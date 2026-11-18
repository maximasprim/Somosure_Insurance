"""Posting the workbook into the system's own tables.

A ledger row (sales_entries) becomes, in the real tables the rest of the system already reads:

    Customer  ->  QuoteRequest  ->  Quote  ->  Application  ->  Policy  ->  Payment  (+ a PolicyEvent)

Every policy came from a quote and was paid for; the manual records just never recorded those steps, so
they are reconstructed here from what the sheet does say, and marked as such (policy source "workbook",
references starting WBQ-/WBA-/WBP-, `origin: workbook` in their data). Policies, payments, customers,
the Policies and Payments pages, search, the customer page and the dashboard then all see them like any other.

What is deliberately NOT done: nothing here calls the platform's own issuing flow, so no sticker is generated, no
notification or automation fires, no affiliate or loan-officer commission is opened and no payment is requested.

The sheet stays the source of truth for the fields it owns (premium, dates, commission, underwriter, policy
number, payment amount/date): `resync_posted` carries later changes in the sheet into the posted records. Fields
only the app owns (a cancelled status, notes, claims, documents) are never overwritten, and policies that were
not created by this module (source other than "workbook") are never touched.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.models.application import Application
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.policy import Policy, PolicyEvent
from app.models.provider import InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.models.sales_ledger import LegacyClaim, SalesEntry, UnderwriterLink
from app.services.sales_import import posting_rules as rules
from app.services.sales_import import unified
from app.services.sales_import.cleaners import norm_text
from app.services.sales_import.matching import match_provider_name, phone_key

logger = logging.getLogger("somosure.sales_import")
CHUNK = 300

ENTRY_COLUMNS = [
    "id", "natural_key", "sheet_name", "sheet_row", "sheet_year", "period_year", "period_month", "client_name", "client_key", "phone",
    "underwriter", "reg_no", "asset_ref", "product_line", "start_date", "expiry_date", "date_paid", "staff_name", "branch",
    "business_type", "policy_number", "cover_type", "premium", "commission", "customer_id", "issue_level", "policy_id",
]


def _chunks(items: list, size: int = CHUNK):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _at(day: date) -> datetime:
    return datetime.combine(day, time(12, 0), tzinfo=timezone.utc)


def _money(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


# --------------------------------------------------------------------------------------
# underwriters <-> providers
# --------------------------------------------------------------------------------------


async def _provider_index(db: AsyncSession) -> dict[str, uuid.UUID]:
    return {norm_text(name): pid for pid, name in (await db.execute(select(InsuranceProvider.id, InsuranceProvider.name))).all()}


async def _links(db: AsyncSession, *, persist: bool) -> dict[str, uuid.UUID]:
    """underwriter -> provider id. Saved links first; then providers whose name matches are linked automatically
    (and saved when `persist`). An underwriter an administrator has deliberately left unlinked stays unlinked."""
    stored = {l.underwriter: l for l in (await db.scalars(select(UnderwriterLink))).all()}
    links = {u: l.provider_id for u, l in stored.items() if l.provider_id}
    index = await _provider_index(db)
    names = [u for (u,) in (await db.execute(
        select(SalesEntry.underwriter).where(SalesEntry.status == "active", SalesEntry.underwriter.is_not(None)).distinct()
    )).all()]
    for name in names:
        if name in links or name in stored:
            continue
        provider_id = match_provider_name(name, index)
        if provider_id:
            links[name] = provider_id
            if persist:
                db.add(UnderwriterLink(id=uuid.uuid4(), underwriter=name, provider_id=provider_id, source="auto"))
    if persist:
        await db.flush()
    return links


async def underwriter_overview(db: AsyncSession) -> dict[str, Any]:
    stored = {l.underwriter: l for l in (await db.scalars(select(UnderwriterLink))).all()}
    providers = (await db.execute(select(InsuranceProvider.id, InsuranceProvider.name, InsuranceProvider.status).order_by(InsuranceProvider.name))).all()
    by_id = {pid: (name, status) for pid, name, status in providers}
    index = {norm_text(name): pid for pid, name, _ in providers}
    rows = (await db.execute(
        select(SalesEntry.underwriter, func.count(), func.count(SalesEntry.posted_at), func.coalesce(func.sum(SalesEntry.premium), 0))
        .where(SalesEntry.status == "active", SalesEntry.underwriter.is_not(None)).group_by(SalesEntry.underwriter).order_by(func.count().desc())
    )).all()
    items = []
    for underwriter, count, posted, premium in rows:
        link = stored.get(underwriter)
        suggested = match_provider_name(underwriter, index)
        provider_id = link.provider_id if link and link.provider_id else suggested
        items.append({
            "underwriter": underwriter, "rows": count, "posted": posted, "premium": premium,
            "provider_id": provider_id, "provider_name": by_id[provider_id][0] if provider_id else None,
            "provider_status": by_id[provider_id][1] if provider_id else None,
            "source": link.source if link and link.provider_id else ("suggested" if suggested else None),
            "linked": bool(link and link.provider_id) or bool(suggested and not link),
        })
    return {
        "underwriters": items,
        "providers": [{"id": pid, "name": name, "status": status} for pid, name, status in providers],
    }


async def link_underwriter(db: AsyncSession, underwriter: str, *, provider_id: uuid.UUID | None, create_new: bool) -> dict[str, Any]:
    """Says which provider an underwriter is. `create_new` makes an inactive provider for it (inactive = it never
    receives quote requests). Posted records are re-pointed, so correcting a link corrects everything already posted."""
    source = "admin"
    if create_new:
        provider = InsuranceProvider(
            id=uuid.uuid4(), name=underwriter.title()[:150], provider_type="insurer", integration_mode="manual", status="inactive",
        )
        db.add(provider)
        await db.flush()
        provider_id, source = provider.id, "created"
    elif provider_id is not None and await db.get(InsuranceProvider, provider_id) is None:
        raise LookupError("That provider no longer exists.")

    link = await db.scalar(select(UnderwriterLink).where(UnderwriterLink.underwriter == underwriter))
    if link is None:
        link = UnderwriterLink(id=uuid.uuid4(), underwriter=underwriter)
        db.add(link)
    link.provider_id, link.source = provider_id, source

    moved = 0
    if provider_id is not None:
        posted = (await db.execute(
            select(SalesEntry.policy_id, SalesEntry.quote_id).where(SalesEntry.underwriter == underwriter, SalesEntry.posted_at.is_not(None))
        )).all()
        policy_ids = [p for p, _ in posted if p]
        quote_ids = [q for _, q in posted if q]
        for chunk in _chunks(policy_ids):
            await db.execute(update(Policy).where(Policy.id.in_(chunk), Policy.source == "workbook").values(provider_id=provider_id))
        for chunk in _chunks(quote_ids):
            await db.execute(update(Quote).where(Quote.id.in_(chunk)).values(provider_id=provider_id))
        await db.execute(update(SalesEntry).where(SalesEntry.underwriter == underwriter).values(provider_id=provider_id))
        moved = len(policy_ids)
    record_event("sales_import.link_underwriter", summary=f"Linked {underwriter} to a provider", underwriter=underwriter, created=create_new, posted_records_moved=moved)
    await db.commit()
    return {"underwriter": underwriter, "provider_id": str(provider_id) if provider_id else None, "posted_records_moved": moved}


async def auto_link_underwriters(db: AsyncSession) -> int:
    before = await db.scalar(select(func.count()).select_from(UnderwriterLink)) or 0
    await _links(db, persist=True)
    await db.commit()
    return int((await db.scalar(select(func.count()).select_from(UnderwriterLink)) or 0) - before)


# --------------------------------------------------------------------------------------
# what can be posted
# --------------------------------------------------------------------------------------


async def _candidates(db: AsyncSession, only_ids: list[uuid.UUID] | None = None) -> list[dict[str, Any]]:
    """Active ledger rows that have not been posted and do not already match a platform policy."""
    columns = [getattr(SalesEntry, c) for c in ENTRY_COLUMNS]
    query = select(*columns).where(SalesEntry.status == "active", SalesEntry.posted_at.is_(None), SalesEntry.policy_id.is_(None))
    if only_ids is not None:
        query = query.where(SalesEntry.id.in_(only_ids))
    return [dict(r) for r in (await db.execute(query)).mappings().all()]


async def status(db: AsyncSession, *, links: dict[str, uuid.UUID] | None = None, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    links = links if links is not None else await _links(db, persist=False)
    candidates = candidates if candidates is not None else await _candidates(db)
    held: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    ready = 0
    unlinked: Counter[str] = Counter()
    for e in candidates:
        result = rules.classify(e, set(links))
        if result.ready:
            ready += 1
            flags.update(f["code"] for f in result.flags)
        else:
            held.update(code for code, _ in result.reasons)
            if e["underwriter"] and e["underwriter"] not in links:
                unlinked[e["underwriter"]] += 1
    posted_flags: Counter[str] = Counter()
    for (post_flags,) in (await db.execute(select(SalesEntry.post_flags).where(SalesEntry.posted_at.is_not(None)))).all():
        posted_flags.update(f["code"] for f in post_flags or [])
    return {
        "ready": ready,
        "held": dict(held),
        "held_total": len(candidates) - ready,
        "flags_on_ready": dict(flags),
        "posted": int(await db.scalar(select(func.count()).where(SalesEntry.posted_at.is_not(None))) or 0),
        "matched_to_platform_policies": int(await db.scalar(select(func.count()).where(SalesEntry.status == "active", SalesEntry.policy_id.is_not(None), SalesEntry.posted_at.is_(None))) or 0),
        "posted_flags": dict(posted_flags),
        "unlinked_underwriters": [{"underwriter": u, "rows": n} for u, n in unlinked.most_common()],
    }


async def held_entries(db: AsyncSession, *, reason: str | None = None, limit: int = 50, offset: int = 0,
                       links: dict[str, uuid.UUID] | None = None, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    links = links if links is not None else await _links(db, persist=False)
    candidates = candidates if candidates is not None else await _candidates(db)
    items = []
    for e in candidates:
        result = rules.classify(e, set(links))
        if result.ready or (reason and reason not in {code for code, _ in result.reasons}):
            continue
        items.append({
            "id": str(e["id"]), "client_name": e["client_name"], "underwriter": e["underwriter"], "policy_number": e["policy_number"],
            "sheet": e["sheet_name"], "row": e["sheet_row"], "premium": e["premium"], "start_date": e["start_date"],
            "expiry_date": e["expiry_date"], "reasons": [{"code": c, "message": m} for c, m in result.reasons],
        })
    items.sort(key=lambda i: (i["sheet"] or "", i["row"] or 0))
    return {"total": len(items), "items": items[offset:offset + limit]}


async def overview(db: AsyncSession, *, reason: str | None = None, code: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Everything the Post to system tab shows, in one call: the candidates and links are worked out once, not once per
    section, so the tab can draw complete in a single step."""
    links = await _links(db, persist=False)
    candidates = await _candidates(db)
    return {
        "status": await status(db, links=links, candidates=candidates),
        "held": await held_entries(db, reason=reason, limit=limit, links=links, candidates=candidates),
        "review": await posted_with_flags(db, code=code, limit=limit),
        "underwriters": await underwriter_overview(db),
    }


