"""One view of the business across both ways data gets in: sold through the platform, or recorded in
the weekly report workbook.

Nothing here writes to policies, applications, quotes or payments, and nothing emits an automation
event. The workbook's sales stay in their own ledger (see app/models/sales_ledger.py for why); this
module lets the rest of the system READ the two together:

* `sales_page` / `sales_options`   - one list of sales, each row marked with where it came from.
* `analytics_section`              - the figures the Reports & analytics dashboard adds for "all sales".
* `renewals_page`                  - one renewals worklist (platform policies and workbook policies).
* `link_customers`                 - matches workbook clients to customers already in the system, and
                                     (only when asked) creates customers for clients that have a phone.
* `customer_history`               - a customer's workbook sales and claims, for the customer page.

Counting rule, so nothing is counted twice: a sale is counted once. A workbook row whose policy number
matches a policy in the app (`policy_id`) stands in for that policy (it carries the staff, branch and
commission the app does not have); a platform policy with no workbook row counts as itself; demo
(mock) policies are never counted.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, Numeric, String, case, cast, exists, extract, func, insert, literal, null, or_, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.audit.context import record_event
from app.models.application import Application
from app.models.asset import Vehicle
from app.models.customer import Customer
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.renewal import Renewal
from app.models.sales_ledger import ImportBatch, LegacyClaim, SalesEntry
from app.models.user import User
from app.services.analytics_buckets import pct_change
from app.services.sales_import.cleaners import KNOWN_UNDERWRITERS, clean_phone
from app.services.sales_import.matching import canonical_underwriter, names_overlap, phone_key

logger = logging.getLogger("somosure.sales_import")

FOLLOW_UP_STATUSES = ("contacted", "quoted", "renewed", "lost")
CLOSED_FOLLOW_UPS = ("renewed", "lost")
CHUNK = 400


# --------------------------------------------------------------------------------------
# small helpers (the pure matching rules live in matching.py)
# --------------------------------------------------------------------------------------


def _chunks(items: list, size: int = CHUNK):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --------------------------------------------------------------------------------------
# the combined sales query
# --------------------------------------------------------------------------------------

COLUMNS = (
    "source", "id", "sold_on", "client_name", "phone", "underwriter", "reg_no", "product", "policy_number",
    "premium", "commission", "wht", "net_revenue", "staff", "branch", "business_type", "start_date",
    "expiry_date", "status", "customer_id",
)


def _platform_select():
    agent = aliased(User)
    covered = select(SalesEntry.policy_id).where(SalesEntry.policy_id.is_not(None), SalesEntry.status == "active")
    return (
        select(
            cast(literal("platform"), String).label("source"),
            cast(Policy.id, String).label("id"),
            cast(Policy.created_at, Date).label("sold_on"),
            Customer.full_name.label("client_name"),
            Customer.phone.label("phone"),
            func.upper(InsuranceProvider.name).label("underwriter"),
            Vehicle.registration_number.label("reg_no"),
            case((Vehicle.id.is_not(None), "motor"), else_="other").label("product"),
            Policy.policy_number.label("policy_number"),
            cast(Policy.premium, Numeric(14, 2)).label("premium"),
            cast(Policy.commission, Numeric(14, 2)).label("commission"),
            cast(null(), Numeric(14, 2)).label("wht"),
            cast(null(), Numeric(14, 2)).label("net_revenue"),
            agent.full_name.label("staff"),
            cast(null(), String).label("branch"),
            cast(null(), String).label("business_type"),
            Policy.start_date.label("start_date"),
            Policy.end_date.label("expiry_date"),
            Policy.status.label("status"),
            Policy.customer_id.label("customer_id"),
        )
        .select_from(Policy)
        .join(Customer, Customer.id == Policy.customer_id)
        .join(InsuranceProvider, InsuranceProvider.id == Policy.provider_id)
        .outerjoin(Application, Application.id == Policy.application_id)
        .outerjoin(Vehicle, Vehicle.id == Application.vehicle_id)
        .outerjoin(agent, agent.id == Policy.agent_id)
        .where(Policy.is_mock.is_(False), Policy.id.notin_(covered))
    )


def _workbook_select():
    return (
        select(
            case(
                (SalesEntry.origin == "manual", "manual"),  # recorded directly in the system
                (SalesEntry.posted_at.is_not(None), "workbook"),  # posted into the system's tables: a workbook sale
                (SalesEntry.policy_id.is_not(None), "platform+workbook"),  # also sold through the platform
                else_="workbook",
            ).label("source"),
            cast(SalesEntry.id, String).label("id"),
            func.coalesce(SalesEntry.date_paid, func.make_date(SalesEntry.period_year, func.coalesce(SalesEntry.period_month, 1), 1)).label("sold_on"),
            SalesEntry.client_name.label("client_name"),
            SalesEntry.phone.label("phone"),
            SalesEntry.underwriter.label("underwriter"),
            func.coalesce(SalesEntry.reg_no, SalesEntry.asset_ref).label("reg_no"),
            SalesEntry.product_line.label("product"),
            SalesEntry.policy_number.label("policy_number"),
            SalesEntry.premium.label("premium"),
            SalesEntry.commission.label("commission"),
            SalesEntry.wht.label("wht"),
            SalesEntry.net_revenue.label("net_revenue"),
            SalesEntry.staff_name.label("staff"),
            SalesEntry.branch.label("branch"),
            SalesEntry.business_type.label("business_type"),
            SalesEntry.start_date.label("start_date"),
            SalesEntry.expiry_date.label("expiry_date"),
            SalesEntry.status.label("status"),
            SalesEntry.customer_id.label("customer_id"),
        )
        .where(SalesEntry.status == "active")
    )


def _sales_union():
    return union_all(_platform_select(), _workbook_select()).subquery("all_sales")


def _sales_conditions(u, *, source=None, year=None, month=None, underwriter=None, staff=None, branch=None, product=None,
                      business_type=None, q=None, start: date | None = None, end: date | None = None):
    conditions = []
    if source == "platform":
        conditions.append(u.c.source == "platform")
    elif source == "workbook":
        conditions.append(u.c.source.in_(("workbook", "platform+workbook")))
    elif source == "manual":
        conditions.append(u.c.source == "manual")
    if year:
        conditions.append(extract("year", u.c.sold_on) == year)
    if month:
        conditions.append(extract("month", u.c.sold_on) == month)
    if start:
        conditions.append(u.c.sold_on >= start)
    if end:
        conditions.append(u.c.sold_on <= end)
    if underwriter:
        conditions.append(u.c.underwriter == underwriter)
    if staff:
        conditions.append(u.c.staff == staff)
    if branch:
        conditions.append(u.c.branch == branch)
    if product:
        conditions.append(u.c.product == product)
    if business_type:
        conditions.append(u.c.business_type == business_type)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(u.c.client_name.ilike(like), u.c.policy_number.ilike(like), u.c.reg_no.ilike(like), u.c.phone.ilike(like)))
    return conditions


async def sales_page(db: AsyncSession, *, limit: int = 50, offset: int = 0, **filters) -> dict[str, Any]:
    u = _sales_union()
    where = _sales_conditions(u, **filters)
    totals = (await db.execute(
        select(func.count(), func.coalesce(func.sum(u.c.premium), 0), func.coalesce(func.sum(u.c.commission), 0)).select_from(u).where(*where)
    )).one()
    rows = (await db.execute(
        select(*[u.c[c] for c in COLUMNS]).where(*where).order_by(u.c.sold_on.desc().nulls_last(), u.c.client_name).limit(limit).offset(offset)
    )).mappings().all()
    return {"total": totals[0], "premium": totals[1], "commission": totals[2], "items": [dict(r) for r in rows]}


async def sales_options(db: AsyncSession) -> dict[str, list]:
    u = _sales_union()

    async def distinct(column):
        return [v for (v,) in (await db.execute(select(column).where(column.is_not(None)).distinct().order_by(column))).all()]

    year_expr = extract("year", u.c.sold_on)
    years = [int(y) for (y,) in (await db.execute(select(year_expr).where(u.c.sold_on.is_not(None)).distinct().order_by(year_expr.desc()))).all()]
    return {
        "years": years, "underwriters": await distinct(u.c.underwriter), "staff": await distinct(u.c.staff),
        "branches": await distinct(u.c.branch), "products": await distinct(u.c.product),
    }


# --------------------------------------------------------------------------------------
# reports: the "all sales" section of the analytics dashboard
# --------------------------------------------------------------------------------------


async def _window(db: AsyncSession, u, start: date, end: date) -> dict[str, float]:
    row = (await db.execute(
        select(
            func.count(), func.coalesce(func.sum(u.c.premium), 0), func.coalesce(func.sum(u.c.commission), 0), func.coalesce(func.sum(u.c.net_revenue), 0),
        ).select_from(u).where(u.c.sold_on >= start, u.c.sold_on <= end)
    )).one()
    return {"sales": float(row[0]), "premium": float(row[1]), "commission": float(row[2]), "net_revenue": float(row[3])}


def _kpi(current: float, previous: float) -> dict[str, Any]:
    return {"value": current, "previous": previous, "change_pct": pct_change(current, previous)}


async def _breakdown(db: AsyncSession, u, column, start: date, end: date, known: set[str] | None = None) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(column, func.count(), func.coalesce(func.sum(u.c.premium), 0)).where(u.c.sold_on >= start, u.c.sold_on <= end).group_by(column)
    )).all()
    merged: dict[str, dict[str, float]] = {}
    for name, count, amount in rows:
        key = canonical_underwriter(name, known) if known is not None else (name or "Not stated")
        slot = merged.setdefault(key, {"count": 0, "amount": 0.0})
        slot["count"] += count
        slot["amount"] += float(amount)
    return sorted(({"name": k, "count": int(v["count"]), "amount": v["amount"]} for k, v in merged.items()), key=lambda r: r["amount"], reverse=True)


async def analytics_section(db: AsyncSession, start: datetime, now: datetime, previous_start: datetime) -> dict[str, Any]:
    """Added to the analytics dashboard's response as `workbook`. Read-only."""
    u = _sales_union()
    s, e, ps = start.date(), now.date(), previous_start.date()
    current = await _window(db, u, s, e)
    previous = await _window(db, u, ps, s - timedelta(days=1))
    kpis = {name: _kpi(current[name], previous[name]) for name in current}

    known = set(KNOWN_UNDERWRITERS) | {v for (v,) in (await db.execute(select(SalesEntry.underwriter).where(SalesEntry.underwriter.is_not(None)).distinct())).all()}
    month = func.date_trunc("month", u.c.sold_on)
    monthly = [
        {"date": m.date().isoformat() if hasattr(m, "date") else str(m), "sales": int(n), "premium": float(p), "commission": float(c)}
        for m, n, p, c in (await db.execute(
            select(month, func.count(), func.coalesce(func.sum(u.c.premium), 0), func.coalesce(func.sum(u.c.commission), 0))
            .where(u.c.sold_on >= s, u.c.sold_on <= e).group_by(month).order_by(month)
        )).all()
    ]
    source_label = case((u.c.source == "platform", "Platform"), (u.c.source == "manual", "Entered in system"), else_="Workbook")
    source_rows = (await db.execute(
        select(source_label, func.count(), func.coalesce(func.sum(u.c.premium), 0)).where(u.c.sold_on >= s, u.c.sold_on <= e).group_by(source_label)
    )).all()

    claims = (await db.execute(
        select(LegacyClaim.outcome, func.count()).where(LegacyClaim.status == "active", LegacyClaim.date_reported >= s, LegacyClaim.date_reported <= e)
        .group_by(LegacyClaim.outcome)
    )).all()

    today = date.today()
    renewal_base = (SalesEntry.status == "active", or_(SalesEntry.policy_id.is_(None), SalesEntry.posted_at.is_not(None)), SalesEntry.follow_up_status.is_(None) | SalesEntry.follow_up_status.notin_(CLOSED_FOLLOW_UPS))
    due_60 = await db.scalar(select(func.count()).where(*renewal_base, SalesEntry.expiry_date >= today, SalesEntry.expiry_date <= today + timedelta(days=60), ~_renewed_exists())) or 0
    overdue = await db.scalar(select(func.count()).where(*renewal_base, SalesEntry.expiry_date < today, SalesEntry.expiry_date >= today - timedelta(days=30), ~_renewed_exists())) or 0
    clients_total = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(SalesEntry.status == "active")) or 0
    clients_linked = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(SalesEntry.status == "active", SalesEntry.customer_id.is_not(None))) or 0
    last_import = await db.scalar(select(func.max(ImportBatch.created_at)))
    span = (await db.execute(select(func.min(SalesEntry.date_paid), func.max(SalesEntry.date_paid)).where(SalesEntry.status == "active"))).one()

    return {
        "kpis": kpis,
        "sources": [{"name": n, "count": int(c), "amount": float(a)} for n, c, a in source_rows],
        "monthly": monthly,
        "by_underwriter": await _breakdown(db, u, u.c.underwriter, s, e, known),
        "by_branch": await _breakdown(db, u, u.c.branch, s, e),
        "by_staff": await _breakdown(db, u, u.c.staff, s, e),
        "by_business_type": await _breakdown(db, u, u.c.business_type, s, e),
        "by_product": await _breakdown(db, u, u.c.product, s, e),
        "claims": [{"name": n, "count": int(c)} for n, c in claims],
        "renewals": {"due_60d": int(due_60), "overdue_30d": int(overdue)},
        "customers": {"workbook_clients": int(clients_total), "linked_to_customers": int(clients_linked)},
        "coverage": {
            "workbook_from": span[0].isoformat() if span[0] else None, "workbook_to": span[1].isoformat() if span[1] else None,
            "last_import": last_import.isoformat() if last_import else None,
        },
    }


