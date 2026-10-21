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
import os
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

try:  # optional, also needs the tesseract program
    import pytesseract

    def _find_tesseract() -> str | None:
        """The Tesseract program: the TESSERACT_CMD environment variable, else the PATH,
        else the folders the Windows installer uses - so it works on a Windows machine
        where Tesseract was installed but never added to the PATH."""
        configured = os.environ.get("TESSERACT_CMD")
        if configured and os.path.isfile(configured):
            return configured
        found = shutil.which("tesseract")
        if found:
            return found
        for candidate in (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ):
            if os.path.isfile(candidate):
                return candidate
        return None

    _TESSERACT = _find_tesseract()
    if _TESSERACT:
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT
    _OCR = _TESSERACT is not None
except Exception:  # pragma: no cover - depends on environment
    _OCR = False

_warned_no_ocr = False


def _warn_no_ocr() -> None:
    """Photos and scans can only be read with Tesseract. Say so once, loudly, rather than
    quietly reading nothing - the reason an ID number 'never appears' is otherwise invisible."""
    global _warned_no_ocr
    if not _warned_no_ocr:
        _warned_no_ocr = True
        logger.warning(
            "Tesseract OCR was not found, so photos and scanned PDFs cannot be read (PDFs that already contain "
            "text still can). Install Tesseract and add it to the PATH, or set TESSERACT_CMD to its full path."
        )

# Document types we know how to read, and the field names they produce.
# These field names are what ends up on the application's applicant details.
# Everything read off a valuation report. Kept under their own "valuation_" names
# (never "value", "chassis_number" ...) so they sit BESIDE what the customer typed
# on the quote form and what was read from the logbook instead of overwriting it -
# the underwriter can then compare the three.
VALUATION_FIELDS: tuple[str, ...] = (
    "valuation_reference",
    "valuation_market_value",
    "valuation_forced_value",
    "valuation_windscreen_value",
    "valuation_radio_value",
    "valuation_registration_number",
    "valuation_make_model",
    "valuation_body_type",
    "valuation_colour",
    "valuation_year",
    "valuation_chassis_number",
    "valuation_engine_number",
    "valuation_engine_cc",
    "valuation_odometer_km",
    "valuation_fuel_type",
    "valuation_date_of_registration",
    "valuation_extras",
    "valuation_general_condition",
    "valuation_coachwork",
    "valuation_accident_repairs",
    "valuation_chassis_frame_damage",
    "valuation_remarks",
    "valuation_client",
    "valuation_valuer",
    "valuation_inspected_at",
    "valuation_assessed_on",
)

READABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "national_id": ("national_id_number",),
    "kra_pin": ("kra_pin",),
    "logbook": ("chassis_number", "engine_number"),
    "valuation_report": VALUATION_FIELDS,
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


# On a photographed or scanned ID the "ID NUMBER" caption is tiny, so OCR often turns it into
# nonsense ("ween", "ssvenecr", "Tide: ONUWOER") while reading the number itself perfectly.
# So when no recognisable label is found, the number is picked out of the card by its shape.
_CARD_CONTEXT = re.compile(
    r"jamhuri|republic\s+of\s+kenya|date\s+of\s+birth|district\s+of\s+birth|place\s+of\s+issue|holder|serial\s*n|full\s*names|\bkya\b",
    re.I,
)
_LABEL_FRAGMENT = re.compile(r"numb|nurn|numer|\bid\b", re.I)
# 7 or 8 digits standing alone: not part of a longer number (the 9-digit serial number) and
# not part of a date such as 17.11.2003.
_STANDALONE_ID = re.compile(r"(?<![\d.\-/])(\d{7,8})(?![\d.\-/])")


def _mrz_lines(text: str) -> list[str]:
    """The machine-readable strip on the back of the card (lines of letters, digits and '<')."""
    lines = []
    for raw in text.splitlines():
        squashed = re.sub(r"[^A-Za-z0-9<]", "", raw).upper()
        if len(squashed) >= 24 and squashed.count("<") >= 3 and any(c.isdigit() for c in squashed):
            lines.append(squashed)
    return lines


def _labelled_national_id(text: str) -> str | None:
    for m in _ID_NUMBER.finditer(text):
        digits = re.sub(r"\s+", "", m.group(1))
        if 7 <= len(digits) <= 9 and digits.isdigit():
            return digits
    return None


