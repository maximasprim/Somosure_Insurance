"""The product catalogue: which insurance categories exist, which can be
quoted online, and what the property cover options are.

One place, so the quote API, the "coming soon" screen, the document checklist
and the demo pricing can never disagree about it.

Changing the catalogue:
  * make a coming-soon product quotable -> remove it from COMING_SOON_ALWAYS
    (and connect a real insurer or rate card for it; see docs/PRODUCT_CATALOGUE.md);
  * retire a product -> add it to LEGACY_ALIASES pointing at its replacement.
"""

from decimal import Decimal
from typing import Any

# Products that can be quoted online. Whether each one is actually live right
# now (real pricing) or demo-only is decided by quote_availability.py.
QUOTABLE_CATEGORIES = (
    "motor",
    "medical",
    "life",
    "travel",
    "property",
    "personal_accident",
    "professional_indemnity",
    "wiba",
)

# Announced products with no pricing at all yet. Always shown as "coming
# soon, talk to an agent" - even in demo mode - and refused by the quote API,
# so no made-up premium can ever be produced for them.
COMING_SOON_ALWAYS = ("cargo", "hull", "cybersecurity")

ALL_CATEGORIES = QUOTABLE_CATEGORIES + COMING_SOON_ALWAYS

# Retired products. Old links, saved quotes in browsers and stale clients that
# still send these are treated as the replacement product.
LEGACY_ALIASES = {"home": "property", "business": "property"}

# Property insurance: what the customer can choose to insure against.
# value, label, group, and a relative weight used ONLY by the demo pricing.
PROPERTY_COVER_OPTIONS: tuple[dict[str, Any], ...] = (
    {"value": "fire", "group": "core", "weight": "1.00", "label": "Fire & lightning"},
    {"value": "theft_burglary", "group": "core", "weight": "0.80", "label": "Theft & burglary"},
    {"value": "natural_perils", "group": "extra", "weight": "0.40", "label": "Flood, storm & other natural perils"},
    {"value": "riot_malicious", "group": "extra", "weight": "0.25", "label": "Riot, strike & malicious damage"},
    {"value": "accidental_damage", "group": "extra", "weight": "0.50", "label": "Accidental damage"},
    {"value": "all_risks", "group": "extra", "weight": "0.60", "label": "All risks (portable valuables)"},
    {"value": "electronic_equipment", "group": "extra", "weight": "0.50", "label": "Electronic equipment"},
    {"value": "money", "group": "extra", "weight": "0.30", "label": "Money in safe or in transit"},
    {"value": "glass", "group": "extra", "weight": "0.15", "label": "Glass breakage"},
    {"value": "public_liability", "group": "extra", "weight": "0.50", "label": "Public liability"},
    {"value": "business_interruption", "group": "extra", "weight": "0.70", "label": "Business interruption"},
    {"value": "machinery_breakdown", "group": "extra", "weight": "0.50", "label": "Machinery breakdown"},
)
_OPTION_BY_VALUE = {o["value"]: o for o in PROPERTY_COVER_OPTIONS}


def normalize_category(category: str) -> str:
    """Maps a retired category (home, business) to its replacement."""
    key = (category or "").strip().lower()
    return LEGACY_ALIASES.get(key, key)


def is_coming_soon(category: str) -> bool:
    return normalize_category(category) in COMING_SOON_ALWAYS


def selected_property_options(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """The valid cover options the customer ticked, in catalogue order."""
    raw = answers.get("cover_options") or []
    if isinstance(raw, str):  # tolerate a comma-separated string from simple clients
        raw = [part.strip() for part in raw.split(",")]
    chosen = {v for v in raw if isinstance(v, str)}
    return [o for o in PROPERTY_COVER_OPTIONS if o["value"] in chosen]


def demo_base_premium(category: str, answers: dict[str, Any], default_base: Decimal) -> Decimal:
    """Base figure the demo insurers apply their variance to. Unchanged for
    every category except property, which responds to the options ticked and
    the sum insured so the demo behaves sensibly. NOT real pricing."""
    if category != "property":
        return default_base
    options = selected_property_options(answers)
    weight = sum((Decimal(o["weight"]) for o in options), Decimal("0")) or Decimal("1.00")
    try:
        sum_insured = Decimal(str(answers.get("sum_insured") or 0))
    except Exception:
        sum_insured = Decimal("0")
    if sum_insured > 0:
        return max(Decimal("3000"), (sum_insured * Decimal("0.0012") * weight).quantize(Decimal("0.01")))
    return (default_base * (Decimal("0.5") + weight * Decimal("0.5"))).quantize(Decimal("0.01"))


def demo_coverage_summary(category: str, answers: dict[str, Any], fallback: str) -> str:
    if category == "property":
        labels = [o["label"] for o in selected_property_options(answers)]
        if labels:
            return "Property cover: " + ", ".join(labels)
    return fallback
