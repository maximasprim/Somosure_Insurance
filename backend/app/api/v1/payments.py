from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.payment import Payment
from app.payments.mock_mpesa import MockMpesaProvider
from app.schemas.payment import PaymentInitiateRequest, PaymentInitiateResponse, PaymentOut
from app.services.payment_service import handle_mpesa_webhook, initiate_payment

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])
webhook_router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
settings = get_settings()


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate(payload: PaymentInitiateRequest, db: AsyncSession = Depends(get_db)):
    payment, provider_txn_id = await initiate_payment(
        db,
        application_id=payload.application_id,
        customer_id=payload.customer_id,
        amount=str(payload.amount),
        phone=payload.phone,
        method=payload.method,
    )
    return PaymentInitiateResponse(
        payment_id=str(payment.id),
        reference=payment.reference,
        status=payment.status,
        provider_transaction_id=provider_txn_id,
    )


@router.get("/{payment_id}/status", response_model=PaymentOut)
async def get_status(payment_id: str, db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    return payment


@webhook_router.post("/mpesa")
async def mpesa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """The ONLY thing allowed to mark a payment successful. Signature is
    verified inside handle_mpesa_webhook - the frontend confirming payment
    is never sufficient (spec §13)."""
    body = await request.body()
    return await handle_mpesa_webhook(db, dict(request.headers), body)


if settings.environment == "development":

    @router.post("/{provider_transaction_id}/simulate-completion")
    async def simulate_completion(provider_transaction_id: str, outcome: str, amount: str, db: AsyncSession = Depends(get_db)):
        """DEV ONLY - stands in for the customer completing the STK push on
        their phone. Builds a properly signed callback and posts it through
        the exact same verify_webhook path a real Daraja callback would use,
        so nothing about the success path is faked or bypassed. Not
        registered outside `environment=development`."""
        provider = MockMpesaProvider()
        body, headers = provider.build_simulated_callback(provider_transaction_id, outcome, amount)
        return await handle_mpesa_webhook(db, headers, body)
