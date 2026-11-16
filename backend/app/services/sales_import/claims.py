"""Reading the free-text claim narratives in the 'Claims YYYY' sheets.

The narrative is written like: "Claim was reported on 23/1/2026. Documents submitted on
23/1/2026. Vehicle assessed on 26/1/2026. Repair Authority issued on 6/2/2026. Release
letter issued on 27th /02/2026." We pull out every (date, what happened) pair so the claim
has a proper timeline. The original text is always kept next to it - this is a reading aid,
not a replacement.

Dates inside the text are day/month/year as typed (they are text, so Excel never swapped them).
"""

from __future__ import annotations

import re
from datetime import date

# (event name, pattern). A single sentence can hold several ("reported and documents submitted").
EVENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cash_in_lieu", re.compile(r"cash\s+in\s+lieu", re.I)),
    ("release_letter", re.compile(r"release\s+letter", re.I)),
    ("repair_authority", re.compile(r"(?i:repair\s+authority)|\bRA\b")),
    ("lpo_issued", re.compile(r"\bLPO\b", re.I)),
    ("discharge_voucher", re.compile(r"(?i:discharge)|\bDV\b")),
    ("assessment", re.compile(r"assess", re.I)),
    ("payment", re.compile(r"refund|reimburs|payment|\bpaid\b", re.I)),
    ("repairs_done", re.compile(r"repair(?!\s+authority)", re.I)),
    ("documents_submitted", re.compile(r"\bdoc\w*|ducument\w*", re.I)),
    ("reported", re.compile(r"report", re.I)),
]

_DATE_TOKEN = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s*/\s*(\d{1,2})\s*/?\s*(\d{4})")

EVENT_LABELS = {
    "reported": "Claim reported",
    "documents_submitted": "Documents submitted",
    "assessment": "Vehicle assessed",
    "repair_authority": "Repair authority issued",
    "release_letter": "Release letter issued",
    "discharge_voucher": "Discharge voucher signed",
    "lpo_issued": "LPO issued",
    "repairs_done": "Repairs done",
    "cash_in_lieu": "Cash in lieu",
    "payment": "Payment / refund",
    "note": "Note",
}


def extract_milestones(text: str | None) -> list[dict[str, str]]:
    """-> [{'event': 'reported', 'date': '2026-01-23'}, ...] in the order written."""
    if not text:
        return []
    milestones: list[dict[str, str]] = []
    previous_end = 0
    for match in _DATE_TOKEN.finditer(text):
        window = text[previous_end:match.start()][-90:]
        previous_end = match.end()
        try:
            when = date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            continue
        events = [name for name, pattern in EVENT_PATTERNS if pattern.search(window)] or ["note"]
        for event in events:
            milestones.append({"event": event, "date": when.isoformat()})
    return milestones


def normalize_outcome(action: str | None, narrative: str | None = None) -> str:
    """'Closed' / 'Closed, client unresponsive' / 'Action' / blank -> a small fixed set."""
    text = (action or "").strip().lower()
    if text.startswith("closed"):
        return "closed_unresponsive" if "unrespons" in text else "closed"
    if "action" in text:
        return "action_needed"
    return "open"
