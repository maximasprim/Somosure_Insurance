"""Recording a sale directly in the system, the way a row is added to the weekly sheet.

The sale is written to the ledger (so it has staff, branch, commission, the month it sits in, and appears in the
cleaned workbook the system exports) and posted straight away into the system's own records (customer, quote,
application, policy, payment) by the same engine that posts imported rows. If the same sale is later typed in the
sheet, the import recognises it and merges it into this one.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from decimal import Decimal
from hashlib import sha1
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.models.customer import Customer
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.sales_ledger import LegacyClaim, SalesEntry, UnderwriterLink
from app.services.sales_import import manual_rules, posting
from app.services.sales_import.cleaners import KNOWN_UNDERWRITERS
from app.services.sales_import.matching import canonical_underwriter, phone_key

logger = logging.getLogger("somosure.sales_import")

PRODUCT_HINTS = ["PI", "WIBA", "MEDICAL", "BID BOND", "CREDIT LIFE", "PERSONAL ACCIDENT", "LIFE", "TRAVEL", "PROPERTY"]


async def _known_underwriters(db: AsyncSession) -> set[str]:
    return set(KNOWN_UNDERWRITERS) | {u for (u,) in (await db.execute(select(SalesEntry.underwriter).where(SalesEntry.underwriter.is_not(None)).distinct())).all()}


async def options(db: AsyncSession) -> dict[str, Any]:
    """Everything the form offers: providers (with the insurer's usual commission rate), staff, branches."""
    providers = (await db.execute(select(InsuranceProvider.id, InsuranceProvider.name, InsuranceProvider.status).order_by(InsuranceProvider.name))).all()
    reverse = {l.provider_id: l.underwriter for l in (await db.scalars(select(UnderwriterLink))).all() if l.provider_id}
    known = await _known_underwriters(db)

    rates: dict[str, list[Decimal]] = defaultdict(list)
    for underwriter, rate in (await db.execute(
        select(SalesEntry.underwriter, SalesEntry.commission_rate).where(SalesEntry.status == "active", SalesEntry.commission_rate > 0, SalesEntry.underwriter.is_not(None))
    )).all():
        rates[underwriter].append(Decimal(rate).quantize(Decimal("0.005")))
    typical = {u: Counter(v).most_common(1)[0][0] for u, v in rates.items() if len(v) >= 3}

    items = []
    for pid, name, status in providers:
        underwriter = reverse.get(pid) or canonical_underwriter(name, known)
        items.append({"id": pid, "name": name, "status": status, "underwriter": underwriter, "typical_commission_rate": typical.get(underwriter)})

    async def distinct(column):
        return [v for (v,) in (await db.execute(select(column).where(column.is_not(None)).distinct().order_by(column))).all()]

    return {
        "providers": items, "staff": await distinct(SalesEntry.staff_name), "branches": await distinct(SalesEntry.branch),
        "product_hints": PRODUCT_HINTS, "wht_rate": str(manual_rules.WHT_RATE),
    }


async def record_sale(db: AsyncSession, p: dict[str, Any], user_id: str | None) -> dict[str, Any]:
    # --- which insurer -------------------------------------------------------------------------
    provider: InsuranceProvider | None = None
    if p.get("provider_id"):
        provider = await db.get(InsuranceProvider, p["provider_id"])
        if provider is None:
            raise ValueError("That insurer no longer exists.")
    elif (p.get("new_underwriter") or "").strip():
        provider = InsuranceProvider(
            id=uuid.uuid4(), name=p["new_underwriter"].strip().title()[:150], provider_type="insurer", integration_mode="manual", status="inactive",
        )
        db.add(provider)
        await db.flush()
    else:
        raise ValueError("Choose the insurer, or add a new one.")

    known = await _known_underwriters(db)
    link = await db.scalar(select(UnderwriterLink).where(UnderwriterLink.provider_id == provider.id))
    underwriter = link.underwriter if link else canonical_underwriter(provider.name, known)
    if link is None:
        other = await db.scalar(select(UnderwriterLink).where(UnderwriterLink.underwriter == underwriter))
        if other and other.provider_id and other.provider_id != provider.id:
            raise ValueError(f"{underwriter} is already linked to a different provider (Post to system tab); choose that one.")
        if other:
            other.provider_id, other.source = provider.id, "admin"
        else:
            db.add(UnderwriterLink(id=uuid.uuid4(), underwriter=underwriter, provider_id=provider.id, source="admin"))
        await db.flush()

    built = manual_rules.build_manual_entry(p, underwriter=underwriter, underwriter_name=provider.name)
    if built.errors:
        raise ValueError(" ".join(built.errors))
    entry = built.entry

    # --- accidental double entry ---------------------------------------------------------------
    if not p.get("confirm_duplicate"):
        duplicates: list[dict[str, Any]] = []
        if entry["policy_number"]:
            for pid, number, premium in (await db.execute(
                select(Policy.id, Policy.policy_number, Policy.premium).where(func.upper(Policy.policy_number) == entry["policy_number"].upper()).limit(3)
            )).all():
                duplicates.append({"where": "Policies", "what": f"Policy number {number} (KES {premium:,.0f}) is already in the system"})
        for row in (await db.execute(
            select(SalesEntry.client_name, SalesEntry.policy_number, SalesEntry.premium, SalesEntry.sheet_name)
            .where((SalesEntry.natural_key == entry["natural_key"]) | (SalesEntry.fallback_key == entry["fallback_key"])).limit(3)
        )).all():
            duplicates.append({"where": row.sheet_name, "what": f"{row.client_name} - {row.policy_number or 'no policy number'} - KES {row.premium:,.0f} looks like the same sale"})
        if duplicates:
            await db.rollback()
            return {"created": False, "duplicates": duplicates}

    if p.get("confirm_duplicate") and await db.scalar(select(func.count()).select_from(SalesEntry).where(SalesEntry.natural_key == entry["natural_key"])):
        # Confirmed as a genuinely separate sale with the same key: it gets its own, so it cannot collide (it will not merge
        # with a sheet row later - which is right for something that is not the same sale).
        entry["natural_key"] = sha1(f"{entry['natural_key']}|{entry['fallback_key']}|{uuid.uuid4()}".encode()).hexdigest()

    # --- the customer --------------------------------------------------------------------------
    customer_id = p.get("customer_id")
    if customer_id and await db.get(Customer, customer_id) is None:
        raise ValueError("That customer no longer exists.")
    if not customer_id and entry["phone"]:
        wanted = phone_key(entry["phone"])
        matches = [cid for cid, phone in (await db.execute(select(Customer.id, Customer.phone))).all() if phone_key(phone) == wanted]
        if len(matches) == 1:
            customer_id = matches[0]
    existing_customer = customer_id is not None

    row = SalesEntry(
        id=uuid.uuid4(), **entry, provider_id=provider.id, customer_id=customer_id,
        entered_by=uuid.UUID(user_id) if user_id else None, first_batch_id=None, last_batch_id=None,
    )
    db.add(row)
    await db.flush()

    result = await posting.post_ready(db, dry_run=False, commit=False, only_ids=[row.id], link_first=False)
    if not result.get("posted"):
        await db.rollback()
        raise ValueError("The sale could not be posted into the system; nothing was saved.")
    await db.refresh(row)
    policy_number = await db.scalar(select(Policy.policy_number).where(Policy.id == row.policy_id))
    record_event(
        "sales_import.record_sale", entity_type="sales_entry", entity_id=row.id, entity_label=row.client_name,
        summary=f"Recorded a sale for {row.client_name} ({underwriter}, KES {row.premium:,.0f})", policy_number=policy_number,
    )
    flags = list(row.post_flags or [])
    out = {
        "created": True, "entry_id": str(row.id), "policy_id": str(row.policy_id), "policy_number": policy_number,
        "customer_id": str(row.customer_id), "customer_existed": existing_customer, "flags": flags,
    }
    await db.commit()
    return out


async def recent(db: AsyncSession, limit: int = 15) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(SalesEntry.id, SalesEntry.client_name, SalesEntry.underwriter, SalesEntry.policy_number, SalesEntry.premium, SalesEntry.date_paid,
               SalesEntry.staff_name, SalesEntry.branch, SalesEntry.policy_id, SalesEntry.customer_id, SalesEntry.post_flags, SalesEntry.created_at)
        .where(SalesEntry.origin == "manual").order_by(SalesEntry.created_at.desc()).limit(limit)
    )).mappings().all()
    return [dict(r) for r in rows]