def _pick_national_id(text: str) -> tuple[str | None, str]:
    """(number, how sure). 'label' = it sat next to an ID-number label; 'mrz' = it also
    appears in the machine-readable strip; 'sole' = the only candidate on something that
    looks like an ID card; '' = nothing safe to return."""
    labelled = _labelled_national_id(text)
    if labelled:
        return labelled, "label"

    mrz = _mrz_lines(text)
    mrz_text = " ".join(mrz)
    if not (mrz or _CARD_CONTEXT.search(text)):
        return None, ""  # doesn't look like an ID card: never guess from stray digits

    scores: dict[str, int] = {}
    for raw in text.splitlines():
        if re.sub(r"[^A-Za-z0-9<]", "", raw).upper() in mrz:
            continue  # the strip itself isn't a candidate, only a cross-check
        for m in _STANDALONE_ID.finditer(raw):
            value = m.group(1)
            score = 1
            if value in mrz_text:
                score += 3  # the same digits printed in the machine-readable strip
            if _LABEL_FRAGMENT.search(raw):
                score += 2  # on the line that carries the (garbled) ID number caption
            scores[value] = max(scores.get(value, 0), score)
    if not scores:
        return None, ""
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == best_score:
        return None, ""  # two equally plausible numbers: don't guess
    return best, ("mrz" if best_score >= 4 else "sole")


def extract_national_id_number(text: str) -> str | None:
    return _pick_national_id(text)[0]


# --- valuation report ------------------------------------------------------
#
# A valuer's report is a form: a label ("MARKET VALUE"), then the value, with two
# labelled columns per row. Once the PDF's text layer is read, a row arrives as
# one line - "REGISTRATION NO KBZ 504A MAKE & MODEL NISSAN TIIDA ..." - so each
# value is whatever sits between its label and the NEXT label. The label list
# below is what makes that work: every label that can follow another must be in
# it, otherwise the previous value would run on into it.
#
# Written against the layout of Topcover Automobile Valuers & Assessors (the report
# Bidii Credit's valuations come on). A report laid out differently simply yields
# fewer fields - never wrong ones: a value is only returned when its label is
# found, and the admin screen shows the rest as "not read yet".

_VAL_LABELS: tuple[tuple[str, str], ...] = (
    ("serial", r"SERIAL\s*NO\.?"),
    ("client", r"CLIENT"),
    ("telephone", r"TELEPHONE"),
    ("broker", r"INS\.?\s*BROKER\s*/\s*AGENT"),
    ("insurance", r"INSURANCE"),
    ("policy", r"POLICY"),
    ("expiry", r"EXPIRY\s*DATE"),
    ("registration", r"REGISTRATION\s*NO\.?"),
    ("make_model", r"MAKE\s*&\s*MODEL"),
    ("body_type", r"BODY\s*TYPE"),
    ("colour", r"COLOU?R"),
    ("engine_cc", r"ENGINE\s*CAPACITY"),
    ("odometer", r"ODOMETER\s*-?\s*READING"),
    ("year", r"YEAR\s*OF\s*MANF\.?"),
    ("date_of_reg", r"DATE\s*OF\s*REG\.?"),
    ("chassis", r"CHASSIS\s*NO\.?"),
    ("engine_no", r"ENGINE\s*NO\.?"),
    ("fuel", r"FUEL\s*TYPE"),
    ("capacity", r"CARRYING\s*CAPACITY"),
    ("market_value", r"MARKET\s*VALUE"),
    ("forced_value", r"FORCED\s*VALUE"),
    ("anti_theft", r"ANTI\s*THEFT"),
    ("extras", r"EXTRAS"),
    ("added_equipment", r"ADDED\s*EQUIPMENT"),
    ("windscreen", r"WINDSCREEN\s*VALUE"),
    ("radio", r"RADIO\s*VALUE"),
    ("origin", r"COUNTRY\s*OF\s*ORIGIN\s*:?"),
    ("examiner", r"EXAMINER\s*:?"),
    ("destination", r"DESTINATION\s*:?"),
    ("attention", r"ATTENTION\s*:?"),
    ("remarks", r"REMARKS\s*:?"),
    ("nb", r"\bNB\s*:"),
    ("remedy", r"REMEDY\s*:?"),
    ("assessed_on", r"ASSESSED\s*ON\s*:?"),
    ("inspected_at", r"INSPECTED\s*AT\s*:?"),
    ("prepared_by", r"PREPARED\s*BY\s*:?"),
    ("quality_check", r"QUALITY\s*CHECK\s*:?"),
    ("sign_manager", r"VALUATION\s*MANAGER\s*SIGN\s*:?"),
    ("sign_quality", r"QUALITY\s*OFFICER\s*:?"),
    ("sign_branch", r"BRANCH\s*MANAGER\s*SIGN\s*:?"),
    ("pin", r"PIN\s*NO\s*:?"),
    ("receipt", r"RECEIPT\s*NO\s*:?"),
    ("ref", r"REF\s*NO\s*:?"),
    # Page 2: the condition write-up.
    ("coachwork", r"COACHWORK(?!\s*CONDITION)"),
    ("electrical", r"ELECTRICAL(?!\s*CONDITION)"),
    ("mechanical", r"MECHANICAL(?!\s*CONDITION)"),
    ("general_condition", r"GENERAL\s*CONDITION"),
    ("tyres", r"TYRES"),
    ("steering", r"STEERING\s*SYSTEM"),
    ("suspension", r"SUSPENSION\s*SYSTEM"),
    ("braking", r"BRAKING\s*SYSTEM"),
    ("transmission", r"TRANSMISSION\s*SYSTEM"),
    ("engine_area", r"ENGINE\s*AREA"),
    ("coachwork_condition", r"COACHWORK\s*CONDITION"),
)
_VAL_LABEL_RES = [(key, re.compile(rx, re.I)) for key, rx in _VAL_LABELS]

