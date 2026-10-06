"""Upload screening (app/services/document_validation.py).

These call the validator directly - no database or HTTP - so they run in
milliseconds and don't depend on DOCUMENT_VALIDATION (which conftest.py
switches off for the older tests that upload placeholder bytes).

The PDF cases use app/services/simple_pdf.py to build real PDFs with a
text layer. Image cases are skipped automatically if Pillow isn't
installed.
"""

import io

import pytest

from app.services.document_validation import capabilities, validate_document
from app.services.simple_pdf import render_text_pdf

PADDING = ["Extra line of ordinary text so the page carries enough words to be judged."] * 4


def _pdf(lines: list[str]) -> bytes:
    # Trailing comment bytes push the file over the 5KB "too small" floor
    # without changing how the PDF parses.
    return render_text_pdf("Document", lines + PADDING) + b"\n%" + b"padding" * 800


def test_genuine_looking_documents_are_recognised():
    cases = {
        "national_id": ["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678", "DATE OF BIRTH 01.01.1990"],
        "logbook": ["THE TRAFFIC ACT", "MOTOR VEHICLE LOG BOOK", "Registration No KDA 123X", "Chassis No ABC123"],
        "kra_pin": ["KENYA REVENUE AUTHORITY", "PIN CERTIFICATE", "PIN: A001234567B"],
        "certificate_of_incorporation": ["CERTIFICATE OF INCORPORATION", "COMPANIES ACT", "ACME LIMITED"],
    }
    for doc_type, lines in cases.items():
        result = validate_document(doc_type, "doc.pdf", _pdf(lines))
        assert result.ok, (doc_type, result.message)
        assert result.verified, doc_type
        assert result.status == "uploaded"


def test_a_rate_card_uploaded_as_a_logbook_is_refused():
    rates = _pdf(["MOTOR RATES 2025", "Private comprehensive 4.5% minimum premium 30000", "Third party only 7500"])
    result = validate_document("logbook", "RATES 2025.pdf", rates)
    assert not result.ok
    assert "logbook" in result.message.lower()


