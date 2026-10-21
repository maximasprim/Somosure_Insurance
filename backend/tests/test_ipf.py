"""Bidii Credit IPF extras (the gaps against the IPF product deck): the 3-month minimum
term, linked/unlinked IPF with a vehicle tracker, post-dated cheques, the original
logbook, early settlement, and loan officers with their commission.

The arithmetic is pure and tested directly. The endpoint tests run against the same
real Postgres as the rest of the suite.
"""

import io
from datetime import date
from decimal import Decimal

from tests.test_quote_experience import _customer_quote, _upload
from tests.test_rbac import _register_and_assign_role

from app.services.ipf_math import (
    cheques_required,
    commission_basis,
    month_window,
    officer_commission,
    settlement_figures,
    target_progress,
)

ADMIN = "/api/v1/admin/financing"
OFFICERS = "/api/v1/admin/loan-officers"


# --- pure arithmetic -----------------------------------------------------------------------


def test_early_settlement_is_outstanding_principal_plus_the_fee_and_never_more_than_the_schedule():
    instalment = Decimal("12300.00")  # 60,000 financed over 6 months incl. interest and fees
    figures = settlement_figures(
        financed_amount=Decimal("60000"), term_months=6, unpaid_instalments=[instalment] * 4, fee_pct=Decimal("3.5")
    )
    assert figures["outstanding_principal"] == Decimal("40000.00")  # 4 of 6 slices of principal
    assert figures["fee_amount"] == Decimal("1400.00")  # 3.5% of that
    assert figures["total_due"] == Decimal("41400.00")
    assert figures["would_have_paid"] == Decimal("49200.00") and figures["saving"] == Decimal("7800.00")

    capped = settlement_figures(
        financed_amount=Decimal("60000"), term_months=6, unpaid_instalments=[instalment], fee_pct=Decimal("50")
    )
    assert capped["total_due"] == Decimal("12300.00") and capped["capped"] is True

    done = settlement_figures(financed_amount=Decimal("60000"), term_months=6, unpaid_instalments=[], fee_pct=Decimal("3.5"))
    assert done["total_due"] == 0 and done["instalments_remaining"] == 0


def test_stand_alone_ipf_needs_one_cheque_per_month_and_linked_ipf_none():
    assert cheques_required("unlinked", 6) == 6
    assert cheques_required("linked", 6) == 0


def test_loan_officer_commission_is_a_share_of_somosures_net_commission():
    assert commission_basis(policy_commission=Decimal("1500"), premium=Decimal("20000"), pct_of_premium=Decimal("10")) == Decimal("1500.00")
    assert commission_basis(policy_commission=None, premium=Decimal("20000"), pct_of_premium=Decimal("10")) == Decimal("2000.00")
    assert commission_basis(policy_commission=None, premium=Decimal("20000"), pct_of_premium=None) is None
    assert officer_commission(Decimal("2000"), Decimal("10")) == Decimal("200.00")


def test_targets_and_month_windows():
    assert month_window(date(2026, 12, 31)) == (date(2026, 12, 1), date(2027, 1, 1))
    assert target_progress(Decimal("500000"), Decimal("1000000")) == 50.0
    assert target_progress(Decimal("5"), None) is None


# --- helpers -----------------------------------------------------------------------------------


async def _staff(client, db_session, email="ipf-staff@example.com"):
    token = await _register_and_assign_role(client, db_session, email, "supersecret1", "super_admin")
    return {"Authorization": f"Bearer {token}"}


async def _apply(client, customer, quote, term=6, **extra):
    res = await client.post(
        "/api/v1/financing/applications",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": term, **extra},
    )
    return res


# --- minimum term -----------------------------------------------------------------------------------


async def test_the_default_minimum_term_is_three_months_and_a_three_month_term_is_accepted(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    settings = (await client.get(f"{ADMIN}/settings", headers=headers)).json()
    assert settings["min_term_months"] == 3 and settings["max_term_months"] == 10

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300001")
    res = await _apply(client, customer, quote, term=3)
    assert res.status_code == 200 and res.json()["term_months"] == 3
    too_short = await client.post(
        "/api/v1/financing/eligibility",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 2},
    )
    assert too_short.status_code == 400


