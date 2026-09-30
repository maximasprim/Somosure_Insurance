import logging
import random
import string
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.actions import generate_sticker
from app.models.application import Application
from app.models.payment import Payment, PaymentTransaction
from app.models.policy import Policy
from app.models.quote import Quote
from app.payments.registry import get_payment_provider
from app.services import motor_terms
from app.services.policy_service import issue_policy

logger = logging.getLogger("somosure.payment_service")


def generate_payment_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-PAY-{year}-{suffix}"


def _remaining_schedule(schedule: list[dict] | None, paid_through_sequence: int) -> list[dict]:
    if not schedule:
        return []
    return [leg for leg in schedule if int(leg["sequence"]) > paid_through_sequence]


async def _resolve_plan_leg(db: AsyncSession, application: Application, plan_code: str, installments: int) -> tuple[Quote, dict]:
    """Looks up the requested plan against the quote THIS application was
    actually created from, so the amount charged is never taken from the
    client - only from what was priced and shown at quote time."""
    quote = await db.get(Quote, application.quote_id)
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The original quote for this application could not be found")

    plans = (quote.payment_options or {}).get("plans") or []
    option = motor_terms.find_option(plans, plan_code, installments)
    if not option:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"'{plan_code}' with {installments} instalment(s) is not one of the payment plans offered for this quote.",
        )
    return quote, option


async def initiate_payment(
    db: AsyncSession,
    application_id: str,
    customer_id: str,
    amount: str,
    phone: str | None,
    method: str = "mpesa",
    plan_code: str | None = None,
    installments: int | None = None,
) -> tuple[Payment, str]:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status != "approved":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This application must be approved by underwriting before payment can be collected",
        )

    total_amount = None
    schedule = None
    installment_sequence = None
    charge_amount = amount

    if plan_code and plan_code != "full" and installments:
        quote, option = await _resolve_plan_leg(db, application, plan_code, installments)
        schedule = option["schedule"]
        total_amount = str(quote.total)
        installment_sequence = 1
        charge_amount = option["due_now"]
        plan_code = option["plan_code"]

    payment = Payment(
        reference=generate_payment_reference(),
        customer_id=customer_id,
        application_id=application_id,
        amount=charge_amount,
        method=method,
        status="initiated",
        payer_phone=phone,
        plan_code=plan_code if plan_code and plan_code != "full" else None,
        installment_sequence=installment_sequence,
        total_amount=total_amount,
        schedule=schedule,
    )
    db.add(payment)
    await db.flush()

    provider = get_payment_provider(method)
    result = await provider.initiate(charge_amount, phone, payment.reference)

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


async def initiate_next_installment(db: AsyncSession, root_payment_id: str, phone: str | None) -> tuple[Payment, str]:
    """Pays the next not-yet-paid leg of a plan that a previous call to
    initiate_payment() started. `root_payment_id` is the id of that FIRST
    payment (the one with installment_sequence=1, plan_code set)."""
    root = await db.get(Payment, root_payment_id)
    if not root or not root.schedule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No payment plan found for that payment")
    if root.root_payment_id is not None:
        # A caller-supplied id that's itself a later leg - walk to the
        # actual root so counting below is always against the same anchor.
        root = await db.get(Payment, root.root_payment_id)

    paid_count = await db.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            ((Payment.id == root.id) | (Payment.root_payment_id == root.id)),
            Payment.status == "successful",
        )
    )
    remaining = _remaining_schedule(root.schedule, paid_through_sequence=paid_count or 0)
    if not remaining:
        raise HTTPException(status.HTTP_409_CONFLICT, "Every instalment on this plan has already been paid")

    next_leg = remaining[0]

    payment = Payment(
        reference=generate_payment_reference(),
        customer_id=root.customer_id,
        application_id=root.application_id,
        amount=next_leg["amount"],
        method="mpesa",
        status="initiated",
        payer_phone=phone,
        plan_code=root.plan_code,
        installment_sequence=int(next_leg["sequence"]),
        total_amount=root.total_amount,
        schedule=root.schedule,
        root_payment_id=root.id,
    )
    db.add(payment)
    await db.flush()

    provider = get_payment_provider("mpesa")
    result = await provider.initiate(next_leg["amount"], phone, payment.reference)

    db.add(
        PaymentTransaction(
            payment_id=payment.id,
            provider="mock_mpesa" if provider.is_mock else "mpesa",
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
        existing_policy = await db.scalar(select(Policy).where(Policy.application_id == payment.application_id))

        if not existing_policy:
            # First successful payment for this application - issue as
            # before, whether it was paid in full, as a deposit, or as
            # instalment #1 of a plan.
            try:
                policy = await issue_policy(db, str(payment.application_id))
                payment.policy_id = policy.id
                await db.commit()
            except Exception:
                logger.exception(
                    "Payment %s succeeded but policy issuance failed - needs manual follow-up", payment.reference
                )
        else:
            # A later instalment on an already-issued policy - never
            # re-issue. If this leg's schedule entry carries a cover
            # window (the plan pays each month for one month of sticker
            # cover), generate that month's sticker; otherwise there's
            # nothing further to do beyond recording the successful
            # payment, which already happened above.
            payment.policy_id = existing_policy.id
            leg = next(
                (
                    row
                    for row in (payment.schedule or [])
                    if int(row.get("sequence", -1)) == (payment.installment_sequence or -1)
                ),
                None,
            )
            if leg and leg.get("cover_from"):
                await generate_sticker(
                    db,
                    context={
                        "policy_id": str(existing_policy.id),
                        "policy_number": existing_policy.policy_number,
                        "valid_from": date.fromisoformat(leg["cover_from"]),
                        "valid_to": date.fromisoformat(leg["cover_to"]),
                    },
                    config={},
                )
            await db.commit()

    return {"status": payment.status}