# --------------------------------------------------------------------------------------
# renewals worklist
# --------------------------------------------------------------------------------------


def _renewed_exists():
    """True when the same plate has a later workbook policy that starts at or about this one's expiry."""
    later = aliased(SalesEntry)
    return exists().where(
        later.reg_no == SalesEntry.reg_no, later.reg_no.is_not(None), later.id != SalesEntry.id, later.status == "active",
        later.start_date >= SalesEntry.expiry_date - timedelta(days=30),
    )


def _renewal_platform_select(first: date, last: date):
    return (
        select(
            cast(literal("platform"), String).label("source"),
            cast(Policy.id, String).label("id"),
            Policy.end_date.label("expiry_date"),
            Customer.full_name.label("client_name"),
            Customer.phone.label("phone"),
            Policy.customer_id.label("customer_id"),
            func.upper(InsuranceProvider.name).label("underwriter"),
            Vehicle.registration_number.label("reg_no"),
            cast(Policy.premium, Numeric(14, 2)).label("premium"),
            cast(null(), String).label("staff"),
            cast(null(), String).label("branch"),
            func.coalesce(Renewal.status, "due").label("status"),
            cast(null(), String).label("note"),
            Policy.policy_number.label("policy_number"),
        )
        .select_from(Policy)
        .join(Customer, Customer.id == Policy.customer_id)
        .join(InsuranceProvider, InsuranceProvider.id == Policy.provider_id)
        .outerjoin(Application, Application.id == Policy.application_id)
        .outerjoin(Vehicle, Vehicle.id == Application.vehicle_id)
        .outerjoin(Renewal, Renewal.policy_id == Policy.id)
        .where(
            Policy.status == "active", Policy.is_mock.is_(False), Policy.end_date >= first, Policy.end_date <= last,
            # a policy posted from the ledger is worked from its ledger row (where follow-up notes live), not twice
            Policy.id.notin_(select(SalesEntry.policy_id).where(SalesEntry.policy_id.is_not(None), SalesEntry.posted_at.is_not(None))),
        )
    )