# Labels whose value may run over several lines. Every other value is one line.
_VAL_MULTILINE = {"extras", "remarks", "coachwork"}
_VAL_MAX_LEN = {"extras": 600, "coachwork": 500, "remarks": 300}

_MONEY = re.compile(r"(?:KES|KSH?S?\.?)?\s*([0-9][0-9,]{2,}(?:\.[0-9]{1,2})?)", re.I)
_ACCIDENT_REPAIRS = re.compile(r"ACCIDENT\s+REPAIRS\s+ON\s+RADIATOR\s*/\s*INNER\s+VALANCES\s*\?\s*(YES|NO)\b", re.I)
_FRAME_DAMAGE = re.compile(r"CROSS\s*MEMBER\s*/\s*CHASSIS\s+FRAME\s+DAMAGE\s*\??\s*(YES|NO)\b", re.I)
# Printed in the page header of every page of these reports: "... MV 420000 FV 360000 ...".
_MV_FV_HEADER = re.compile(r"\bMV\s*([0-9]{4,9})\s*FV\s*([0-9]{4,9})\b")
_ISO_DATE = re.compile(r"\b(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})\b")


def _clean(value: str, limit: int = 200) -> str:
    return re.sub(r"\s+", " ", value).strip(" :-\t")[:limit]


def _money(value: str | None) -> str | None:
    if not value:
        return None
    m = _MONEY.search(value)
    if not m:
        return None
    number = m.group(1).replace(",", "")
    return number if number.replace(".", "", 1).isdigit() and float(number) > 0 else None


def _iso_date(value: str | None) -> str | None:
    m = _ISO_DATE.search(value or "")
    if not m:
        return None
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{year:04d}-{month:02d}-{day:02d}" if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31 else None


def _val_sections(text: str) -> dict[str, str]:
    """{label key: the text between that label and the next label}. First
    occurrence of each label wins (so the "NB:" in the footer never replaces the
    one in the form)."""
    hits: list[tuple[int, int, str]] = []
    for key, rx in _VAL_LABEL_RES:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), key))
    hits.sort()
    # Drop a label match that starts inside an earlier one ("ENGINE NO" vs "ENGINE").
    cleaned: list[tuple[int, int, str]] = []
    for start, end, key in hits:
        if cleaned and start < cleaned[-1][1]:
            continue
        cleaned.append((start, end, key))

    sections: dict[str, str] = {}
    for i, (_, end, key) in enumerate(cleaned):
        if key in sections:
            continue
        stop = cleaned[i + 1][0] if i + 1 < len(cleaned) else len(text)
        raw = text[end:stop]
        if key not in _VAL_MULTILINE:
            raw = raw.split("\n", 1)[0]
        sections[key] = _clean(raw, _VAL_MAX_LEN.get(key, 200))
    return sections