async def posted_with_flags(db: AsyncSession, *, code: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    rows = (await db.execute(
        select(SalesEntry.id, SalesEntry.client_name, SalesEntry.underwriter, SalesEntry.policy_number, SalesEntry.sheet_name, SalesEntry.sheet_row,
               SalesEntry.policy_id, SalesEntry.customer_id, SalesEntry.post_flags)
        .where(SalesEntry.posted_at.is_not(None), SalesEntry.post_flags.is_not(None)).order_by(SalesEntry.sheet_year.desc(), SalesEntry.sheet_row)
    )).all()
    items = [
        {"id": str(r.id), "client_name": r.client_name, "underwriter": r.underwriter, "policy_number": r.policy_number, "sheet": r.sheet_name,
         "row": r.sheet_row, "policy_id": str(r.policy_id) if r.policy_id else None, "customer_id": str(r.customer_id) if r.customer_id else None,
         "flags": r.post_flags}
        for r in rows if r.post_flags and (code is None or any(f["code"] == code for f in r.post_flags))
    ]
    return {"total": len(items), "items": items[offset:offset + limit]}


# --------------------------------------------------------------------------------------
# posting
# --------------------------------------------------------------------------------------


async def post_ready(db: AsyncSession, *, dry_run: bool = True, commit: bool = True, only_ids: list[uuid.UUID] | None = None,
                     link_first: bool = True) -> dict[str, Any]:
    """Posts every ready ledger row (or just `only_ids`). `link_first` runs the customer-matching pass first."""
    links = await _links(db, persist=not dry_run)
    ready: list[tuple[dict[str, Any], rules.Classification]] = []
    held: Counter[str] = Counter()
    for e in await _candidates(db, only_ids):
        result = rules.classify(e, set(links))
        if result.ready:
            ready.append((e, result))
        else:
            held.update(code for code, _ in result.reasons)

    if dry_run:
        return {
            "dry_run": True, "to_post": len(ready), "held": dict(held),
            "flags": dict(Counter(f["code"] for _, r in ready for f in r.flags)),
        }
    if not ready:
        return {"dry_run": False, "posted": 0, "customers_created": 0, "held": dict(held), "flags": {}}

    # Workbook policies that belong to customers already in the system are matched first (policy, phone, plate).
    if link_first:
        await unified.link_customers(db, create=False, dry_run=False, commit=False)
    fresh = (await db.execute(select(SalesEntry.id, SalesEntry.customer_id).where(SalesEntry.id.in_([e["id"] for e, _ in ready])))).all()
    customer_of = {i: c for i, c in fresh}

    by_client: dict[str, uuid.UUID] = {}
    by_phone: dict[str, uuid.UUID] = {}
    for client_key, phone, customer_id in (await db.execute(
        select(SalesEntry.client_key, SalesEntry.phone, SalesEntry.customer_id).where(SalesEntry.customer_id.is_not(None))
    )).all():
        by_client.setdefault(client_key, customer_id)
        if phone_key(phone):
            by_phone.setdefault(phone_key(phone), customer_id)
    existing_phone = {cid: ph for cid, ph in (await db.execute(select(Customer.id, Customer.phone))).all()}

    # numbers already in use, so a policy number is never duplicated
    wanted = {e["policy_number"][:50] for e, _ in ready if e["policy_number"]}
    wanted |= {f"{e['policy_number'][:45]}-{e['sheet_year']}" for e, _ in ready if e["policy_number"]}
    taken: set[str] = set()
    for chunk in _chunks(list(wanted), 500):
        taken.update(n for (n,) in (await db.execute(select(Policy.policy_number).where(Policy.policy_number.in_(chunk)))).all())

    new_customers: dict[uuid.UUID, dict[str, Any]] = {}
    group_of: dict[str, uuid.UUID] = {}
    rows: dict[str, list[dict[str, Any]]] = {k: [] for k in ("customers", "qr", "quotes", "apps", "policies", "events", "payments", "ledger")}
    today = date.today()
    now = datetime.now(timezone.utc)

    for e, result in sorted(ready, key=lambda pair: (rules.sold_on(pair[0]), pair[0]["sheet_row"] or 0)):
        flags = list(result.flags)
        customer_id = customer_of.get(e["id"])
        key = phone_key(e["phone"])
        if customer_id is None and key:
            customer_id = by_phone.get(key)
        if customer_id is None and not key:
            customer_id = by_client.get(e["client_key"])
            if customer_id is not None:
                flags.append({"code": "customer_matched_by_name", "message": "Matched to a customer with the same name - no phone number to confirm it is the same person"})
        if customer_id is None:
            group = f"P{key}" if key else f"N{e['client_key']}"
            customer_id = group_of.get(group)
            if customer_id is None:
                customer_id = uuid.uuid4()
                group_of[group] = customer_id
                new_customers[customer_id] = {"names": Counter(), "phone": e["phone"] or "", "first": rules.sold_on(e)}
            new_customers[customer_id]["names"][e["client_name"]] += 1
            new_customers[customer_id]["first"] = min(new_customers[customer_id]["first"], rules.sold_on(e))
        elif existing_phone.get(customer_id):
            flags = [f for f in flags if f["code"] != "customer_no_phone"]  # the customer already has a number
        by_client.setdefault(e["client_key"], customer_id)
        if key:
            by_phone.setdefault(key, customer_id)

        start, end, _ = rules.derive_dates(e["start_date"], e["expiry_date"])
        number, number_flag = rules.unique_policy_number(e, taken)
        taken.add(number)
        if number_flag == "policy_number_year_added":
            flags.append({"code": number_flag, "message": f"The policy number is already in use (a renewal under the same number?) - the year was added: {number}"})
        sold = _at(rules.sold_on(e))
        paid = _at(e["date_paid"]) if e["date_paid"] else sold
        h = rules.short_hash(e["natural_key"])
        origin = {"origin": "workbook", "reconstructed_from": "weekly report", "sheet": e["sheet_name"], "sheet_row": e["sheet_row"]}
        provider_id = links[e["underwriter"]]
        ids = {k: uuid.uuid4() for k in ("qr", "quote", "app", "policy", "payment")}
        premium = _money(e["premium"])

        rows["qr"].append({
            "id": ids["qr"], "reference": f"WBQ-{h}", "customer_id": customer_id, "category": rules.category_for(e["product_line"]),
            "input_data": {**origin, "registration": e["reg_no"] or e["asset_ref"], "client": e["client_name"], "cover_type": e["cover_type"],
                           "staff": e["staff_name"], "branch": e["branch"], "business_type": e["business_type"]},
            "status": "quoted", "created_at": sold, "updated_at": sold,
        })
        rows["quotes"].append({
            "id": ids["quote"], "quote_request_id": ids["qr"], "provider_id": provider_id, "product_id": None,
            "premium": premium, "taxes": Decimal("0"), "fees": Decimal("0"), "total": premium, "currency": "KES",
            "coverage": {"cover_type": e["cover_type"]}, "exclusions": {}, "deductibles": {}, "payment_options": {},
            "provider_metadata": {**origin, "commission": str(e["commission"]) if e["commission"] is not None else None},
            "underlying_provider_name": e["underwriter"], "is_mock": False, "valid_until": None, "status": "selected", "created_at": sold,
        })
        rows["apps"].append({
            "id": ids["app"], "reference": f"WBA-{h}", "quote_id": ids["quote"], "customer_id": customer_id, "vehicle_id": None,
            "applicant_details": {**origin, "full_name": e["client_name"], "phone": e["phone"], "registration": e["reg_no"] or e["asset_ref"]},
            "status": "approved", "provider_reference": number, "created_at": sold, "updated_at": sold,
        })
        rows["policies"].append({
            "id": ids["policy"], "policy_number": number, "application_id": ids["app"], "provider_id": provider_id, "product_id": None,
            "customer_id": customer_id, "start_date": start, "end_date": end, "premium": premium, "payment_status": "paid",
            "status": rules.policy_status(end, today), "agent_id": None, "source": "workbook", "commission": _money(e["commission"]),
            "is_mock": False, "created_at": sold, "updated_at": sold,
        })
        rows["events"].append({
            "id": uuid.uuid4(), "policy_id": ids["policy"], "event_type": "imported", "from_status": None,
            "to_status": rules.policy_status(end, today),
            "metadata_json": {**origin, "ledger_entry_id": str(e["id"]), "staff": e["staff_name"], "branch": e["branch"], "flags": [f["code"] for f in flags]},
            "created_at": sold,
        })
        rows["payments"].append({
            "id": ids["payment"], "reference": f"WBP-{h}", "customer_id": customer_id, "application_id": ids["app"], "policy_id": ids["policy"],
            "amount": premium, "currency": "KES", "method": "offline", "status": "successful", "payer_phone": e["phone"],
            "created_at": paid, "updated_at": paid,
        })
        rows["ledger"].append({
            "id": e["id"], "customer_id": customer_id, "policy_id": ids["policy"], "quote_request_id": ids["qr"], "quote_id": ids["quote"],
            "application_id": ids["app"], "payment_id": ids["payment"], "provider_id": provider_id, "posted_at": now,
            "post_flags": flags or None,
        })

    for customer_id, info in new_customers.items():
        rows["customers"].append({
            "id": customer_id, "full_name": info["names"].most_common(1)[0][0].title()[:255], "phone": info["phone"],
            "lead_source": "workbook", "consent_marketing": False, "created_at": _at(info["first"]), "updated_at": _at(info["first"]),
        })

    for table, model in (("customers", Customer), ("qr", QuoteRequest), ("quotes", Quote), ("apps", Application),
                         ("policies", Policy), ("events", PolicyEvent), ("payments", Payment)):
        for chunk in _chunks(rows[table]):
            await db.execute(insert(model), chunk)
    for chunk in _chunks(rows["ledger"]):
        await db.execute(update(SalesEntry), chunk)

    summary = {
        "dry_run": False, "posted": len(rows["policies"]), "customers_created": len(rows["customers"]), "held": dict(held),
        "flags": dict(Counter(f["code"] for r in rows["ledger"] for f in (r["post_flags"] or []))),
    }
    record_event("sales_import.post", summary=f"Posted {summary['posted']} workbook policies into the system", **{k: v for k, v in summary.items() if k != "dry_run"})
    if commit:
        await db.commit()
    return summary


# --------------------------------------------------------------------------------------
# keeping posted records in step with the sheet
# --------------------------------------------------------------------------------------


async def resync_posted(db: AsyncSession, *, commit: bool = True) -> dict[str, int]:
    """Carries later changes in the sheet into the records posted earlier. Only fields the sheet owns, only policies
    this module created, and a cancelled/under-review status is never overwritten."""
    links = await _links(db, persist=False)
    today = date.today()
    rows = (await db.execute(
        select(
            SalesEntry.id, SalesEntry.natural_key, SalesEntry.sheet_year, SalesEntry.underwriter, SalesEntry.start_date, SalesEntry.expiry_date,
            SalesEntry.date_paid, SalesEntry.policy_number, SalesEntry.premium, SalesEntry.commission, SalesEntry.phone, SalesEntry.policy_id,
            SalesEntry.quote_id, SalesEntry.payment_id, SalesEntry.customer_id,
            Policy.provider_id.label("p_provider"), Policy.start_date.label("p_start"), Policy.end_date.label("p_end"),
            Policy.premium.label("p_premium"), Policy.commission.label("p_commission"), Policy.policy_number.label("p_number"),
            Policy.status.label("p_status"), Quote.premium.label("q_premium"), Payment.amount.label("pay_amount"), Payment.created_at.label("pay_at"),
            Customer.phone.label("c_phone"),
        )
        .join(Policy, Policy.id == SalesEntry.policy_id).join(Quote, Quote.id == SalesEntry.quote_id)
        .join(Payment, Payment.id == SalesEntry.payment_id).join(Customer, Customer.id == SalesEntry.customer_id)
        .where(SalesEntry.posted_at.is_not(None), SalesEntry.status == "active", Policy.source == "workbook")
    )).mappings().all()

    real_numbers = list({r["policy_number"][:50] for r in rows if r["policy_number"] and rules.is_placeholder(r["p_number"])})
    taken: set[str] = set()
    for chunk in _chunks(real_numbers, 500):
        taken.update(n for (n,) in (await db.execute(select(Policy.policy_number).where(Policy.policy_number.in_(chunk)))).all())

    policies, quotes, payments, customers, ledger_providers = [], [], [], [], []
    now = datetime.now(timezone.utc)
    for r in rows:
        provider = links.get(r["underwriter"]) or r["p_provider"]
        start, end, _ = rules.derive_dates(r["start_date"], r["expiry_date"])
        start, end = start or r["p_start"], end or r["p_end"]
        number = r["p_number"]
        if rules.is_placeholder(number) and r["policy_number"] and r["policy_number"][:50] not in taken:
            number = r["policy_number"][:50]
            taken.add(number)
        status = rules.policy_status(end, today) if r["p_status"] in ("active", "expired") else r["p_status"]
        premium, commission = _money(r["premium"]), _money(r["commission"])
        if (provider, start, end, premium, commission, number, status) != (r["p_provider"], r["p_start"], r["p_end"], _money(r["p_premium"]), _money(r["p_commission"]), r["p_number"], r["p_status"]):
            policies.append({"id": r["policy_id"], "provider_id": provider, "start_date": start, "end_date": end, "premium": premium,
                             "commission": commission, "policy_number": number, "status": status, "updated_at": now})
            if provider != r["p_provider"]:
                ledger_providers.append({"id": r["id"], "provider_id": provider})
        if provider != r["p_provider"] or premium != _money(r["q_premium"]):
            quotes.append({"id": r["quote_id"], "provider_id": provider, "premium": premium, "total": premium})
        paid_at = _at(r["date_paid"]) if r["date_paid"] else r["pay_at"]
        if premium != _money(r["pay_amount"]) or paid_at != r["pay_at"]:
            payments.append({"id": r["payment_id"], "amount": premium, "created_at": paid_at, "updated_at": now})
        if not r["c_phone"] and r["phone"]:
            customers.append({"id": r["customer_id"], "phone": r["phone"]})

    for model, items in ((Policy, policies), (Quote, quotes), (Payment, payments), (Customer, customers), (SalesEntry, ledger_providers)):
        for chunk in _chunks(items):
            await db.execute(update(model), chunk)
    result = {"checked": len(rows), "policies": len(policies), "payments": len(payments), "customers": len(customers)}
    if policies or payments or customers:
        record_event("sales_import.resync", summary=f"Carried sheet changes into {len(policies)} posted policies", **result)
    if commit:
        await db.commit()
    return result


# --------------------------------------------------------------------------------------
# undo
# --------------------------------------------------------------------------------------


async def unpost(db: AsyncSession, *, dry_run: bool = True) -> dict[str, Any]:
    """Removes every record this module created, and only those: policies with source "workbook", their quotes,
    applications, payments and history, and customers created from the workbook that nothing else refers to. The
    ledger keeps the rows (back to "not posted"). Records staff added to a posted policy (a claim, a renewal) stop
    that one policy from being removed; it is reported, not forced."""
    posted = (await db.execute(
        select(SalesEntry.id, SalesEntry.policy_id, SalesEntry.quote_id, SalesEntry.quote_request_id, SalesEntry.application_id, SalesEntry.payment_id)
        .join(Policy, Policy.id == SalesEntry.policy_id).where(SalesEntry.posted_at.is_not(None), Policy.source == "workbook")
    )).all()
    counts = {"policies": len(posted), "customers_created_by_workbook": int(await db.scalar(select(func.count()).select_from(Customer).where(Customer.lead_source == "workbook")) or 0)}
    if dry_run:
        return {"dry_run": True, **counts}

    removed, kept = 0, 0
    for chunk in _chunks(posted, 100):
        removed_here = await _unpost_chunk(db, chunk)
        if removed_here is None:  # something refers to one of them: go one by one
            for single in chunk:
                ok = await _unpost_chunk(db, [single])
                removed += 1 if ok else 0
                kept += 0 if ok else 1
        else:
            removed += removed_here

    deleted_customers = 0
    candidates = [c for (c,) in (await db.execute(select(Customer.id).where(Customer.lead_source == "workbook"))).all()]
    for chunk in _chunks(candidates, 100):
        try:
            async with db.begin_nested():
                await db.execute(update(SalesEntry).where(SalesEntry.customer_id.in_(chunk)).values(customer_id=None))
                await db.execute(update(LegacyClaim).where(LegacyClaim.customer_id.in_(chunk)).values(customer_id=None))
                await db.execute(delete(Customer).where(Customer.id.in_(chunk)))
            deleted_customers += len(chunk)
        except IntegrityError:
            for one in chunk:
                try:
                    async with db.begin_nested():
                        await db.execute(update(SalesEntry).where(SalesEntry.customer_id == one).values(customer_id=None))
                        await db.execute(update(LegacyClaim).where(LegacyClaim.customer_id == one).values(customer_id=None))
                        await db.execute(delete(Customer).where(Customer.id == one))
                    deleted_customers += 1
                except IntegrityError:
                    pass  # the customer has activity of its own now: kept (and relinked by the next import)
    record_event("sales_import.unpost", summary=f"Removed {removed} posted workbook policies", removed=removed, kept=kept, customers_removed=deleted_customers)
    await db.commit()
    return {"dry_run": False, "policies_removed": removed, "policies_kept": kept, "customers_removed": deleted_customers}


async def unpost_entries(db: AsyncSession, entry_ids: list) -> dict[str, int]:
    """Removes the records posted for these ledger rows only (used when a revert puts back an older workbook that does
    not contain them). Same rules as `unpost`: only policies posting created; a policy that staff have since added a
    claim or renewal to is kept and counted, never forced. Customers are left alone. Runs inside the caller's
    transaction - nothing is committed here."""
    removed = kept = 0
    for ids in _chunks(list(entry_ids), 500):
        posted = (await db.execute(
            select(SalesEntry.id, SalesEntry.policy_id, SalesEntry.quote_id, SalesEntry.quote_request_id, SalesEntry.application_id, SalesEntry.payment_id)
            .join(Policy, Policy.id == SalesEntry.policy_id)
            .where(SalesEntry.id.in_(ids), SalesEntry.posted_at.is_not(None), Policy.source == "workbook")
        )).all()
        for chunk in _chunks(posted, 100):
            done = await _unpost_chunk(db, chunk)
            if done is None:  # something refers to one of them: go one by one
                for single in chunk:
                    ok = await _unpost_chunk(db, [single])
                    removed += 1 if ok else 0
                    kept += 0 if ok else 1
            else:
                removed += done
    if removed or kept:
        record_event("sales_import.unpost_entries", summary=f"Removed {removed} posted policies for rows no longer in the sheet", removed=removed, kept=kept)
    return {"removed": removed, "kept": kept}


async def _unpost_chunk(db: AsyncSession, chunk: list) -> int | None:
    """Removes the posted records for these ledger rows. Returns how many, or None if something refers to them."""
    entry_ids = [r.id for r in chunk]
    policy_ids = [r.policy_id for r in chunk]
    try:
        async with db.begin_nested():
            await db.execute(update(SalesEntry).where(SalesEntry.id.in_(entry_ids)).values(
                policy_id=None, quote_request_id=None, quote_id=None, application_id=None, payment_id=None, posted_at=None, post_flags=None,
            ))
            await db.execute(delete(Payment).where(Payment.id.in_([r.payment_id for r in chunk])))
            await db.execute(delete(PolicyEvent).where(PolicyEvent.policy_id.in_(policy_ids)))
            await db.execute(delete(Policy).where(Policy.id.in_(policy_ids), Policy.source == "workbook"))
            await db.execute(delete(Application).where(Application.id.in_([r.application_id for r in chunk])))
            await db.execute(delete(Quote).where(Quote.id.in_([r.quote_id for r in chunk])))
            await db.execute(delete(QuoteRequest).where(QuoteRequest.id.in_([r.quote_request_id for r in chunk])))
        return len(chunk)
    except IntegrityError:
        return None
