"""Helpers for the "applicant details" an application carries.

Where the data comes from:
  1. The quote form the customer filled in (stored on the QuoteRequest as
     `input_data`) - copied onto the application when it is created, so the
     underwriter sees exactly what the customer submitted.
  2. Documents the customer uploads - ID number, KRA PIN and similar are read
     out of them (see document_extraction.py) and appended here.

Nothing in this module touches the database, so it is cheap to test.

Keys that start with an underscore are bookkeeping, not applicant data; the
admin screen hides them or uses them for small "read from document" tags:
  _prefilled_from  - "quote_form" when the details were copied from the quote request
  _extracted       - {field: "kra_pin"} which uploaded document each field was read from
"""

from typing import Any

PREFILLED_KEY = "_prefilled_from"
EXTRACTED_KEY = "_extracted"

# Extracted field -> the Customer column it should also fill (when still empty),
# so the Customer card, profile and later applications see it too.
CUSTOMER_COLUMNS: dict[str, str] = {
    "national_id_number": "id_number",
    "kra_pin": "kra_pin",
}


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def form_answers(answers: dict | None) -> dict:
    """The quote form's answers with empty ones dropped. Lists (e.g. the
    extensions or cover options asked for) are kept as lists."""
    return {k: v for k, v in (answers or {}).items() if not _is_blank(v) and not str(k).startswith("_")}


def seed_applicant_details(supplied: dict | None, answers: dict | None) -> dict:
    """What to store when an application is created: the quote form's answers,
    overlaid with anything the browser explicitly sent (which wins)."""
    details = form_answers(answers)
    if details:
        details[PREFILLED_KEY] = "quote_form"
    details.update(supplied or {})
    return details


def effective_applicant_details(stored: dict | None, answers: dict | None) -> dict:
    """The read-time view used by the admin screen. Applications created before
    details were copied across have an empty `stored`; for them the quote
    form's answers are used so the screen is never blank. Stored values always
    win, and nothing is written back."""
    stored = dict(stored or {})
    base = form_answers(answers)
    merged = {**base, **{k: v for k, v in stored.items() if not _is_blank(v)}}
    has_real_stored = any(not str(k).startswith("_") for k in stored)
    if base and not has_real_stored:
        merged[PREFILLED_KEY] = "quote_form"
    return merged


def apply_extracted(details: dict | None, fields: dict[str, str], document_type: str) -> dict:
    """Returns a NEW dict with the extracted fields appended (a new object, so
    SQLAlchemy sees the JSON column change) and remembers which document each
    value came from."""
    out = dict(details or {})
    if not fields:
        return out
    marks = dict(out.get(EXTRACTED_KEY) or {})
    for key, value in fields.items():
        out[key] = value
        marks[key] = document_type
    out[EXTRACTED_KEY] = marks
    return out


def fill_customer_blanks(customer: Any, fields: dict[str, str]) -> list[str]:
    """Fills the customer's ID number / KRA PIN from extracted values, but only
    where the customer record has nothing yet - a value that is already there
    (typed by the customer or by staff) is never overwritten. Returns the
    Customer columns that were set."""
    changed: list[str] = []
    for field_name, column in CUSTOMER_COLUMNS.items():
        value = fields.get(field_name)
        if value and not getattr(customer, column, None):
            setattr(customer, column, value)
            changed.append(column)
    return changed
