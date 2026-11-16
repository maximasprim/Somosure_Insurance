"""Pure matching helpers shared by the customer linking and the combined reports (no database)."""

from __future__ import annotations

import re
from typing import Any

from app.services.sales_import.cleaners import norm_text


def phone_key(value: Any) -> str | None:
    """The last nine digits of a phone number, so '0721 559 694', '+254721559694' and
    '254721559694' are the same number. None when there are not nine digits."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-9:] if len(digits) >= 9 else None


def _name_tokens(name: str | None) -> set[str]:
    return {t for t in norm_text(name).split() if len(t) >= 3}


def names_overlap(a: str | None, b: str | None) -> bool:
    """Do two names share a word of three letters or more? Used before trusting a plate match."""
    return bool(_name_tokens(a) & _name_tokens(b))


def canonical_underwriter(name: str | None, known: set[str]) -> str:
    """Brings a platform provider name ('AMACO INSURANCE') onto the name the workbook uses ('AMACO')."""
    key = norm_text(name)
    if not key:
        return "NOT STATED"
    if key in known:
        return key
    for candidate in sorted(known, key=len, reverse=True):
        if key.startswith(candidate + " "):
            return candidate
    return key


def match_provider_name(underwriter: str | None, providers: dict[str, Any]) -> Any | None:
    """Finds the existing provider the workbook's underwriter means. `providers` maps a provider's normalised
    name to whatever identifies it. 'MONARCH' matches 'Monarch Insurance Company' (the provider's name starts with
    it) and 'AMACO INSURANCE' matches 'AMACO'. None when there is no confident match."""
    key = norm_text(underwriter)
    if not key:
        return None
    if key in providers:
        return providers[key]
    for name, ident in providers.items():
        if name.startswith(key + " ") or key.startswith(name + " "):
            return ident
    return None