async def void_sale(db: AsyncSession, entry_id: uuid.UUID) -> dict[str, Any]:
    """Takes back a sale recorded in error: removes its posted records and the ledger row. Only sales entered in the
    system; a workbook row is corrected in the sheet. Refused if staff have added activity to the policy."""
    entry = await db.get(SalesEntry, entry_id)
    if entry is None or entry.origin != "manual":
        raise LookupError("Only a sale recorded in the system can be voided here. A workbook row is corrected in the sheet.")
    name, customer_id = entry.client_name, entry.customer_id
    ref = SimpleNamespace(id=entry.id, policy_id=entry.policy_id, payment_id=entry.payment_id, application_id=entry.application_id,
                          quote_id=entry.quote_id, quote_request_id=entry.quote_request_id)
    posted = entry.posted_at is not None
    db.expunge(entry)
    if posted and await posting._unpost_chunk(db, [ref]) is None:
        raise ValueError("This policy has activity added in the app (a claim, renewal or payment), so it cannot be voided automatically.")
    await db.execute(update(LegacyClaim).where(LegacyClaim.sales_entry_id == entry_id).values(sales_entry_id=None))
    await db.execute(delete(SalesEntry).where(SalesEntry.id == entry_id))
    removed_customer = False
    if customer_id and not await db.scalar(select(func.count()).select_from(SalesEntry).where(SalesEntry.customer_id == customer_id)):
        customer = await db.get(Customer, customer_id)
        if customer is not None and customer.lead_source == "workbook":
            try:
                async with db.begin_nested():
                    await db.delete(customer)
                removed_customer = True
            except IntegrityError:
                pass  # the customer has other records now: kept
    record_event("sales_import.void_sale", summary=f"Voided the sale recorded for {name}", client=name)
    await db.commit()
    return {"voided": True, "customer_removed": removed_customer}
