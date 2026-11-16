"""Cleaning rules for the weekly sales workbook.

Everything here is a pure function: no database, no web framework, no I/O. That is
deliberate - the rules are the part most likely to need tuning as the workbook
evolves, and pure functions can be tested against the real file in seconds.

The workbook's recurring problems (all seen in the real 2023-2026 data):

* Dates are a mix of true Excel dates and text such as "13/01/2026". The text is
  day/month/year. The true dates are mostly day/month values that Excel read as
  month/day when they were typed (so "06/01/2026" became 1 June) - which only
  happens when the day is 12 or less. We therefore treat every true date with a day
  of 12 or less as "probably swapped" and let the other dates on the same row
  (start, expiry, paid, and the month block it sits in) confirm or overrule it.
* Names (underwriters, staff, branches) are typed freehand.
* Policy numbers are sometimes numbers, sometimes text, sometimes carry the cover
  type in brackets, and are sometimes missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from itertools import product
from typing import Any, Iterable

# --------------------------------------------------------------------------------------
# Flags - what we noticed about a row. Never silently "fixed": every correction or doubt
# is recorded on the row so staff can see it.
# --------------------------------------------------------------------------------------

ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass(frozen=True)
class Flag:
    code: str
    severity: str
    message: str
    fix: dict[str, str] | None = None  # a suggested correction a person can accept: {"field", "value", "label"}

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"code": self.code, "severity": self.severity, "message": self.message}
        if self.fix:
            out["fix"] = self.fix
        return out


# --------------------------------------------------------------------------------------
# Small text helpers
# --------------------------------------------------------------------------------------


def norm_text(value: Any) -> str:
    """Upper-case, letters/digits only, single spaces. Used for matching, never for display."""
    if value is None:
        return ""
    text = re.sub(r"[^A-Z0-9]+", " ", str(value).upper())
    return re.sub(r"\s+", " ", text).strip()


def clean_display(value: Any) -> str | None:
    """Trim and collapse whitespace; None for empty / placeholder values."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()
    if text.upper() in {"", "NONE", "N/A", "NA", "-", "--", "NIL"}:
        return None
    return text


MONTH_NAMES = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]
_MONTH_LOOKUP: dict[str, int] = {}
for _i, _name in enumerate(MONTH_NAMES, start=1):
    _MONTH_LOOKUP[_name] = _i
    _MONTH_LOOKUP[_name[:3]] = _i
_MONTH_LOOKUP["SEPT"] = 9


def month_from_label(value: Any) -> int | None:
    """'January', 'JAN', 'Sept', 'MARCH 2026' -> month number; anything else -> None."""
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"\s*([A-Za-z]{3,9})\.?(?:\s+\d{4})?\s*", value)
    if not m:
        return None
    return _MONTH_LOOKUP.get(m.group(1).upper())


# --------------------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------------------


def to_money(value: Any) -> Decimal | None:
    """Numbers and numeric text ('1,234.50', 'KES 5,000') -> Decimal(2dp); everything else -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = re.sub(r"(?i)\b(kes|ksh|ksh\.|kshs)\b", "", value).replace(",", "").strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return None


# --------------------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------------------


def parse_text_date(value: Any) -> date | None:
    """Text dates are day/month/year. Tolerates the typos seen in the real sheets:
    '13/1/2026', '13.01.2026', '13/01//2026', 'O9/01/2026' (letter O), 2-digit years, ISO text."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = re.sub(r"(?<=\d)[Oo]|[Oo](?=\d)", "0", text)  # letter O typed for zero
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text, flags=re.I)
    iso = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?", text)
    try:
        if iso:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        m = re.fullmatch(r"(\d{1,2})\s*[/.\-]+\s*(\d{1,2})\s*[/.\-]+\s*(\d{2,4})", text)
        if not m:
            return None
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        if not 1990 <= year <= 2100:  # '31/03/202' - a typo, not a date
            return None
        return date(year, month, day)
    except ValueError:
        return None


class ExactDate(date):
    """A true Excel date whose cell is formatted day-first or with the month spelled out
    ('13/01/2026', '13-Jan-2026'). Someone looking at that cell sees the right date, so the
    stored value is taken as it is. The workbook the app exports uses this format, which is
    what keeps cleaned dates from being second-guessed on the next upload."""


