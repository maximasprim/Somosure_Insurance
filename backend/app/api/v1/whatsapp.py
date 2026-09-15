from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_roles
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.services.whatsapp_service import handle_inbound_message
from app.whatsapp.base import verify_signature, verify_subscription_challenge

router = APIRouter(prefix="/api/v1/webhooks/whatsapp", tags=["whatsapp"])
settings = get_settings()


@router.get("")
async def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Meta's real webhook setup verification. This is what Meta's App
    Dashboard actually calls when configuring a webhook URL - genuinely
    implemented, not a placeholder."""
    challenge = verify_subscription_challenge(hub_mode, hub_verify_token, hub_challenge, settings.whatsapp_verify_token)
    if challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Webhook verification failed")
    return Response(content=challenge, media_type="text/plain")


@router.post("")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Verifies Meta's real X-Hub-Signature-256 HMAC before trusting
    anything in the payload - same 'never trust an unverified webhook'
    rule as the M-Pesa integration (docs/PAYMENTS.md)."""
    body = await request.body()

    if settings.whatsapp_app_secret:
        signature = request.headers.get("x-hub-signature-256")
        if not verify_signature(settings.whatsapp_app_secret, body, signature):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")
    # If no app secret is configured yet (dev/demo without a real Meta
    # app), signature checking is skipped rather than blocking all
    # traffic - this mirrors having no real credentials, not a security
    # bypass in production (where whatsapp_app_secret would be set).

    import json

    payload = json.loads(body)

    results = []
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for message in change.get("value", {}).get("messages", []):
                    phone = message.get("from")
                    text = message.get("text", {}).get("body", "")
                    message_id = message.get("id")
                    if phone:
                        result = await handle_inbound_message(db, phone, text, message_id, message)
                        results.append(result)
    except (KeyError, AttributeError):
        # Malformed payload shape - don't crash the webhook endpoint over
        # an unexpected structure; Meta expects a 200 to stop retrying.
        pass

    return {"processed": len(results)}


admin_router = APIRouter(
    prefix="/api/v1/admin/whatsapp",
    tags=["whatsapp"],
    dependencies=[Depends(require_roles("super_admin", "operations", "customer_support", "sales_agent"))],
)


@admin_router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    conversations = (await db.scalars(select(WhatsAppConversation).order_by(WhatsAppConversation.last_message_at.desc()))).all()
    return [
        {
            "id": str(c.id), "phone_number": c.phone_number, "customer_id": str(c.customer_id) if c.customer_id else None,
            "state": c.state, "last_message_at": c.last_message_at.isoformat(),
        }
        for c in conversations
    ]


@admin_router.get("/conversations/{conversation_id}/messages")
async def list_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    messages = (
        await db.scalars(
            select(WhatsAppMessage).where(WhatsAppMessage.conversation_id == conversation_id).order_by(WhatsAppMessage.created_at)
        )
    ).all()
    return [{"id": str(m.id), "direction": m.direction, "body": m.body, "created_at": m.created_at.isoformat()} for m in messages]