def extract_valuation_fields(text: str) -> dict[str, str]:
    """A valuer's report -> the fields in VALUATION_FIELDS that could be read.
    Only fields whose label was found are returned."""
    if not text:
        return {}
    sec = _val_sections(text)
    out: dict[str, str] = {}

    def put(field: str, value: str | None) -> None:
        if value:
            out[field] = value

    # Values. The page-header "MV 420000 FV 360000" is only a fallback: the
    # labelled figures are what the report actually states.
    market = _money(sec.get("market_value"))
    forced = _money(sec.get("forced_value"))
    header = _MV_FV_HEADER.search(text)
    if header:
        market = market or _money(header.group(1))
        forced = forced or _money(header.group(2))
    put("valuation_market_value", market)
    put("valuation_forced_value", forced)
    put("valuation_windscreen_value", _money(sec.get("windscreen")))
    put("valuation_radio_value", _money(sec.get("radio")))

    # The vehicle.
    serial = re.search(r"\b([A-Z]{1,3}-?\d{3,8})\b", sec.get("serial", "") or sec.get("ref", ""))
    put("valuation_reference", serial.group(1).upper() if serial else None)
    reg = re.sub(r"[^A-Z0-9 ]", "", sec.get("registration", "").upper()).strip()
    put("valuation_registration_number", reg if 3 <= len(reg) <= 14 else None)
    put("valuation_make_model", _clean(sec.get("make_model", ""), 80) or None)
    put("valuation_body_type", _clean(sec.get("body_type", ""), 40).title() or None)
    put("valuation_colour", _clean(sec.get("colour", ""), 30).title() or None)
    year = re.search(r"\b(19|20)\d{2}\b", sec.get("year", ""))
    put("valuation_year", year.group(0) if year else None)
    chassis = re.search(r"[A-Z0-9][A-Z0-9\-]{5,24}", sec.get("chassis", "").upper())
    put("valuation_chassis_number", chassis.group(0) if chassis and any(c.isdigit() for c in chassis.group(0)) else None)
    engine = re.search(r"[A-Z0-9][A-Z0-9\-]{3,24}", sec.get("engine_no", "").upper())
    put("valuation_engine_number", engine.group(0) if engine and any(c.isdigit() for c in engine.group(0)) else None)
    cc = re.search(r"(\d{3,5})\s*(?:CC)?\b", sec.get("engine_cc", "").upper())
    put("valuation_engine_cc", cc.group(1) if cc else None)
    km = re.search(r"([0-9][0-9,]*)\s*(?:KM|KMS)?\b", sec.get("odometer", "").upper())
    put("valuation_odometer_km", km.group(1).replace(",", "") if km else None)
    put("valuation_fuel_type", _clean(sec.get("fuel", ""), 20).title() or None)
    put("valuation_date_of_registration", _iso_date(sec.get("date_of_reg")))
    extras = _clean(sec.get("extras", ""), 600)
    put("valuation_extras", extras if extras and extras.upper() != "NONE" else None)

    # Condition.
    condition = _clean(sec.get("general_condition", ""), 30)
    put("valuation_general_condition", condition.title() if condition else None)
    put("valuation_coachwork", _clean(sec.get("coachwork", ""), 500) or None)
    for field, rx in (("valuation_accident_repairs", _ACCIDENT_REPAIRS), ("valuation_chassis_frame_damage", _FRAME_DAMAGE)):
        m = rx.search(text)
        if m:
            out[field] = m.group(1).capitalize()
    put("valuation_remarks", _clean(sec.get("remarks", ""), 300) or None)

    # Who and when.
    put("valuation_client", _clean(sec.get("client", ""), 80).title() or None)
    put("valuation_valuer", _clean(sec.get("prepared_by", ""), 80).title() or None)
    put("valuation_inspected_at", _clean(sec.get("inspected_at", ""), 60).title() or None)
    put("valuation_assessed_on", _iso_date(sec.get("assessed_on")))

    # A report with no value on it is not worth recording as "read".
    return out if "valuation_market_value" in out else {}


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
    elif document_type == "valuation_report":
        found.update(extract_valuation_fields(text))
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


def _ocr_fields(document_type: str, prepared: "Image.Image") -> dict[str, str]:
    """Reads one prepared image. Layout 3 suits a page of text; 11 ("sparse text") suits an ID
    card where the labels and numbers are scattered; 6 is a third opinion for ID numbers."""
    if document_type != "national_id":
        for psm in (3, 11):
            found = extract_fields(document_type, _ocr(prepared, psm))
            if found:
                return found
        return {}

    # An ID number backed by its label or by the machine-readable strip is taken at once. One
    # found only by its shape is taken if no other pass disagrees; two passes naming
    # different numbers means the read is unreliable, so nothing is returned.
    weak: list[str] = []
    for psm in (3, 11, 6):
        value, how = _pick_national_id(_ocr(prepared, psm))
        if value and how in ("label", "mrz"):
            return {"national_id_number": value}
        if value:
            weak.append(value)
    if weak and len(set(weak)) == 1:
        return {"national_id_number": weak[0]}
    return {}


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
                    found = _ocr_fields(document_type, _prepare_for_ocr(image))
                    if found:
                        return found
            if not found and not _OCR and _alnum_count(text) < MIN_TEXT_CHARS:
                _warn_no_ocr()  # an image-only PDF that nothing can read without Tesseract
            return found

        if not (_PIL and _OCR):
            _warn_no_ocr()
            return {}
        img = Image.open(io.BytesIO(content))
        img.load()
        return _ocr_fields(document_type, _prepare_for_ocr(img))
    except Exception as exc:
        # Usually just "this isn't an image/PDF we can open" - not worth a stack trace.
        logger.info("Could not read details from a %s document (%s)", document_type, type(exc).__name__)
        logger.debug("Extraction failure detail", exc_info=True)
        return {}