def test_wrong_document_type_is_refused_even_when_it_is_a_real_document():
    id_pdf = _pdf(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678"])
    result = validate_document("kra_pin", "id.pdf", id_pdf)
    assert not result.ok
    assert "KRA PIN" in result.message


def test_renamed_non_documents_are_refused_by_real_content_not_extension():
    for payload in (b"MZ\x90\x00" + b"\x00" * 9000, b"PK\x03\x04" + b"\x00" * 9000, b"hello world " * 1000):
        result = validate_document("national_id", "scan.pdf", payload)
        assert not result.ok
        assert "PDF, JPEG or PNG" in result.message


def test_tiny_and_corrupt_files_are_refused():
    assert not validate_document("national_id", "a.pdf", b"%PDF-1.4 tiny").ok  # too small
    assert not validate_document("national_id", "a.pdf", b"%PDF-1.4 " + b"x" * 9000).ok  # not a real PDF
    assert not validate_document("national_id", "a.jpg", b"\xff\xd8\xff" + b"0" * 9000).ok  # corrupt JPEG


def test_pdf_without_a_text_layer_is_accepted_but_not_claimed_verified():
    # A PDF with almost no text stands in for a scanned page.
    scanned = render_text_pdf("", ["."]) + b"\n%" + b"padding" * 800
    result = validate_document("national_id", "scan.pdf", scanned)
    assert result.ok
    assert not result.verified
    assert "not machine-verified" in (result.notes or "")


def test_same_bytes_produce_the_same_hash():
    data = _pdf(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 1"])
    assert validate_document("national_id", "a.pdf", data).file_hash == validate_document("logbook", "b.pdf", data).file_hash


def test_simple_pdf_is_a_valid_pdf_with_extractable_text():
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(io.BytesIO(render_text_pdf("Insurance premium quote", ["TOTAL PAYABLE: KES 30,000.00"])))
    text = reader.pages[0].extract_text()
    assert "Insurance premium quote" in text and "30,000.00" in text


def test_blank_dark_and_tiny_images_are_refused():
    pytest.importorskip("PIL")
    from PIL import Image

    blank = io.BytesIO()
    Image.new("RGB", (1000, 700), (255, 255, 255)).save(blank, "PNG")
    assert not validate_document("national_id", "b.png", blank.getvalue() + b"\0" * 6000).ok

    dark = io.BytesIO()
    Image.new("RGB", (1000, 700), (5, 5, 5)).save(dark, "PNG")
    assert not validate_document("national_id", "d.png", dark.getvalue() + b"\0" * 6000).ok

    tiny = io.BytesIO()
    Image.effect_noise((200, 150), 64).convert("RGB").save(tiny, "PNG")
    result = validate_document("national_id", "t.png", tiny.getvalue() + b"\0" * 6000)
    assert not result.ok and "too small" in result.message


def test_a_sharp_photo_passes_and_a_blurry_one_is_flagged_for_review():
    pytest.importorskip("PIL")
    import glob

    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    fonts = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(fonts[0], 38) if fonts else ImageFont.load_default()

    def render(blur):
        img = Image.new("RGB", (1200, 800), (235, 235, 225))
        draw = ImageDraw.Draw(img)
        for i in range(5):
            draw.text((50, 40 + i * 70), "REPUBLIC OF KENYA IDENTITY CARD ID NUMBER 123456", fill=(10, 10, 10), font=font)
        if blur:
            img = img.filter(ImageFilter.GaussianBlur(blur))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue()

    sharp = validate_document("national_id", "s.jpg", render(0))
    assert sharp.ok and sharp.status == "uploaded"

    blurry = validate_document("national_id", "b.jpg", render(5))
    assert blurry.ok and blurry.status == "needs_review"
    assert "blurry" in blurry.message


def test_capabilities_reports_which_checks_are_active():
    assert set(capabilities()) == {"image_checks", "pdf_text_checks", "ocr"}


def test_a_photo_that_ocr_cannot_confirm_is_kept_for_review_not_rejected():
    """OCR on a phone photo is unreliable, so not finding the expected words
    must flag the upload for staff rather than refuse a genuine document."""
    pytest.importorskip("PIL")
    if not capabilities()["ocr"]:
        pytest.skip("Tesseract not installed")
    import glob

    from PIL import Image, ImageDraw, ImageFont

    fonts = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(fonts[0], 38) if fonts else ImageFont.load_default()
    img = Image.new("RGB", (1200, 800), (235, 235, 225))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(["MOTOR RATES 2025", "Private comprehensive 4.5%", "Third party 7500", "Commercial 5%", "Minimum premium 30000"]):
        draw.text((50, 40 + i * 70), line, fill=(10, 10, 10), font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    result = validate_document("national_id", "photo.jpg", buf.getvalue())
    assert result.ok and result.status == "needs_review"


def test_an_id_photo_in_the_logbook_slot_is_refused_when_ocr_can_read_it():
    pytest.importorskip("PIL")
    if not capabilities()["ocr"]:
        pytest.skip("Tesseract not installed")
    import glob

    from PIL import Image, ImageDraw, ImageFont

    fonts = glob.glob("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(fonts[0], 38) if fonts else ImageFont.load_default()
    img = Image.new("RGB", (1200, 800), (235, 235, 225))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678", "DATE OF BIRTH 01.01.1990"]):
        draw.text((50, 40 + i * 70), line, fill=(10, 10, 10), font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    result = validate_document("logbook", "id.jpg", buf.getvalue())
    assert not result.ok and "National ID" in result.message


def test_a_pdf_of_the_wrong_document_names_what_it_looks_like():
    id_pdf = _pdf(["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678"])
    result = validate_document("logbook", "id.pdf", id_pdf)
    assert not result.ok and "looks like a National ID" in result.message
