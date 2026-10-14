"""Reading ID number / KRA PIN / logbook numbers out of uploaded documents
(app/services/document_extraction.py) and appending them to the applicant
details (app/services/applicant_details.py).

Pure functions - no database, no HTTP. The PDF cases use app/services/simple_pdf.py
to build real PDFs with a text layer; the photo case is skipped automatically when
Pillow or the tesseract program is not installed.
"""

import io
from types import SimpleNamespace

import pytest

from app.services import document_extraction as de
from app.services.applicant_details import (
    EXTRACTED_KEY,
    PREFILLED_KEY,
    apply_extracted,
    effective_applicant_details,
    fill_customer_blanks,
    seed_applicant_details,
)
from app.services.simple_pdf import render_text_pdf

PADDING = ["Extra line of ordinary text so the page carries enough words to be judged."] * 4


def _pdf(lines):
    return render_text_pdf("Document", lines + PADDING) + b"\n%" + b"padding" * 800


# --- reading text ------------------------------------------------------------


def test_kra_pin_is_found_by_its_shape():
    assert de.extract_fields("kra_pin", "KENYA REVENUE AUTHORITY\nPIN CERTIFICATE\nPIN: A001234567B") == {
        "kra_pin": "A001234567B"
    }
    assert de.extract_fields("kra_pin", "Personal Identification Number P051234567Z") == {"kra_pin": "P051234567Z"}


def test_kra_pin_tolerates_ocr_spacing_and_lookalike_characters_only_next_to_the_word_pin():
    assert de.extract_fields("kra_pin", "PIN: a 00l234S67 b") == {"kra_pin": "A001234567B"}
    assert de.extract_fields("kra_pin", "reference a 00l234S67 b") == {}


def test_national_id_number_must_follow_an_id_label():
    assert de.extract_fields("national_id", "REPUBLIC OF KENYA\nIDENTITY CARD\nID NUMBER 12345678") == {
        "national_id_number": "12345678"
    }
    assert de.extract_fields("national_id", "ID NO: 23456789") == {"national_id_number": "23456789"}
    assert de.extract_fields("national_id", "NAMBA YA KITAMBULISHO 3456789") == {"national_id_number": "3456789"}
    assert de.extract_fields("national_id", "ID NUMBER 12 345 678") == {"national_id_number": "12345678"}


def test_stray_digits_are_never_taken_for_an_id_number():
    text = "SERIAL NUMBER 123456789\nDATE OF BIRTH 01.01.1990\nDISTRICT OF BIRTH NAIROBI"
    assert de.extract_fields("national_id", text) == {}
    assert de.extract_fields("national_id", "ID NUMBER 12345678901") == {}  # too long to be an ID


def test_logbook_numbers_need_a_label_and_a_digit():
    text = "Registration No KDA 123X\nChassis No: KZN130-0012345\nEngine No 1KZ0123456"
    assert de.extract_fields("logbook", text) == {"chassis_number": "KZN130-0012345", "engine_number": "1KZ0123456"}
    assert de.extract_fields("logbook", "CHASSIS NO ENGINE NO") == {}


def test_other_document_types_are_not_read():
    assert de.extract_fields("property_proof", "ID NUMBER 12345678") == {}
    assert de.extract_from_document("property_proof", _pdf(["ID NUMBER 12345678"])) == {}


# --- reading files -----------------------------------------------------------


def test_text_pdfs_are_read():
    id_pdf = _pdf(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678", "DATE OF BIRTH 01.01.1990"])
    assert de.extract_from_document("national_id", id_pdf) == {"national_id_number": "12345678"}
    pin_pdf = _pdf(["KENYA REVENUE AUTHORITY", "PIN CERTIFICATE", "PIN: A001234567B"])
    assert de.extract_from_document("kra_pin", pin_pdf) == {"kra_pin": "A001234567B"}


def test_unreadable_input_returns_nothing_instead_of_raising():
    assert de.extract_from_document("national_id", b"not a document at all" * 500) == {}
    assert de.extract_from_document("kra_pin", b"") == {}


@pytest.mark.skipif(not (de._PIL and de._OCR), reason="needs Pillow and the tesseract program")
def test_a_phone_photo_is_read_with_ocr():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 700), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for i, line in enumerate(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678", "DATE OF BIRTH 01.01.1990"]):
        draw.text((60, 40 + i * 95), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    assert de.extract_from_document("national_id", buf.getvalue()) == {"national_id_number": "12345678"}


# --- applicant details -------------------------------------------------------


def test_new_applications_copy_the_quote_form_and_blanks_are_dropped():
    answers = {"owner_name": "Jane Doe", "owner_phone": "0712345678", "make": "Toyota", "tonnage": "", "extensions": []}
    details = seed_applicant_details({}, answers)
    assert details == {
        "owner_name": "Jane Doe",
        "owner_phone": "0712345678",
        "make": "Toyota",
        PREFILLED_KEY: "quote_form",
    }
    # whatever the browser sends still wins
    assert seed_applicant_details({"owner_name": "Typed Name"}, answers)["owner_name"] == "Typed Name"


def test_old_applications_with_empty_details_fall_back_to_the_quote_form_without_changing_stored_data():
    stored = {}
    shown = effective_applicant_details(stored, {"owner_name": "Jane Doe"})
    assert shown["owner_name"] == "Jane Doe" and shown[PREFILLED_KEY] == "quote_form"
    assert stored == {}  # read-only view

    # stored values always win over the form's answers
    assert effective_applicant_details({"owner_name": "Edited"}, {"owner_name": "Jane Doe"})["owner_name"] == "Edited"


def test_extracted_fields_are_appended_and_remember_their_document():
    before = {"owner_name": "Jane Doe"}
    after = apply_extracted(before, {"kra_pin": "A001234567B"}, "kra_pin")
    assert after["kra_pin"] == "A001234567B" and after["owner_name"] == "Jane Doe"
    assert after[EXTRACTED_KEY] == {"kra_pin": "kra_pin"}
    assert "kra_pin" not in before  # a new dict, so the JSON column change is noticed
    assert apply_extracted(before, {}, "kra_pin") == before  # nothing found, nothing changed


def test_customer_blanks_are_filled_but_existing_values_are_never_overwritten():
    customer = SimpleNamespace(id_number=None, kra_pin="A999999999Z")
    changed = fill_customer_blanks(customer, {"national_id_number": "12345678", "kra_pin": "A001234567B"})
    assert changed == ["id_number"]
    assert customer.id_number == "12345678"
    assert customer.kra_pin == "A999999999Z"
