"""Phone-number matching helpers.

Kenyan numbers are typed many ways - 0712 345 678, +254712345678,
254712345678, 0712-345-678 - and customers are matched by phone (guest
quotes, the contact form). Comparing the raw strings makes one person
look like several customers. These helpers let a LOOKUP match every
common spelling of the same number without changing how any number is
stored.
"""

import re


def phone_variants(phone: str | None) -> list[str]:
    """Every common spelling of this number, original first. Returns just
    the original (stripped) when it doesn't look like a Kenyan mobile or
    landline number, so unusual numbers still match exactly as before."""
    if not phone:
        return []
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)

    local: str | None = None
    if digits.startswith("254") and len(digits) == 12:
        local = "0" + digits[3:]
    elif digits.startswith("0") and len(digits) == 10:
        local = digits
    elif len(digits) == 9 and digits[0] in "17":  # 712345678 typed without the leading 0
        local = "0" + digits

    variants = [raw]
    if local:
        national = local[1:]
        for candidate in (local, f"254{national}", f"+254{national}", digits):
            if candidate not in variants:
                variants.append(candidate)
    elif digits and digits != raw:
        variants.append(digits)
    return variants