def day_first_format(number_format: str | None) -> bool:
    fmt = (number_format or "").lower()
    if "mmm" in fmt:
        return True
    d, m = fmt.find("d"), fmt.find("m")
    return d != -1 and m != -1 and d < m


@dataclass(frozen=True)
class DateReading:
    value: date
    swapped: bool = False  # True when this reading swaps day and month of a true Excel date


def date_readings(cell: Any) -> list[DateReading]:
    """Every plausible meaning of one date cell."""
    if isinstance(cell, ExactDate):
        return [DateReading(date(cell.year, cell.month, cell.day))]
    if isinstance(cell, datetime):
        cell = cell.date()
    if isinstance(cell, date):
        if cell.day <= 12 and cell.day != cell.month:
            return [DateReading(date(cell.year, cell.day, cell.month), swapped=True), DateReading(cell)]
        return [DateReading(cell)]
    parsed = parse_text_date(cell)
    return [DateReading(parsed)] if parsed else []


def _month_distance(a: date, b_year: int, b_month: int) -> int:
    return abs((a.year * 12 + a.month) - (b_year * 12 + b_month))


def _score(start: DateReading | None, expiry: DateReading | None, paid: DateReading | None,
           block: tuple[int, int] | None) -> tuple[float, int]:
    """Higher is more plausible. Second value counts independent confirmations."""
    score, confirmations = 0.0, 0
    if start and expiry:
        span = (expiry.value - start.value).days
        if 360 <= span <= 367:
            score += 3
            confirmations += 1
        elif 28 <= span < 360:
            score += 0.5
        elif span <= 0 or span > 800:
            score -= 3
        else:
            score -= 1
    if start and paid:
        gap = abs((start.value - paid.value).days)
        if gap <= 45:
            score += 2
            confirmations += 1
        elif gap <= 120:
            score += 0.5
        else:
            score -= 0.5
    if paid and block:
        dist = _month_distance(paid.value, block[0], block[1])
        if dist == 0:
            score += 1.5
            confirmations += 1
        elif dist == 1:
            score += 0.5
    score += 0.5 * sum(1 for r in (start, expiry, paid) if r and r.swapped)
    return score, confirmations


@dataclass
class ResolvedDates:
    start: date | None = None
    expiry: date | None = None
    paid: date | None = None
    flags: list[Flag] = field(default_factory=list)


def resolve_policy_dates(start_cell: Any, expiry_cell: Any, paid_cell: Any,
                         block: tuple[int, int] | None = None) -> ResolvedDates:
    """Pick the most plausible reading of the three date cells on one sales row.

    `block` is (year, month) of the month block the row sits in, used as one more
    cross-check. Cells that were corrected are reported in the flags."""
    options = [date_readings(start_cell) or [None], date_readings(expiry_cell) or [None], date_readings(paid_cell) or [None]]
    best: tuple[float, int, tuple] | None = None
    for combo in product(*options):
        score, confirmations = _score(*combo, block)
        if best is None or score > best[0]:
            best = (score, confirmations, combo)
    assert best is not None
    _, confirmations, (start, expiry, paid) = best

    out = ResolvedDates(
        start=start.value if start else None,
        expiry=expiry.value if expiry else None,
        paid=paid.value if paid else None,
    )
    swapped_notes = [
        f"{label} stored as {_fmt(cell)}, read as {reading.value:%d/%m/%Y}"
        for label, reading, cell in (("start date", start, start_cell), ("expiry date", expiry, expiry_cell), ("date paid", paid, paid_cell))
        if reading and reading.swapped
    ]
    if swapped_notes:
        out.flags.append(Flag("date_day_month_swapped", INFO, "Day and month swapped back: " + "; ".join(swapped_notes)))
    missing, unreadable = [], []
    for lbl, r, cell in (("start date", start, start_cell), ("expiry date", expiry, expiry_cell), ("date paid", paid, paid_cell)):
        if r is None:
            (unreadable if cell not in (None, "") else missing).append(f"{lbl} ('{cell}')" if cell not in (None, "") else lbl)
    if missing:
        out.flags.append(Flag("date_missing", WARNING, "Missing: " + ", ".join(missing)))
    if unreadable:
        out.flags.append(Flag("date_unreadable", WARNING, "Could not be read as a date: " + ", ".join(unreadable)))
    if start and expiry:
        span = (expiry.value - start.value).days
        fix = suggest_date_fix(start.value, expiry.value, paid.value if paid else None)
        suffix = f" Possible fix: {fix['label']} {date.fromisoformat(fix['value']):%d/%m/%Y}." if fix else ""
        if span <= 0:
            out.flags.append(Flag("expiry_before_start", ERROR, f"Expiry {expiry.value:%d/%m/%Y} is not after start {start.value:%d/%m/%Y}.{suffix}", fix))
        elif span > 367:
            out.flags.append(Flag("period_over_a_year", WARNING, f"Policy period is {span} days - check the start and expiry dates.{suffix}", fix))
        elif span < 360:
            out.flags.append(Flag("period_under_a_year", INFO, f"Policy period is {span} days (short-period cover?)"))
    if start and paid and (paid.value - start.value).days > 120:
        out.flags.append(Flag("paid_long_after_start", INFO, f"Paid {(paid.value - start.value).days} days after the start date"))
    if (start or expiry or paid) and confirmations == 0 and any(r and r.swapped for r in (start, expiry, paid)):
        out.flags.append(Flag("dates_unverified", WARNING, "Day/month order could not be confirmed from the other dates on this row"))
    return out