# --- linked / unlinked, tracker, cheques, original logbook ---------------------------------------------


async def test_ipf_type_follows_the_existing_loan_and_decides_what_security_is_needed(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300002")
    standalone = (await _apply(client, customer, quote, term=6)).json()
    assert standalone["ipf_type"] == "unlinked"
    detail = (await client.get(f"{ADMIN}/applications/{standalone['id']}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 6 and detail["tracker"]["required"] is False

    customer2, quote2 = await _customer_quote(db_session, seeded_providers[0], "0788300003")
    linked = (await _apply(client, customer2, quote2, term=6, has_existing_logbook_loan=True, logbook_loan_age_months=1)).json()
    assert linked["ipf_type"] == "linked"
    detail = (await client.get(f"{ADMIN}/applications/{linked['id']}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 0 and detail["tracker"]["required"] is True

    # staff can correct the type
    changed = await client.post(f"{ADMIN}/applications/{linked['id']}/ipf-type", json={"ipf_type": "unlinked"}, headers=headers)
    assert changed.status_code == 200 and changed.json()["ipf_type"] == "unlinked" and changed.json()["cheques_required"] == 6


async def test_having_a_logbook_loan_is_not_enough_the_client_must_also_choose_to_link(client, db_session, seeded_providers):
    """Linked IPF = a recent Bidii Credit logbook loan AND choosing to link the financing to it."""
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300020")
    base = {"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6, "has_existing_logbook_loan": True, "logbook_loan_age_months": 1}

    # the choice left unanswered counts as linking - how it has always behaved
    unanswered = (await client.post("/api/v1/financing/eligibility", json=base)).json()
    assert unanswered["ipf_type"] == "linked" and unanswered["concession_applied"] is True
    assert unanswered["can_link_to_logbook_loan"] is True and Decimal(str(unanswered["deposit_amount"])) == 0

    # chose to link: no deposit, reduced terms, tracker instead of cheques
    linked = (await client.post("/api/v1/financing/eligibility", json={**base, "link_to_logbook_loan": True})).json()
    assert linked["ipf_type"] == "linked" and linked["concession_applied"] is True

    # has the loan but chose NOT to link: standard deposit and rate, like anyone else
    separate = (await client.post("/api/v1/financing/eligibility", json={**base, "link_to_logbook_loan": False})).json()
    assert separate["ipf_type"] == "unlinked" and separate["concession_applied"] is False
    assert separate["can_link_to_logbook_loan"] is True  # still offered the choice
    assert Decimal(str(separate["deposit_amount"])) > 0
    assert Decimal(str(separate["interest_rate_monthly"])) == Decimal(str(separate["standard_interest_rate_monthly"]))
    assert Decimal(str(separate["total_repayable"])) > Decimal(str(linked["total_repayable"]))

    # the application carries that decision, and with it the security that is needed
    fin_separate = (await client.post("/api/v1/financing/applications", json={**base, "link_to_logbook_loan": False})).json()
    assert fin_separate["ipf_type"] == "unlinked"
    detail = (await client.get(f"{ADMIN}/applications/{fin_separate['id']}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 6 and detail["tracker"]["required"] is False

    customer2, quote2 = await _customer_quote(db_session, seeded_providers[0], "0788300021")
    fin_linked = (await client.post("/api/v1/financing/applications", json={**base, "customer_id": str(customer2.id), "quote_id": str(quote2.id), "link_to_logbook_loan": True})).json()
    assert fin_linked["ipf_type"] == "linked"
    detail = (await client.get(f"{ADMIN}/applications/{fin_linked['id']}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 0 and detail["tracker"]["required"] is True


async def test_a_client_cannot_link_to_a_loan_they_do_not_have_or_one_that_is_too_old(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300022")
    base = {"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6}

    no_loan = (await client.post("/api/v1/financing/eligibility", json={**base, "link_to_logbook_loan": True})).json()
    assert no_loan["ipf_type"] == "unlinked" and no_loan["can_link_to_logbook_loan"] is False and no_loan["concession_applied"] is False

    too_old = (
        await client.post(
            "/api/v1/financing/eligibility",
            json={**base, "has_existing_logbook_loan": True, "logbook_loan_age_months": 24, "link_to_logbook_loan": True},
        )
    ).json()
    assert too_old["ipf_type"] == "unlinked" and too_old["can_link_to_logbook_loan"] is False and too_old["concession_applied"] is False


async def test_a_loan_can_be_linked_up_to_the_existing_loan_window_but_waivers_need_the_shorter_concession_window(
    client, db_session, seeded_providers
):
    """Defaults: existing-loan window 10 months, concession window 3. A loan in between can be linked
    (tracker, no cheques) but gets the standard deposit, rate and fees."""
    headers = await _staff(client, db_session)
    settings = (await client.get(f"{ADMIN}/settings", headers=headers)).json()
    assert settings["existing_loan_max_months"] == 10 and settings["concession_loan_age_max_months"] == 3

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300030")
    base = {"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6, "has_existing_logbook_loan": True, "logbook_loan_age_months": 6}

    # 6 months old: still within the 10-month window, past the 3-month concession window
    unanswered = (await client.post("/api/v1/financing/eligibility", json=base)).json()
    assert unanswered["can_link_to_logbook_loan"] is True and unanswered["concession_eligible"] is False
    assert unanswered["ipf_type"] == "unlinked"  # left unanswered it behaves as it always did: no waivers, not linked
    assert unanswered["existing_loan_max_months"] == 10

    linked = (await client.post("/api/v1/financing/eligibility", json={**base, "link_to_logbook_loan": True})).json()
    assert linked["ipf_type"] == "linked" and linked["concession_applied"] is False
    assert Decimal(str(linked["deposit_amount"])) > 0  # the waivers don't apply
    assert Decimal(str(linked["interest_rate_monthly"])) == Decimal(str(linked["standard_interest_rate_monthly"]))

    fin = (await client.post("/api/v1/financing/applications", json={**base, "link_to_logbook_loan": True})).json()
    assert fin["ipf_type"] == "linked"
    detail = (await client.get(f"{ADMIN}/applications/{fin['id']}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 0 and detail["tracker"]["required"] is True

    # the window's edge: 10 months can still be linked, 11 cannot
    edge = (await client.post("/api/v1/financing/eligibility", json={**base, "logbook_loan_age_months": 10, "link_to_logbook_loan": True})).json()
    assert edge["can_link_to_logbook_loan"] is True and edge["ipf_type"] == "linked"
    beyond = (await client.post("/api/v1/financing/eligibility", json={**base, "logbook_loan_age_months": 11, "link_to_logbook_loan": True})).json()
    assert beyond["can_link_to_logbook_loan"] is False and beyond["ipf_type"] == "unlinked"


async def test_the_existing_loan_window_is_a_setting_and_cannot_be_shorter_than_the_concession_window(client, db_session):
    headers = await _staff(client, db_session)
    url = f"{ADMIN}/settings"

    changed = await client.patch(url, json={"existing_loan_max_months": 12}, headers=headers)
    assert changed.status_code == 200 and changed.json()["existing_loan_max_months"] == 12

    too_short = await client.patch(url, json={"existing_loan_max_months": 2}, headers=headers)  # concession window is 3
    assert too_short.status_code == 400 and "shorter" in too_short.json()["detail"]
    widened_past_it = await client.patch(url, json={"concession_loan_age_max_months": 15}, headers=headers)
    assert widened_past_it.status_code == 400  # the concession window can't outgrow the existing-loan window either

    kept = await client.patch(url, json={"existing_loan_max_months": None}, headers=headers)
    assert kept.status_code == 200 and kept.json()["existing_loan_max_months"] == 12  # can be changed, never cleared


async def test_the_tracker_needs_its_details_and_the_original_logbook_can_be_marked_received(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300004")
    fin = (await _apply(client, customer, quote, has_existing_logbook_loan=True, logbook_loan_age_months=1)).json()
    url = f"{ADMIN}/applications/{fin['id']}"

    assert (await client.post(f"{url}/tracker", json={"installed": True}, headers=headers)).status_code == 400
    ok = await client.post(f"{url}/tracker", json={"installed": True, "provider": "Cartrack", "device_id": "CT-99812"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["tracker"]["installed"] is True and ok.json()["tracker"]["provider"] == "Cartrack"

    got = await client.post(f"{url}/original-logbook", json={"received": True}, headers=headers)
    assert got.json()["original_logbook_received_at"] is not None
    undone = await client.post(f"{url}/original-logbook", json={"received": False}, headers=headers)
    assert undone.json()["original_logbook_received_at"] is None


async def test_post_dated_cheques_can_be_recorded_updated_and_removed(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300005")
    fin = (await _apply(client, customer, quote, term=4)).json()
    base = f"{ADMIN}/applications/{fin['id']}"

    cheque = {"cheque_number": "000123", "bank_name": "Equity Bank", "amount": "7000.00", "cheque_date": "2026-12-01"}
    created = await client.post(f"{base}/cheques", json=cheque, headers=headers)
    assert created.status_code == 200 and created.json()["status"] == "received"
    assert (await client.post(f"{base}/cheques", json=cheque, headers=headers)).status_code == 409  # same cheque twice

    detail = (await client.get(f"{base}/ipf", headers=headers)).json()
    assert detail["cheques_required"] == 4 and detail["cheques_received"] == 1

    banked = await client.patch(f"{base}/cheques/{created.json()['id']}", json={"status": "banked"}, headers=headers)
    assert banked.status_code == 200 and banked.json()["status"] == "banked"

    assert (await client.delete(f"{base}/cheques/{created.json()['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"{base}/ipf", headers=headers)).json()["cheques_received"] == 0


# --- early settlement -----------------------------------------------------------------------------------


async def test_there_is_nothing_to_settle_until_the_financing_is_approved(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300006")
    fin = (await _apply(client, customer, quote)).json()  # waits for staff, so no loan yet

    quote_out = (await client.get(f"{ADMIN}/applications/{fin['id']}/early-settlement", headers=headers)).json()
    assert quote_out["eligible"] is False and "approved" in quote_out["reason"]
    res = await client.post(f"{ADMIN}/applications/{fin['id']}/early-settlement", json={}, headers=headers)
    assert res.status_code == 409


async def test_clearing_the_loan_early_waives_what_is_left_and_closes_the_agreement(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300007")
    fin = (await _apply(client, customer, quote, term=6)).json()
    approved = await client.post(f"{ADMIN}/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=headers)
    assert approved.status_code == 200

    agreement = (await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")).json()
    instalments = agreement["installments"]
    assert len(instalments) == 6
    for instalment in instalments[:2]:  # two months paid on schedule
        paid = await client.post(f"{ADMIN}/installments/{instalment['id']}/mark-paid", headers=headers)
        assert paid.status_code == 200

    quote_out = (await client.get(f"{ADMIN}/applications/{fin['id']}/early-settlement", headers=headers)).json()
    financed = Decimal(str(fin["financed_amount"]))
    expected_principal = (financed * 4 / 6).quantize(Decimal("0.01"))
    assert quote_out["eligible"] is True and quote_out["instalments_remaining"] == 4
    assert Decimal(str(quote_out["outstanding_principal"])) == expected_principal
    assert Decimal(str(quote_out["fee_pct"])) == Decimal("3.50")
    assert Decimal(str(quote_out["total_due"])) < Decimal(str(quote_out["would_have_paid"]))  # clearing early costs less

    settled = await client.post(
        f"{ADMIN}/applications/{fin['id']}/early-settlement",
        json={"payment_reference": "MPESA-QWE123", "notes": "Client paid in full"},
        headers=headers,
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["instalments_remaining"] == 4

    after = (await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")).json()
    assert after["status"] == "completed"
    assert [i["status"] for i in after["installments"]] == ["paid", "paid", "waived", "waived", "waived", "waived"]

    again = await client.post(f"{ADMIN}/applications/{fin['id']}/early-settlement", json={}, headers=headers)
    assert again.status_code == 409  # can only be settled once
    detail = (await client.get(f"{ADMIN}/applications/{fin['id']}/ipf", headers=headers)).json()
    assert detail["settlement"]["payment_reference"] == "MPESA-QWE123"
    assert detail["early_settlement"]["eligible"] is False


async def test_the_early_settlement_fee_is_a_setting(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    saved = await client.patch(f"{ADMIN}/settings", json={"early_settlement_fee_pct": "5.00"}, headers=headers)
    assert saved.status_code == 200 and Decimal(str(saved.json()["early_settlement_fee_pct"])) == Decimal("5.00")
    # it can hold a value but never be cleared
    kept = await client.patch(f"{ADMIN}/settings", json={"early_settlement_fee_pct": None}, headers=headers)
    assert kept.status_code == 200 and Decimal(str(kept.json()["early_settlement_fee_pct"])) == Decimal("5.00")

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300008")
    fin = (await _apply(client, customer, quote)).json()
    await client.post(f"{ADMIN}/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=headers)
    quote_out = (await client.get(f"{ADMIN}/applications/{fin['id']}/early-settlement", headers=headers)).json()
    assert Decimal(str(quote_out["fee_pct"])) == Decimal("5.00")


# --- loan officers and their commission ------------------------------------------------------------------


async def test_a_loan_officer_code_credits_the_sale_and_a_wrong_code_is_refused(client, db_session, seeded_providers):
    headers = await _staff(client, db_session)
    officer = await client.post(
        OFFICERS, json={"full_name": "Wanjiku Mwangi", "staff_number": "BC-014", "monthly_target": "500000"}, headers=headers
    )
    assert officer.status_code == 201
    assert (await client.post(OFFICERS, json={"full_name": "Someone Else", "staff_number": "bc-014"}, headers=headers)).status_code == 409

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300009")
    bad = await _apply(client, customer, quote, loan_officer_code="NOPE-1")
    assert bad.status_code == 400

    good = await _apply(client, customer, quote, loan_officer_code="bc-014")  # not case sensitive
    assert good.status_code == 200
    detail = (await client.get(f"{ADMIN}/applications/{good.json()['id']}/ipf", headers=headers)).json()
    assert detail["loan_officer"]["staff_number"] == "BC-014"

    summary = {o["staff_number"]: o for o in (await client.get(OFFICERS, headers=headers)).json()}
    assert summary["BC-014"]["monthly_target"] is not None and summary["BC-014"]["requests_this_month"] == 0  # not approved yet


async def test_a_financed_policy_earns_the_officer_a_share_of_somosures_commission(client, db_session, seeded_providers):
    from app.services.application_service import approve_application
    from app.services.policy_service import issue_policy

    headers = await _staff(client, db_session)
    officer = (await client.post(OFFICERS, json={"full_name": "Otieno Odhiambo", "staff_number": "BC-021"}, headers=headers)).json()

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300010")
    fin = (await _apply(client, customer, quote, loan_officer_code="BC-021")).json()
    approved = await client.post(f"{ADMIN}/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=headers)
    assert approved.status_code == 200
    assert (await client.get(f"{OFFICERS}/commissions", headers=headers)).json() == []  # no policy yet, nothing earned

    # the insurance side: application -> documents -> submit -> approve -> policy issued
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    for doc_type in ("national_id", "logbook", "kra_pin"):
        assert (await _upload(client, application["id"], doc_type)).status_code == 200
    await client.post(f"/api/v1/applications/{application['id']}/submit")
    await approve_application(db_session, application["id"])
    policy = await issue_policy(db_session, application["id"])

    rows = (await client.get(f"{OFFICERS}/commissions", headers=headers)).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["loan_officer_id"] == officer["id"] and row["policy_number"] == policy.policy_number
    assert row["status"] == "awaiting_basis" and row["commission_amount"] is None  # Somosure's net commission isn't known yet
    assert Decimal(str(row["rate_pct"])) == Decimal("10.00")

    # finance enters Somosure's net commission; the officer's 10% follows
    based = await client.post(f"{OFFICERS}/commissions/{row['id']}/basis", json={"net_commission": "2000"}, headers=headers)
    assert based.status_code == 200
    assert based.json()["status"] == "pending" and Decimal(str(based.json()["commission_amount"])) == Decimal("200.00")

    # it has to be approved before it can be paid
    assert (await client.post(f"{OFFICERS}/commissions/{row['id']}/transition", json={"to_status": "paid"}, headers=headers)).status_code == 409
    assert (await client.post(f"{OFFICERS}/commissions/{row['id']}/transition", json={"to_status": "approved"}, headers=headers)).status_code == 200
    paid = await client.post(
        f"{OFFICERS}/commissions/{row['id']}/transition", json={"to_status": "paid", "payout_reference": "PAY-77"}, headers=headers
    )
    assert paid.status_code == 200 and paid.json()["status"] == "paid" and paid.json()["payout_reference"] == "PAY-77"
    assert (await client.post(f"{OFFICERS}/commissions/{row['id']}/basis", json={"net_commission": "5000"}, headers=headers)).status_code == 409

    summary = {o["staff_number"]: o for o in (await client.get(OFFICERS, headers=headers)).json()}
    assert Decimal(str(summary["BC-021"]["commission_paid"])) == Decimal("200.00")


async def test_a_percentage_of_premium_setting_works_out_somosures_commission_automatically(client, db_session, seeded_providers):
    from app.services.application_service import approve_application
    from app.services.policy_service import issue_policy

    headers = await _staff(client, db_session)
    await client.patch(f"{ADMIN}/settings", json={"somosure_commission_pct_of_premium": "10"}, headers=headers)
    await client.post(OFFICERS, json={"full_name": "Auto Calc", "staff_number": "BC-030"}, headers=headers)

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788300011")
    fin = (await _apply(client, customer, quote, loan_officer_code="BC-030")).json()
    await client.post(f"{ADMIN}/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=headers)
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    for doc_type in ("national_id", "logbook", "kra_pin"):
        await _upload(client, application["id"], doc_type)
    await client.post(f"/api/v1/applications/{application['id']}/submit")
    await approve_application(db_session, application["id"])
    await issue_policy(db_session, application["id"])

    row = (await client.get(f"{OFFICERS}/commissions", headers=headers)).json()[0]
    # premium on the helper's quote is 25,862.00: 10% of it is Somosure's commission, 10% of that is the officer's
    assert Decimal(str(row["somosure_net_commission"])) == Decimal("2586.20")
    assert Decimal(str(row["commission_amount"])) == Decimal("258.62") and row["status"] == "pending"


async def test_only_finance_and_management_roles_reach_these_endpoints(client, db_session):
    assert (await client.get(OFFICERS)).status_code == 401
    token = await _register_and_assign_role(client, db_session, "uw-ipf@example.com", "supersecret1", "underwriter")
    assert (await client.get(OFFICERS, headers={"Authorization": f"Bearer {token}"})).status_code == 403


# --- Last expense is announced but not quotable --------------------------------------------------------------


async def test_last_expense_is_listed_as_coming_soon_and_never_quoted(client, seeded_providers):
    categories = (await client.get("/api/v1/quotes/availability")).json()["categories"]
    assert categories["last_expense"] == {"available": False, "mode": "coming_soon"}
    res = await client.post("/api/v1/quotes", json={"category": "last_expense", "answers": {"phone": "0700111222"}})
    assert res.status_code == 422 and "coming soon" in res.json()["detail"]
