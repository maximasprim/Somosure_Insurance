"""Bidii Credit IPF extras: early settlement, post-dated cheques, linked/unlinked +
vehicle tracker, the original logbook, and loan officers with their commission.

Everything here is additive - it reads the existing financing tables and writes only
to the new ones (see models/ipf.py) and to the new columns on the application. The
arithmetic lives in ipf_math.py. Nothing in this file decides whether a financing
request is approved: that stays in financing_service.py.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.financing import (
    FinancingAgreement,
    FinancingApplication,
    FinancingEvent,
    FinancingInstallment,
)
from app.models.ipf import FinancingCheque, FinancingSettlement, LoanOfficer, LoanOfficerCommission
from app.models.policy import Policy
from app.services import ipf_math
from app.services.financing_service import get_financing_settings

logger = logging.getLogger("somosure.ipf")

COMMISSION_TRANSITIONS: dict[str, set[str]] = {
    "awaiting_basis": {"cancelled"},
    "pending": {"approved", "cancelled"},
    "approved": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


def _uid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def _application(db: AsyncSession, application_id: Any) -> FinancingApplication:
    application = await db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Financing application not found")
    return application


def _event(db: AsyncSession, application: FinancingApplication, event_type: str, notes: str, actor: Any = None) -> None:
    db.add(
        FinancingEvent(
            financing_application_id=application.id, event_type=event_type, notes=notes, actor_user_id=_uid(actor)
        )
    )


# --- early settlement ---------------------------------------------------------------------


async def _agreement_and_unpaid(
    db: AsyncSession, application: FinancingApplication
) -> tuple[FinancingAgreement | None, list[FinancingInstallment]]:
    agreement = await db.scalar(select(FinancingAgreement).where(FinancingAgreement.application_id == application.id))
    if not agreement:
        return None, []
    unpaid = (
        await db.scalars(
            select(FinancingInstallment)
            .where(FinancingInstallment.agreement_id == agreement.id, FinancingInstallment.status.in_(["pending", "overdue"]))
            .order_by(FinancingInstallment.installment_number)
        )
    ).all()
    return agreement, list(unpaid)


async def early_settlement_quote(db: AsyncSession, application_id: Any) -> dict:
    application = await _application(db, application_id)
    return await _settlement_quote_for(db, application)


async def _settlement_quote_for(db: AsyncSession, application: FinancingApplication) -> dict:
    settled = await db.scalar(select(FinancingSettlement).where(FinancingSettlement.financing_application_id == application.id))
    if settled:
        return {"eligible": False, "reason": "This loan has already been settled early."}
    if application.status != "approved":
        return {"eligible": False, "reason": "Only an approved financing request has a loan that can be settled."}
    agreement, unpaid = await _agreement_and_unpaid(db, application)
    if not agreement:
        return {"eligible": False, "reason": "There is no loan agreement for this request yet."}
    if agreement.status != "active":
        return {"eligible": False, "reason": f"The loan agreement is {agreement.status}, so there is nothing to settle."}
    if not unpaid:
        return {"eligible": False, "reason": "Every instalment has already been paid."}
    settings = await get_financing_settings(db)
    figures = ipf_math.settlement_figures(
        financed_amount=Decimal(str(agreement.financed_amount)),
        term_months=agreement.term_months,
        unpaid_instalments=[Decimal(str(i.amount)) for i in unpaid],
        fee_pct=Decimal(str(settings.early_settlement_fee_pct)),
    )
    return {"eligible": True, "reason": None, **figures}


async def settle_early(
    db: AsyncSession, application_id: Any, actor: Any, payment_reference: str | None, notes: str | None
) -> FinancingSettlement:
    """Record that the client cleared the loan now: the remaining instalments are waived
    (the interest still to come is dropped in return for the fee), the agreement is
    closed as completed, and the settlement is kept on record."""
    application = await _application(db, application_id)
    quote = await _settlement_quote_for(db, application)
    if not quote["eligible"]:
        raise HTTPException(status.HTTP_409_CONFLICT, quote["reason"])
    agreement, unpaid = await _agreement_and_unpaid(db, application)

    for installment in unpaid:
        installment.status = "waived"
    agreement.status = "completed"

    settlement = FinancingSettlement(
        agreement_id=agreement.id,
        financing_application_id=application.id,
        instalments_remaining=quote["instalments_remaining"],
        outstanding_principal=quote["outstanding_principal"],
        fee_pct=quote["fee_pct"],
        fee_amount=quote["fee_amount"],
        total_paid=quote["total_due"],
        would_have_paid=quote["would_have_paid"],
        payment_reference=(payment_reference or None),
        notes=(notes or None),
        settled_by=str(actor) if actor else None,
    )
    db.add(settlement)
    _event(
        db,
        application,
        "early_settlement",
        f"Loan cleared early: KES {quote['total_due']:,} paid for {quote['instalments_remaining']} remaining instalment(s) "
        f"(principal {quote['outstanding_principal']:,} + {quote['fee_pct']}% fee {quote['fee_amount']:,}); "
        f"the other KES {quote['saving']:,} of future interest and fees was waived.",
        actor,
    )
    await db.commit()
    await db.refresh(settlement)
    return settlement


# --- post-dated cheques -------------------------------------------------------------------


async def list_cheques(db: AsyncSession, application_id: Any) -> list[FinancingCheque]:
    return list(
        (
            await db.scalars(
                select(FinancingCheque)
                .where(FinancingCheque.financing_application_id == application_id)
                .order_by(FinancingCheque.cheque_date, FinancingCheque.received_at)
            )
        ).all()
    )


async def add_cheque(db: AsyncSession, application_id: Any, payload: Any, actor: Any) -> FinancingCheque:
    application = await _application(db, application_id)
    clash = await db.scalar(
        select(FinancingCheque.id).where(
            FinancingCheque.financing_application_id == application.id,
            FinancingCheque.cheque_number == payload.cheque_number.strip(),
            FinancingCheque.bank_name == payload.bank_name.strip(),
        )
    )
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, "That cheque has already been recorded for this request")
    cheque = FinancingCheque(
        financing_application_id=application.id,
        cheque_number=payload.cheque_number.strip(),
        bank_name=payload.bank_name.strip(),
        amount=payload.amount,
        cheque_date=payload.cheque_date,
        notes=payload.notes,
    )
    db.add(cheque)
    _event(db, application, "cheque_received", f"Post-dated cheque {cheque.cheque_number} ({cheque.bank_name}) for KES {payload.amount:,} dated {payload.cheque_date}", actor)
    await db.commit()
    await db.refresh(cheque)
    return cheque


async def _cheque(db: AsyncSession, application_id: Any, cheque_id: Any) -> FinancingCheque:
    cheque = await db.get(FinancingCheque, cheque_id)
    if not cheque or str(cheque.financing_application_id) != str(application_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cheque not found")
    return cheque


async def update_cheque(db: AsyncSession, application_id: Any, cheque_id: Any, payload: Any, actor: Any) -> FinancingCheque:
    application = await _application(db, application_id)
    cheque = await _cheque(db, application_id, cheque_id)
    changed = []
    if payload.status is not None and payload.status != cheque.status:
        changed.append(f"{cheque.status} -> {payload.status}")
        cheque.status = payload.status
    if payload.notes is not None:
        cheque.notes = payload.notes or None
    if changed:
        _event(db, application, "cheque_updated", f"Cheque {cheque.cheque_number}: {', '.join(changed)}", actor)
    await db.commit()
    await db.refresh(cheque)
    return cheque


async def delete_cheque(db: AsyncSession, application_id: Any, cheque_id: Any, actor: Any) -> None:
    application = await _application(db, application_id)
    cheque = await _cheque(db, application_id, cheque_id)
    _event(db, application, "cheque_removed", f"Cheque {cheque.cheque_number} ({cheque.bank_name}) removed from the record", actor)
    await db.delete(cheque)
    await db.commit()


# --- linked/unlinked, tracker, original logbook ----------------------------------------------


async def set_ipf_type(db: AsyncSession, application_id: Any, ipf_type: str, actor: Any) -> FinancingApplication:
    application = await _application(db, application_id)
    if application.ipf_type != ipf_type:
        _event(db, application, "ipf_type_changed", f"IPF type changed from {application.ipf_type} to {ipf_type}", actor)
        application.ipf_type = ipf_type
        await db.commit()
        await db.refresh(application)
    return application


async def record_tracker(
    db: AsyncSession, application_id: Any, installed: bool, provider: str | None, device_id: str | None, actor: Any
) -> FinancingApplication:
    application = await _application(db, application_id)
    if installed:
        if not (provider and provider.strip()) or not (device_id and device_id.strip()):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter the tracker company and the device ID")
        application.tracker_provider = provider.strip()
        application.tracker_device_id = device_id.strip()
        application.tracker_installed_at = datetime.now(timezone.utc)
        _event(db, application, "tracker_installed", f"Vehicle tracker confirmed: {provider.strip()}, device {device_id.strip()}", actor)
    else:
        application.tracker_provider = None
        application.tracker_device_id = None
        application.tracker_installed_at = None
        _event(db, application, "tracker_cleared", "Vehicle tracker details cleared", actor)
    await db.commit()
    await db.refresh(application)
    return application


async def record_original_logbook(db: AsyncSession, application_id: Any, received: bool, actor: Any) -> FinancingApplication:
    application = await _application(db, application_id)
    application.original_logbook_received_at = datetime.now(timezone.utc) if received else None
    _event(
        db, application, "original_logbook", "Original logbook received and held" if received else "Original logbook marked as not received", actor
    )
    await db.commit()
    await db.refresh(application)
    return application


# --- loan officers ------------------------------------------------------------------------------


async def find_active_officer_by_code(db: AsyncSession, code: str) -> LoanOfficer | None:
    code = (code or "").strip()
    if not code:
        return None
    return await db.scalar(
        select(LoanOfficer).where(func.lower(LoanOfficer.staff_number) == code.lower(), LoanOfficer.is_active.is_(True))
    )


async def create_officer(db: AsyncSession, payload: Any) -> LoanOfficer:
    taken = await db.scalar(select(LoanOfficer.id).where(func.lower(LoanOfficer.staff_number) == payload.staff_number.strip().lower()))
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "A loan officer with that staff number already exists")
    officer = LoanOfficer(
        full_name=payload.full_name.strip(),
        staff_number=payload.staff_number.strip(),
        email=payload.email,
        phone=payload.phone,
        monthly_target=payload.monthly_target,
    )
    db.add(officer)
    await db.commit()
    await db.refresh(officer)
    return officer


async def update_officer(db: AsyncSession, officer_id: Any, payload: Any) -> LoanOfficer:
    officer = await db.get(LoanOfficer, officer_id)
    if not officer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan officer not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "is_active" and value is None:
            continue
        setattr(officer, field, value)
    await db.commit()
    await db.refresh(officer)
    return officer


async def assign_loan_officer(db: AsyncSession, application_id: Any, officer_id: Any, actor: Any) -> FinancingApplication:
    application = await _application(db, application_id)
    if officer_id is None:
        if application.loan_officer_id is not None:
            existing = await db.scalar(
                select(LoanOfficerCommission).where(LoanOfficerCommission.financing_application_id == application.id)
            )
            if existing and existing.status in ("approved", "paid"):
                raise HTTPException(status.HTTP_409_CONFLICT, "This officer's commission is already approved or paid, so they can't be removed")
            if existing:
                existing.status = "cancelled"
            application.loan_officer_id = None
            _event(db, application, "loan_officer_removed", "Loan officer removed from this request", actor)
        await db.commit()
        await db.refresh(application)
        return application

    officer = await db.get(LoanOfficer, officer_id)
    if not officer or not officer.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan officer not found or no longer active")
    existing = await db.scalar(
        select(LoanOfficerCommission).where(LoanOfficerCommission.financing_application_id == application.id)
    )
    if existing and existing.loan_officer_id != officer.id and existing.status in ("approved", "paid"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Commission for the current officer is already approved or paid, so the officer can't be changed")
    application.loan_officer_id = officer.id
    if existing and existing.status != "paid":
        existing.loan_officer_id = officer.id  # still unpaid: the earnings move with the sale
        if existing.status == "cancelled":  # an officer put back after being removed
            existing.status = "pending" if existing.somosure_net_commission is not None else "awaiting_basis"
    _event(db, application, "loan_officer_assigned", f"Credited to loan officer {officer.full_name} ({officer.staff_number})", actor)
    await db.flush()
    await ensure_commission_for_application(db, application)
    await db.commit()
    await db.refresh(application)
    return application


async def _financed_policy(db: AsyncSession, application: FinancingApplication) -> Policy | None:
    """The policy this financing paid for: issued from the insurance application on
    the same quote, for the same customer."""
    return await db.scalar(
        select(Policy)
        .join(Application, Application.id == Policy.application_id)
        .where(Application.quote_id == application.quote_id, Application.customer_id == application.customer_id)
        .order_by(Policy.created_at.desc())
        .limit(1)
    )


async def ensure_commission_for_application(db: AsyncSession, application: FinancingApplication) -> LoanOfficerCommission | None:
    """Creates (once) the loan officer's commission row for a financed policy. Does
    nothing until there is an approved financing request, an officer on it and an
    issued policy. Adds and flushes only - the caller commits."""
    if not application.loan_officer_id or application.status != "approved":
        return None
    existing = await db.scalar(
        select(LoanOfficerCommission).where(LoanOfficerCommission.financing_application_id == application.id)
    )
    if existing:
        return existing
    policy = await _financed_policy(db, application)
    if not policy:
        return None
    settings = await get_financing_settings(db)
    basis = ipf_math.commission_basis(
        policy_commission=policy.commission, premium=policy.premium, pct_of_premium=settings.somosure_commission_pct_of_premium
    )
    rate = Decimal(str(settings.loan_officer_commission_pct))
    row = LoanOfficerCommission(
        loan_officer_id=application.loan_officer_id,
        financing_application_id=application.id,
        policy_id=policy.id,
        somosure_net_commission=basis,
        rate_pct=rate,
        commission_amount=ipf_math.officer_commission(basis, rate) if basis is not None else None,
        status="pending" if basis is not None else "awaiting_basis",
    )
    db.add(row)
    await db.flush()
    _event(
        db,
        application,
        "officer_commission_created",
        f"Loan officer commission opened at {rate}% of Somosure's net commission on policy {policy.policy_number}"
        + ("" if basis is not None else " - waiting for the net commission to be entered"),
    )
    return row


async def record_loan_officer_commission_for_policy(db: AsyncSession, policy_id: Any) -> None:
    """Called after a policy is issued (best effort - see policy_service)."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        return
    rows = (
        await db.scalars(
            select(FinancingApplication)
            .join(Application, (Application.quote_id == FinancingApplication.quote_id) & (Application.customer_id == FinancingApplication.customer_id))
            .where(Application.id == policy.application_id, FinancingApplication.loan_officer_id.is_not(None), FinancingApplication.status == "approved")
        )
    ).all()
    for application in rows:
        await ensure_commission_for_application(db, application)
    await db.commit()


