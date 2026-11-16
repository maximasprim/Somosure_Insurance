"""The admin Customers list: everyone in the system, wherever they came from (the platform, WhatsApp, a lead, or the weekly
report workbook), with what they hold. Read-only.

One query per page: customers joined to a per-customer summary of their policies. Demo (mock) policies are not counted."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.policy import Policy

SORTS = ("newest", "name", "expiry", "premium")
POLICY_FILTERS = ("active", "expiring", "expired", "none")


def _policy_summary(today: date):
    active = and_(Policy.status == "active", Policy.end_date >= today)
    return (
        select(
            Policy.customer_id.label("customer_id"),
            func.count().label("policies"),
            func.count().filter(active).label("active_policies"),
            func.coalesce(func.sum(Policy.premium), 0).label("premium"),
            func.min(Policy.end_date).filter(active).label("next_expiry"),
            func.bool_or(Policy.source == "workbook").label("has_workbook"),
        )
        .where(Policy.is_mock.is_(False))
        .group_by(Policy.customer_id)
        .subquery("pol")
    )


def _query(today: date, *, q: str | None, lead_source: str | None, has_phone: bool | None, policy: str | None):
    pol = _policy_summary(today)
    policies = func.coalesce(pol.c.policies, 0)
    active = func.coalesce(pol.c.active_policies, 0)
    columns = [
        Customer.id, Customer.full_name, Customer.phone, Customer.email, Customer.lead_source, Customer.created_at,
        policies.label("policies"), active.label("active_policies"), func.coalesce(pol.c.premium, 0).label("premium"),
        pol.c.next_expiry.label("next_expiry"), func.coalesce(pol.c.has_workbook, False).label("has_workbook"),
    ]
    base = select(*columns).select_from(Customer).outerjoin(pol, pol.c.customer_id == Customer.id)
    where = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        where.append(or_(Customer.full_name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like)))
    if lead_source:
        where.append(Customer.lead_source == lead_source)
    if has_phone is True:
        where.append(Customer.phone != "")
    elif has_phone is False:
        where.append(or_(Customer.phone == "", Customer.phone.is_(None)))
    if policy == "active":
        where.append(active > 0)
    elif policy == "none":
        where.append(policies == 0)
    elif policy == "expiring":
        where.append(pol.c.next_expiry.between(today, today + timedelta(days=60)))
    elif policy == "expired":
        where.append(and_(policies > 0, active == 0))
    return base.where(*where), pol


def _ordered(statement, pol, sort: str):
    if sort == "name":
        return statement.order_by(Customer.full_name)
    if sort == "expiry":
        return statement.order_by(pol.c.next_expiry.asc().nulls_last(), Customer.full_name)
    if sort == "premium":
        return statement.order_by(func.coalesce(pol.c.premium, 0).desc(), Customer.full_name)
    return statement.order_by(Customer.created_at.desc())


async def list_customers(db: AsyncSession, *, q=None, lead_source=None, has_phone=None, policy=None, sort="newest", limit=50, offset=0) -> dict[str, Any]:
    """The page, the counts above it and the filter choices - in one result, so the screen can draw everything at once."""
    today = date.today()
    statement, pol = _query(today, q=q, lead_source=lead_source, has_phone=has_phone, policy=policy)
    total = await db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (await db.execute(_ordered(statement, pol, sort if sort in SORTS else "newest").limit(limit).offset(offset))).mappings().all()

    everyone, pol_all = _query(today, q=None, lead_source=None, has_phone=None, policy=None)
    sub = everyone.subquery()
    stats_row = (await db.execute(
        select(
            func.count(),
            func.count().filter(sub.c.active_policies > 0),
            func.count().filter(or_(sub.c.phone == "", sub.c.phone.is_(None))),
            func.count().filter(or_(sub.c.lead_source == "workbook", sub.c.has_workbook.is_(True))),
        ).select_from(sub)
    )).one()
    sources = [s for (s,) in (await db.execute(select(Customer.lead_source).where(Customer.lead_source.is_not(None)).distinct().order_by(Customer.lead_source))).all()]
    return {
        "total": total,
        "items": [dict(r) for r in rows],
        "stats": {"customers": stats_row[0], "with_active_policy": stats_row[1], "without_phone": stats_row[2], "from_workbook": stats_row[3]},
        "sources": sources,
    }


EXPORT_LIMIT = 20000


async def export_csv(db: AsyncSession, *, q=None, lead_source=None, has_phone=None, policy=None, sort="newest") -> str:
    statement, pol = _query(date.today(), q=q, lead_source=lead_source, has_phone=has_phone, policy=policy)
    rows = (await db.execute(_ordered(statement, pol, sort if sort in SORTS else "newest").limit(EXPORT_LIMIT))).mappings().all()
    out = io.StringIO()
    out.write("\ufeff")  # so Excel reads the file as UTF-8
    writer = csv.writer(out)
    writer.writerow(["Name", "Phone", "Email", "Source", "Added", "Policies", "Active policies", "Next expiry", "Total premium (KES)", "From workbook"])
    for r in rows:
        writer.writerow([
            r["full_name"], r["phone"] or "", r["email"] or "", r["lead_source"] or "", r["created_at"].date().isoformat() if r["created_at"] else "",
            r["policies"], r["active_policies"], r["next_expiry"].isoformat() if r["next_expiry"] else "", f"{r['premium']:.2f}",
            "yes" if r["has_workbook"] or r["lead_source"] == "workbook" else "no",
        ])
    return out.getvalue()
