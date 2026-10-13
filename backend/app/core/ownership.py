"""Who may touch which record on the customer-facing (non-admin) endpoints.

Rule of thumb: you may act on an application / financing application / payment if
  (a) you are logged in as the customer it belongs to, or
  (b) you hold the signed guest token the server issued when it was created
      (see app/core/guest_access.py).
Anything else gets a plain 404, the same as a record that doesn't exist, so ids
can't be probed.
"""

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.guest_access import has_grant
from app.models.application import Application
from app.models.financing import FinancingApplication
from app.models.payment import Payment
from app.models.quote import Quote, QuoteRequest


def _as_uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


async def load_application(db: AsyncSession, request: Request, authed_customer_id: str | None, application_id) -> Application:
    key = _as_uuid(application_id)
    application = await db.get(Application, key) if key else None
    if not application:
        raise _not_found("Application")
    if authed_customer_id and str(application.customer_id) == str(authed_customer_id):
        return application
    if has_grant(request, "application", application.id):
        return application
    raise _not_found("Application")


async def load_financing_application(
    db: AsyncSession, request: Request, authed_customer_id: str | None, application_id
) -> FinancingApplication:
    key = _as_uuid(application_id)
    application = await db.get(FinancingApplication, key) if key else None
    if not application:
        raise _not_found("Financing application")
    if authed_customer_id and str(application.customer_id) == str(authed_customer_id):
        return application
    if has_grant(request, "financing", application.id):
        return application
    raise _not_found("Financing application")


async def load_payment(db: AsyncSession, request: Request, authed_customer_id: str | None, payment_id) -> Payment:
    key = _as_uuid(payment_id)
    payment = await db.get(Payment, key) if key else None
    if not payment:
        raise _not_found("Payment")
    if payment.application_id:
        # Same access as the application the payment is for.
        await load_application(db, request, authed_customer_id, payment.application_id)
        return payment
    if authed_customer_id and str(payment.customer_id) == str(authed_customer_id):
        return payment
    raise _not_found("Payment")


async def customer_for_quote(db: AsyncSession, authed_customer_id: str | None, quote_id, claimed_customer_id) -> str:
    """Which customer an application / financing application for this quote belongs
    to. The browser says who it is; we only accept that if it matches the customer
    the server itself resolved when the quote was requested (or the logged-in
    customer) - so nobody can open an application under someone else's customer id."""
    key = _as_uuid(quote_id)
    quote = await db.get(Quote, key) if key else None
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    quote_request = await db.get(QuoteRequest, quote.quote_request_id)
    quote_customer = str(quote_request.customer_id) if quote_request and quote_request.customer_id else None

    claimed = str(claimed_customer_id)
    if claimed in {quote_customer, str(authed_customer_id) if authed_customer_id else None}:
        return claimed
    if quote_customer is None and _as_uuid(claimed):
        # An anonymous quote (no contact details were given) has no customer to
        # compare with; the application is the first thing that names one.
        return claimed
    raise HTTPException(status.HTTP_403_FORBIDDEN, "This quote belongs to a different customer")
