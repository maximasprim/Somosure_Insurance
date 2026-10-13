import logging
import secrets
import string
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.actions import generate_sticker
from app.models.application import Application
from app.models.financing import FinancingApplication
from app.models.payment import Payment, PaymentTransaction
from app.models.policy import Policy
from app.models.quote import Quote
from app.core.config import get_settings
from app.payments.base import PaymentProviderAdapter, WebhookVerificationResult
from app.payments.registry import get_payment_provider, mock_payments_allowed
from app.services import motor_terms
from app.services.discount_math import apply_discount_to_schedule
from app.services.policy_service import issue_policy

logger = logging.getLogger("somosure.payment_service")


def generate_payment_reference() -> str:
    year = date.today().year
    # secrets (not random): references must not be guessable, and 8 digits makes
    # a collision with an existing reference very unlikely (the column is unique).
    suffix = "".join(secrets.choice(string.digits) for _ in range(8))
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

    # A referral discount staff applied to this application comes off what is
    # charged. It is worked out HERE, from the stored quote - never from the
    # amount the browser sends - and an application without one is untouched.
    discount = Decimal(application.discount_amount or 0)

    if plan_code and plan_code != "full" and installments:
        quote, option = await _resolve_plan_leg(db, application, plan_code, installments)
        schedule = option["schedule"]
        total_amount = str(quote.total)
        installment_sequence = 1
        charge_amount = option["due_now"]
        plan_code = option["plan_code"]
        if discount > 0:
            # The discount comes off the first payment (the customer benefits
            # straight away); the plan's other payments are unchanged.
            schedule, taken = apply_discount_to_schedule(schedule, discount)
            total_amount = str(Decimal(str(quote.total)) - taken)
            charge_amount = schedule[0]["amount"]
    else:
        # NEVER charge what the browser says. The amount is worked out here from
        # records we hold: the deposit of an approved Bidii Credit financing
        # application for this quote, otherwise the quote's total less any discount.
        financing = await db.scalar(
            select(FinancingApplication)
            .where(
                FinancingApplication.quote_id == application.quote_id,
                FinancingApplication.customer_id == application.customer_id,
                FinancingApplication.status == "approved",
            )
            .order_by(FinancingApplication.created_at.desc())
        )
        if financing:
            deposit = Decimal(str(financing.deposit_amount))
            if deposit <= 0:
                raise HTTPException(status.HTTP_409_CONFLICT, "No deposit is due - your financing covers the premium.")
            charge_amount = str(deposit)
        else:
            quote = await db.get(Quote, application.quote_id)
            if not quote:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "The original quote for this application could not be found")
            charge_amount = str(max(Decimal(str(quote.total)) - discount, Decimal("1.00")))

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


async def _find_outbound_transaction(db: AsyncSession, provider_transaction_id: str | None) -> PaymentTransaction | None:
    if not provider_transaction_id:
        return None
    return await db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.provider_transaction_id == provider_transaction_id,
            PaymentTransaction.direction == "outbound",
        )
        .order_by(PaymentTransaction.created_at.asc())
    )


