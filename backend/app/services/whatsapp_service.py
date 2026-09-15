from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Communication
from app.models.customer import Customer
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.whatsapp.registry import get_whatsapp_adapter

# Minimal keyword routing (spec §17's use cases) - not NLP. A real
# deployment handling ambiguous free text would want proper intent
# classification; this is a skeleton proving the conversation → CRM
# linkage works, not a finished bot.
KEYWORD_RESPONSES = {
    "quote": "To get a quote, visit our website or reply with what you'd like to insure (car, health, home, etc).",
    "claim": "To report a claim, please call our claims line or visit your account at somosure.co.ke/claims.",
    "agent": "Connecting you to an agent - someone will respond shortly.",
    "status": "To check your policy or application status, please log in to your account at somosure.co.ke/dashboard.",
}
DEFAULT_RESPONSE = "Thanks for reaching out to Somosure! Reply with 'quote', 'claim', 'status', or 'agent' and we'll help."


async def get_or_create_conversation(db: AsyncSession, phone_number: str) -> WhatsAppConversation:
    conversation = await db.scalar(select(WhatsAppConversation).where(WhatsAppConversation.phone_number == phone_number))
    if conversation:
        return conversation

    # Match or create a guest Customer by phone - same pattern as the
    # quote engine's guest resolution (app/services/quote_service.py).
    customer = await db.scalar(select(Customer).where(Customer.phone == phone_number))
    if not customer:
        customer = Customer(full_name="WhatsApp Guest", phone=phone_number, lead_source="whatsapp")
        db.add(customer)
        await db.flush()

    conversation = WhatsAppConversation(phone_number=phone_number, customer_id=customer.id, state="idle")
    db.add(conversation)
    await db.flush()
    return conversation


async def handle_inbound_message(db: AsyncSession, phone_number: str, body: str, provider_message_id: str | None, raw_payload: dict) -> dict:
    conversation = await get_or_create_conversation(db, phone_number)
    conversation.last_message_at = datetime.now(timezone.utc)

    db.add(
        WhatsAppMessage(
            conversation_id=conversation.id, direction="inbound", body=body,
            provider_message_id=provider_message_id, raw_payload=raw_payload,
        )
    )

    if conversation.customer_id:
        db.add(Communication(customer_id=conversation.customer_id, channel="whatsapp", direction="inbound", body=body))

    # Route on the first matching keyword; default otherwise.
    lowered = body.lower()
    reply_body = next((resp for kw, resp in KEYWORD_RESPONSES.items() if kw in lowered), DEFAULT_RESPONSE)

    adapter = get_whatsapp_adapter()
    send_result = await adapter.send_text_message(phone_number, reply_body)

    db.add(
        WhatsAppMessage(
            conversation_id=conversation.id, direction="outbound", body=reply_body,
            provider_message_id=send_result.provider_message_id,
        )
    )
    if conversation.customer_id:
        db.add(Communication(customer_id=conversation.customer_id, channel="whatsapp", direction="outbound", body=reply_body))

    await db.commit()
    return {"conversation_id": str(conversation.id), "reply_sent": reply_body, "is_mock": send_result.is_mock}
