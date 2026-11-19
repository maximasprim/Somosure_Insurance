"""One function per AutomationRule.action_type. Each takes the run's
context dict (whatever emit_event was called with) and the action_config
from the rule, and returns a result dict logged onto the AutomationRun.

Adding a new action type means adding a function here and registering it
in ACTIONS below - the engine itself (app/automation/engine.py) doesn't
change.
"""

import logging
import random
import string
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Task
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.sticker import Sticker, StickerEvent
from app.notifications.registry import get_dispatcher

logger = logging.getLogger("somosure.automation.actions")


async def send_notification(db: AsyncSession, context: dict, config: dict) -> dict:
    customer_id = context.get("customer_id")
    if not customer_id:
        return {"skipped": "no customer_id in context"}

    channel = config.get("channel", "in_app")
    body = config.get("body_template", "").format(**context) if config.get("body_template") else config.get("body", "")
    subject = config.get("subject")

    notification = Notification(
        customer_id=customer_id, channel=channel, event_type=context.get("event", "unknown"),
        subject=subject, body=body, status="pending",
    )
    db.add(notification)
    await db.flush()

    # in_app notifications are "delivered" simply by existing in the table
    # (visible at /api/v1/me/notifications) - no external dispatch needed.
    if channel == "in_app":
        notification.status = "sent"
        notification.sent_at = datetime.now(timezone.utc)
        return {"notification_id": str(notification.id), "channel": "in_app"}

    customer = await db.get(Customer, customer_id)
    if not customer:
        notification.status = "failed"
        return {"notification_id": str(notification.id), "error": "customer not found"}

    dispatcher = get_dispatcher()
    try:
        if channel == "sms":
            if not customer.phone:
                notification.status = "failed"
                return {"notification_id": str(notification.id), "error": "customer has no phone number"}
            result = await dispatcher.send_sms(customer.phone, body)
        elif channel == "email":
            if not customer.email:
                notification.status = "failed"
                return {"notification_id": str(notification.id), "error": "customer has no email"}
            result = await dispatcher.send_email(customer.email, subject or "", body)
        else:
            notification.status = "failed"
            return {"notification_id": str(notification.id), "error": f"unsupported channel '{channel}'"}

        notification.status = "sent" if result.delivered else "failed"
        if result.delivered:
            notification.sent_at = datetime.now(timezone.utc)
        return {
            "notification_id": str(notification.id),
            "delivered": result.delivered,
            "provider_message_id": result.provider_message_id,
            "is_mock": result.is_mock,
        }
    except Exception as e:
        logger.exception("Notification dispatch failed for %s", notification.id)
        notification.status = "failed"
        return {"notification_id": str(notification.id), "error": str(e)}


async def create_task(db: AsyncSession, context: dict, config: dict) -> dict:
    task = Task(
        title=config.get("title_template", "Follow up").format(**context),
        lead_id=context.get("lead_id"),
        assigned_to_user_id=config.get("assigned_to_user_id"),
        status="open",
    )
    db.add(task)
    await db.flush()
    return {"task_id": str(task.id)}


def _as_date(value) -> date | None:
    """A date, or the ISO text of one (event context is stored as JSON, which has no dates)."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(value) if isinstance(value, str) and value else None


async def generate_sticker(db: AsyncSession, context: dict, config: dict) -> dict:
    policy_id = context.get("policy_id")
    if not policy_id:
        return {"skipped": "no policy_id in context"}

    valid_from, valid_to = _as_date(context.get("valid_from")), _as_date(context.get("valid_to"))
    reference = f"SOM-STK-{date.today().year}-{''.join(random.choices(string.digits, k=6))}"
    sticker = Sticker(
        reference=reference,
        policy_id=policy_id,
        status="pending",
        qr_payload=f"{reference}|{context.get('policy_number', '')}",
        valid_from=valid_from,
        valid_to=valid_to,
        # Set when this sticker is one month of a monthly payment plan (see
        # payment_service) or the one-month cover of a policy still waiting for
        # its valuation report; otherwise both stay NULL, meaning "covers the
        # whole policy term" as before.
    )
    db.add(sticker)
    await db.flush()
    note = "Auto-created on policy activation"
    if context.get("provisional"):
        note = f"One-month sticker {valid_from} to {valid_to}: valuation report not yet received"
    elif valid_from:
        note = f"Auto-created for monthly plan cover {valid_from} to {valid_to}"
    db.add(StickerEvent(sticker_id=sticker.id, from_status=None, to_status="pending", notes=note))
    return {"sticker_id": str(sticker.id), "reference": reference}


ACTIONS = {
    "send_notification": send_notification,
    "create_task": create_task,
    "generate_sticker": generate_sticker,
}