async def set_commission_basis(db: AsyncSession, commission_id: Any, net_commission: Decimal) -> LoanOfficerCommission:
    row = await db.get(LoanOfficerCommission, commission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commission not found")
    if row.status not in ("awaiting_basis", "pending"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This commission is already {row.status}, so its basis can't be changed")
    row.somosure_net_commission = ipf_math.money(net_commission)
    row.commission_amount = ipf_math.officer_commission(net_commission, row.rate_pct)
    row.status = "pending"
    await db.commit()
    await db.refresh(row)
    return row


async def transition_commission(
    db: AsyncSession, commission_id: Any, to_status: str, payout_reference: str | None, actor: Any
) -> LoanOfficerCommission:
    row = await db.get(LoanOfficerCommission, commission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commission not found")
    allowed = COMMISSION_TRANSITIONS.get(row.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Cannot move a {row.status} commission to {to_status} - allowed: {sorted(allowed) or 'none'}"
        )
    now = datetime.now(timezone.utc)
    row.status = to_status
    if to_status == "approved":
        row.approved_at = now
    elif to_status == "paid":
        row.paid_at = now
        row.paid_by = str(actor) if actor else None
        row.payout_reference = payout_reference or None
    await db.commit()
    await db.refresh(row)
    return row


async def commission_view(db: AsyncSession, commission_id: Any) -> dict:
    rows = await list_commissions(db, commission_id=commission_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commission not found")
    return rows[0]


async def list_commissions(
    db: AsyncSession, officer_id: Any = None, status_filter: str | None = None, commission_id: Any = None
) -> list[dict]:
    stmt = (
        select(LoanOfficerCommission, LoanOfficer.full_name, FinancingApplication.reference, Policy.policy_number)
        .join(LoanOfficer, LoanOfficer.id == LoanOfficerCommission.loan_officer_id)
        .join(FinancingApplication, FinancingApplication.id == LoanOfficerCommission.financing_application_id)
        .outerjoin(Policy, Policy.id == LoanOfficerCommission.policy_id)
        .order_by(LoanOfficerCommission.created_at.desc())
    )
    if officer_id is not None:
        stmt = stmt.where(LoanOfficerCommission.loan_officer_id == officer_id)
    if status_filter:
        stmt = stmt.where(LoanOfficerCommission.status == status_filter)
    if commission_id is not None:
        stmt = stmt.where(LoanOfficerCommission.id == commission_id)
    out = []
    for row, officer_name, reference, policy_number in (await db.execute(stmt)).all():
        out.append(_commission_dict(row, officer_name, reference, policy_number))
    return out


def _commission_dict(row: LoanOfficerCommission, officer_name: str | None, reference: str | None, policy_number: str | None) -> dict:
    return {
        "id": row.id,
        "loan_officer_id": row.loan_officer_id,
        "loan_officer_name": officer_name,
        "financing_application_id": row.financing_application_id,
        "financing_reference": reference,
        "policy_id": row.policy_id,
        "policy_number": policy_number,
        "somosure_net_commission": row.somosure_net_commission,
        "rate_pct": row.rate_pct,
        "commission_amount": row.commission_amount,
        "status": row.status,
        "approved_at": row.approved_at,
        "paid_at": row.paid_at,
        "payout_reference": row.payout_reference,
        "created_at": row.created_at,
    }


async def officers_with_results(db: AsyncSession) -> list[dict]:
    """Every officer with this month's financed total against their target, and what
    they have earned by status."""
    officers = (await db.scalars(select(LoanOfficer).order_by(LoanOfficer.full_name))).all()
    start, nxt = ipf_math.month_window(date.today())
    month_rows = (
        await db.execute(
            select(
                FinancingApplication.loan_officer_id,
                func.count(FinancingApplication.id),
                func.coalesce(func.sum(FinancingApplication.financed_amount), 0),
            )
            .where(
                FinancingApplication.loan_officer_id.is_not(None),
                FinancingApplication.status == "approved",
                FinancingApplication.created_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                FinancingApplication.created_at < datetime.combine(nxt, datetime.min.time(), tzinfo=timezone.utc),
            )
            .group_by(FinancingApplication.loan_officer_id)
        )
    ).all()
    month = {r[0]: (int(r[1]), Decimal(str(r[2]))) for r in month_rows}
    earned_rows = (
        await db.execute(
            select(
                LoanOfficerCommission.loan_officer_id,
                LoanOfficerCommission.status,
                func.coalesce(func.sum(LoanOfficerCommission.commission_amount), 0),
            )
            .where(LoanOfficerCommission.status.in_(["pending", "approved", "paid"]))
            .group_by(LoanOfficerCommission.loan_officer_id, LoanOfficerCommission.status)
        )
    ).all()
    earned: dict[Any, dict[str, Decimal]] = {}
    for officer_id, st, amount in earned_rows:
        earned.setdefault(officer_id, {})[st] = Decimal(str(amount))

    out = []
    for officer in officers:
        count, financed = month.get(officer.id, (0, Decimal("0")))
        mine = earned.get(officer.id, {})
        out.append(
            {
                "id": officer.id,
                "full_name": officer.full_name,
                "staff_number": officer.staff_number,
                "email": officer.email,
                "phone": officer.phone,
                "monthly_target": officer.monthly_target,
                "is_active": officer.is_active,
                "financed_this_month": financed,
                "requests_this_month": count,
                "target_progress_pct": ipf_math.target_progress(financed, officer.monthly_target),
                "commission_pending": mine.get("pending", Decimal("0")),
                "commission_approved": mine.get("approved", Decimal("0")),
                "commission_paid": mine.get("paid", Decimal("0")),
            }
        )
    return out


# --- the per-application panel ------------------------------------------------------------------------


async def get_ipf_detail(db: AsyncSession, application_id: Any) -> dict:
    application = await _application(db, application_id)
    officer = await db.get(LoanOfficer, application.loan_officer_id) if application.loan_officer_id else None
    commission_row = await db.scalar(
        select(LoanOfficerCommission).where(LoanOfficerCommission.financing_application_id == application.id)
    )
    commission = None
    if commission_row:
        policy_number = await db.scalar(select(Policy.policy_number).where(Policy.id == commission_row.policy_id)) if commission_row.policy_id else None
        commission = _commission_dict(commission_row, officer.full_name if officer else None, application.reference, policy_number)

    cheques = await list_cheques(db, application.id)
    settlement = await db.scalar(select(FinancingSettlement).where(FinancingSettlement.financing_application_id == application.id))
    quote = await _settlement_quote_for(db, application) if application.status == "approved" else None

    return {
        "ipf_type": application.ipf_type,
        "loan_officer": officer,
        "commission": commission,
        "tracker": {
            "required": ipf_math.tracker_required(application.ipf_type),
            "installed": application.tracker_installed_at is not None,
            "provider": application.tracker_provider,
            "device_id": application.tracker_device_id,
            "installed_at": application.tracker_installed_at,
        },
        "original_logbook_received_at": application.original_logbook_received_at,
        "cheques_required": ipf_math.cheques_required(application.ipf_type, application.term_months),
        "cheques_received": len(cheques),
        "cheques": cheques,
        "early_settlement": quote,
        "settlement": settlement,
    }