def suggest_date_fix(start: date, expiry: date, paid: date | None) -> dict[str, str] | None:
    """A year typed wrongly is the commonest slip ('14/03/2027' for '14/03/2026'). Try moving
    the start or expiry by a year and offer it when that gives a one-year policy that begins
    near the payment date. Only a suggestion - nothing is changed unless a person accepts it.
    -> {"field": "start_date" | "expiry_date", "value": "2026-03-14", "label": "start date"}"""
    from dateutil.relativedelta import relativedelta

    tries = [
        ("start_date", "start date", start - relativedelta(years=1), expiry),
        ("expiry_date", "expiry date", start, expiry + relativedelta(years=1)),
        ("start_date", "start date", start + relativedelta(years=1), expiry),
        ("expiry_date", "expiry date", start, expiry - relativedelta(years=1)),
    ]
    for field_name, label, new_start, new_expiry in tries:
        if 360 <= (new_expiry - new_start).days <= 367 and (paid is None or abs((new_start - paid).days) <= 45):
            changed = new_start if field_name == "start_date" else new_expiry
            return {"field": field_name, "value": changed.isoformat(), "label": label}
    return None


def _fmt(cell: Any) -> str:
    if isinstance(cell, (datetime, date)):
        return f"{cell:%d/%m/%Y}"
    return str(cell)


def resolve_sequential_date(cell: Any, previous: date | None) -> tuple[date | None, list[Flag]]:
    """For sheets with a single date per row (claims, IPF) and no block to cross-check.
    Rows are entered roughly in date order, so prefer the reading that does not run
    backwards; otherwise fall back to the swapped-day/month default."""
    readings = date_readings(cell)
    if not readings:
        return None, []
    chosen = readings[0]
    if previous is not None and len(readings) > 1:
        ordered = [r for r in readings if r.value >= previous]
        if ordered and readings[0] not in ordered:
            chosen = ordered[0]
    flags = []
    if chosen.swapped:
        flags.append(Flag("date_day_month_swapped", INFO, f"Date stored as {_fmt(cell)} and read as {chosen.value:%d/%m/%Y}"))
    return chosen.value, flags


# --------------------------------------------------------------------------------------
# Policy numbers, plates, phones, business type
# --------------------------------------------------------------------------------------


def clean_policy_number(value: Any) -> tuple[str | None, str | None]:
    """-> (policy number, cover type). '(COMP)' / '(TPO)' written after the number is the
    cover type, not part of the number."""
    if value is None:
        return None, None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = clean_display(value)
    if not text:
        return None, None
    cover = None
    m = re.search(r"\(\s*([A-Za-z][A-Za-z ]{1,14})\s*\)\s*$", text)
    if m:
        cover = m.group(1).strip().upper()
        text = text[: m.start()].strip()
    text = re.sub(r"\s+", "", text).upper()
    return (text or None), cover


