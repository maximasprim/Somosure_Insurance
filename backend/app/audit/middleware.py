"""HTTP-level auditing (pure ASGI, so uploads and streaming are untouched).

For every request that changes data - and for sensitive reads (opening an
uploaded document, exports) - this:
  1. works out WHO is calling (from the bearer token) and from WHERE;
  2. captures the staff member's stated REASON: the X-Audit-Reason header, or
     the `reason` / `notes` field of a small JSON body (the body itself is
     never stored);
  3. makes that context available to the change listeners, so every record
     changed during the request is stamped with the same actor and reason;
  4. after the response, writes one request row (method, route, outcome,
     status, IP, timing) plus any explicit events - including for refused or
     failed attempts, which never reach the database layer.

Nothing in here is allowed to break the request: all failures are logged and
swallowed.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from jose import JWTError, jwt

from app.audit.capture import _build_row
from app.audit.context import AuditContext, audit_ctx, entity_from_path
from app.core.config import get_settings

logger = logging.getLogger("somosure.audit")

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
BODY_LIMIT = 256 * 1024
REASON_KEYS = ("reason", "rejection_reason", "cancellation_reason", "override_reason", "notes", "note", "comment")
_SENSITIVE_READ = re.compile(r"/documents/[^/]+/(url|download)$|export")

_USER_CACHE: dict[str, tuple[float, tuple[str | None, str | None]]] = {}
_USER_TTL = 300.0


def is_sensitive_read(path: str) -> bool:
    return bool(_SENSITIVE_READ.search(path))


def extract_reason(headers: dict[str, str], body: bytes | None) -> str | None:
    """The stated reason for an action, if any. Header wins; otherwise the
    first non-empty reason-like field of a JSON object body."""
    # The admin UI URL-encodes the header so non-ASCII text survives HTTP.
    header = unquote(headers.get("x-audit-reason") or "").strip()
    if header:
        return header[:1000]
    if not body:
        return None
    try:
        data = json.loads(body)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for key in REASON_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
    return None


def _client_ip(scope, headers: dict[str, str]) -> str | None:
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    client = scope.get("client")
    return client[0][:64] if client else None


def _read_actor(headers: dict[str, str]) -> tuple[str | None, str | None]:
    """(user_id, role) from a valid access token, else (None, None)."""
    auth = headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    settings = get_settings()
    try:
        claims = jwt.decode(auth[7:].strip(), settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None, None
    if claims.get("type") != "access":
        return None, None
    return claims.get("sub"), claims.get("role")


async def _lookup_user(factory, user_id: str) -> tuple[str | None, str | None]:
    cached = _USER_CACHE.get(user_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        from app.models.user import User

        async with factory() as session:
            user = await session.get(User, user_id)
            result = (user.full_name, user.email) if user else (None, None)
    except Exception:
        logger.debug("audit: could not look up actor %s", user_id, exc_info=True)
        return None, None
    _USER_CACHE[user_id] = (time.monotonic() + _USER_TTL, result)
    return result


def _summary_for(method: str, path: str, template: str, status: int) -> str:
    if method == "GET" and re.search(r"/documents/[^/]+/(url|download)$", path):
        what = "Opened an uploaded document"
    elif "export" in path:
        what = "Exported data"
    else:
        what = f"{method} {template}"
    return f"{what} → {status}"


class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        settings = get_settings()
        if scope["type"] != "http" or not settings.audit_enabled:
            return await self.app(scope, receive, send)

        method, path = scope["method"], scope["path"]
        if not path.startswith("/api/") or method in ("OPTIONS", "HEAD"):
            return await self.app(scope, receive, send)

        mutating = method in MUTATING
        sensitive = method == "GET" and is_sensitive_read(path)
        admin_read = method == "GET" and settings.audit_log_reads and "/admin/" in path
        if not (mutating or sensitive or admin_read):
            return await self.app(scope, receive, send)

        started = time.monotonic()
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        factory = None
        try:
            factory = self._factory(scope)
        except Exception:
            logger.debug("audit: no session factory", exc_info=True)

        ctx = AuditContext(
            method=method,
            path=path,
            ip=_client_ip(scope, headers),
            user_agent=headers.get("user-agent"),
        )
        try:
            user_id, role = _read_actor(headers)
            if user_id:
                ctx.actor_user_id = str(user_id)
                ctx.actor_role = role
                ctx.actor_type = "customer" if role in (None, "customer", "partner") else "staff"
                if factory:
                    ctx.actor_name, ctx.actor_email = await _lookup_user(factory, str(user_id))
            elif "webhook" in path:
                ctx.actor_type, ctx.actor_name = "system", "Payment/WhatsApp webhook"
        except Exception:
            logger.debug("audit: could not resolve actor", exc_info=True)

        # Capture the stated reason; only small JSON bodies are looked at, and
        # the body is replayed untouched for the real handler.
        replay_receive = receive
        try:
            content_type = headers.get("content-type", "")
            if mutating and content_type.startswith("application/json"):
                buffered: list[dict[str, Any]] = []
                total, complete = 0, False
                while True:
                    message = await receive()
                    buffered.append(message)
                    if message["type"] != "http.request":
                        break
                    total += len(message.get("body", b""))
                    if not message.get("more_body"):
                        complete = True
                        break
                    if total > BODY_LIMIT:
                        break

                async def replay():
                    if buffered:
                        return buffered.pop(0)
                    return await receive()

                replay_receive = replay
                body = b"".join(m.get("body", b"") for m in buffered if m["type"] == "http.request") if complete else None
                ctx.reason = extract_reason(headers, body)
            else:
                ctx.reason = extract_reason(headers, None)
        except Exception:
            logger.debug("audit: could not read reason", exc_info=True)

        status_holder = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        token = audit_ctx.set(ctx)
        try:
            await self.app(scope, replay_receive, send_wrapper)
        finally:
            audit_ctx.reset(token)
            try:
                await self._persist(scope, ctx, status_holder["code"], started, factory, mutating)
            except Exception:
                logger.exception("audit: failed to write request row")

    @staticmethod
    def _factory(scope):
        app = scope.get("app")
        factory = getattr(getattr(app, "state", None), "audit_session_factory", None)
        if factory is None:
            from app.core.database import AsyncSessionLocal

            factory = AsyncSessionLocal
        return factory

    async def _persist(self, scope, ctx: AuditContext, status: int, started: float, factory, mutating: bool) -> None:
        if factory is None:
            return
        settings = get_settings()
        rows = []
        for ev in ctx.events:
            row = _build_row(
                "event", ev["action"], ev["occurred_at"], ctx, ev["entity_type"], ev["entity_id"], ev["entity_label"],
                ev["related_customer_id"], ev["summary"], None, reason=ev["reason"], details=ev["details"],
            )
            row.status_code = status
            rows.append(row)

        guest_mutation = ctx.actor_type == "guest" and mutating
        if not (guest_mutation and not settings.audit_log_guest_requests):
            route = scope.get("route")
            template = getattr(route, "path", None) or ctx.path
            entity_type, entity_id = entity_from_path(ctx.path)
            request_row = _build_row(
                "request", f"{ctx.method} {template}", datetime.now(timezone.utc), ctx, entity_type, entity_id, None,
                None, _summary_for(ctx.method, ctx.path, template, status), None, details=ctx.details or None,
            )
            request_row.status_code = status
            request_row.duration_ms = int((time.monotonic() - started) * 1000)
            rows.append(request_row)

        if not rows:
            return
        async with factory() as session:
            session.add_all(rows)
            await session.commit()
