"""SMTPDispatcher: registry selection and graceful failure handling.
No real SMTP server involved - aiosmtplib.send is monkeypatched so this
never makes a real network call."""


def test_get_email_dispatcher_falls_back_to_mock_when_unconfigured(monkeypatch):
    from app.notifications import registry
    from app.notifications.mock_dispatcher import MockDispatcher

    monkeypatch.setattr(registry.settings, "smtp_host", "")
    monkeypatch.setattr(registry.settings, "smtp_username", "")
    monkeypatch.setattr(registry.settings, "smtp_password", "")

    assert isinstance(registry.get_email_dispatcher(), MockDispatcher)


def test_get_email_dispatcher_selects_smtp_when_configured(monkeypatch):
    from app.notifications import registry
    from app.notifications.smtp_dispatcher import SMTPDispatcher

    monkeypatch.setattr(registry.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(registry.settings, "smtp_username", "someone@example.com")
    monkeypatch.setattr(registry.settings, "smtp_password", "app-password")

    dispatcher = registry.get_email_dispatcher()
    assert isinstance(dispatcher, SMTPDispatcher)
    assert dispatcher.host == "smtp.example.com"


def test_get_email_dispatcher_does_not_activate_on_partial_config(monkeypatch):
    """Host set but no username/password yet (mid-setup) should not
    silently try to send through an unauthenticated connection."""
    from app.notifications import registry
    from app.notifications.mock_dispatcher import MockDispatcher

    monkeypatch.setattr(registry.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(registry.settings, "smtp_username", "")
    monkeypatch.setattr(registry.settings, "smtp_password", "")

    assert isinstance(registry.get_email_dispatcher(), MockDispatcher)


async def test_smtp_send_failure_returns_dispatch_result_not_an_exception(monkeypatch):
    """A down/misconfigured SMTP server must never crash the caller
    (e.g. forgot-password) - send_email should catch and report the
    failure, not raise."""
    import app.notifications.smtp_dispatcher as smtp_module
    from app.notifications.smtp_dispatcher import SMTPDispatcher

    async def _boom(*args, **kwargs):
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(smtp_module.aiosmtplib, "send", _boom)

    dispatcher = SMTPDispatcher(
        host="smtp.example.com", port=587, username="u", password="p",
        from_email="u@example.com", from_name="Somosure", use_tls=True,
    )
    result = await dispatcher.send_email("customer@example.com", "Subject", "Body")

    assert result.delivered is False
    assert result.is_mock is False
    assert "nope" in result.error


async def test_smtp_send_success_marks_is_mock_false(monkeypatch):
    import app.notifications.smtp_dispatcher as smtp_module
    from app.notifications.smtp_dispatcher import SMTPDispatcher

    async def _ok(*args, **kwargs):
        return None

    monkeypatch.setattr(smtp_module.aiosmtplib, "send", _ok)

    dispatcher = SMTPDispatcher(
        host="smtp.example.com", port=587, username="u", password="p",
        from_email="u@example.com", from_name="Somosure", use_tls=True,
    )
    result = await dispatcher.send_email("customer@example.com", "Subject", "Body")

    assert result.delivered is True
    assert result.is_mock is False