_PLATE = re.compile(r"^(K[A-Z]{2}\d{3}[A-Z]?|K[A-Z]{3}\d{3}[A-Z]?|Z[A-Z]\d{3,4}|GK[A-Z]?\d{3,4}[A-Z]?)$")


def clean_plate(value: Any) -> tuple[str | None, bool]:
    """-> (plate, looks_like_a_kenyan_plate). Spaces, dashes and case are removed so
    'KDR 904V' and 'kdr904v' match."""
    text = clean_display(value)
    if not text:
        return None, False
    plate = re.sub(r"[^A-Z0-9]", "", text.upper())
    m = re.fullmatch(r"(K[A-Z]{2})([0-9O]{3})([A-Z]?)", plate)
    if m and "O" in m.group(2):  # letter O typed for zero: KDN45OT
        plate = m.group(1) + m.group(2).replace("O", "0") + m.group(3)
    return (plate or None), bool(_PLATE.match(plate))


# The "REG NO" column also carries the product for non-motor policies.
PRODUCT_TOKENS: dict[str, str] = {
    "PI": "professional_indemnity", "PROFESSIONAL INDEMNITY": "professional_indemnity",
    "MEDICAL": "medical", "WIBA": "wiba", "WORK INJURY": "wiba",
    "BID BOND": "bid_bond", "BIDBOND": "bid_bond",
    "CREDIT LIFE": "credit_life", "CREDITLIFE": "credit_life",
    "PA": "personal_accident", "PERSONAL ACCIDENT": "personal_accident",
    "LIFE": "life", "TRAVEL": "travel", "ADDITIONS": "additions", "ADDITION": "additions",
    "FIRE": "property", "BURGLARY": "property", "PROPERTY": "property", "HOME": "property",
}


def classify_asset(value: Any) -> tuple[str, str | None, str | None]:
    """-> (product_line, plate, asset_ref).

    'KDR 904V' -> ('motor', 'KDR904V', None); 'PI' -> ('professional_indemnity', None, 'PI');
    anything unrecognised -> ('other', None, <as typed>)."""
    text = clean_display(value)
    if not text:
        return "unknown", None, None
    token = norm_text(text)
    if token in PRODUCT_TOKENS:
        return PRODUCT_TOKENS[token], None, text
    plate, ok = clean_plate(text)
    if ok:
        return "motor", plate, None
    if plate and re.fullmatch(r"K[A-Z]{2,3}\d{3,4}[A-Z]?", plate):  # plate-shaped but not valid: still a vehicle
        return "motor", plate, text
    return "other", None, text


def looks_like_plate(value: Any) -> bool:
    return clean_plate(value)[1]


def clean_phone(value: Any) -> str | None:
    """Kenyan numbers to +254XXXXXXXXX. Numbers stored as Excel numbers have lost their
    leading zero (721559694.0), which is restored here."""
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("254") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10 and digits[0] == "0":
        return "+254" + digits[1:]
    if len(digits) == 9 and digits[0] in "17":
        return "+254" + digits
    return None


def clean_business_type(value: Any) -> str | None:
    text = norm_text(value)
    if not text:
        return None
    if text.startswith("NEW"):
        return "new_business"
    if text.startswith("RENEW"):
        return "renewal"
    return None


# --------------------------------------------------------------------------------------
# Underwriters
# --------------------------------------------------------------------------------------