def _renewal_workbook_select(first: date, last: date):
    return (
        select(
            cast(literal("workbook"), String).label("source"),
            cast(SalesEntry.id, String).label("id"),
            SalesEntry.expiry_date.label("expiry_date"),
            SalesEntry.client_name.label("client_name"),
            SalesEntry.phone.label("phone"),
            SalesEntry.customer_id.label("customer_id"),
            SalesEntry.underwriter.label("underwriter"),
            func.coalesce(SalesEntry.reg_no, SalesEntry.asset_ref).label("reg_no"),
            SalesEntry.premium.label("premium"),
            SalesEntry.staff_name.label("staff"),
            SalesEntry.branch.label("branch"),
            func.coalesce(SalesEntry.follow_up_status, "due").label("status"),
            SalesEntry.follow_up_note.label("note"),
            SalesEntry.policy_number.label("policy_number"),
        )
        .where(
            SalesEntry.status == "active", or_(SalesEntry.policy_id.is_(None), SalesEntry.posted_at.is_not(None)), SalesEntry.expiry_date.is_not(None),
            SalesEntry.expiry_date >= first, SalesEntry.expiry_date <= last, ~_renewed_exists(),
        )
    )


RENEWAL_COLUMNS = ("source", "id", "expiry_date", "client_name", "phone", "customer_id", "underwriter", "reg_no", "premium",
                   "staff", "branch", "status", "note", "policy_number")


