import logging
import random
import string
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.payment import Payment, PaymentTransaction
from app.payments.registry import get_payment_provider
from app.services.policy_service import issue_policy

logger = logging.getLogger("somosure.payment_service")


def generate_payment_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-PAY-{year}-{suffix}"


async def initiate_payment(
    db: AsyncSession, application_id: str, customer_id: str, amount: str, phone: str | None, method: str = "mpesa"
) -> tuple[Payment, str]:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status != "approved":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This application must be approved by underwriting before payment can be collected",
        )

    payment = Payment(
        reference=generate_payment_reference(),
        customer_id=customer_id,
        application_id=application_id,
        amount=amount,
        method=method,
        status="initiated",
        payer_phone=phone,
    )
    db.add(payment)
    await db.flush()

    provider = get_payment_provider(method)
    result = await provider.initiate(amount, phone, payment.reference)

    db.add(
        PaymentTransaction(
            payment_id=payment.id,
            provider="mock_mpesa" if provider.is_mock else method,
            provider_transaction_id=result.provider_transaction_id,
            direction="outbound",
            status=result.status,
            raw_payload=result.raw,
        )
    )
    payment.status = "pending"

    await db.commit()
    await db.refresh(payment)
    return payment, result.provider_transaction_id


async def handle_mpesa_webhook(db: AsyncSession, headers: dict[str, str], body: bytes) -> dict:
    """Never trusts the payload until the signature verifies. On a verified
    success, records the transaction, marks the payment successful, and
    triggers policy issuance - the one automatic issuance path in the
    system before Phase 6's automation engine generalizes it."""
    from app.payments.mock_mpesa import MockMpesaProvider  # local import: this route is mock-only for now

    provider = MockMpesaProvider()
    verification = provider.verify_webhook(headers, body)

    if not verification.is_valid:
        logger.warning("Rejected M-Pesa webhook with invalid/missing signature")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    from sqlalchemy import select

    txn = await db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.provider_transaction_id == verification.provider_transaction_id
        )
    )
    if not txn:
        logger.error("Webhook referenced unknown transaction %s", verification.provider_transaction_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown transaction")

    payment = await db.get(Payment, txn.payment_id)
    if payment.status == "successful":
        # Idempotency: a duplicate callback should not double-issue a policy.
        return {"status": "already_processed"}

    db.add(
        PaymentTransaction(
            payment_id=payment.id,
            provider="mock_mpesa",
            provider_transaction_id=verification.provider_transaction_id,
            direction="inbound",
            status=verification.status or "unknown",
            raw_payload=verification.raw,
        )
    )

    payment.status = verification.status or "failed"
    await db.commit()

    if payment.status == "successful" and payment.application_id:
        try:
            policy = await issue_policy(db, str(payment.application_id))
            payment.policy_id = policy.id
            await db.commit()
        except Exception:
            logger.exception("Payment %s succeeded but policy issuance failed - needs manual follow-up", payment.reference)

    return {"status": payment.status}