# Spellings seen in the real sheets -> the one name we use. Extended at run time by the
# aliases an administrator saves in the app.
DEFAULT_UNDERWRITER_ALIASES: dict[str, str] = {
    "MORNACH": "MONARCH",
    "MONARCH INSURANCE": "MONARCH",
    "DIRECTLINE": "DIRECT LINE",
    "DIRECT LINE ASSURANCE": "DIRECT LINE",
    "KENYAN ALLIANCE": "KENYA ALLIANCE",
    "KENYA ALLIANCE INSURANCE": "KENYA ALLIANCE",
    "GA": "GA INSURANCE",
    "G A": "GA INSURANCE",
    "CIC GENERAL INSURANCE COMPANY": "CIC",
    "CIC GENERAL": "CIC",
    "CIC INSURANCE": "CIC",
    "APA CREDIT": "APA",
    "APA INSURANCE": "APA",
    "KEN INDIA": "KENINDIA",
    "HERITAGE INSURANCE": "HERITAGE",
    "JUBILEE INSURANCE": "JUBILEE",
    "BRITAM INSURANCE": "BRITAM",
    "MADISON INSURANCE": "MADISON",
    "PIONEER INSURANCE": "PIONEER",
}
KNOWN_UNDERWRITERS = {
    "MONARCH", "CIC", "MADISON", "HERITAGE", "APA", "AMACO", "PIONEER", "JUBILEE", "BRITAM", "FIDELITY",
    "TRIDENT", "GA INSURANCE", "DIRECT LINE", "KENYA ORIENT", "KENYA ALLIANCE", "XPLICO", "KENINDIA",
}


def resolve_underwriter(raw: Any, db_aliases: dict[str, str] | None = None) -> tuple[str | None, list[Flag]]:
    key = norm_text(raw)
    if not key:
        return None, [Flag("underwriter_missing", WARNING, "No underwriter on this row")]
    if db_aliases and key in db_aliases:
        return db_aliases[key], []
    if key in DEFAULT_UNDERWRITER_ALIASES:
        return DEFAULT_UNDERWRITER_ALIASES[key], []
    if key in KNOWN_UNDERWRITERS:
        return key, []
    best, best_ratio = None, 0.0
    for known in KNOWN_UNDERWRITERS:
        ratio = SequenceMatcher(None, key, known).ratio()
        if ratio > best_ratio:
            best, best_ratio = known, ratio
    if best and best_ratio >= 0.86:
        return best, [Flag("underwriter_fuzzy_match", INFO, f"'{str(raw).strip()}' read as {best}")]
    return key, [Flag("underwriter_unknown", INFO, f"'{str(raw).strip()}' is not a known underwriter - kept as typed")]


# --------------------------------------------------------------------------------------
# Staff and branch
# --------------------------------------------------------------------------------------

BRANCH_VARIANTS: dict[str, list[str]] = {
    "HQ": ["HQ", "H Q", "HEAD OFFICE"],
    "RUIRU": ["RUIRU", "RURU", "RIRU"],
    "EMBAKASI": ["EMBAKASI", "EMBAKASSI"],
    "NGONG ROAD": ["NGONG ROAD", "NGONG RD", "NGONG", "NGNG RD", "NG RD", "NG ROAD", "NGONGROAD"],
    "KITENGELA": ["KITENGELA"],
    "KAJIADO": ["KAJIADO"],
    "CBD": ["CBD"],
    "THIKA": ["THIKA"],
    "KAWANGWARE": ["KAWANGWARE", "KAWAGWARE", "KAWGWARE"],
    "NAKURU": ["NAKURU"],
    "KARATINA": ["KARATINA"],
    "MOMBASA": ["MOMBASA", "MSA"],
    "KASARANI": ["KASARANI"],
    "RONGAI": ["RONGAI"],
    "MACHAKOS": ["MACHAKOS"],
    "NYERI": ["NYERI"],
    "ELDORET": ["ELDORET"],
}
_BRANCH_LOOKUP = {variant: branch for branch, variants in BRANCH_VARIANTS.items() for variant in variants}


def match_branch(text: str) -> str | None:
    key = norm_text(text)
    if not key:
        return None
    if key in _BRANCH_LOOKUP:
        return _BRANCH_LOOKUP[key]
    if len(key) >= 5:
        for variant, branch in _BRANCH_LOOKUP.items():
            if len(variant) >= 5 and SequenceMatcher(None, key, variant).ratio() >= 0.85:
                return branch
    return None


