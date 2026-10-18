"""The two staff-configurable pricing features:

  * Bidii Credit IPF rate tiers - the monthly interest rate by loan amount and term;
  * renewing all of a customer's covers on one anniversary date, with the short-period
    premium method and tables set by staff.

The matching and arithmetic are pure and tested directly. The endpoint tests run on
the same real Postgres as the rest of the suite.
"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace as NS

from tests.test_quote_experience import _customer_quote
from tests.test_rbac import _register_and_assign_role

from app.services.anniversary_math import renewal_term, suggest_anniversary, term_premium
from app.services.rate_tier_math import describe, find_tier, overlaps

TIERS = "/api/v1/admin/financing/rate-tiers"
ANNIV = "/api/v1/admin/anniversaries"


# --- pure: rate tiers --------------------------------------------------------------------------


def _tier(label, lo, hi, tmin, tmax, rate, applies="all", active=True):
    return NS(
        id=label, label=label, min_amount=Decimal(str(lo)), max_amount=None if hi is None else Decimal(str(hi)),
        min_term_months=tmin, max_term_months=tmax, interest_rate_monthly=Decimal(str(rate)), applies_to=applies, is_active=active,
    )


def test_a_loan_gets_the_tier_for_its_size_and_term_and_boundaries_belong_to_the_higher_tier():
    small, mid, big = _tier("Small", 0, 100000, 3, 10, "3.5"), _tier("Mid", 100000, 500000, 3, 10, "3.2"), _tier("Big", 500000, None, 3, 10, "3.0")
    tiers = [small, mid, big]
    assert find_tier(tiers, Decimal("99999.99"), 6, False).label == "Small"
    assert find_tier(tiers, Decimal("100000"), 6, False).label == "Mid"  # from-inclusive, up-to-exclusive
    assert find_tier(tiers, Decimal("9999999"), 6, False).label == "Big"
    assert find_tier([small], Decimal("200000"), 6, False) is None
    assert find_tier([_tier("Short", 0, None, 3, 5, "3.8"), _tier("Long", 0, None, 6, 10, "3.4")], Decimal("1000"), 5, False).label == "Short"


def test_specific_tiers_beat_general_ones_and_overlaps_are_detected():
    corp, general = _tier("Corp", 0, None, 3, 10, "4.0", "corporate"), _tier("All", 0, None, 3, 10, "3.5")
    assert find_tier([general, corp], Decimal("1000"), 6, True).label == "Corp"
    assert find_tier([general, corp], Decimal("1000"), 6, False).label == "All"
    assert find_tier([_tier("Wide", 0, None, 3, 10, "3.5"), _tier("Narrow", 0, 200000, 3, 10, "3.1")], Decimal("5"), 6, False).label == "Narrow"
    assert overlaps(_tier("A", 0, 200000, 3, 10, "3"), _tier("B", 100000, 300000, 3, 10, "3"))
    assert not overlaps(_tier("A", 0, 100000, 3, 10, "3"), _tier("B", 100000, 300000, 3, 10, "3"))  # meet cleanly
    assert not overlaps(_tier("A", 0, None, 3, 10, "3", "corporate"), _tier("B", 0, None, 3, 10, "3", "individual"))
    assert describe(_tier("M", 100000, 500000, 3, 10, "3.2")) == "KES 100,000 to under KES 500,000, 3-10 months"


# --- pure: anniversary alignment --------------------------------------------------------------------


def test_a_policy_is_renewed_for_a_short_period_to_reach_the_anniversary():
    ann = date(2026, 3, 15)
    short = renewal_term(end_date=date(2026, 8, 10), anniversary=ann)
    assert (short["strategy"], short["new_end"], short["term_days"]) == ("short_period", date(2027, 3, 15), 217)
    aligned = renewal_term(end_date=date(2026, 3, 15), anniversary=ann)
    assert (aligned["strategy"], aligned["term_days"]) == ("already_aligned", 365)
    tiny = renewal_term(end_date=date(2027, 3, 10), anniversary=ann)
    assert tiny["very_short"] is True and tiny["strategy"] == "short_period"  # a longer term isn't allowed by default
    assert renewal_term(end_date=date(2027, 3, 10), anniversary=ann, max_term_days=400)["strategy"] == "long_period"
    assert suggest_anniversary([date(2026, 5, 1), date(2026, 11, 9)]) == date(2026, 11, 9)


def test_the_short_period_premium_follows_the_configured_method():
    annual = Decimal("30000")
    pro_rata = term_premium(annual_premium=annual, term_days=217, strategy="short_period", method="pro_rata_daily")
    assert pro_rata["premium"] == Decimal("17835.62")
    scale = [NS(up_to_days=90, percent_of_annual=Decimal("40")), NS(up_to_days=270, percent_of_annual=Decimal("85"))]
    banded = term_premium(annual_premium=annual, term_days=217, strategy="short_period", method="short_period_scale", scale_rows=scale)
    assert banded["premium"] == Decimal("25500.00") and banded["method_used"] == "short_period_scale"
    beyond = term_premium(annual_premium=annual, term_days=300, strategy="short_period", method="short_period_scale", scale_rows=scale)
    assert beyond["method_used"] == "pro_rata_daily"  # beyond every band: pro-rata, never silently a full year
    floor = term_premium(annual_premium=annual, term_days=10, strategy="short_period", method="pro_rata_daily", minimum_premium_pct=Decimal("20"))
    assert floor["premium"] == Decimal("6000.00")


# --- helpers --------------------------------------------------------------------------------------------


async def _staff(client, db_session, role="super_admin", email="pricing-admin@example.com"):
    token = await _register_and_assign_role(client, db_session, email, "supersecret1", role)
    return {"Authorization": f"Bearer {token}"}


async def _customer_with_policies(db_session, provider, phone, end_offsets, premium="30000.00"):
    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Align Tester", phone=phone)
    db_session.add(customer)
    await db_session.flush()
    policies = []
    for i, offset in enumerate(end_offsets):
        tag = f"{phone[-4:]}{i:02d}"
        qr = QuoteRequest(reference=f"SOM-2026-{tag}", customer_id=customer.id, category="motor", input_data={}, status="quoted")
        db_session.add(qr)
        await db_session.flush()
        quote = Quote(
            quote_request_id=qr.id, provider_id=provider.id, premium=Decimal(premium), taxes=Decimal("0"), fees=Decimal("0"),
            total=Decimal(premium), currency="KES", is_mock=True, status="available",
        )
        db_session.add(quote)
        await db_session.flush()
        application = Application(reference=f"SOM-APP-{tag}", quote_id=quote.id, customer_id=customer.id, applicant_details={}, status="approved")
        db_session.add(application)
        await db_session.flush()
        end = date.today() + timedelta(days=offset)
        policy = Policy(
            policy_number=f"POL-{tag}", application_id=application.id, provider_id=provider.id, customer_id=customer.id,
            start_date=end - timedelta(days=365), end_date=end, premium=Decimal(premium), payment_status="paid", status="active", is_mock=True,
        )
        db_session.add(policy)
        await db_session.flush()
        policies.append(policy)
    await db_session.commit()
    return customer, policies


# --- rate tiers: configuration --------------------------------------------------------------------------


def _body(**over):
    base = {"label": "Under 100k", "applies_to": "all", "min_amount": "0", "max_amount": "100000", "min_term_months": 3, "max_term_months": 10, "interest_rate_monthly": "3.10"}
    base.update(over)
    return base


async def test_rate_tiers_can_be_created_changed_and_removed_but_not_left_ambiguous(client, db_session):
    headers = await _staff(client, db_session)
    first = await client.post(TIERS, json=_body(), headers=headers)
    assert first.status_code == 201, first.text

    # the same loans claimed twice is refused, naming the tier in the way
    clash = await client.post(TIERS, json=_body(label="Overlap", min_amount="50000", max_amount="200000"), headers=headers)
    assert clash.status_code == 409 and "Under 100k" in clash.json()["detail"]

    # back-to-back is fine, and so is an open-ended top tier
    assert (await client.post(TIERS, json=_body(label="100k-500k", min_amount="100000", max_amount="500000", interest_rate_monthly="3.00"), headers=headers)).status_code == 201
    top = await client.post(TIERS, json=_body(label="500k+", min_amount="500000", max_amount=None, interest_rate_monthly="2.80"), headers=headers)
    assert top.status_code == 201 and top.json()["max_amount"] is None

    # nonsense ranges are refused
    assert (await client.post(TIERS, json=_body(label="Bad", min_amount="900", max_amount="100"), headers=headers)).status_code == 400
    assert (await client.post(TIERS, json=_body(label="Bad2", min_term_months=8, max_term_months=4), headers=headers)).status_code == 400

    # a tier switched off can't clash, and switching it back on re-checks
    off = await client.patch(f"{TIERS}/{first.json()['id']}", json={"is_active": False}, headers=headers)
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert (await client.post(TIERS, json=_body(label="Replacement", min_amount="0", max_amount="100000", interest_rate_monthly="3.3"), headers=headers)).status_code == 201
    assert (await client.patch(f"{TIERS}/{first.json()['id']}", json={"is_active": True}, headers=headers)).status_code == 409

    # edit and delete
    renamed = await client.patch(f"{TIERS}/{top.json()['id']}", json={"interest_rate_monthly": "2.75"}, headers=headers)
    assert Decimal(str(renamed.json()["interest_rate_monthly"])) == Decimal("2.75")
    assert (await client.delete(f"{TIERS}/{top.json()['id']}", headers=headers)).status_code == 204
    assert len((await client.get(TIERS, headers=headers)).json()) == 3  # 4 were created, 1 deleted


async def test_only_finance_and_management_roles_may_configure_pricing(client, db_session):
    assert (await client.get(TIERS)).status_code == 401
    uw = await _staff(client, db_session, "underwriter", "uw-pricing@example.com")
    assert (await client.get(TIERS, headers=uw)).status_code == 403
    assert (await client.get(f"{ANNIV}/settings", headers=uw)).status_code == 403


# --- rate tiers: they price the loan --------------------------------------------------------------------


async def test_a_matching_tier_sets_the_rate_and_without_one_nothing_changes(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788400001")  # 30,000 total -> 24,000 financed
    ask = {"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6}

    plain = (await client.post("/api/v1/financing/eligibility", json=ask)).json()
    assert Decimal(str(plain["interest_rate_monthly"])) == Decimal("3.50")  # the standard rate, as before
    assert plain["rate_tier_applied"] is False and plain["rate_tier_name"] is None

    # a tier for loans under 50,000 over 6 to 10 months
    await client.post(TIERS, json=_body(label="Small loans", max_amount="50000", min_term_months=6, interest_rate_monthly="3.00"), headers=headers)
    tiered = (await client.post("/api/v1/financing/eligibility", json=ask)).json()
    assert Decimal(str(tiered["interest_rate_monthly"])) == Decimal("3.00")
    assert tiered["rate_tier_applied"] is True and tiered["rate_tier_name"] == "Small loans"
    assert Decimal(str(tiered["total_repayable"])) < Decimal(str(plain["total_repayable"]))  # a lower rate costs less

    # a shorter term than the tier covers keeps the standard rate
    shorter = (await client.post("/api/v1/financing/eligibility", json={**ask, "term_months": 4})).json()
    assert shorter["rate_tier_applied"] is False and Decimal(str(shorter["interest_rate_monthly"])) == Decimal("3.50")

    # and the rate the customer was quoted is the rate the application carries
    applied = await client.post("/api/v1/financing/applications", json=ask)
    assert applied.status_code == 200 and Decimal(str(applied.json()["interest_rate_monthly"])) == Decimal("3.00")


async def test_the_existing_customer_concession_is_never_overridden_by_a_tier(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    await client.post(TIERS, json=_body(label="Everyone", max_amount=None, interest_rate_monthly="9.99"), headers=headers)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788400002")
    res = (
        await client.post(
            "/api/v1/financing/eligibility",
            json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6, "has_existing_logbook_loan": True, "logbook_loan_age_months": 1},
        )
    ).json()
    assert res["concession_applied"] is True and res["rate_tier_applied"] is False
    assert Decimal(str(res["interest_rate_monthly"])) == Decimal(str(res["preferred_interest_rate_monthly"]))


async def test_a_company_tier_only_prices_companies_and_the_preview_explains_the_rate(client, db_session):
    headers = await _staff(client, db_session)
    await client.post(TIERS, json=_body(label="Companies", applies_to="corporate", max_amount=None, interest_rate_monthly="4.20"), headers=headers)

    company = (await client.get(f"{TIERS}/preview", params={"amount": 20000, "term_months": 6, "corporate": True}, headers=headers)).json()
    assert company["source"] == "tier" and company["tier"]["label"] == "Companies" and Decimal(str(company["rate"])) == Decimal("4.20")
    person = (await client.get(f"{TIERS}/preview", params={"amount": 20000, "term_months": 6, "corporate": False}, headers=headers)).json()
    assert person["source"] == "standard" and person["tier"] is None and Decimal(str(person["rate"])) == Decimal(str(person["standard_rate"]))


# --- anniversary: configuration --------------------------------------------------------------------------


async def test_anniversary_settings_have_sensible_defaults_and_can_be_changed(client, db_session):
    headers = await _staff(client, db_session)
    got = (await client.get(f"{ANNIV}/settings", headers=headers)).json()
    assert got["enabled"] is True and got["method"] == "pro_rata_daily"
    assert (got["year_basis_days"], got["min_stub_days"], got["max_term_days"]) == (365, 30, 366)
    assert Decimal(str(got["minimum_premium_pct"])) == 0

    saved = await client.patch(f"{ANNIV}/settings", json={"method": "short_period_scale", "minimum_premium_pct": "20", "min_stub_days": 14}, headers=headers)
    assert saved.status_code == 200 and saved.json()["method"] == "short_period_scale" and saved.json()["min_stub_days"] == 14
    assert (await client.patch(f"{ANNIV}/settings", json={"year_basis_days": 300}, headers=headers)).status_code == 422
    kept = await client.patch(f"{ANNIV}/settings", json={"method": None}, headers=headers)
    assert kept.json()["method"] == "short_period_scale"  # none of these can be cleared


async def test_short_period_tables_are_per_insurer_with_a_default_and_drive_the_preview(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    provider = seeded_providers[0]
    for days, pct in ((90, "40"), (180, "65"), (270, "85")):
        assert (await client.post(f"{ANNIV}/scales", json={"up_to_days": days, "percent_of_annual": pct}, headers=headers)).status_code == 201
    assert (await client.post(f"{ANNIV}/scales", json={"up_to_days": 90, "percent_of_annual": "50"}, headers=headers)).status_code == 409  # one band per length per table

    own = await client.post(f"{ANNIV}/scales", json={"provider_id": str(provider.id), "up_to_days": 365, "percent_of_annual": "90"}, headers=headers)
    assert own.status_code == 201 and own.json()["provider_name"] == provider.name
    assert len((await client.get(f"{ANNIV}/scales", headers=headers)).json()) == 4

    # with the default method (pro-rata) the tables aren't consulted
    flat = (await client.get(f"{ANNIV}/preview", params={"annual_premium": 30000, "term_days": 217}, headers=headers)).json()
    assert Decimal(str(flat["premium"])) == Decimal("17835.62") and flat["method_used"] == "pro_rata_daily"

    await client.patch(f"{ANNIV}/settings", json={"method": "short_period_scale"}, headers=headers)
    default_table = (await client.get(f"{ANNIV}/preview", params={"annual_premium": 30000, "term_days": 217}, headers=headers)).json()
    assert Decimal(str(default_table["premium"])) == Decimal("25500.00") and default_table["method_used"] == "short_period_scale"
    # an insurer with its own table uses it instead of the default one
    theirs = (await client.get(f"{ANNIV}/preview", params={"annual_premium": 30000, "term_days": 217, "provider_id": str(provider.id)}, headers=headers)).json()
    assert Decimal(str(theirs["premium"])) == Decimal("27000.00")

    band = (await client.get(f"{ANNIV}/scales", headers=headers)).json()[0]
    changed = await client.patch(f"{ANNIV}/scales/{band['id']}", json={"percent_of_annual": "45"}, headers=headers)
    assert changed.status_code == 200 and Decimal(str(changed.json()["percent_of_annual"])) == Decimal("45")
    assert (await client.delete(f"{ANNIV}/scales/{band['id']}", headers=headers)).status_code == 204


# --- anniversary: a customer's plan --------------------------------------------------------------------


async def test_a_customers_covers_can_be_lined_up_on_one_anniversary(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, policies = await _customer_with_policies(db_session, seeded_providers[0], "0788400003", [30, 120, 200])
    url = f"{ANNIV}/customers/{customer.id}"

    plan = (await client.get(url, headers=headers)).json()
    assert plan["anniversary_date"] is None and plan["using_suggestion"] is True
    assert plan["suggested_anniversary"] == (date.today() + timedelta(days=200)).isoformat()  # the latest expiry
    by_number = {p["policy_number"]: p for p in plan["policies"]}
    soonest, middle, latest = (by_number[p.policy_number] for p in policies)
    assert soonest["strategy"] == "short_period" and soonest["term_days"] == 170
    assert Decimal(str(soonest["estimated_premium"])) == Decimal("13972.60")  # 30,000 x 170/365
    assert middle["term_days"] == 80 and Decimal(str(middle["estimated_premium"])) == Decimal("6575.34")
    assert latest["strategy"] == "already_aligned" and Decimal(str(latest["estimated_premium"])) == Decimal("30000.00")

    # save it: the plan now reads from the saved anniversary
    saved = await client.put(url, json={"anniversary_date": (date.today() + timedelta(days=200)).isoformat(), "notes": "Agreed on the phone"}, headers=headers)
    assert saved.status_code == 200
    body = saved.json()
    assert body["using_suggestion"] is False and body["notes"] == "Agreed on the phone"
    assert {p["term_days"] for p in body["policies"] if p["strategy"] == "short_period"} == {170, 80}

    listed = (await client.get(ANNIV, headers=headers)).json()
    assert [row["customer_id"] for row in listed] == [str(customer.id)] and listed[0]["active_policies"] == 3

    cleared = await client.delete(url, headers=headers)
    assert cleared.status_code == 200 and cleared.json()["anniversary_date"] is None
    assert (await client.get(ANNIV, headers=headers)).json() == []


async def test_customers_can_be_found_by_name_or_phone(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, _ = await _customer_with_policies(db_session, seeded_providers[0], "0788400004", [60, 90])
    found = (await client.get(f"{ANNIV}/customers", params={"search": "0788400004"}, headers=headers)).json()
    assert len(found) == 1 and found[0]["id"] == str(customer.id) and found[0]["active_policies"] == 2
    assert (await client.get(f"{ANNIV}/customers", params={"search": "a"}, headers=headers)).status_code == 422  # too short to search on


async def test_renewal_staff_can_see_plans_but_not_change_the_rules(client, db_session, seeded_providers):
    customer, _ = await _customer_with_policies(db_session, seeded_providers[0], "0788400005", [40, 100])
    sales = await _staff(client, db_session, "sales_agent", "sales-pricing@example.com")
    assert (await client.get(f"{ANNIV}/customers/{customer.id}", headers=sales)).status_code == 200
    assert (await client.patch(f"{ANNIV}/settings", json={"enabled": False}, headers=sales)).status_code == 403
    uw = await _staff(client, db_session, "underwriter", "uw2-pricing@example.com")
    assert (await client.get(f"{ANNIV}/customers/{customer.id}", headers=uw)).status_code == 403


# --- anniversary: the renewals screen ---------------------------------------------------------------------


async def test_the_renewals_list_shows_the_aligned_renewal_and_is_unchanged_without_one(client, db_session, seeded_providers):
    from app.models.renewal import Renewal

    headers = await _staff(client, db_session)
    customer, policies = await _customer_with_policies(db_session, seeded_providers[0], "0788400006", [30, 200])
    db_session.add(Renewal(policy_id=policies[0].id, due_date=policies[0].end_date, status="due"))
    await db_session.commit()

    before = (await client.get("/api/v1/admin/renewals", headers=headers)).json()
    assert len(before) == 1 and before[0]["alignment"] is None  # no anniversary yet: exactly as it was

    await client.put(f"{ANNIV}/customers/{customer.id}", json={"anniversary_date": (date.today() + timedelta(days=200)).isoformat()}, headers=headers)
    after = (await client.get("/api/v1/admin/renewals", headers=headers)).json()
    alignment = after[0]["alignment"]
    assert alignment["strategy"] == "short_period" and alignment["term_days"] == 170
    assert Decimal(str(alignment["estimated_premium"])) == Decimal("13972.60")
    assert alignment["new_end"] == (date.today() + timedelta(days=200)).isoformat()

    # switched off, the renewals screen goes back to showing nothing extra
    await client.patch(f"{ANNIV}/settings", json={"enabled": False}, headers=headers)
    assert (await client.get("/api/v1/admin/renewals", headers=headers)).json()[0]["alignment"] is None
