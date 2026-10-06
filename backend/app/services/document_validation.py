"""Pre-storage checks on an uploaded document.

Goal: stop junk (a renamed Word file, a blank photo, a rate card uploaded
as a logbook) at the door with a message the customer can act on, instead
of discovering it days later in underwriting.

This module is deliberately self-contained (standard library only, plus
OPTIONAL Pillow / pypdf / pytesseract - each is used if installed and
skipped cleanly if not) so it can be unit-tested without a database or the
web framework. The route-facing wrapper that reads settings, talks to the
DB and raises HTTP errors is app/services/document_intake.py.

What it can and cannot prove (be honest with yourself about this):
  * ALWAYS: real file type from the bytes (not the filename/header),
    not corrupted, not tiny, not password-protected, sane page count.
  * Images: readable resolution, not blank / single-colour, not nearly
    black, and a soft blur flag.
  * PDFs with a text layer (online NTSA logbook, iTax KRA PIN, digital
    copies): the text is read and must look like the claimed document.
  * Photos and scanned PDFs have no text layer. They are only
    content-checked if Tesseract OCR is installed on the server;
    otherwise they pass the quality checks and are stored as
    "not machine-verified" for staff to eyeball, exactly as before.
"""

import hashlib
import io
import logging
import re
import shutil
from dataclasses import dataclass

from app.services.document_requirements import SPECS, DocumentSpec

logger = logging.getLogger("somosure.document_validation")

try:  # optional
    from PIL import Image, ImageFilter, ImageStat

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

MIN_BYTES = 5 * 1024
MIN_IMAGE_SHORT_SIDE = 300
MAX_PDF_PAGES = 10
MIN_TEXT_CHARS_TO_JUDGE = 60  # fewer alphanumerics than this = no usable text layer
BLANK_STDDEV = 6.0
DARK_MEAN_REJECT = 30.0
DARK_MEAN_WARN = 55.0
BLUR_EDGE_VARIANCE_WARN = 60.0  # calibrated on synthetic sharp vs Gaussian-blurred text images
MAX_ASPECT_REJECT = 8.0

STATUS_OK = "uploaded"
STATUS_REVIEW = "needs_review"


@dataclass
class ValidationResult:
    ok: bool  # False = hard reject
    status: str  # stored on the document: uploaded | needs_review
    message: str | None  # customer-facing: the error if not ok, a gentle warning if ok-with-flags
    notes: str | None  # staff-facing, stored on the document
    file_hash: str
    kind: str  # pdf | jpeg | png | unknown
    verified: bool = False  # content positively recognised as the claimed type


def _sniff(content: bytes) -> str:
    head = content[:1024]
    if b"%PDF-" in head:
        return "pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return "unknown"


