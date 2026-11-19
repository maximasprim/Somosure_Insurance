"""Comprehensive motor cover without a valuation report: a one-month sticker now, the report later.

A customer asking for comprehensive cover is quoted on the vehicle value they entered. The valuation report is what
confirms that value, but it is optional at application time:

* with a report, nothing here applies - the policy and its sticker are issued as always;
* without one, the customer still pays the amount on the quote, the policy is issued, and only a ONE-MONTH sticker is
  issued. The policy is flagged `valuation_pending` (with the day the sticker ends in `valuation_due`) so staff can
  reconcile the premium once the real report arrives, and so the customer is reminded to provide it.

Nothing is repriced here: the premium stays what was quoted until staff reconcile it.
One rule keeps this from being used as a loophole: a vehicle that already has a one-month cover whose report has not
arrived cannot be given another one (it must be applied for with the report).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationDocument
from app.models.policy import Policy
from app.models.quote import Quote, QuoteRequest
from app.services.document_requirements import is_comprehensive, quote_cover_type
from app.services.motor_terms import add_months

VALUATION_DOCUMENT = "valuation_report"


def normalise_registration(value: object) -> str | None:
    """'kda 123x' -> 'KDA123X', so the same vehicle matches however it was typed."""
    text = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    return text[:30] or None


def cover_window(start: date) -> tuple[date, date]:
    """The one-month sticker: from `start` to the day before the same date next month."""
    return start, add_months(start, 1) - timedelta(days=1)


def registration_of(quote_request: QuoteRequest | None) -> str | None:
    return normalise_registration((quote_request.input_data or {}).get("registration_number")) if quote_request else None


async def lacks_valuation(db: AsyncSession, application: Application, quote: Quote | None, quote_request: QuoteRequest | None) -> bool:
    """True for a comprehensive motor application with no (accepted) valuation report on it."""
    if quote_request and quote_request.category != "motor":
        return False
    cover = quote_cover_type(quote.provider_metadata if quote else None, quote_request.input_data if quote_request else None)
    if not is_comprehensive(cover):
        return False
    have = await db.scalar(
        select(func.count()).select_from(ApplicationDocument).where(
            ApplicationDocument.application_id == application.id,
            ApplicationDocument.document_type == VALUATION_DOCUMENT,
            ApplicationDocument.status != "rejected",
        )
    )
    return not have


async def ensure_no_open_provisional_cover(db: AsyncSession, quote_request: QuoteRequest | None) -> None:
    """Refuses a second one-month cover for a vehicle whose first one is still waiting for its report."""
    registration = registration_of(quote_request)
    if not registration:
        return
    open_cover = await db.scalar(
        select(Policy.id).where(
            Policy.provisional_vehicle == registration,
            Policy.valuation_pending.is_(True),
            Policy.status != "cancelled",
        ).limit(1)
    )
    if open_cover:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"A one-month comprehensive sticker has already been issued for {registration} and its valuation report has not "
            "been received. Please upload the valuation report to continue with this application.",
        )