async def _issue_policy_after_payment(db: AsyncSession, payment: Payment) -> None:
    """Runs once a payment is marked successful: issue the policy for the first
    successful payment, or (for a later instalment) generate that month's sticker."""
    if not payment.application_id:
        return
    existing_policy = await db.scalar(select(Policy).where(Policy.application_id == payment.application_id))

    if not existing_policy:
        # First successful payment for this application - issue as before,
        # whether it was paid in full, as a deposit, or as instalment #1 of a plan.
        try:
            policy = await issue_policy(db, str(payment.application_id))
            payment.policy_id = policy.id
            await db.commit()
        except Exception:
            logger.exception("Payment %s succeeded but policy issuance failed - needs manual follow-up", payment.reference)
    else:
        # A later instalment on an already-issued policy - never re-issue. If this
        # leg's schedule entry carries a cover window (the plan pays each month for
        # one month of sticker cover), generate that month's sticker.
        payment.policy_id = existing_policy.id
        leg = next(
            (row for row in (payment.schedule or []) if int(row.get("sequence", -1)) == (payment.installment_sequence or -1)),
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


async def settle_payment(
    db: AsyncSession,
    provider: PaymentProviderAdapter,
    payment: Payment,
    verification: WebhookVerificationResult,
    *,
    already_confirmed: bool = False,
) -> dict:
    """Applies a provider's verdict to a payment. Used by the callback route and by
    the reconciliation job, so both go through the same safeguards.

    For a real (non-mock) provider a "successful" verdict is only accepted if
      - the amount reported equals the amount we asked for, and
      - the provider independently confirms it (provider.confirm), unless the
        verdict itself already came from such a confirmation (already_confirmed).
    Otherwise the payment is left pending and nothing is issued."""
    if payment.status == "successful":
        # Idempotency: a duplicate callback must not double-issue a policy.
        return {"status": "already_processed"}

    outcome = verification.status or "failed"
    provider_name = "mock_mpesa" if provider.is_mock else "mpesa"

    if outcome == "successful" and not provider.is_mock:
        if verification.amount is not None and not provider.amount_matches(verification.amount, payment.amount):
            logger.error(
                "Payment %s: provider reported amount %s but %s was requested - NOT marking successful",
                payment.reference, verification.amount, payment.amount,
            )
            db.add(
                PaymentTransaction(
                    payment_id=payment.id, provider=provider_name, provider_transaction_id=verification.provider_transaction_id,
                    direction="inbound", status="amount_mismatch", raw_payload=verification.raw,
                )
            )
            await db.commit()
            return {"status": "amount_mismatch"}

        if not already_confirmed:
            try:
                confirmation = await provider.confirm(verification.provider_transaction_id or "")
            except Exception:
                logger.exception("Could not confirm payment %s with the provider yet - leaving it pending", payment.reference)
                return {"status": "pending_confirmation"}
            if confirmation is not None and confirmation.status != "successful":
                logger.error(
                    "Payment %s: callback said successful but the provider says %s - NOT marking successful",
                    payment.reference, confirmation.status or "not final",
                )
                return {"status": "unconfirmed"}

    db.add(
        PaymentTransaction(
            payment_id=payment.id,
            provider=provider_name,
            provider_transaction_id=verification.provider_transaction_id,
            direction="inbound",
            status=outcome,
            raw_payload=verification.raw,
        )
    )
    payment.status = outcome
    await db.commit()

    if outcome == "successful":
        await _issue_policy_after_payment(db, payment)

    return {"status": payment.status}


async def handle_payment_callback(db: AsyncSession, provider: PaymentProviderAdapter, headers: dict[str, str], body: bytes) -> dict:
    """Never trusts the payload until the provider's own check passes. The route
    that receives the call has already authenticated it (callback-address secret for
    Daraja, signature for the simulator)."""
    verification = provider.verify_webhook(headers, body)
    if not verification.is_valid:
        logger.warning("Rejected payment callback that failed verification")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    txn = await _find_outbound_transaction(db, verification.provider_transaction_id)
    if not txn:
        logger.error("Webhook referenced unknown transaction %s", verification.provider_transaction_id)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown transaction")

    payment = await db.get(Payment, txn.payment_id)
    return await settle_payment(db, provider, payment, verification)


async def handle_mpesa_webhook(db: AsyncSession, headers: dict[str, str], body: bytes) -> dict:
    """The SIMULATOR's callback path (signed with the dev secret). Refused outright
    where mock payments aren't allowed, so it can never confirm a real payment."""
    from app.payments.mock_mpesa import MockMpesaProvider

    if not mock_payments_allowed():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return await handle_payment_callback(db, MockMpesaProvider(), headers, body)


async def reconcile_pending_payments(db: AsyncSession, *, min_age_seconds: int = 90, max_age_hours: int = 24, limit: int = 50) -> dict:
    """Settles M-Pesa payments whose callback never arrived (server down, network
    blip, Safaricom retry exhausted) by asking Safaricom directly. Payments still
    unanswered after `max_age_hours` are closed as failed so they don't hang forever.
    Does nothing unless M-Pesa is in Daraja mode."""
    if get_settings().mpesa_mode != "daraja":
        return {"skipped": "mpesa_mode is not daraja"}

    provider = get_payment_provider("mpesa")
    now = datetime.now(timezone.utc)
    pending = (
        await db.scalars(
            select(Payment)
            .where(
                Payment.status == "pending",
                Payment.method == "mpesa",
                Payment.created_at < now - timedelta(seconds=min_age_seconds),
            )
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
    ).all()

    settled = expired = still_waiting = errors = 0
    for payment in pending:
        txn = await _find_outbound_transaction_for_payment(db, payment.id)
        if not txn or not txn.provider_transaction_id or txn.provider == "mock_mpesa":
            continue
        try:
            result = await provider.confirm(txn.provider_transaction_id)
        except Exception:
            logger.exception("Reconcile: could not query M-Pesa for payment %s", payment.reference)
            errors += 1
            continue

        if result is not None and result.status is not None:
            await settle_payment(db, provider, payment, result, already_confirmed=True)
            settled += 1
        elif payment.created_at < now - timedelta(hours=max_age_hours):
            db.add(
                PaymentTransaction(
                    payment_id=payment.id, provider="mpesa", provider_transaction_id=txn.provider_transaction_id,
                    direction="inbound", status="expired", raw_payload={"reason": "no result after %d hours" % max_age_hours},
                )
            )
            payment.status = "failed"
            await db.commit()
            expired += 1
        else:
            still_waiting += 1

    return {"checked": len(pending), "settled": settled, "expired": expired, "still_waiting": still_waiting, "errors": errors}


async def _find_outbound_transaction_for_payment(db: AsyncSession, payment_id) -> PaymentTransaction | None:
    return await db.scalar(
        select(PaymentTransaction)
        .where(PaymentTransaction.payment_id == payment_id, PaymentTransaction.direction == "outbound")
        .order_by(PaymentTransaction.created_at.asc())
    )