def split_staff_branch(raw: Any) -> tuple[str | None, str | None]:
    """'JOSPHINE -HQ', 'HQ-JOSPHINE', 'JOSSY EMBAKASI', 'Jesse' -> (name, branch)."""
    text = clean_display(raw)
    if not text:
        return None, None
    text = text.replace("(", " ").replace(")", " ")
    parts = [p.strip() for p in re.split(r"\s*[-–—]\s*", text) if p.strip()]
    if len(parts) >= 2:
        first, last = " ".join(parts[:-1]), parts[-1]
        if match_branch(last):
            return first, match_branch(last)
        if match_branch(first):
            return last, match_branch(first)
        return " ".join(parts), None
    words = text.split()
    if match_branch(text):
        return None, match_branch(text)
    # "JOSSY EMBAKASI", "KATE NGONG RD": a trailing 1-2 words that are a branch
    for take in (2, 1):
        if len(words) > take and match_branch(" ".join(words[-take:])):
            return " ".join(words[:-take]), match_branch(" ".join(words[-take:]))
    return text, None


def _title(name: str | None) -> str | None:
    return " ".join(w.capitalize() for w in name.split()) if name else None


class StaffResolver:
    """Groups the many spellings of a staff member into one name for a whole upload.

    Saved aliases (from the app's Names screen) always win. Otherwise names within about
    one typo of a more common spelling are merged into it ('Josphine' / 'Josephine',
    'Scola' / 'Schola'); every spelling resolved this way is reported in `resolved` so an
    administrator can confirm it once."""

    def __init__(self, raw_values: Iterable[Any], db_aliases: dict[str, tuple[str | None, str | None]] | None = None):
        self.db_aliases = db_aliases or {}
        counts: dict[str, int] = {}
        for raw in raw_values:
            name, _ = split_staff_branch(raw)
            if name:
                key = norm_text(name)
                counts[key] = counts.get(key, 0) + 1
        self._head: dict[str, str] = {}
        heads: list[str] = []
        for key in sorted(counts, key=lambda k: (-counts[k], k)):
            match = next((h for h in heads if h[:1] == key[:1] and SequenceMatcher(None, key, h).ratio() >= 0.84), None)
            if match:
                self._head[key] = match
            else:
                heads.append(key)
                self._head[key] = key
        # Every spelling resolved without a saved alias: key -> (name, branch, text as typed).
        # The import saves these as unconfirmed aliases so an administrator can review them once.
        self.resolved: dict[str, tuple[str | None, str | None, str]] = {}

    def resolve(self, raw: Any) -> tuple[str | None, str | None, list[Flag]]:
        key = norm_text(raw)
        if not key:
            return None, None, [Flag("staff_missing", INFO, "No staff / branch on this row")]
        if key in self.db_aliases:
            name, branch = self.db_aliases[key]
            return name, branch, []
        name, branch = split_staff_branch(raw)
        if name:
            name = _title(self._head.get(norm_text(name), norm_text(name)))
        flags: list[Flag] = []
        self.resolved[key] = (name, branch, str(raw).strip())
        if name is None:
            flags.append(Flag("staff_missing", INFO, "Branch given but no staff name"))
        return name, branch, flags


# --------------------------------------------------------------------------------------
# Row keys - how a sheet row is recognised again on the next upload
# --------------------------------------------------------------------------------------


def _clean_key_part(value: Any) -> str:
    return norm_text(value).replace(" ", "")


def row_keys(underwriter: str | None, policy_number: str | None, plate: str | None, start: date | None,
             premium: Decimal | None, client: str | None, sheet_year: int | None = None) -> tuple[str, str]:
    """-> (primary key, fallback key).

    Primary: insurer + policy number + the sheet's year when there is a policy number (the same
    number legitimately returns in later years when a policy is renewed under it), otherwise
    the fallback. Fallback: insurer + plate + start date + premium + client - lets a row that
    later gains a policy number, or moves to another sheet, be recognised as the same row."""
    from hashlib import sha1

    fallback_raw = "|".join([
        _clean_key_part(underwriter), plate or "", start.isoformat() if start else "",
        f"{premium:.2f}" if premium is not None else "", _clean_key_part(client),
    ])
    fallback = sha1(("F|" + fallback_raw).encode()).hexdigest()
    if policy_number:
        primary = sha1(("P|" + _clean_key_part(underwriter) + "|" + _clean_key_part(policy_number) + "|" + str(sheet_year or "")).encode()).hexdigest()
    else:
        primary = fallback
    return primary, fallback
