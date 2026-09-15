from app.automation.actions import send_notification
from app.notifications.mock_dispatcher import MockDispatcher


async def test_mock_dispatcher_sends_sms():
    dispatcher = MockDispatcher()
    result = await dispatcher.send_sms("0700000000", "Test message")
    assert result.delivered is True
    assert result.is_mock is True
    assert result.provider_message_id is not None


async def test_send_notification_sms_marks_sent_when_customer_has_phone(db_session):
    from app.models.customer import Customer

    customer = Customer(full_name="Notify Test", phone="0700123456")
    db_session.add(customer)
    await db_session.commit()

    result = await send_notification(
        db_session,
        context={"customer_id": str(customer.id), "event": "test.event"},
        config={"channel": "sms", "body_template": "Hello {event}"},
    )
    await db_session.commit()

    assert "notification_id" in result
    assert result["delivered"] is True

    from sqlalchemy import select

    from app.models.notification import Notification

    notification = await db_session.get(Notification, result["notification_id"])
    assert notification.status == "sent"
    assert notification.sent_at is not None
    assert notification.body == "Hello test.event"


async def test_send_notification_sms_fails_gracefully_without_phone(db_session):
    from app.models.customer import Customer

    customer = Customer(full_name="No Phone Test", phone="")
    db_session.add(customer)
    await db_session.commit()

    result = await send_notification(
        db_session,
        context={"customer_id": str(customer.id), "event": "test.event"},
        config={"channel": "sms", "body": "Hello"},
    )
    await db_session.commit()

    assert "error" in result

    from app.models.notification import Notification

    notification = await db_session.get(Notification, result["notification_id"])
    assert notification.status == "failed"


async def test_in_app_notification_does_not_need_dispatch(db_session):
    from app.models.customer import Customer

    customer = Customer(full_name="In App Test", phone="0700999888")
    db_session.add(customer)
    await db_session.commit()

    result = await send_notification(
        db_session,
        context={"customer_id": str(customer.id), "event": "test.event"},
        config={"channel": "in_app", "body": "Hello"},
    )
    await db_session.commit()

    assert result["channel"] == "in_app"

    from app.models.notification import Notification

    notification = await db_session.get(Notification, result["notification_id"])
    assert notification.status == "sent"
