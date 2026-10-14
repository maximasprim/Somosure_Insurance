"""End to end: what an underwriter sees on the admin application screen.

Covers the two reported problems - "Applicant details" showing nothing even
though the customer filled in the form, and the ID number / KRA PIN never
appearing - plus the "Product" field showing "-".
"""

import io

from sqlalchemy import select

from tests.test_rbac import _register_and_assign_role


class _DemoQuotes:
    allow_demo_quote_categories = True


PADDING = ["Extra line of ordinary text so the page carries enough words to be judged."] * 4


def _pdf(lines):
    from app.services.simple_pdf import render_text_pdf

    return render_text_pdf("Document", lines + PADDING) + b"\n%" + b"padding" * 800


async def _application(client, db_session, monkeypatch, phone):
    from app.models.customer import Customer
    from app.services import quote_service

    monkeypatch.setattr(quote_service, "get_settings", lambda: _DemoQuotes())
    answers = {
        "owner_name": "Detail Test",
        "owner_phone": phone,
        "make": "Toyota",
        "model": "Axio",
        "registration_number": "KDA 123X",
        "extensions": ["excess_protector"],
    }
    quote = (await client.post("/api/v1/quotes", json={"category": "motor", "answers": answers})).json()["quotes"][0]
    customer = await db_session.scalar(select(Customer).where(Customer.phone == phone))
    res = await client.post(
        "/api/v1/applications",
        json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}},
    )
    assert res.status_code == 200
    return res.json()["id"]


async def _admin_token(client, db_session):
    return await _register_and_assign_role(client, db_session, "detail-admin@example.com", "supersecret1", "super_admin")


async def _detail(client, token, application_id):
    res = await client.get(f"/api/v1/admin/applications/{application_id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    return res.json()


async def test_applicant_details_carry_what_the_customer_submitted(client, db_session, seeded_providers, monkeypatch):
    application_id = await _application(client, db_session, monkeypatch, "0711000111")
    detail = await _detail(client, await _admin_token(client, db_session), application_id)

    details = detail["applicant_details"]
    assert details["owner_name"] == "Detail Test"
    assert details["make"] == "Toyota"
    assert details["extensions"] == ["excess_protector"]

    quote = detail["quote"]
    assert quote["product_name"]  # no longer "-": falls back to the cover summary / category
    assert quote["category"] == "motor"
    assert quote["request_reference"]


async def test_an_older_application_with_empty_details_still_shows_the_form(client, db_session, seeded_providers, monkeypatch):
    from app.models.application import Application

    application_id = await _application(client, db_session, monkeypatch, "0711000222")
    application = await db_session.get(Application, application_id)
    application.applicant_details = {}  # how applications looked before details were copied across
    await db_session.commit()

    detail = await _detail(client, await _admin_token(client, db_session), application_id)
    assert detail["applicant_details"]["owner_name"] == "Detail Test"


async def test_uploading_a_kra_pin_and_id_appends_them_and_fills_the_customer(
    client, db_session, seeded_providers, monkeypatch
):
    from app.core.config import get_settings

    # Upload screening (and the reading that follows it) is switched off for the
    # wider suite; turn it on for this test only.
    monkeypatch.setattr(get_settings(), "document_validation", "strict")

    application_id = await _application(client, db_session, monkeypatch, "0711000333")
    uploads = {
        "kra_pin": ["KENYA REVENUE AUTHORITY", "PIN CERTIFICATE", "PIN: A001234567B"],
        "national_id": ["REPUBLIC OF KENYA", "IDENTITY CARD", "ID NUMBER 12345678", "DATE OF BIRTH 01.01.1990"],
    }
    for doc_type, lines in uploads.items():
        res = await client.post(
            f"/api/v1/applications/{application_id}/documents",
            params={"document_type": doc_type},
            files={"file": (f"{doc_type}.pdf", io.BytesIO(_pdf(lines)), "application/pdf")},
        )
        assert res.status_code == 200, res.text

    detail = await _detail(client, await _admin_token(client, db_session), application_id)
    assert detail["applicant_details"]["kra_pin"] == "A001234567B"
    assert detail["applicant_details"]["national_id_number"] == "12345678"
    assert detail["applicant_details"]["_extracted"] == {"kra_pin": "kra_pin", "national_id_number": "national_id"}
    assert detail["customer"]["kra_pin"] == "A001234567B"
    assert detail["customer"]["id_number"] == "12345678"


async def test_rescan_reads_documents_that_were_uploaded_before_reading_existed(
    client, db_session, seeded_providers, monkeypatch
):
    application_id = await _application(client, db_session, monkeypatch, "0711000444")
    # Screening is off in this suite, so this upload stores the file but reads nothing.
    await client.post(
        f"/api/v1/applications/{application_id}/documents",
        params={"document_type": "kra_pin"},
        files={
            "file": (
                "kra.pdf",
                io.BytesIO(_pdf(["KENYA REVENUE AUTHORITY", "PIN CERTIFICATE", "PIN: A001234567B"])),
                "application/pdf",
            )
        },
    )
    token = await _admin_token(client, db_session)
    before = await _detail(client, token, application_id)
    assert "kra_pin" not in before["applicant_details"]

    res = await client.post(
        f"/api/v1/admin/applications/{application_id}/documents/rescan", headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["fields_found"] == ["kra_pin"]

    after = await _detail(client, token, application_id)
    assert after["applicant_details"]["kra_pin"] == "A001234567B"
    assert after["customer"]["kra_pin"] == "A001234567B"
