import hashlib
import hmac
import json

from sqlalchemy import select


async def test_webhook_verification_challenge_succeeds_with_correct_token(client):
    """Proves the REAL Meta verification mechanism works - this exact
    request shape is what Meta's App Dashboard sends when configuring a
    webhook URL."""
    res = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "somosure-dev-verify-token", "hub.challenge": "12345"},
    )
    assert res.status_code == 200
    assert res.text == "12345"


async def test_webhook_verification_fails_with_wrong_token(client):
    res = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "12345"},
    )
    assert res.status_code == 403


async def test_webhook_verification_fails_with_wrong_mode(client):
    res = await client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "unsubscribe", "hub.verify_token": "somosure-dev-verify-token", "hub.challenge": "12345"},
    )
    assert res.status_code == 403


def test_signature_verification_logic_directly():
    """Unit-level proof that verify_signature implements Meta's real
    HMAC-SHA256 scheme correctly, independent of the HTTP layer."""
    from app.whatsapp.base import verify_signature

    app_secret = "test-app-secret"
    payload = b'{"test": "payload"}'
    correct_signature = "sha256=" + hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_signature(app_secret, payload, correct_signature) is True
    assert verify_signature(app_secret, payload, "sha256=wrongsignature") is False
    assert verify_signature(app_secret, payload, None) is False
    assert verify_signature(app_secret, payload, "not-even-sha256-prefixed") is False
    # Tampered payload should fail even with a signature that was valid
    # for the original payload - proves it's actually checking the body,
    # not just the header format.
    assert verify_signature(app_secret, b'{"test": "tampered"}', correct_signature) is False


async def test_inbound_message_creates_conversation_and_customer(client, db_session):
    from app.models.crm import Communication
    from app.models.customer import Customer
    from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage

    payload = {
        "entry": [{"changes": [{"value": {"messages": [{"from": "254700111222", "id": "wamid.123", "text": {"body": "I need a quote"}}]}}]}]
    }

    res = await client.post("/api/v1/webhooks/whatsapp", content=json.dumps(payload).encode())
    assert res.status_code == 200
    assert res.json()["processed"] == 1

    customer = await db_session.scalar(select(Customer).where(Customer.phone == "254700111222"))
    assert customer is not None
    assert customer.lead_source == "whatsapp"

    conversation = await db_session.scalar(select(WhatsAppConversation).where(WhatsAppConversation.phone_number == "254700111222"))
    assert conversation is not None
    assert conversation.customer_id == customer.id

    messages = (await db_session.scalars(select(WhatsAppMessage).where(WhatsAppMessage.conversation_id == conversation.id))).all()
    assert len(messages) == 2  # inbound + the routed reply
    assert messages[0].direction == "inbound"
    assert messages[0].body == "I need a quote"
    assert messages[1].direction == "outbound"
    assert "quote" in messages[1].body.lower()

    communications = (await db_session.scalars(select(Communication).where(Communication.customer_id == customer.id))).all()
    assert len(communications) == 2, "both inbound and outbound should mirror into CRM Communication history"


async def test_repeat_message_reuses_same_conversation(client, db_session):
    from app.models.whatsapp import WhatsAppConversation

    payload_1 = {"entry": [{"changes": [{"value": {"messages": [{"from": "254700333444", "id": "wamid.1", "text": {"body": "hello"}}]}}]}]}
    payload_2 = {"entry": [{"changes": [{"value": {"messages": [{"from": "254700333444", "id": "wamid.2", "text": {"body": "claim status?"}}]}}]}]}

    await client.post("/api/v1/webhooks/whatsapp", content=json.dumps(payload_1).encode())
    await client.post("/api/v1/webhooks/whatsapp", content=json.dumps(payload_2).encode())

    conversations = (
        await db_session.scalars(select(WhatsAppConversation).where(WhatsAppConversation.phone_number == "254700333444"))
    ).all()
    assert len(conversations) == 1, "the same phone number should reuse one conversation, not create duplicates"


async def test_admin_can_view_conversations_and_messages(client, db_session):
    import uuid

    from app.models.user import Role, User, UserRole
    from app.core.security import hash_password

    payload = {"entry": [{"changes": [{"value": {"messages": [{"from": "254700555666", "id": "wamid.3", "text": {"body": "agent please"}}]}}]}]}
    await client.post("/api/v1/webhooks/whatsapp", content=json.dumps(payload).encode())

    await client.post("/api/v1/auth/register", json={"full_name": "Support Staff", "email": "support@example.com", "password": "supersecret1"})
    user = await db_session.scalar(select(User).where(User.email == "support@example.com"))
    role = Role(id=uuid.uuid4(), name="customer_support")
    db_session.add(role)
    await db_session.flush()
    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": "support@example.com", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    conv_res = await client.get("/api/v1/admin/whatsapp/conversations", headers=headers)
    assert conv_res.status_code == 200
    assert len(conv_res.json()) == 1
    conversation_id = conv_res.json()[0]["id"]

    msg_res = await client.get(f"/api/v1/admin/whatsapp/conversations/{conversation_id}/messages", headers=headers)
    assert msg_res.status_code == 200
    assert len(msg_res.json()) == 2
