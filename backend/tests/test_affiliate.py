"""The affiliate program: attribution, commission maths, the approval workflow,
and the admin/customer APIs. Needs the same real Postgres as the rest of the suite."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import select

_ids = count(1)


# ------------------------------------------------------------------ fixtures


async def _staff_token(client, db_session, email, role, name="Affiliate Tester"):
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


async def _pair(db_session, via_affiliate_code=False):
    """A referrer and a referred customer, linked the way a real referral is."""
    from app.models.customer import Customer
    from app.services.affiliate_service import enroll_affiliate
    from app.services.referral_service import attribute_referrer, get_or_create_referral_code

    n = next(_ids)
    referrer = Customer(full_name=f"Referrer {n}", phone=f"0711{n:06d}")
    referred = Customer(full_name=f"Friend {n}", phone=f"0722{n:06d}")
    db_session.add_all([referrer, referred])
    await db_session.commit()
    if via_affiliate_code:
        code = (await enroll_affiliate(db_session, referrer.id)).code
    else:
        code = (await get_or_create_referral_code(db_session, str(referrer.id))).code
    referral = await attribute_referrer(db_session, code, str(referred.id))
    assert referral is not None
    return referrer, referred, referral


async def _policy(db_session, provider, customer, premium="20000.00", category="motor"):
    from app.models.application import Application
    from app.models.policy import Policy
    from app.models.quote import Quote, QuoteRequest

    n = next(_ids)
    qr = QuoteRequest(reference=f"SOM-AFF-{n:06d}", customer_id=customer.id, category=category, status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(
        quote_request_id=qr.id, provider_id=provider.id, premium=Decimal(premium), taxes=Decimal("0"), fees=Decimal("0"),
        total=Decimal(premium), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.flush()
    application = Application(reference=f"SOM-APP-AFF-{n:06d}", quote_id=quote.id, customer_id=customer.id, status="approved")
    db_session.add(application)
    await db_session.flush()
    policy = Policy(
        policy_number=f"POL-AFF-{n:06d}", application_id=application.id, provider_id=provider.id, customer_id=customer.id,
        start_date=date.today(), end_date=date.today() + timedelta(days=365), premium=Decimal(premium),
        payment_status="pending", status="active", is_mock=True,
    )
    db_session.add(policy)
    await db_session.commit()
    return policy


async def _commission(db_session, policy_id):
    from app.models.affiliate import AffiliateCommission

    return await db_session.scalar(select(AffiliateCommission).where(AffiliateCommission.policy_id == policy_id))


# ------------------------------------------------------------ commission maths


async def test_nothing_is_earned_until_the_program_is_switched_on(db_session, seeded_providers):
    from app.services.affiliate_service import get_affiliate_settings, record_commission_for_policy

    settings = await get_affiliate_settings(db_session)
    assert settings.program_enabled is False and Decimal(settings.default_rate_value) == 0

    _, referred, _ = await _pair(db_session)
    policy = await _policy(db_session, seeded_providers[0], referred)
    assert await record_commission_for_policy(db_session, policy.id) is None


async def test_default_rate_creates_a_pending_commission_with_the_rate_copied_on(db_session, seeded_providers):
    from app.models.referral import Referral
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    referrer, referred, referral = await _pair(db_session)
    policy = await _policy(db_session, seeded_providers[0], referred, premium="20000.00")

    commission = await record_commission_for_policy(db_session, policy.id)
    assert commission.status == "pending"
    assert commission.commission_amount == Decimal("1000.00")  # 5% of 20,000
    assert commission.rate_type == "percent" and commission.rate_value == Decimal("5.00")
    assert commission.referrer_customer_id == referrer.id and commission.referred_customer_id == referred.id

    refreshed = await db_session.get(Referral, referral.id)
    await db_session.refresh(refreshed)
    assert refreshed.reward_amount == Decimal("1000.00") and refreshed.reward_paid is False

    # calling again never creates a second commission for the same policy
    assert await record_commission_for_policy(db_session, policy.id) is None


async def test_a_rate_for_one_referrer_beats_the_default_and_other_referrers_keep_the_default(db_session, seeded_providers):
    from app.models.affiliate import AffiliateRateRule
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    vip, vip_friend, _ = await _pair(db_session)
    other, other_friend, _ = await _pair(db_session)
    db_session.add(AffiliateRateRule(name="VIP partner", rate_type="percent", rate_value=Decimal("10.00"), affiliate_customer_id=vip.id))
    await db_session.commit()

    vip_policy = await _policy(db_session, seeded_providers[0], vip_friend, premium="20000.00")
    other_policy = await _policy(db_session, seeded_providers[0], other_friend, premium="20000.00")
    assert (await record_commission_for_policy(db_session, vip_policy.id)).commission_amount == Decimal("2000.00")
    assert (await record_commission_for_policy(db_session, other_policy.id)).commission_amount == Decimal("1000.00")


async def test_category_rules_caps_and_minimum_premium(db_session, seeded_providers):
    from app.models.affiliate import AffiliateRateRule
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session, min_premium=Decimal("5000.00"), max_commission_per_policy=Decimal("1500.00"))
    db_session.add(AffiliateRateRule(name="Medical flat fee", rate_type="fixed", rate_value=Decimal("700.00"), category="medical"))
    await db_session.commit()

    _, friend_a, _ = await _pair(db_session)
    medical = await _policy(db_session, seeded_providers[0], friend_a, premium="30000.00", category="medical")
    assert (await record_commission_for_policy(db_session, medical.id)).commission_amount == Decimal("700.00")

    _, friend_b, _ = await _pair(db_session)
    big_motor = await _policy(db_session, seeded_providers[0], friend_b, premium="100000.00", category="motor")
    assert (await record_commission_for_policy(db_session, big_motor.id)).commission_amount == Decimal("1500.00")  # 5% = 5,000, capped

    _, friend_c, _ = await _pair(db_session)
    small = await _policy(db_session, seeded_providers[0], friend_c, premium="3000.00", category="motor")
    assert await record_commission_for_policy(db_session, small.id) is None  # under the minimum premium


async def test_expired_and_inactive_rules_are_ignored(db_session, seeded_providers):
    from app.models.affiliate import AffiliateRateRule
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    referrer, referred, _ = await _pair(db_session)
    yesterday = date.today() - timedelta(days=1)
    db_session.add_all([
        AffiliateRateRule(name="Old promo", rate_type="percent", rate_value=Decimal("20.00"), ends_on=yesterday),
        AffiliateRateRule(name="Switched off", rate_type="percent", rate_value=Decimal("30.00"), active=False),
    ])
    await db_session.commit()
    policy = await _policy(db_session, seeded_providers[0], referred, premium="20000.00")
    assert (await record_commission_for_policy(db_session, policy.id)).commission_amount == Decimal("1000.00")  # default 5%


async def test_first_policy_scope_pays_once_and_all_policies_pays_each(db_session, seeded_providers):
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session, scope="first_policy")
    _, friend, referral = await _pair(db_session)
    first = await _policy(db_session, seeded_providers[0], friend)
    second = await _policy(db_session, seeded_providers[0], friend)
    assert await record_commission_for_policy(db_session, first.id) is not None
    assert await record_commission_for_policy(db_session, second.id) is None

    await _enable(db_session, scope="all_policies", window_months=12)
    _, friend2, _ = await _pair(db_session)
    a = await _policy(db_session, seeded_providers[0], friend2)
    b = await _policy(db_session, seeded_providers[0], friend2)
    assert await record_commission_for_policy(db_session, a.id) is not None
    assert await record_commission_for_policy(db_session, b.id) is not None


async def test_a_suspended_affiliate_earns_nothing_new(db_session, seeded_providers):
    from app.models.affiliate import Affiliate
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    referrer, friend, _ = await _pair(db_session, via_affiliate_code=True)
    affiliate = await db_session.scalar(select(Affiliate).where(Affiliate.customer_id == referrer.id))
    affiliate.status = "suspended"
    await db_session.commit()
    policy = await _policy(db_session, seeded_providers[0], friend)
    assert await record_commission_for_policy(db_session, policy.id) is None


async def test_auto_approve_skips_the_review_step(db_session, seeded_providers):
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session, auto_approve=True)
    _, friend, _ = await _pair(db_session)
    policy = await _policy(db_session, seeded_providers[0], friend)
    commission = await record_commission_for_policy(db_session, policy.id)
    assert commission.status == "approved" and commission.approved_at is not None


# ------------------------------------------------------------------ attribution


async def test_an_affiliate_code_is_reusable_and_each_customer_gets_their_own_referral(db_session):
    from app.models.customer import Customer
    from app.services.affiliate_service import enroll_affiliate
    from app.services.referral_service import attribute_referrer

    n = next(_ids)
    referrer = Customer(full_name="Reusable Rita", phone=f"0733{n:06d}")
    friends = [Customer(full_name=f"Friend {i}", phone=f"0744{n:03d}{i:03d}") for i in range(3)]
    db_session.add_all([referrer, *friends])
    await db_session.commit()
    code = (await enroll_affiliate(db_session, referrer.id)).code
    assert code.startswith("AFF")

    referrals = [await attribute_referrer(db_session, code.lower(), str(f.id)) for f in friends]
    assert all(r is not None for r in referrals)
    assert len({r.id for r in referrals}) == 3 and all(r.referrer_customer_id == referrer.id for r in referrals)

    # the referrer can't use their own code
    assert await attribute_referrer(db_session, code, str(referrer.id), raise_on_self=False) is None


async def test_attribution_is_for_new_customers_only_and_only_once(db_session, seeded_providers):
    from app.models.customer import Customer
    from app.services.affiliate_service import enroll_affiliate
    from app.services.referral_service import attribute_referrer

    n = next(_ids)
    a = Customer(full_name="Affiliate A", phone=f"0755{n:06d}")
    b = Customer(full_name="Affiliate B", phone=f"0766{n:06d}")
    existing = Customer(full_name="Already A Customer", phone=f"0777{n:06d}")
    newcomer = Customer(full_name="Newcomer", phone=f"0788{n:06d}")
    db_session.add_all([a, b, existing, newcomer])
    await db_session.commit()
    code_a = (await enroll_affiliate(db_session, a.id)).code
    code_b = (await enroll_affiliate(db_session, b.id)).code

    await _policy(db_session, seeded_providers[0], existing)
    assert await attribute_referrer(db_session, code_a, str(existing.id)) is None  # already bought something

    assert await attribute_referrer(db_session, code_a, str(newcomer.id)) is not None
    assert await attribute_referrer(db_session, code_b, str(newcomer.id)) is None  # first referrer keeps the credit


async def test_a_used_single_use_code_cannot_be_taken_over(db_session):
    from app.models.customer import Customer
    from app.services.referral_service import attribute_referrer, get_or_create_referral_code

    n = next(_ids)
    referrer = Customer(full_name="Single Use", phone=f"0791{n:06d}")
    first = Customer(full_name="First Friend", phone=f"0792{n:06d}")
    second = Customer(full_name="Second Friend", phone=f"0793{n:06d}")
    db_session.add_all([referrer, first, second])
    await db_session.commit()
    code = (await get_or_create_referral_code(db_session, str(referrer.id))).code

    assert (await attribute_referrer(db_session, code, str(first.id))).referred_customer_id == first.id
    assert await attribute_referrer(db_session, code, str(second.id)) is None  # was silently overwritten before


async def test_a_guest_who_arrives_through_a_link_is_credited_when_they_ask_for_a_quote(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.models.referral import Referral
    from app.services.referral_service import get_or_create_referral_code

    n = next(_ids)
    referrer = Customer(full_name="Link Sharer", phone=f"0701{n:06d}")
    db_session.add(referrer)
    await db_session.commit()
    code = (await get_or_create_referral_code(db_session, str(referrer.id))).code

    res = await client.post(
        "/api/v1/quotes",
        json={"category": "medical", "answers": {"phone": f"0702{n:06d}", "full_name": "Guest Buyer"}, "referral_code": code},
    )
    assert res.status_code == 200
    referral = await db_session.scalar(select(Referral).where(Referral.code == code))
    await db_session.refresh(referral)
    assert str(referral.referred_customer_id) == res.json()["customer_id"]

    # a bad code never gets in the way of the quote
    bad = await client.post(
        "/api/v1/quotes", json={"category": "medical", "answers": {"phone": f"0703{n:06d}", "full_name": "Other Guest"}, "referral_code": "NOPE123"}
    )
    assert bad.status_code == 200


# ------------------------------------------------------------ approval workflow


async def test_approve_pay_reverse_keeps_the_older_referral_fields_in_step(client, db_session, seeded_providers):
    from app.models.referral import Referral
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    token = await _staff_token(client, db_session, "fin1@example.com", "finance_officer", "Fiona Finance")
    auth = {"Authorization": f"Bearer {token}"}
    _, friend, referral = await _pair(db_session)
    policy = await _policy(db_session, seeded_providers[0], friend)
    commission = await record_commission_for_policy(db_session, policy.id)
    base = f"/api/v1/admin/affiliate-program/commissions/{commission.id}"

    # paying before approval is refused
    assert (await client.post(f"{base}/pay", json={"payout_reference": "QWE123"}, headers=auth)).status_code == 409

    assert (await client.post(f"{base}/approve", headers=auth)).json()["status"] == "approved"
    assert (await client.post(f"{base}/approve", headers=auth)).status_code == 409  # not twice

    # a payout reference is required
    assert (await client.post(f"{base}/pay", json={"payout_reference": "  "}, headers=auth)).status_code == 422
    paid = (await client.post(f"{base}/pay", json={"payout_reference": "QWE123"}, headers=auth)).json()
    assert paid["status"] == "paid" and paid["payout_reference"] == "QWE123" and paid["paid_at"]

    await db_session.refresh(await db_session.get(Referral, referral.id))
    fresh = await db_session.get(Referral, referral.id)
    await db_session.refresh(fresh)
    assert fresh.status == "rewarded" and fresh.reward_paid is True

    # taking a paid commission back needs a reason, and unwinds the referral
    assert (await client.post(f"{base}/reverse", json={"reason": ""}, headers=auth)).status_code == 422
    reversed_ = (await client.post(f"{base}/reverse", json={"reason": "Policy cancelled and refunded"}, headers=auth)).json()
    assert reversed_["status"] == "reversed" and reversed_["status_note"] == "Policy cancelled and refunded"
    await db_session.refresh(fresh)
    assert fresh.status == "converted" and fresh.reward_paid is False and fresh.reward_amount == Decimal("0")


async def test_reject_needs_a_reason_and_is_final(client, db_session, seeded_providers):
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    token = await _staff_token(client, db_session, "mgr-aff@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    _, friend, _ = await _pair(db_session)
    commission = await record_commission_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    base = f"/api/v1/admin/affiliate-program/commissions/{commission.id}"

    assert (await client.post(f"{base}/reject", json={}, headers=auth)).status_code == 422
    assert (await client.post(f"{base}/reject", json={"reason": "Self-referral suspected"}, headers=auth)).json()["status"] == "rejected"
    assert (await client.post(f"{base}/approve", headers=auth)).status_code == 409


async def test_bulk_actions_handle_each_commission_on_its_own(client, db_session, seeded_providers):
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session)
    token = await _staff_token(client, db_session, "bulk@example.com", "finance_officer")
    auth = {"Authorization": f"Bearer {token}"}
    ids = []
    for _ in range(3):
        _, friend, _ = await _pair(db_session)
        c = await record_commission_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
        ids.append(str(c.id))

    await client.post(f"/api/v1/admin/affiliate-program/commissions/{ids[0]}/approve", headers=auth)  # already approved
    res = await client.post("/api/v1/admin/affiliate-program/commissions/bulk", json={"action": "approve", "ids": ids}, headers=auth)
    body = res.json()
    assert body["done"] == 2 and len(body["failed"]) == 1 and body["failed"][0]["id"] == ids[0]

    paid = await client.post(
        "/api/v1/admin/affiliate-program/commissions/bulk",
        json={"action": "pay", "ids": ids, "payout_reference": "BATCH-1"}, headers=auth,
    )
    assert paid.json()["done"] == 3


# ------------------------------------------------------------------ admin API


async def test_only_the_right_roles_can_change_rates_or_see_the_queue(client, db_session):
    base = "/api/v1/admin/affiliate-program"
    cust = {"Authorization": "Bearer " + await _staff_token(client, db_session, "c1@example.com", "customer")}
    fin = {"Authorization": "Bearer " + await _staff_token(client, db_session, "f1@example.com", "finance_officer")}
    mgr = {"Authorization": "Bearer " + await _staff_token(client, db_session, "m1@example.com", "management")}

    assert (await client.get(f"{base}/settings", headers=cust)).status_code == 403
    assert (await client.get(f"{base}/commissions", headers=cust)).status_code == 403

    assert (await client.get(f"{base}/settings", headers=fin)).status_code == 200  # finance can look
    assert (await client.patch(f"{base}/settings", json={"program_enabled": True}, headers=fin)).status_code == 403
    assert (await client.post(f"{base}/rules", json={"name": "x1", "rate_value": "5"}, headers=fin)).status_code == 403

    on = await client.patch(f"{base}/settings", json={"program_enabled": True, "default_rate_value": "7.5"}, headers=mgr)
    assert on.status_code == 200 and on.json()["program_enabled"] is True and Decimal(on.json()["default_rate_value"]) == Decimal("7.5")


async def test_rules_can_be_created_changed_previewed_and_removed(client, db_session):
    from app.models.customer import Customer

    base = "/api/v1/admin/affiliate-program"
    mgr = {"Authorization": "Bearer " + await _staff_token(client, db_session, "rules@example.com", "management")}
    n = next(_ids)
    partner = Customer(full_name="Partner Pat", phone=f"0715{n:06d}")
    db_session.add(partner)
    await db_session.commit()
    await client.patch(f"{base}/settings", json={"program_enabled": True, "default_rate_value": "5"}, headers=mgr)

    bad = await client.post(f"{base}/rules", json={"name": "Too much", "rate_type": "percent", "rate_value": "150"}, headers=mgr)
    assert bad.status_code == 422
    backwards = await client.post(
        f"{base}/rules", json={"name": "Backwards", "rate_value": "5", "starts_on": "2026-12-01", "ends_on": "2026-11-01"}, headers=mgr
    )
    assert backwards.status_code == 422

    created = await client.post(
        f"{base}/rules",
        json={"name": "Pat's rate", "rate_type": "percent", "rate_value": "12", "affiliate_customer_id": str(partner.id)}, headers=mgr,
    )
    assert created.status_code == 201 and created.json()["affiliate_name"] == "Partner Pat"
    rule_id = created.json()["id"]

    preview = (await client.get(f"{base}/preview", params={"referrer_customer_id": str(partner.id), "premium": "10000", "category": "motor"}, headers=mgr)).json()
    assert preview["rate_label"] == "Pat's rate" and Decimal(preview["amount"]) == Decimal("1200.00")

    changed = await client.patch(f"{base}/rules/{rule_id}", json={"rate_value": "15"}, headers=mgr)
    assert Decimal(changed.json()["rate_value"]) == Decimal("15.00")
    preview2 = (await client.get(f"{base}/preview", params={"referrer_customer_id": str(partner.id), "premium": "10000"}, headers=mgr)).json()
    assert Decimal(preview2["amount"]) == Decimal("1500.00")

    assert (await client.delete(f"{base}/rules/{rule_id}", headers=mgr)).status_code == 204
    preview3 = (await client.get(f"{base}/preview", params={"referrer_customer_id": str(partner.id), "premium": "10000"}, headers=mgr)).json()
    assert preview3["rate_label"] == "Default rate" and Decimal(preview3["amount"]) == Decimal("500.00")


async def test_customer_finder_matches_name_phone_or_email(client, db_session):
    from app.models.customer import Customer

    mgr = {"Authorization": "Bearer " + await _staff_token(client, db_session, "finder@example.com", "management")}
    n = next(_ids)
    db_session.add(Customer(full_name="Zuberi Findable", phone=f"0718{n:06d}", email=f"zuberi{n}@example.com"))
    await db_session.commit()
    base = "/api/v1/admin/affiliate-program/customers"
    for term in ("Zuberi", f"0718{n:06d}", f"zuberi{n}@"):
        found = (await client.get(base, params={"q": term}, headers=mgr)).json()
        assert any(c["full_name"] == "Zuberi Findable" for c in found), term
    assert (await client.get(base, params={"q": "z"}, headers=mgr)).status_code == 422  # too short to search


async def test_enrol_and_suspend_an_affiliate_and_list_the_queue(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.services.affiliate_service import record_commission_for_policy

    base = "/api/v1/admin/affiliate-program"
    mgr = {"Authorization": "Bearer " + await _staff_token(client, db_session, "enrol@example.com", "management")}
    n = next(_ids)
    person = Customer(full_name="Enrol Me", phone=f"0716{n:06d}", email=f"enrol{n}@example.com")
    db_session.add(person)
    await db_session.commit()

    missing = await client.post(f"{base}/partners", json={"email": "nobody@nowhere.example"}, headers=mgr)
    assert missing.status_code == 404
    enrolled = await client.post(f"{base}/partners", json={"email": f"ENROL{n}@example.com"}, headers=mgr)
    assert enrolled.status_code == 201 and enrolled.json()["code"].startswith("AFF") and enrolled.json()["payout_phone"] == person.phone
    again = await client.post(f"{base}/partners", json={"customer_id": str(person.id)}, headers=mgr)
    assert again.json()["id"] == enrolled.json()["id"]  # enrolling twice is harmless

    suspended = await client.patch(f"{base}/partners/{enrolled.json()['id']}", json={"status": "suspended"}, headers=mgr)
    assert suspended.json()["status"] == "suspended"

    await _enable(db_session)
    _, friend, _ = await _pair(db_session)
    commission = await record_commission_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend)).id)
    queue = (await client.get(f"{base}/commissions", params={"status": "pending"}, headers=mgr)).json()
    assert queue["total"] >= 1 and any(i["id"] == str(commission.id) for i in queue["items"])
    summary = (await client.get(f"{base}/summary", headers=mgr)).json()
    assert summary["pending_count"] >= 1 and summary["affiliates"] >= 1


# ---------------------------------------------------------------- customer API


async def test_my_affiliate_overview_and_self_enrolment(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.services.affiliate_service import record_commission_for_policy

    await _enable(db_session, allow_self_enrollment=False)
    await client.post("/api/v1/auth/register", json={"full_name": "Eager Eve", "email": "eve@example.com", "password": "supersecret1"})
    token = (await client.post("/api/v1/auth/login", json={"email": "eve@example.com", "password": "supersecret1"})).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    overview = (await client.get("/api/v1/me/affiliate", headers=auth)).json()
    assert overview["program_enabled"] is True and overview["is_affiliate"] is False and overview["can_self_enroll"] is False
    assert (await client.post("/api/v1/me/affiliate/enroll", headers=auth)).status_code == 403  # invitation only

    await _enable(db_session, allow_self_enrollment=True)
    joined = (await client.post("/api/v1/me/affiliate/enroll", headers=auth)).json()
    assert joined["is_affiliate"] is True and joined["affiliate_code"].startswith("AFF")

    updated = await client.patch("/api/v1/me/affiliate", json={"payout_phone": "0712345678"}, headers=auth)
    assert updated.json()["payout_phone"] == "0712345678"

    # earnings appear, showing the referred customer's first name only
    eve = await db_session.scalar(select(Customer).where(Customer.email == "eve@example.com"))
    from app.services.referral_service import attribute_referrer

    n = next(_ids)
    friend = Customer(full_name="Wanjiru Kamau", phone=f"0717{n:06d}")
    db_session.add(friend)
    await db_session.commit()
    await attribute_referrer(db_session, joined["affiliate_code"], str(friend.id))
    await record_commission_for_policy(db_session, (await _policy(db_session, seeded_providers[0], friend, premium="20000.00")).id)

    after = (await client.get("/api/v1/me/affiliate", headers=auth)).json()
    assert after["referred"] == 1 and Decimal(after["earned_pending"]) == Decimal("1000.00")
    assert after["commissions"][0]["referred_first_name"] == "Wanjiru"
    assert "Kamau" not in str(after)


async def test_the_affiliate_changes_are_on_the_audit_trail(client, db_session):
    from app.models.audit import AuditLog

    base = "/api/v1/admin/affiliate-program"
    mgr = {"Authorization": "Bearer " + await _staff_token(client, db_session, "aud-aff@example.com", "management", "Audit Manager"), "X-Audit-Reason": "Launching the affiliate program"}
    await client.get(f"{base}/settings", headers=mgr)
    await client.patch(f"{base}/settings", json={"program_enabled": True, "default_rate_value": "6"}, headers=mgr)
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "affiliate_settings", AuditLog.action == "updated")
    )
    assert row.actor_name == "Audit Manager" and row.reason == "Launching the affiliate program"
    assert row.changes["program_enabled"][1] is True
