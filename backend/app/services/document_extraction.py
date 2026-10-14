"""Reads identity details (KRA PIN, national ID number, ...) out of an
uploaded document so staff don't have to retype them.

Runs right after the upload check passes (see document_intake.py) and is
deliberately separate from document_validation.py: validation decides
"is this junk?", this module only answers "what numbers are printed on it?".
Keeping them apart means a change here can never affect what gets accepted
or refused.

Same ground rules as the validator:
  * standard library only, plus OPTIONAL pypdf / Pillow / pytesseract - each
    is used if installed and skipped cleanly if not;
  * never raises - a failure to read a document just means "nothing
    extracted", and the customer's upload is unaffected;
  * only returns a value when it is found next to its label or has an
    unmistakable shape (a KRA PIN). It never guesses from stray digits.

Extracted values are a convenience for staff, not proof: a phone photo read
by OCR can be wrong, so the admin screen labels them "read from document".
"""

import io
import logging
import re
import shutil

logger = logging.getLogger("somosure.document_extraction")

try:  # optional
    from PIL import Image, ImageOps

    _PIL = True
except Exception:  # pragma: no cover - depends on environment
    _PIL = False

try:  # optional
    from pypdf import PdfReader

    _PYPDF = True
except Exception:  # pragma: no cover - depends on environment
    _PYPDF = False

try:  # optional, also needs the tesseract binary
    import pytesseract

    _OCR = shutil.which("tesseract") is not None
except Exception:  # pragma: no cover - depends on environment
    _OCR = False

# Document types we know how to read, and the field names they produce.
# These field names are what ends up on the application's applicant details.
READABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "national_id": ("national_id_number",),
    "kra_pin": ("kra_pin",),
    "logbook": ("chassis_number", "engine_number"),
}

MAX_PDF_PAGES_READ = 6
MAX_IMAGE_SIDE = 2600  # larger photos are scaled down - OCR gains nothing from 12MP
MIN_IMAGE_SIDE = 1100  # smaller scans are scaled up - tesseract struggles under ~150dpi
OCR_TIMEOUT_SECONDS = 12
MIN_TEXT_CHARS = 40  # fewer letters/digits than this = no usable text layer

# --- patterns -------------------------------------------------------------

# KRA PIN: a letter A (individual) or P (company), nine digits, a letter.
_PIN_STRICT = re.compile(r"\b([AP]\d{9}[A-Z])\b", re.I)
# OCR often splits the PIN with spaces or swaps look-alike characters, so a
# looser read is only allowed when the word "PIN" is nearby.
_PIN_NEAR_LABEL = re.compile(r"\bPIN\b[^A-Za-z0-9]{0,12}([AP])\s?([0-9OIlSB]{9})\s?([A-Z])\b", re.I)
_OCR_DIGIT_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "B": "8"})

# National ID number: 7-9 digits that follow an "ID number" style label.
_ID_LABEL = (
    r"(?:\bnational\s*id\s*(?:number|no\.?|num\.?)"
    r"|\bid\s*(?:number|no\.?|num\.?)"
    r"|\bid\s*/\s*passport\s*(?:number|no\.?)"
    r"|\bidentity\s*(?:card\s*)?(?:number|no\.?)"
    r"|\bnamba\s*ya\s*kitambulisho)"
)
_ID_NUMBER = re.compile(_ID_LABEL + r"[^A-Za-z0-9]{0,10}(\d[\d ]{5,11}\d)\b", re.I)

# Logbook numbers: a label followed by a code that contains at least one digit.
_CHASSIS = re.compile(r"\bchass?is\s*(?:no\.?|number|num\.?|#)?[^A-Za-z0-9]{0,8}([A-Z0-9][A-Z0-9\-]{6,24})\b", re.I)
_ENGINE = re.compile(r"\bengine\s*(?:no\.?|number|num\.?|#)?[^A-Za-z0-9]{0,8}([A-Z0-9][A-Z0-9\-]{4,24})\b", re.I)


def _alnum_count(text: str) -> int:
    return sum(1 for c in text if c.isalnum())


def _has_digit(value: str) -> bool:
    return any(c.isdigit() for c in value)


def _first_with_digit(pattern: re.Pattern, text: str) -> str | None:
    for match in pattern.finditer(text):
        value = match.group(1)
        if _has_digit(value):
            return value.upper().strip("-")
    return None