async def renewals_page(db: AsyncSession, *, days: int = 60, overdue_days: int = 30, source: str | None = None, status: str | None = None,
                        q: str | None = None, include_closed: bool = False, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    today = date.today()
    first, last = today - timedelta(days=overdue_days), today + timedelta(days=days)
    selects = []
    if source in (None, "platform"):
        selects.append(_renewal_platform_select(first, last))
    if source in (None, "workbook"):
        selects.append(_renewal_workbook_select(first, last))
    u = union_all(*selects).subquery("renewals")

    where = []
    if status:
        where.append(u.c.status == status)
    elif not include_closed:
        where.append(u.c.status.notin_(CLOSED_FOLLOW_UPS + ("paid",)))
    if q:
        like = f"%{q.strip()}%"
        where.append(or_(u.c.client_name.ilike(like), u.c.policy_number.ilike(like), u.c.reg_no.ilike(like), u.c.phone.ilike(like)))
    total = await db.scalar(select(func.count()).select_from(u).where(*where)) or 0
    rows = (await db.execute(
        select(*[u.c[c] for c in RENEWAL_COLUMNS]).where(*where).order_by(u.c.expiry_date, u.c.client_name).limit(limit).offset(offset)
    )).mappings().all()
    items = []
    for r in rows:
        item = dict(r)
        item["days_left"] = (r["expiry_date"] - today).days if r["expiry_date"] else None
        items.append(item)
    return {"total": total, "items": items}


async def set_follow_up(db: AsyncSession, entry_id: uuid.UUID, *, status: str | None, note: str | None, user_id: str | None) -> SalesEntry:
    if status and status not in FOLLOW_UP_STATUSES:
        raise ValueError("Status must be contacted, quoted, renewed or lost.")
    entry = await db.get(SalesEntry, entry_id)
    if entry is None:
        raise LookupError("That workbook policy no longer exists.")
    entry.follow_up_status = status or None
    entry.follow_up_note = (note or "").strip() or None
    entry.follow_up_at = datetime.now(timezone.utc)
    entry.follow_up_by = uuid.UUID(user_id) if user_id else None
    await db.commit()
    return entry


# --------------------------------------------------------------------------------------
# customers
# --------------------------------------------------------------------------------------


async def link_customers(db: AsyncSession, *, create: bool = False, dry_run: bool = False, commit: bool = True) -> dict[str, int]:
    """Attach workbook clients (and their claims) to customers.

    Matching, strongest first: the policy is also a policy in the app (its customer); the phone number
    matches exactly one customer; the number plate belongs to one customer's vehicle AND the names share a
    word. Nothing is merged and no existing customer is changed. With create=True, clients that have a phone
    number but match nobody get a new customer (lead source "workbook", no marketing consent) - one per phone
    number. Clients with no phone are never created; they are listed so a number can be added."""
    customers = (await db.execute(select(Customer.id, Customer.full_name, Customer.phone))).all()
    names = {cid: name for cid, name, _ in customers}
    by_phone: dict[str, set[uuid.UUID]] = defaultdict(set)
    for cid, _, phone in customers:
        key = phone_key(phone)
        if key:
            by_phone[key].add(cid)

    entries = (await db.execute(
        select(SalesEntry.id, SalesEntry.client_name, SalesEntry.client_key, SalesEntry.phone, SalesEntry.reg_no, SalesEntry.policy_id)
        .where(SalesEntry.customer_id.is_(None), SalesEntry.status == "active")
    )).all()

    policy_customer: dict[uuid.UUID, uuid.UUID] = {}
    for chunk in _chunks([e.policy_id for e in entries if e.policy_id]):
        policy_customer.update({pid: cid for pid, cid in (await db.execute(select(Policy.id, Policy.customer_id).where(Policy.id.in_(chunk)))).all()})

    plate_owner: dict[str, set[uuid.UUID]] = defaultdict(set)
    plate_expr = func.upper(func.replace(Vehicle.registration_number, " ", ""))
    for chunk in _chunks(list({e.reg_no for e in entries if e.reg_no})):
        for plate, cid in (await db.execute(select(plate_expr, Vehicle.customer_id).where(plate_expr.in_(chunk)))).all():
            plate_owner[plate].add(cid)

    links: dict[uuid.UUID, uuid.UUID] = {}
    how: Counter[str] = Counter()
    unmatched = []
    for e in entries:
        customer_id, reason = None, None
        if e.policy_id and e.policy_id in policy_customer:
            customer_id, reason = policy_customer[e.policy_id], "policy"
        else:
            candidates = by_phone.get(phone_key(e.phone) or "", set())
            owners = plate_owner.get(e.reg_no or "", set())
            if len(candidates) == 1:
                customer_id, reason = next(iter(candidates)), "phone"
            elif len(owners) == 1 and names_overlap(e.client_name, names.get(next(iter(owners)))):
                customer_id, reason = next(iter(owners)), "plate"
        if customer_id:
            links[e.id] = customer_id
            how[reason] += 1
        else:
            unmatched.append(e)

    # Clients that have a phone and match nobody: one new customer per phone number (only when asked).
    candidates_to_create: dict[str, dict[str, Any]] = {}
    for e in unmatched:
        key = phone_key(e.phone)
        if key and e.phone:
            slot = candidates_to_create.setdefault(key, {"phone": e.phone, "names": Counter(), "entries": []})
            slot["names"][e.client_name] += 1
            slot["entries"].append(e.id)
    entries_with_phone = sum(len(s["entries"]) for s in candidates_to_create.values())
    clients_without_phone = len({e.client_key for e in unmatched if not phone_key(e.phone)})

    created = 0
    if create:
        new_customers = []
        for slot in candidates_to_create.values():
            customer_id = uuid.uuid4()
            new_customers.append({
                "id": customer_id, "full_name": slot["names"].most_common(1)[0][0].title()[:255], "phone": slot["phone"],
                "lead_source": "workbook", "consent_marketing": False,
            })
            for entry_id in slot["entries"]:
                links[entry_id] = customer_id
        created = len(new_customers)
        if not dry_run:
            for chunk in _chunks(new_customers):
                await db.execute(insert(Customer), chunk)

    claims_linked = 0
    if not dry_run:
        for chunk in _chunks([{"id": entry_id, "customer_id": customer_id} for entry_id, customer_id in links.items()]):
            await db.execute(update(SalesEntry), chunk)
        claims_linked = await _link_claims(db, by_phone)
        record_event(
            "sales_import.link_customers",
            summary=f"Linked {len(links)} workbook policies to customers" + (f" ({created} new customers created)" if created else ""),
            linked=len(links), created=created, by=dict(how),
        )
        if commit:
            await db.commit()

    return {
        "linked_by_policy": how["policy"], "linked_by_phone": how["phone"], "linked_by_plate": how["plate"],
        # what "Create customers" would do (dry run) or did (real run)
        "customers_created": created,
        "policies_waiting_for_a_customer": 0 if create else entries_with_phone,
        "customers_that_would_be_created": 0 if create else len(candidates_to_create),
        "clients_without_phone": clients_without_phone,
        "claims_linked": claims_linked,
    }


async def _link_claims(db: AsyncSession, by_phone: dict[str, set[uuid.UUID]]) -> int:
    """A claim follows the sale it is attached to; failing that, a matching phone number."""
    before = await db.scalar(select(func.count()).select_from(LegacyClaim).where(LegacyClaim.customer_id.is_not(None))) or 0
    await db.execute(
        update(LegacyClaim)
        .where(LegacyClaim.customer_id.is_(None), LegacyClaim.sales_entry_id.is_not(None))
        .values(customer_id=select(SalesEntry.customer_id).where(SalesEntry.id == LegacyClaim.sales_entry_id).scalar_subquery())
    )
    loose = (await db.execute(select(LegacyClaim.id, LegacyClaim.contact).where(LegacyClaim.customer_id.is_(None), LegacyClaim.contact.is_not(None)))).all()
    updates = []
    for claim_id, contact in loose:
        candidates = by_phone.get(phone_key(contact) or "", set())
        if len(candidates) == 1:
            updates.append({"id": claim_id, "customer_id": next(iter(candidates))})
    for chunk in _chunks(updates):
        await db.execute(update(LegacyClaim), chunk)
    after = await db.scalar(select(func.count()).select_from(LegacyClaim).where(LegacyClaim.customer_id.is_not(None))) or 0
    return int(after - before)


async def customer_link_status(db: AsyncSession) -> dict[str, int]:
    """Where workbook clients stand: matched, matchable by phone, or waiting for a phone number."""
    base = (SalesEntry.status == "active",)
    clients = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(*base)) or 0
    linked = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(*base, SalesEntry.customer_id.is_not(None))) or 0
    with_phone = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(*base, SalesEntry.customer_id.is_(None), SalesEntry.phone.is_not(None))) or 0
    without_phone = await db.scalar(select(func.count(func.distinct(SalesEntry.client_key))).where(*base, SalesEntry.customer_id.is_(None), SalesEntry.phone.is_(None))) or 0
    return {"clients": int(clients), "linked": int(linked), "unlinked_with_phone": int(with_phone), "unlinked_without_phone": int(without_phone)}


