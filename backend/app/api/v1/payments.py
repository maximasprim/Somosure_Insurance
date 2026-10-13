import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_optional_customer_id
from app.core.ownership import load_application, load_payment
from app.models.payment import Payment
from app.payments.mock_mpesa import MockMpesaProvider
from app.payments.registry import mock_payments_allowed, mpesa_is_mock
from app.schemas.payment import NextInstallmentRequest, PaymentInitiateRequest, PaymentInitiateResponse, PaymentOut
from app.services.payment_service import (
    handle_mpesa_webhook,
    handle_payment_callback,
    initiate_next_installment,
    initiate_payment,
)

logger = logging.getLogger("somosure.payments")

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
webhook_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
settings = get_settings()


def _remaining_schedule(payment: Payment) -> list[dict] | None:
    if not payment.schedule:
        return None
    done = payment.installment_sequence or 0
    return [leg for leg in payment.schedule if int(leg["sequence"]) > done] or None


def _response(payment: Payment, provider_txn_id: str) -> PaymentInitiateResponse:
    return PaymentInitiateResponse(
        payment_id=str(payment.id),
        reference=payment.reference,
        status=payment.status,
        provider_transaction_id=provider_txn_id,
        # The frontend shows the "simulate payment" buttons only when this is true.
        is_mock=mpesa_is_mock() if payment.method == "mpesa" else True,
        plan_code=payment.plan_code,
        installment_sequence=payment.installment_sequence,
        remaining_schedule=_remaining_schedule(payment),
    )


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate(
    payload: PaymentInitiateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    # Only the owner of the application (logged in, or holding the guest token
    # issued when it was created) can start a payment for it. The customer is the
    # application's own customer - the id in the request body is ignored - and the
    # amount is worked out on the server (see initiate_payment).
    application = await load_application(db, request, authed_customer_id, payload.application_id)
    payment, provider_txn_id = await initiate_payment(
        db,
        application_id=str(application.id),
        customer_id=str(application.customer_id),
        amount=str(payload.amount),
        phone=payload.phone,
        method=payload.method,
        plan_code=payload.plan_code,
        installments=payload.installments,
    )
    return _response(payment, provider_txn_id)


@router.post("/{payment_id}/next-installment", response_model=PaymentInitiateResponse)
async def next_installment(
    payment_id: str,
    payload: NextInstallmentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    """Pays the next not-yet-paid leg of a plan started by /initiate.
    `payment_id` is any earlier leg of that same plan (usually the first).
    """
    await load_payment(db, request, authed_customer_id, payment_id)
    payment, provider_txn_id = await initiate_next_installment(db, payment_id, payload.phone)
    return _response(payment, provider_txn_id)


@router.get("/{payment_id}/status", response_model=PaymentOut)
async def get_status(
    payment_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    return await load_payment(db, request, authed_customer_id, payment_id)


@webhook_router.post("/mpesa")
async def mpesa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """SIMULATOR callback (signed with the dev secret). Only works where mock
    payments are allowed; on a live server with real M-Pesa this answers 404, so
    the simulator's public secret can never confirm a real payment."""
    body = await request.body()
    return await handle_mpesa_webhook(db, dict(request.headers), body)


@webhook_router.post("/pay/{secret}")
async def daraja_callback(secret: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Where Safaricom posts the result of an STK push. The secret in the address
    is the first check; the payment is then only accepted if the amount matches and
    Safaricom independently confirms it (see settle_payment). Always answers quickly
    and plainly - Safaricom retries on errors, and the reconcile job covers the rest."""
    s = get_settings()
    expected = s.mpesa_callback_secret
    if s.mpesa_mode != "daraja" or not expected or not hmac.compare_digest(secret, expected):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    from app.payments.daraja import DarajaMpesaProvider

    body = await request.body()
    try:
        result = await handle_payment_callback(db, DarajaMpesaProvider(s), dict(request.headers), body)
    except HTTPException as exc:
        # An unknown / malformed callback is logged, not retried forever.
        logger.warning("Daraja callback not accepted: %s", exc.detail)
        return {"ResultCode": 0, "ResultDesc": "Received"}
    logger.info("Daraja callback processed: %s", result.get("status"))
    return {"ResultCode": 0, "ResultDesc": "Received"}


if settings.environment == "development" or settings.allow_mock_payments:

    @router.post("/{provider_transaction_id}/simulate-completion")
    async def simulate_completion(provider_transaction_id: str, outcome: str, amount: str, db: AsyncSession = Depends(get_db)):
        """DEV ONLY - stands in for the customer completing the STK push on
        their phone. Builds a properly signed callback and posts it through
        the exact same verify_webhook path a real callback would use, so
        nothing about the success path is faked or bypassed. Not registered
        outside development (unless ALLOW_MOCK_PAYMENTS=true), and refuses to
        run while real M-Pesa is switched on."""
        if not mock_payments_allowed() or not mpesa_is_mock():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        provider = MockMpesaProvider()
        body, headers = provider.build_simulated_callback(provider_transaction_id, outcome, amount)
        return await handle_mpesa_webhook(db, headers, body)
