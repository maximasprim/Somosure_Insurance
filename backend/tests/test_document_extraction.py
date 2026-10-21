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


# --- ID numbers on a photographed or scanned card ------------------------------------------------
# The numbers below are made up. They copy the SHAPE of what OCR really produces for a Kenyan ID:
# the number itself is read perfectly, but the tiny "ID NUMBER" caption beside it comes out as nonsense.


def test_an_id_number_is_found_even_when_ocr_turns_its_tiny_caption_into_nonsense():
    card = "JAMHURI YA KENYA REPUBLIC OF KENYA\nSERIAL NUMBER : 123456789 ava, ween 87654321\nFULL NAMES\nJANE DOE\nDATE OF BIRTH\n01. 02. 1990"
    assert de.extract_fields("national_id", card) == {"national_id_number": "87654321"}
    for garbled in ("one: 87654321", "ssvenecr: 87654321", "Tide: ONUWOER 87654321", "Re ener 87654321 28"):
        text = f"REPUBLIC OF KENYA\nSERIAL NUMBER 123456789\n{garbled}"
        assert de.extract_fields("national_id", text) == {"national_id_number": "87654321"}, garbled


def test_the_serial_number_dates_and_other_digits_are_never_taken_for_the_id_number():
    text = "REPUBLIC OF KENYA\nSERIAL NUMBER 123456789\nDATE OF BIRTH 17.11.2003\nDATE OF ISSUE 29.03.2022\nPLACE OF ISSUE NAIROBI"
    assert de.extract_fields("national_id", text) == {}


def test_the_machine_readable_strip_confirms_the_number_and_settles_a_tie():
    strip = "IDKYA1234567891<<3931<<<<<3931\n0311177M2203296<B087654321T<<3\nJANE<DOE<<<<<<<"
    text = f"REPUBLIC OF KENYA\n87654321\n76543210\n{strip}"
    assert de.extract_fields("national_id", text) == {"national_id_number": "87654321"}


def test_it_never_guesses_from_stray_digits():
    assert de.extract_fields("national_id", "REPUBLIC OF KENYA\n87654321\n76543210") == {}  # two equally likely numbers
    assert de.extract_fields("national_id", "INVOICE NO 55512345 TOTAL DUE 87654321") == {}  # not an ID card at all
    assert de.extract_fields("national_id", "KENYA REVENUE AUTHORITY\nPIN CERTIFICATE\n87654321") == {}  # no ID-card wording


def _blank_jpeg() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), "white").save(buf, "JPEG")
    return buf.getvalue()


def _read_with_ocr_saying(texts: dict[int, str]) -> dict:
    """Runs the real image path with OCR replaced by canned text for each layout mode."""
    original = (de._ocr, de._OCR)
    de._ocr, de._OCR = (lambda img, psm: texts.get(psm, "")), True
    try:
        return de.extract_from_document("national_id", _blank_jpeg())
    finally:
        de._ocr, de._OCR = original


@pytest.mark.skipif(not de._PIL, reason="needs Pillow")
def test_a_weak_read_is_accepted_unless_two_passes_name_different_numbers():
    card = "REPUBLIC OF KENYA\nSERIAL NUMBER 123456789\n"
    # found by shape in one pass, nothing contradicting it: accepted
    assert _read_with_ocr_saying({3: card + "ween 87654321"}) == {"national_id_number": "87654321"}
    # two passes agree: accepted
    assert _read_with_ocr_saying({3: card + "ween 87654321", 11: card + "one: 87654321"}) == {"national_id_number": "87654321"}
    # two passes disagree: the read can't be trusted, so nothing is returned
    assert _read_with_ocr_saying({3: card + "ween 87654321", 11: card + "one: 87654322"}) == {}
    # a number backed by its label is taken at once, whatever the other passes say
    assert _read_with_ocr_saying({3: card + "ID NUMBER 87654321", 11: card + "one: 87654322"}) == {"national_id_number": "87654321"}