def extract_kra_pin(text: str) -> str | None:
    m = _PIN_STRICT.search(text)
    if m:
        return m.group(1).upper()
    m = _PIN_NEAR_LABEL.search(text)
    if m:
        digits = m.group(2).translate(_OCR_DIGIT_FIX)
        if digits.isdigit():
            return f"{m.group(1)}{digits}{m.group(3)}".upper()
    return None


def extract_national_id_number(text: str) -> str | None:
    for m in _ID_NUMBER.finditer(text):
        digits = re.sub(r"\s+", "", m.group(1))
        if 7 <= len(digits) <= 9 and digits.isdigit():
            return digits
    return None


def extract_fields(document_type: str, text: str) -> dict[str, str]:
    """Pure text -> fields. Only the fields found are returned."""
    if not text or document_type not in READABLE_FIELDS:
        return {}
    found: dict[str, str] = {}
    if document_type == "kra_pin":
        pin = extract_kra_pin(text)
        if pin:
            found["kra_pin"] = pin
    elif document_type == "national_id":
        number = extract_national_id_number(text)
        if number:
            found["national_id_number"] = number
    elif document_type == "logbook":
        chassis = _first_with_digit(_CHASSIS, text)
        engine = _first_with_digit(_ENGINE, text)
        if chassis:
            found["chassis_number"] = chassis
        if engine:
            found["engine_number"] = engine
    return found


# --- reading text out of files -------------------------------------------


def _prepare_for_ocr(img: "Image.Image") -> "Image.Image":
    grey = ImageOps.exif_transpose(img).convert("L")
    long_side = max(grey.size)
    if long_side > MAX_IMAGE_SIDE:
        scale = MAX_IMAGE_SIDE / long_side
        grey = grey.resize((int(grey.width * scale), int(grey.height * scale)), Image.LANCZOS)
    elif long_side < MIN_IMAGE_SIDE:
        scale = MIN_IMAGE_SIDE / long_side
        grey = grey.resize((int(grey.width * scale), int(grey.height * scale)), Image.LANCZOS)
    return ImageOps.autocontrast(grey)


def _ocr(img: "Image.Image", psm: int) -> str:
    try:
        return pytesseract.image_to_string(img, config=f"--psm {psm}", timeout=OCR_TIMEOUT_SECONDS) or ""
    except Exception:  # OCR trouble must never block anything
        logger.warning("OCR failed during extraction", exc_info=True)
        return ""


def _pdf_text_and_images(content: bytes) -> tuple[str, list]:
    """Text layer of the first pages, plus (only if the PDF is image-only)
    the embedded page images so they can be OCR'd."""
    if not _PYPDF:
        return "", []
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return "", []
    pages = list(reader.pages)[:MAX_PDF_PAGES_READ]
    parts: list[str] = []
    for page in pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts)
    images: list = []
    if _alnum_count(text) < MIN_TEXT_CHARS and _PIL and _OCR:
        for page in pages[:3]:
            try:
                for image in page.images:
                    images.append(Image.open(io.BytesIO(image.data)))
            except Exception:
                continue
    return text, images


def extract_from_document(document_type: str, content: bytes) -> dict[str, str]:
    """The one function the upload path calls. Returns {} when the type isn't
    readable, nothing was found, or anything at all goes wrong."""
    if document_type not in READABLE_FIELDS:
        return {}
    try:
        if content.lstrip()[:5] == b"%PDF-" or b"%PDF-" in content[:1024]:
            text, images = _pdf_text_and_images(content)
            found = extract_fields(document_type, text)
            if not found and images:
                for image in images:
                    prepared = _prepare_for_ocr(image)
                    for psm in (3, 11):
                        found = extract_fields(document_type, _ocr(prepared, psm))
                        if found:
                            return found
            return found

        if not (_PIL and _OCR):
            return {}
        img = Image.open(io.BytesIO(content))
        img.load()
        prepared = _prepare_for_ocr(img)
        # Layout 3 suits a page of text; 11 ("sparse text") suits an ID card
        # where the labels and numbers are scattered - try both before giving up.
        for psm in (3, 11):
            found = extract_fields(document_type, _ocr(prepared, psm))
            if found:
                return found
        return {}
    except Exception as exc:
        # Usually just "this isn't an image/PDF we can open" - not worth a stack trace.
        logger.info("Could not read details from a %s document (%s)", document_type, type(exc).__name__)
        logger.debug("Extraction failure detail", exc_info=True)
        return {}