def _norm(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _alnum_count(text: str) -> int:
    return sum(1 for c in text if c.isalnum())


def _content_hits(spec: DocumentSpec, text: str) -> int:
    norm = _norm(text)
    hits = 0
    for group in spec.keyword_groups:
        if any(_norm(alt).strip() and f" {_norm(alt).strip()} " in norm for alt in group):
            hits += 1
    for pattern in spec.patterns:
        if re.search(pattern, text, re.I):
            hits += 1
    return hits


def _reject(kind: str, file_hash: str, message: str, notes: str | None = None) -> ValidationResult:
    return ValidationResult(False, STATUS_REVIEW, message, notes or message, file_hash, kind)


def _check_content(spec: DocumentSpec | None, text: str, source: str) -> tuple[str, str | None]:
    """Returns (outcome, note) where outcome is one of
    'verified' | 'mismatch' | 'unreadable' | 'skipped'."""
    if not spec or not spec.keyword_groups:
        return "skipped", None
    if _alnum_count(text) < MIN_TEXT_CHARS_TO_JUDGE:
        return "unreadable", None
    hits = _content_hits(spec, text)
    if hits >= spec.min_hits:
        return "verified", f"Recognised as {_name(spec)} from its {source}."
    return "mismatch", None


def _name(spec: DocumentSpec) -> str:
    first = spec.label.split()[0]
    return spec.label if first.isupper() or first == "National" else spec.label[0].lower() + spec.label[1:]


def _looks_like_other(spec: DocumentSpec | None, text: str) -> DocumentSpec | None:
    """If the text positively matches a DIFFERENT document type, return
    that type - the strongest evidence that the wrong file was chosen
    (e.g. a national ID uploaded in the logbook slot)."""
    best: tuple[int, DocumentSpec] | None = None
    for other in SPECS.values():
        if (spec and other.type == spec.type) or not other.keyword_groups:
            continue
        hits = _content_hits(other, text)
        if hits >= other.min_hits and (best is None or hits > best[0]):
            best = (hits, other)
    return best[1] if best else None


def _wrong_document_message(claimed: DocumentSpec, other: DocumentSpec) -> str:
    return (
        f"This looks like a {_name(other)}, not a {_name(claimed)}. Please upload the right document - "
        f"{claimed.description[0].lower() + claimed.description[1:]}"
    )


def _mismatch_message(spec: DocumentSpec) -> str:
    return (
        f"This doesn't look like a {_name(spec)}. Please upload the right document - "
        f"{spec.description[0].lower() + spec.description[1:]}"
    )


def _validate_pdf(spec: DocumentSpec | None, content: bytes, file_hash: str) -> ValidationResult:
    if not _PYPDF:
        if b"%%EOF" not in content[-2048:]:
            return _reject(
                "pdf", file_hash, "This PDF looks incomplete or damaged. Please re-save or re-download it and try again."
            )
        return ValidationResult(True, STATUS_OK, None, "PDF accepted - content not machine-verified.", file_hash, "pdf")

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
            if reader.is_encrypted:
                return _reject(
                    "pdf", file_hash, "This PDF is password-protected. Please remove the password (or print it to a new PDF) and upload it again."
                )
        page_count = len(reader.pages)
    except Exception:
        return _reject(
            "pdf", file_hash, "We couldn't open this PDF - it looks damaged. Please re-save or re-download it and try again."
        )

    if page_count == 0:
        return _reject("pdf", file_hash, "This PDF has no pages. Please upload the actual document.")
    if page_count > MAX_PDF_PAGES:
        return _reject(
            "pdf",
            file_hash,
            f"This PDF has {page_count} pages - far more than a single document. Please upload only the relevant pages.",
        )

    text_parts: list[str] = []
    try:
        for page in list(reader.pages)[:6]:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                continue
    except Exception:
        pass
    text = "\n".join(text_parts)

    outcome, note = _check_content(spec, text, "text")
    if outcome == "mismatch" and spec:
        other = _looks_like_other(spec, text)
        message = _wrong_document_message(spec, other) if other else _mismatch_message(spec)
        return _reject("pdf", file_hash, message, "PDF text did not match the claimed document type.")
    if outcome == "verified":
        return ValidationResult(True, STATUS_OK, None, note, file_hash, "pdf", verified=True)
    if outcome == "unreadable":
        return ValidationResult(
            True, STATUS_OK, None, "Scanned/image-only PDF - content not machine-verified.", file_hash, "pdf"
        )
    return ValidationResult(True, STATUS_OK, None, None, file_hash, "pdf")


def _validate_image(spec: DocumentSpec | None, content: bytes, kind: str, file_hash: str) -> ValidationResult:
    if not _PIL:
        return ValidationResult(True, STATUS_OK, None, "Image accepted - quality not machine-checked.", file_hash, kind)

    try:
        probe = Image.open(io.BytesIO(content))
        probe.verify()  # structural check; the image must be reopened afterwards
        img = Image.open(io.BytesIO(content))
        img.load()
    except Exception:
        return _reject(kind, file_hash, "We couldn't read this image - it looks damaged. Please take the photo again and re-upload.")

    width, height = img.size
    short_side, long_side = min(width, height), max(width, height)
    if short_side < MIN_IMAGE_SHORT_SIDE:
        return _reject(
            kind,
            file_hash,
            f"This image is too small to read ({width}x{height}). Please upload a larger, clearer photo or scan.",
        )
    if long_side / max(short_side, 1) > MAX_ASPECT_REJECT:
        return _reject(kind, file_hash, "This image has an unusual shape for a document. Please photograph the whole page or card.")

    grey = img.convert("L")
    if max(grey.size) > 800:
        grey.thumbnail((800, 800))
    stat = ImageStat.Stat(grey)
    mean, std = stat.mean[0], stat.stddev[0]

    if std < BLANK_STDDEV:
        return _reject(kind, file_hash, "This image looks blank or a single colour. Please upload a photo or scan of the actual document.")
    if mean < DARK_MEAN_REJECT:
        return _reject(kind, file_hash, "This image is far too dark to read. Please retake it in better light.")

    warnings: list[str] = []
    if mean < DARK_MEAN_WARN:
        warnings.append("quite dark")
    edges = grey.filter(ImageFilter.FIND_EDGES)
    ew, eh = edges.size
    # Crop the border: the edge filter leaves a constant ring there that
    # would otherwise put a floor under the variance of a blurry image.
    edge_var = ImageStat.Stat(edges.crop((3, 3, max(ew - 3, 4), max(eh - 3, 4)))).var[0]
    if edge_var < BLUR_EDGE_VARIANCE_WARN:
        warnings.append("a little blurry")

    verified = False
    note = None
    if _OCR:
        try:
            text = pytesseract.image_to_string(grey, timeout=15)
        except Exception:  # OCR trouble must never block a customer
            logger.warning("OCR failed on an uploaded image", exc_info=True)
            text = ""
        outcome, note = _check_content(spec, text, "photo (OCR)")
        if outcome == "mismatch" and spec:
            other = _looks_like_other(spec, text)
            if other:
                # Positive evidence it's a different document - refuse.
                return _reject(
                    kind, file_hash, _wrong_document_message(spec, other), f"OCR text looks like a {_name(other)}."
                )
            # OCR on a phone photo is far less reliable than reading a PDF's
            # text, so not finding the expected words is NOT proof of junk:
            # keep the upload, but flag it for staff and tell the customer.
            warnings.append(f"hard for us to read as a {_name(spec)}")
            note = "OCR could not confirm the document type - staff to check."
        verified = outcome == "verified"
    if not verified and note is None:
        note = "Image accepted - content not machine-verified."

    if warnings:
        joined = " and ".join(warnings)
        return ValidationResult(
            True,
            STATUS_REVIEW,
            f"Uploaded, but the image looks {joined}. If you can, retake it - a sharper copy gets approved faster.",
            f"Image flagged ({joined}); staff may ask for a clearer copy. {note}",
            file_hash,
            kind,
            verified,
        )
    return ValidationResult(True, STATUS_OK, None, note, file_hash, kind, verified)


def validate_document(document_type: str, filename: str, content: bytes) -> ValidationResult:
    """Runs every applicable check. Never raises - an unexpected error in
    a check is logged and the document is let through as unverified, since
    a bug in validation must not stop a customer from applying."""
    file_hash = hashlib.sha256(content).hexdigest()
    spec = SPECS.get(document_type)

    kind = _sniff(content)
    if kind == "unknown":
        return _reject(
            "unknown",
            file_hash,
            "This file isn't a real PDF, JPEG or PNG (it may be a renamed Word, ZIP or other file). "
            "Please upload a PDF, or a JPEG/PNG photo of the document.",
        )
    if len(content) < MIN_BYTES:
        return _reject(
            kind,
            file_hash,
            "This file is too small to be a real document scan. Please upload the actual document.",
        )

    try:
        if kind == "pdf":
            return _validate_pdf(spec, content, file_hash)
        return _validate_image(spec, content, kind, file_hash)
    except Exception:
        logger.exception("Document validation crashed for %s (%s); letting it through unverified", filename, document_type)
        return ValidationResult(True, STATUS_OK, None, "Validation could not run - not machine-verified.", file_hash, kind)


def capabilities() -> dict[str, bool]:
    """Which optional checks are active on this server (for diagnostics)."""
    return {"image_checks": _PIL, "pdf_text_checks": _PYPDF, "ocr": _OCR}