@pytest.mark.skipif(not (de._PIL and de._OCR), reason="needs Pillow and the tesseract program")
def test_a_card_photo_with_an_unreadable_caption_is_read_by_its_number():
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 800), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=40)
    lines = ["JAMHURI YA KENYA   REPUBLIC OF KENYA", "SERIAL NUMBER : 123456789        ID NUMBER : 87654321", "FULL NAMES", "JANE WANJIKU DOE", "DATE OF BIRTH  01. 02. 1990"]
    for i, line in enumerate(lines):
        draw.text((50, 30 + i * 88), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    assert de.extract_from_document("national_id", buf.getvalue()) == {"national_id_number": "87654321"}


def test_tesseract_can_be_pointed_to_with_an_environment_variable():
    import os
    import tempfile

    if not hasattr(de, "_find_tesseract"):
        return  # OCR libraries not installed in this environment
    with tempfile.NamedTemporaryFile(suffix=".exe") as fake:
        previous = os.environ.get("TESSERACT_CMD")
        os.environ["TESSERACT_CMD"] = fake.name
        try:
            assert de._find_tesseract() == fake.name
        finally:
            if previous is None:
                del os.environ["TESSERACT_CMD"]
            else:
                os.environ["TESSERACT_CMD"] = previous

# --- valuation report ----------------------------------------------------------
# Text modelled on a real valuer's report (invented person and vehicle).

VALUATION_PAGE_1 = [
    "Friday 16th October 2026KAA 123B MV 420000 FV 360000BIDII CREDIT LIMITED",
    "SERIAL NO F-12345",
    "BANK VALUATION REPORT FOR STATION WAGON KAA 123B",
    "CLIENT JANE WANJIKU TELEPHONE 07***000",
    "INS. BROKER/AGENT INSURANCE 0",
    "POLICY TBA EXPIRY DATE 0000-00-00",
    "REGISTRATION NO KAA 123B MAKE & MODEL TOYOTA FIELDER 1.5L PETROL",
    "BODY TYPE STATION WAGON COLOR SILVER",
    "ENGINE CAPACITY 1490CC ODOMETER-READING 150000KM",
    "YEAR OF MANF 2010 DATE OF REG. 2015-03-02",
    "CHASSIS NO. NZE-1234567 ENGINE NO 1NZ9876543",
    "FUEL TYPE PETROL",
    "MARKET VALUE KES 420,000",
    "FOUR HUNDRED AND TWENTY THOUSAND Shillings",
    "FORCED VALUE KES 360,000",
    "ANTI THEFT KEY LOCK",
    "EXTRAS Abs, Air Bags, Alloy Rims,",
    "Power Windows, Tinted Windows",
    "ADDED EQUIPMENT NONE",
    "WINDSCREEN VALUE Estimated value of KES 20,000 RADIO VALUE Estimated value of KES 15,000",
    "COUNTRY OF ORIGIN: JAPAN EXAMINER: Sam",
    "REMARKS: Credit worthy",
    "NB: NONE",
    "REMEDY: NONE",
    "ASSESSED ON: 2026/10/16 11:39:06 INSPECTED AT: DONHOLM",
    "PREPARED BY : EXAMPLE VALUERS & ASSESSORS QUALITY CHECK: A. OTIENO",
    "Pin NO : P000000001X RECEIPT NO: REF NO: F-12345",
]
VALUATION_PAGE_2 = [
    "COACHWORK COMPLETE RESPRAY NOTED AFTER DENT REPAIRS ON THE BOOT",
    "LID WITH SCRATCHES ON THE FRONT BUMPER",
    "ELECTRICAL ALL LIGHTS FULLY FUNCTIONAL",
    "MECHANICAL ALL MECHANICAL SYSTEMS FULLY FUNCTIONAL",
    "GENERAL CONDITION FAIR",
    "TYRES 4 RUNNING TYRES OF GOOD TREAD DEPTH",
    "COACHWORK CONDITION",
    "ACCIDENT REPAIRS ON RADIATOR / INNER VALANCES? YES ARE INNER VALANCES /BONNET WINGS OKAY? YES",
    "IS THE PAINT FADED? NO ARE CROSSMEMBER/CHASSIS FRAME DAMAGE NO",
]


def test_valuation_report_values_and_condition_are_read():
    found = de.extract_fields("valuation_report", "\n".join(VALUATION_PAGE_1 + VALUATION_PAGE_2))
    assert found["valuation_market_value"] == "420000"
    assert found["valuation_forced_value"] == "360000"
    assert found["valuation_windscreen_value"] == "20000"
    assert found["valuation_radio_value"] == "15000"
    assert found["valuation_registration_number"] == "KAA 123B"
    assert found["valuation_make_model"] == "TOYOTA FIELDER 1.5L PETROL"
    assert found["valuation_year"] == "2010"
    assert found["valuation_chassis_number"] == "NZE-1234567"
    assert found["valuation_engine_number"] == "1NZ9876543"
    assert found["valuation_engine_cc"] == "1490"
    assert found["valuation_odometer_km"] == "150000"
    assert found["valuation_date_of_registration"] == "2015-03-02"
    assert found["valuation_assessed_on"] == "2026-10-16"
    assert found["valuation_reference"] == "F-12345"
    assert found["valuation_valuer"] == "Example Valuers & Assessors"
    assert found["valuation_general_condition"] == "Fair"
    assert found["valuation_accident_repairs"] == "Yes"
    assert found["valuation_chassis_frame_damage"] == "No"
    assert found["valuation_coachwork"].endswith("FRONT BUMPER")
    assert found["valuation_extras"] == "Abs, Air Bags, Alloy Rims, Power Windows, Tinted Windows"
    assert found["valuation_remarks"] == "Credit worthy"
    assert set(found) <= set(de.VALUATION_FIELDS)


def test_valuation_market_value_falls_back_to_the_page_header_figures():
    text = "KAA 123B MV 420000 FV 360000 BIDII\nREGISTRATION NO KAA 123B"
    found = de.extract_fields("valuation_report", text)
    assert found["valuation_market_value"] == "420000" and found["valuation_forced_value"] == "360000"


def test_text_with_no_value_is_not_treated_as_a_valuation():
    assert de.extract_fields("valuation_report", "REGISTRATION NO KAA 123B\nCHASSIS NO NZE-1234567") == {}
    assert de.extract_fields("valuation_report", "") == {}


def test_valuation_fields_sit_beside_the_logbook_numbers_not_over_them():
    details = apply_extracted({}, {"chassis_number": "LOGBOOK-111"}, "logbook")
    details = apply_extracted(details, {"valuation_chassis_number": "VAL-222", "valuation_market_value": "420000"}, "valuation_report")
    assert details["chassis_number"] == "LOGBOOK-111" and details["valuation_chassis_number"] == "VAL-222"
    assert details[EXTRACTED_KEY]["valuation_market_value"] == "valuation_report"


def test_a_valuation_pdf_is_read_end_to_end():
    pdf = render_text_pdf("Valuation", VALUATION_PAGE_1 + VALUATION_PAGE_2) + b"\n%" + b"padding" * 800
    found = de.extract_from_document("valuation_report", pdf)
    assert found.get("valuation_market_value") == "420000"
    assert found.get("valuation_registration_number") == "KAA 123B"