async def clients_needing_phone(db: AsyncSession, *, q: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    where = [SalesEntry.status == "active", SalesEntry.customer_id.is_(None), SalesEntry.phone.is_(None), SalesEntry.client_key.is_not(None)]
    if q:
        where.append(SalesEntry.client_name.ilike(f"%{q.strip()}%"))
    grouped = (
        select(SalesEntry.client_key, func.min(SalesEntry.client_name).label("client_name"), func.count().label("policies"),
               func.coalesce(func.sum(SalesEntry.premium), 0).label("premium"), func.max(SalesEntry.expiry_date).label("latest_expiry"),
               func.min(func.coalesce(SalesEntry.reg_no, SalesEntry.asset_ref)).label("sample_reg"))
        .where(*where).group_by(SalesEntry.client_key)
    )
    sub = grouped.subquery()
    total = await db.scalar(select(func.count()).select_from(sub)) or 0
    rows = (await db.execute(select(sub).order_by(sub.c.latest_expiry.desc().nulls_last()).limit(limit).offset(offset))).mappings().all()
    return {"total": total, "items": [dict(r) for r in rows]}


async def set_client_phone(db: AsyncSession, *, client_key: str, phone_text: str, user_id: str | None = None) -> dict[str, int]:
    """Adds a phone number for a workbook client the sheet has no number for. It is kept as a correction
    on each of their rows: it holds while the sheet's phone cell is empty, and gives way to the sheet the
    moment the sheet gets a number."""
    phone = clean_phone(phone_text)
    if not phone:
        raise ValueError("Enter a Kenyan mobile number, like 0712 345 678 or +254712345678.")
    entries = (await db.scalars(select(SalesEntry).where(SalesEntry.client_key == client_key, SalesEntry.status == "active", SalesEntry.phone.is_(None)))).all()
    if not entries:
        raise LookupError("That client has no rows waiting for a phone number.")
    for entry in entries:
        overrides = dict(entry.overrides or {})
        overrides["phone"] = {"value": phone, "sheet": None}
        entry.overrides = overrides
        entry.phone = phone
    # Customers already posted from the workbook with a blank phone get this number too.
    customer_ids = [e.customer_id for e in entries if e.customer_id]
    if customer_ids:
        await db.execute(update(Customer).where(Customer.id.in_(customer_ids), Customer.phone == "").values(phone=phone))
    await db.flush()
    link = await link_customers(db, create=False, dry_run=False, commit=False)
    record_event("sales_import.client_phone", summary=f"Added a phone number for {entries[0].client_name}", client=entries[0].client_name, rows=len(entries))
    await db.commit()
    return {"rows": len(entries), "linked_now": link["linked_by_policy"] + link["linked_by_phone"] + link["linked_by_plate"]}


async def customer_history(db: AsyncSession, customer_id: uuid.UUID) -> dict[str, Any]:
    entries = (await db.scalars(
        select(SalesEntry).where(SalesEntry.customer_id == customer_id, SalesEntry.status == "active")
        .order_by(SalesEntry.expiry_date.desc().nulls_last(), SalesEntry.period_year.desc()).limit(200)
    )).all()
    claims = (await db.scalars(
        select(LegacyClaim).where(LegacyClaim.customer_id == customer_id, LegacyClaim.status == "active")
        .order_by(LegacyClaim.date_reported.desc().nulls_last()).limit(100)
    )).all()
    return {"entries": list(entries), "claims": list(claims)}
