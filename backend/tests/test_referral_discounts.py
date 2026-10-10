"""Referral discount credits: an existing customer who refers someone that buys
insurance can be rewarded with a discount on their own insurance, applied by
staff case by case. Needs the same real Postgres as the rest of the suite."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

from sqlalchemy import select

_ids = count(1)
BASE = "/api/v1/admin/affiliate-program"


# ------------------------------------------------------------------ fixtures


async def _staff_token(client, db_session, email, role, name="Discount Tester"):
    from app.models.user import Role, User, UserRole

    await client.post("/api/v1/auth/register", json={"full_name": name, "email": email, "password": "supersecret1"})
    user = await db_session.scalar(select(User).where(User.email == email))
    found = await db_session.scalar(select(Role).where(Role.name == role))
    if not found:
        found = Role(id=uuid.uuid4(), name=role)
        db_session.add(found)
        await db_session.flush()
    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=found.id))
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return login.json()["access_token"]


async def _enable(db_session, **overrides):
    from app.services.affiliate_service import get_affiliate_settings

    settings = await get_affiliate_settings(db_session)
    settings.program_enabled = True
    settings.default_rate_type = "percent"
    settings.default_rate_value = Decimal("5.00")
    for key, value in overrides.items():
        setattr(settings, key, value)
    await db_session.commit()
    return settings


async def _pair(db_session):
    from app.models.customer import Customer
    from app.services.referral_service import attribute_referrer, get_or_create_referral_code

    n = next(_ids)
    referrer = Customer(full_name=f"Referrer {n}", phone=f"0731{n:06d}")
    referred = Customer(full_name=f"Friend {n}", phone=f"0732{n:06d}")
    db_session.add_all([referrer, referred])
    await db_session.commit()
    code = (await get_or_create_referral_code(db_session, str(referrer.id))).code
    referral = await attribute_referrer(db_session, code, str(referred.id))
    assert referral is not None
    return referrer, referred, referral


async def _application(db_session, provider, customer, premium="20000.00", total="23000.00", plans=None, status="approved"):
    from app.models.application import Application
    from app.models.quote import Quote, QuoteRequest

    n = next(_ids)
    qr = QuoteRequest(reference=f"SOM-DSC-{n:06d}", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(
        quote_request_id=qr.id, provider_id=provider.id, premium=Decimal(premium), taxes=Decimal(total) - Decimal(premium),
        fees=Decimal("0"), total=Decimal(total), currency="KES", is_mock=True, status="available",
        payment_options={"plans": plans} if plans else None,
    )
    db_session.add(quote)
    await db_session.flush()
    application = Application(reference=f"SOM-APP-DSC-{n:06d}", quote_id=quote.id, customer_id=customer.id, status=status)
    db_session.add(application)
    await db_session.commit()
    return application, quote


async def _policy(db_session, provider, customer, premium="20000.00"):
    from app.models.policy import Policy

    application, _ = await _application(db_session, provider, customer, premium=premium, total=str(Decimal(premium) + Decimal("3000")))
    n = next(_ids)
    policy = Policy(
        policy_number=f"POL-DSC-{n:06d}", application_id=application.id, provider_id=provider.id, customer_id=customer.id,
        start_date=date.today(), end_date=date.today() + timedelta(days=365), premium=Decimal(premium),
        payment_status="pending", status="active", is_mock=True,
    )
    db_session.add(policy)
    await db_session.commit()
    return policy


async def _loyal_pair(db_session, provider):
    """A referrer who is an existing customer (has an active policy) and the friend they referred."""
    referrer, referred, referral = await _pair(db_session)
    await _policy(db_session, provider, referrer)
    return referrer, referred, referral


async def _credits(db_session, customer_id):
    from app.models.affiliate import ReferralDiscount

    return (await db_session.scalars(select(ReferralDiscount).where(ReferralDiscount.customer_id == customer_id))).all()


async def _commissions(db_session, customer_id):
    from app.models.affiliate import AffiliateCommission

    return (await db_session.scalars(select(AffiliateCommission).where(AffiliateCommission.referrer_customer_id == customer_id))).all()


# ------------------------------------------------------------------ granting


async def test_by_default_existing_customers_still_earn_commission_and_get_no_credit(db_session, seeded_providers):
    from app.services.affiliate_service import record_rewards_for_policy

    await _enable(db_session)  # existing_customer_reward stays "commission"
    loyal, friend, _ = await _loyal_pair(db_session, seeded_providers[0])
    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    assert len(await _commissions(db_session, loyal.id)) == 1
    assert await _credits(db_session, loyal.id) == []


async def test_discount_mode_gives_an_existing_customer_a_credit_instead_of_commission(db_session, seeded_providers):
    from app.services.affiliate_service import record_rewards_for_policy

    await _enable(db_session, existing_customer_reward="discount", discount_type="percent", discount_value=Decimal("10.00"), discount_valid_days=90)
    loyal, friend, referral = await _loyal_pair(db_session, seeded_providers[0])
    outsider, outsider_friend, _ = await _pair(db_session)  # never bought anything

    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], outsider_friend)).id)

    assert await _commissions(db_session, loyal.id) == []  # discount INSTEAD of cash
    [credit] = await _credits(db_session, loyal.id)
    assert credit.status == "available" and credit.source == "referral" and credit.referral_id == referral.id
    assert credit.discount_type == "percent" and credit.discount_value == Decimal("10.00")
    assert credit.expires_at > datetime.now(timezone.utc) + timedelta(days=89)
    assert "Friend" in credit.note

    # a referrer who isn't a customer still earns commission, and gets no credit
    assert len(await _commissions(db_session, outsider.id)) == 1
    assert await _credits(db_session, outsider.id) == []


async def test_both_mode_gives_commission_and_a_credit(db_session, seeded_providers):
    from app.services.affiliate_service import record_rewards_for_policy

    await _enable(db_session, existing_customer_reward="both", discount_value=Decimal("5.00"))
    loyal, friend, _ = await _loyal_pair(db_session, seeded_providers[0])
    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    assert len(await _commissions(db_session, loyal.id)) == 1
    assert len(await _credits(db_session, loyal.id)) == 1


async def test_no_credit_without_a_value_and_never_two_for_one_policy(db_session, seeded_providers):
    from app.services.referral_discount_service import grant_discount_for_policy

    await _enable(db_session, existing_customer_reward="discount", discount_value=Decimal("0.00"))
    loyal, friend, _ = await _loyal_pair(db_session, seeded_providers[0])
    policy = await _policy(db_session, seeded_providers[0], friend)
    assert await grant_discount_for_policy(db_session, policy.id) is None  # nothing to give yet

    await _enable(db_session, existing_customer_reward="discount", discount_value=Decimal("10.00"))
    assert await grant_discount_for_policy(db_session, policy.id) is not None
    assert await grant_discount_for_policy(db_session, policy.id) is None  # same policy again
    assert len(await _credits(db_session, loyal.id)) == 1


async def test_first_policy_scope_applies_to_credits_too(db_session, seeded_providers):
    from app.services.affiliate_service import record_rewards_for_policy

    await _enable(db_session, existing_customer_reward="discount", discount_value=Decimal("10.00"), scope="first_policy")
    loyal, friend, _ = await _loyal_pair(db_session, seeded_providers[0])
    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    await record_rewards_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    assert len(await _credits(db_session, loyal.id)) == 1


async def test_no_credit_is_granted_while_the_programme_is_off(db_session, seeded_providers):
    from app.services.referral_discount_service import grant_discount_for_policy

    settings = await _enable(db_session, existing_customer_reward="discount", discount_value=Decimal("10.00"))
    loyal, friend, _ = await _loyal_pair(db_session, seeded_providers[0])
    policy = await _policy(db_session, seeded_providers[0], friend)
    settings.program_enabled = False
    await db_session.commit()
    assert await grant_discount_for_policy(db_session, policy.id) is None


# ------------------------------------------------------- applying (admin API)


async def _credit_for(db_session, customer, **kw):
    from app.models.affiliate import ReferralDiscount

    credit = ReferralDiscount(
        customer_id=customer.id, source="manual", discount_type=kw.get("type", "percent"), discount_value=Decimal(kw.get("value", "10")),
        max_amount=Decimal(kw["max"]) if "max" in kw else None, status="available", note="test credit",
        expires_at=kw.get("expires_at"),
    )
    db_session.add(credit)
    await db_session.commit()
    return credit


async def test_staff_apply_a_credit_to_the_customers_own_application(client, db_session, seeded_providers):
    token = await _staff_token(client, db_session, "disc1@example.com", "finance_officer")
    auth = {"Authorization": f"Bearer {token}"}
    loyal, _, _ = await _pair(db_session)
    other, _, _ = await _pair(db_session)
    credit = await _credit_for(db_session, loyal, value="10")
    mine, _ = await _application(db_session, seeded_providers[0], loyal, premium="20000.00", total="23000.00")
    theirs, _ = await _application(db_session, seeded_providers[0], other)

    listed = (await client.get(f"{BASE}/discounts/{credit.id}/applications", headers=auth)).json()
    row = next(a for a in listed if a["application_id"] == str(mine.id))
    assert row["eligible"] is True and Decimal(row["max_discount"]) == Decimal("2000.00")  # 10% of the 20,000 premium
    assert all(a["application_id"] != str(theirs.id) for a in listed)  # only this customer's applications

    # someone else's application, no reason, or too much: all refused
    assert (await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(theirs.id), "reason": "Loyalty"}, headers=auth)).status_code == 409
    assert (await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(mine.id), "reason": ""}, headers=auth)).status_code == 422
    assert (await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(mine.id), "amount": "2500", "reason": "Too generous"}, headers=auth)).status_code == 422

    applied = await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(mine.id), "reason": "Referred a friend who bought motor cover"}, headers=auth)
    assert applied.status_code == 200
    body = applied.json()
    assert body["status"] == "applied" and Decimal(body["applied_amount"]) == Decimal("2000.00") and body["applied_application_reference"] == mine.reference

    await db_session.refresh(mine)
    assert mine.discount_amount == Decimal("2000.00") and mine.discount_credit_id == credit.id

    # the open endpoint the payment screen reads
    shown = (await client.get(f"/api/v1/applications/{mine.id}/discount")).json()
    assert Decimal(shown["discount_amount"]) == Decimal("2000.00")
    assert (await client.get(f"/api/v1/applications/{theirs.id}/discount")).json()["discount_amount"] is None

    # one discount per application, and a credit is used once
    again = await _credit_for(db_session, loyal, value="5")
    assert (await client.post(f"{BASE}/discounts/{again.id}/apply", json={"application_id": str(mine.id), "reason": "Second one"}, headers=auth)).status_code == 409
    assert (await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(mine.id), "reason": "Again"}, headers=auth)).status_code == 409


async def test_staff_can_choose_a_smaller_discount_and_a_fixed_credit_is_capped_at_the_premium(client, db_session, seeded_providers):
    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc2@example.com", "management")}
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal, premium="20000.00", total="23000.00")
    big = await _credit_for(db_session, loyal, type="fixed", value="50000")
    listed = (await client.get(f"{BASE}/discounts/{big.id}/applications", headers=auth)).json()
    assert Decimal(next(a for a in listed if a["application_id"] == str(app_.id))["max_discount"]) == Decimal("20000.00")  # never more than the premium

    done = await client.post(f"{BASE}/discounts/{big.id}/apply", json={"application_id": str(app_.id), "amount": "1500", "reason": "Goodwill only"}, headers=auth)
    assert Decimal(done.json()["applied_amount"]) == Decimal("1500.00")


async def test_an_expired_cancelled_or_unrelated_credit_cannot_be_applied(client, db_session, seeded_providers):
    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc3@example.com", "management")}
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal)

    expired = await _credit_for(db_session, loyal, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    listing = (await client.get(f"{BASE}/discounts", params={"status": "expired", "customer_id": str(loyal.id)}, headers=auth)).json()
    assert [i["id"] for i in listing["items"]] == [str(expired.id)] and listing["items"][0]["status"] == "expired"
    assert (await client.post(f"{BASE}/discounts/{expired.id}/apply", json={"application_id": str(app_.id), "reason": "Try anyway"}, headers=auth)).status_code == 409

    cancelled = await _credit_for(db_session, loyal)
    assert (await client.post(f"{BASE}/discounts/{cancelled.id}/cancel", json={}, headers=auth)).status_code == 422  # reason needed
    assert (await client.post(f"{BASE}/discounts/{cancelled.id}/cancel", json={"reason": "Issued by mistake"}, headers=auth)).json()["status"] == "cancelled"
    assert (await client.post(f"{BASE}/discounts/{cancelled.id}/apply", json={"application_id": str(app_.id), "reason": "No"}, headers=auth)).status_code == 409


async def test_an_applied_credit_can_be_released_until_something_is_paid(client, db_session, seeded_providers):
    from app.models.payment import Payment

    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc4@example.com", "management")}
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal)
    credit = await _credit_for(db_session, loyal)
    await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(app_.id), "reason": "Referral reward"}, headers=auth)

    released = await client.post(f"{BASE}/discounts/{credit.id}/release", json={"reason": "Customer chose a different policy"}, headers=auth)
    assert released.json()["status"] == "available"
    await db_session.refresh(app_)
    assert app_.discount_amount is None and app_.discount_credit_id is None
    assert (await client.post(f"{BASE}/discounts/{credit.id}/release", json={"reason": "Twice"}, headers=auth)).status_code == 409  # not applied any more

    # apply again, then record a successful payment: now it can't be released
    await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(app_.id), "reason": "Reapplied"}, headers=auth)
    db_session.add(Payment(reference=f"SOM-PAY-DSC-{next(_ids)}", customer_id=loyal.id, application_id=app_.id, amount=Decimal("100"), method="mpesa", status="successful"))
    await db_session.commit()
    assert (await client.post(f"{BASE}/discounts/{credit.id}/release", json={"reason": "Too late"}, headers=auth)).status_code == 409


async def test_credits_cannot_be_applied_to_a_paid_application(client, db_session, seeded_providers):
    from app.models.payment import Payment

    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc5@example.com", "management")}
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal)
    db_session.add(Payment(reference=f"SOM-PAY-DSC-{next(_ids)}", customer_id=loyal.id, application_id=app_.id, amount=Decimal("100"), method="mpesa", status="successful"))
    await db_session.commit()
    credit = await _credit_for(db_session, loyal)
    row = next(a for a in (await client.get(f"{BASE}/discounts/{credit.id}/applications", headers=auth)).json() if a["application_id"] == str(app_.id))
    assert row["eligible"] is False and "paid" in row["blocked_reason"].lower()
    assert (await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(app_.id), "reason": "Late"}, headers=auth)).status_code == 409


async def test_staff_can_grant_a_credit_directly_and_only_with_a_reason(client, db_session):
    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc6@example.com", "finance_officer", "Fiona Finance")}
    customer, _, _ = await _pair(db_session)
    body = {"customer_id": str(customer.id), "discount_type": "percent", "discount_value": "7.5", "valid_days": 30, "reason": "Apology for a delayed claim"}
    ok = await client.post(f"{BASE}/discounts", json=body, headers=auth)
    assert ok.status_code == 201 and ok.json()["source"] == "manual" and ok.json()["status"] == "available" and ok.json()["customer_name"] == customer.full_name
    assert (await client.post(f"{BASE}/discounts", json={**body, "reason": ""}, headers=auth)).status_code == 422
    assert (await client.post(f"{BASE}/discounts", json={**body, "discount_value": "150"}, headers=auth)).status_code == 422
    assert (await client.post(f"{BASE}/discounts", json={**body, "customer_id": str(uuid.uuid4())}, headers=auth)).status_code == 404


# ---------------------------------------------------------- payment honours it


async def test_pay_in_full_charges_the_discounted_amount_whatever_the_browser_sends(client, db_session, seeded_providers):
    from app.models.payment import Payment

    loyal, _, _ = await _pair(db_session)
    app_, quote = await _application(db_session, seeded_providers[0], loyal, premium="20000.00", total="23000.00")
    app_.discount_amount = Decimal("2000.00")
    await db_session.commit()

    res = await client.post(
        "/api/v1/payments/initiate",
        json={"application_id": str(app_.id), "customer_id": str(loyal.id), "amount": "23000.00", "phone": "0700000001", "method": "mpesa"},
    )
    assert res.status_code == 200
    payment = await db_session.scalar(select(Payment).where(Payment.application_id == app_.id))
    assert payment.amount == Decimal("21000.00")  # 23,000 less the 2,000 discount, not the 23,000 the browser sent


async def test_a_payment_plan_gets_the_discount_off_its_first_payment(client, db_session, seeded_providers):
    from app.models.payment import Payment

    plans = [{
        "plan_code": "monthly", "label": "Pay monthly", "type": "installments", "installments": 2, "deposit_percent": "0",
        "due_now": "11500.00", "sticker_months_per_payment": None,
        "schedule": [
            {"sequence": 1, "kind": "installment", "due_date": date.today().isoformat(), "amount": "11500.00"},
            {"sequence": 2, "kind": "installment", "due_date": (date.today() + timedelta(days=30)).isoformat(), "amount": "11500.00"},
        ],
    }]
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal, premium="20000.00", total="23000.00", plans=plans)
    app_.discount_amount = Decimal("2000.00")
    await db_session.commit()

    res = await client.post(
        "/api/v1/payments/initiate",
        json={"application_id": str(app_.id), "customer_id": str(loyal.id), "amount": "11500", "phone": "0700000002", "method": "mpesa", "plan_code": "monthly", "installments": 2},
    )
    assert res.status_code == 200
    payment = await db_session.scalar(select(Payment).where(Payment.application_id == app_.id))
    assert payment.amount == Decimal("9500.00")
    assert [leg["amount"] for leg in payment.schedule] == ["9500.00", "11500.00"]
    assert payment.total_amount == Decimal("21000.00")


async def test_an_application_without_a_discount_pays_exactly_as_before(client, db_session, seeded_providers):
    from app.models.payment import Payment

    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal, premium="20000.00", total="23000.00")
    res = await client.post(
        "/api/v1/payments/initiate",
        json={"application_id": str(app_.id), "customer_id": str(loyal.id), "amount": "23000.00", "phone": "0700000003", "method": "mpesa"},
    )
    assert res.status_code == 200
    assert (await db_session.scalar(select(Payment).where(Payment.application_id == app_.id))).amount == Decimal("23000.00")


# ------------------------------------------------------- settings + customer


async def test_the_reward_choice_and_credit_terms_are_configured_in_the_admin_settings(client, db_session):
    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc7@example.com", "management")}
    ok = await client.patch(
        f"{BASE}/settings",
        json={"existing_customer_reward": "discount", "discount_type": "percent", "discount_value": "10", "discount_max_amount": "5000", "discount_valid_days": 180},
        headers=auth,
    )
    body = ok.json()
    assert ok.status_code == 200 and body["existing_customer_reward"] == "discount" and Decimal(body["discount_value"]) == Decimal("10")
    assert Decimal(body["discount_max_amount"]) == Decimal("5000") and body["discount_valid_days"] == 180

    assert (await client.patch(f"{BASE}/settings", json={"existing_customer_reward": "gold"}, headers=auth)).status_code == 422
    assert (await client.patch(f"{BASE}/settings", json={"discount_value": "150"}, headers=auth)).status_code == 422
    assert (await client.patch(f"{BASE}/settings", json={"discount_max_amount": None}, headers=auth)).json()["discount_max_amount"] is None


async def test_a_customer_sees_their_credits(client, db_session):
    from app.models.customer import Customer

    await client.post("/api/v1/auth/register", json={"full_name": "Credit Carl", "email": "carl@example.com", "password": "supersecret1"})
    token = (await client.post("/api/v1/auth/login", json={"email": "carl@example.com", "password": "supersecret1"})).json()["access_token"]
    carl = await db_session.scalar(select(Customer).where(Customer.email == "carl@example.com"))
    await _credit_for(db_session, carl, value="12")

    mine = (await client.get("/api/v1/me/affiliate", headers={"Authorization": f"Bearer {token}"})).json()
    assert len(mine["discounts"]) == 1 and mine["discounts"][0]["status"] == "available" and "12% off" in mine["discounts"][0]["description"]


async def test_applying_a_credit_is_on_the_audit_trail_with_who_and_why(client, db_session, seeded_providers):
    from app.models.audit import AuditLog

    auth = {"Authorization": "Bearer " + await _staff_token(client, db_session, "disc8@example.com", "management", "Mary Manager")}
    loyal, _, _ = await _pair(db_session)
    app_, _ = await _application(db_session, seeded_providers[0], loyal)
    credit = await _credit_for(db_session, loyal)
    await client.post(f"{BASE}/discounts/{credit.id}/apply", json={"application_id": str(app_.id), "reason": "Referred a friend who bought"}, headers=auth)
    row = await db_session.scalar(select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "referral_discounts", AuditLog.action == "updated"))
    assert row.actor_name == "Mary Manager" and row.reason == "Referred a friend who bought" and row.changes["status"][1] == "applied"
