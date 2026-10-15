"""Financing is its own approval - not a by-product of the insurance application's.

Covers: a new Bidii Credit request waits for staff (instead of approving itself the
moment the customer applies), approving the insurance application leaves it alone,
staff approval then creates the agreement, the switch that restores the old instant
approval, and the "replace a document we attached for you" behaviour on the last page.

Needs the same real Postgres as the rest of the suite. DOCUMENT_VALIDATION is off for
the suite, so uploads here are placeholder bytes.
"""

import io
from decimal import Decimal

from sqlalchemy import select

from tests.test_quote_experience import _customer_quote, _upload
from tests.test_rbac import _register_and_assign_role


async def _staff(client, db_session, role="super_admin", email="fin-approval@example.com"):
    return await _register_and_assign_role(client, db_session, email, "supersecret1", role)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _apply_for_financing(client, customer, quote, term=6):
    res = await client.post(
        "/api/v1/financing/applications",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": term},
    )
    assert res.status_code == 200, res.text
    return res.json()


# --- a new request waits for staff ------------------------------------------------


async def test_a_new_financing_request_waits_for_staff_instead_of_approving_itself(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200001")
    fin = await _apply_for_financing(client, customer, quote)

    assert fin["status"] == "submitted"
    # no agreement or repayment schedule exists until somebody approves it
    assert (await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")).status_code == 404

    token = await _staff(client, db_session)
    detail = (await client.get(f"/api/v1/admin/financing/applications/{fin['id']}", headers=_auth(token))).json()
    assert detail["status"] == "submitted"
    assert "awaiting_staff_approval" in [e["event_type"] for e in detail["events"]]
    assert detail["agreement"] is None


async def test_staff_approval_creates_the_agreement(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200002")
    fin = await _apply_for_financing(client, customer, quote)
    token = await _staff(client, db_session)

    res = await client.post(
        f"/api/v1/admin/financing/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=_auth(token)
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"

    agreement = await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")
    assert agreement.status_code == 200
    assert len(agreement.json()["installments"]) == 6


async def test_staff_can_also_decline_a_financing_request(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200003")
    fin = await _apply_for_financing(client, customer, quote)
    token = await _staff(client, db_session)

    res = await client.post(
        f"/api/v1/admin/financing/applications/{fin['id']}/transition",
        json={"to_status": "rejected", "notes": "Documents incomplete"},
        headers=_auth(token),
    )
    assert res.status_code == 200 and res.json()["status"] == "rejected"
    assert (await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")).status_code == 404


async def test_a_zero_deposit_request_creates_its_staff_task_when_staff_approve_it(client, db_session, seeded_providers):
    from app.models.crm import Task

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200008")
    fin = (
        await client.post(
            "/api/v1/financing/applications",
            json={
                "customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6,
                "has_existing_logbook_loan": True, "logbook_loan_age_months": 1,
            },
        )
    ).json()
    assert fin["status"] == "submitted" and Decimal(fin["deposit_amount"]) == 0
    # nothing to chase yet - the request hasn't been approved
    assert (await db_session.scalars(select(Task).where(Task.title.contains(fin["reference"])))).all() == []

    token = await _staff(client, db_session)
    res = await client.post(
        f"/api/v1/admin/financing/applications/{fin['id']}/transition", json={"to_status": "approved"}, headers=_auth(token)
    )
    assert res.status_code == 200
    tasks = (await db_session.scalars(select(Task).where(Task.title.contains(fin["reference"])))).all()
    assert len(tasks) == 1 and tasks[0].status == "open"


# --- the two approvals are independent ------------------------------------------------


async def test_approving_the_insurance_application_does_not_approve_the_financing(client, db_session, seeded_providers):
    from app.services.application_service import approve_application

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200004")
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    for doc_type in ("national_id", "logbook", "kra_pin"):
        assert (await _upload(client, application["id"], doc_type)).status_code == 200
    fin = await _apply_for_financing(client, customer, quote)

    assert (await client.post(f"/api/v1/applications/{application['id']}/submit")).status_code == 200
    await approve_application(db_session, application["id"])  # underwriting signs off the INSURANCE

    still = (await client.get(f"/api/v1/financing/applications/{fin['id']}/status")).json()
    assert still["status"] == "submitted"  # financing still needs its own decision

    # ...and staff reviewing the insurance application can see that, side by side
    token = await _staff(client, db_session)
    insurance = (await client.get(f"/api/v1/admin/applications/{application['id']}", headers=_auth(token))).json()
    assert insurance["status"] == "approved"
    assert insurance["financing"]["reference"] == fin["reference"]
    assert insurance["financing"]["status"] == "submitted"


async def test_an_insurance_application_without_financing_shows_none(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200005")
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    token = await _staff(client, db_session)
    insurance = (await client.get(f"/api/v1/admin/applications/{application['id']}", headers=_auth(token))).json()
    assert insurance["financing"] is None


# --- the switch ------------------------------------------------------------------------------


async def test_turning_staff_approval_off_restores_instant_approval(client, db_session, seeded_providers):
    from app.services.financing_service import get_financing_settings

    settings = await get_financing_settings(db_session)
    settings.require_staff_approval = False
    await db_session.commit()

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200006")
    fin = await _apply_for_financing(client, customer, quote)
    assert fin["status"] == "approved"
    assert (await client.get(f"/api/v1/financing/applications/{fin['id']}/agreement")).status_code == 200


async def test_the_setting_can_be_changed_from_the_admin_api_and_cannot_be_cleared(client, db_session):
    token = await _staff(client, db_session)
    url = "/api/v1/admin/financing/settings"

    assert (await client.get(url, headers=_auth(token))).json()["require_staff_approval"] is True  # default

    res = await client.patch(url, json={"require_staff_approval": False}, headers=_auth(token))
    assert res.status_code == 200 and res.json()["require_staff_approval"] is False

    res = await client.patch(url, json={"require_staff_approval": None}, headers=_auth(token))
    assert res.status_code == 200 and res.json()["require_staff_approval"] is False  # null is ignored


# --- the last page: documents already on file, and replacing them -------------------------


async def test_replacing_a_document_we_attached_makes_the_new_one_count(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788200007")
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    for doc_type in ("national_id", "logbook", "kra_pin"):
        assert (await _upload(client, application["id"], doc_type)).status_code == 200
    fin = await _apply_for_financing(client, customer, quote)

    prepared = (await client.post(f"/api/v1/financing/applications/{fin['id']}/documents/prepare")).json()
    states = {i["type"]: (i["state"], i["source"]) for i in prepared["items"]}
    assert states["national_id"] == ("provided", "insurance_application")
    assert states["kra_pin"] == ("provided", "insurance_application")
    assert states["premium_quote"] == ("provided", "generated")
    assert prepared["missing"] == ["application_form"]  # the loan form is the only thing left

    # the customer chooses to replace their ID with a fresh copy
    res = await client.post(
        f"/api/v1/financing/applications/{fin['id']}/documents",
        params={"document_type": "national_id"},
        files={"file": ("new_id.pdf", io.BytesIO(b"%PDF-1.4 a different, newer copy"), "application/pdf")},
    )
    assert res.status_code == 200

    after = (await client.post(f"/api/v1/financing/applications/{fin['id']}/documents/prepare")).json()
    states = {i["type"]: (i["state"], i["source"]) for i in after["items"]}
    assert states["national_id"] == ("provided", "uploaded")  # the new upload is the one in force
    assert states["kra_pin"] == ("provided", "insurance_application")  # untouched
    assert after["missing"] == ["application_form"]

    # nothing was lost: the original is still on the record for staff
    from app.models.financing import FinancingDocument

    docs = (
        await db_session.scalars(select(FinancingDocument).where(FinancingDocument.financing_application_id == fin["id"]))
    ).all()
    assert sorted(d.document_type for d in docs).count("national_id") == 2
