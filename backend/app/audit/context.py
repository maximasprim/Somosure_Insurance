"""The request-scoped audit context.

Set by the audit middleware at the start of a request and read by the change
listeners and by record_event(). Outside a request (seed scripts, background
jobs) there is no context, and rows are attributed to "system".
"""

import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AuditContext:
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str | None = None
    path: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    reason: str | None = None

    actor_type: str = "guest"  # staff | customer | guest | system
    actor_user_id: str | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None

    # Explicit events recorded during the request (record_event); written by
    # the middleware together with the request row.
    events: list[dict[str, Any]] = field(default_factory=list)
    # Extra facts for the request row (e.g. the email tried on a failed login).
    details: dict[str, Any] = field(default_factory=dict)


audit_ctx: ContextVar[AuditContext | None] = ContextVar("audit_ctx", default=None)

STAFF_ROLES_EXCLUDED = {"customer", "partner"}


def current_context() -> AuditContext | None:
    return audit_ctx.get()


def bind_actor(
    user_id: str | None,
    role: str | None,
    name: str | None = None,
    email: str | None = None,
) -> None:
    """Attribute the rest of this request to a known user - used where the
    request itself carries no token yet (e.g. the login request)."""
    ctx = audit_ctx.get()
    if not ctx:
        return
    ctx.actor_user_id = str(user_id) if user_id else None
    ctx.actor_role = role
    ctx.actor_name = name
    ctx.actor_email = email
    ctx.actor_type = "customer" if (role in STAFF_ROLES_EXCLUDED or not role) else "staff"


def note(**details: Any) -> None:
    """Attach extra facts to this request's audit row."""
    ctx = audit_ctx.get()
    if ctx:
        ctx.details.update({k: v for k, v in details.items() if v is not None})


def record_event(
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: Any = None,
    entity_label: str | None = None,
    summary: str | None = None,
    reason: str | None = None,
    related_customer_id: Any = None,
    **details: Any,
) -> None:
    """Record something that isn't a plain data change - a document being
    opened, a report exported, a bulk delete, a sign-in. Safe to call from any
    request handler; does nothing outside a request."""
    ctx = audit_ctx.get()
    if not ctx:
        return
    ctx.events.append(
        {
            "occurred_at": datetime.now(timezone.utc),
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "entity_label": entity_label,
            "summary": summary or action,
            "reason": reason or ctx.reason,
            "related_customer_id": str(related_customer_id) if related_customer_id else None,
            "details": details or None,
        }
    )


_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# Lookahead (not a consumed slash) so back-to-back ids like
# /applications/<id>/documents/<id> are both found.
_ENTITY_IN_PATH = re.compile(rf"/([a-z][a-z0-9\-_]*)/({_UUID})(?=/|$)")


def entity_from_path(path: str) -> tuple[str | None, str | None]:
    """Best-effort 'which record is this URL about' - the LAST id in the path
    and the collection name before it (…/applications/<id>/approve →
    ('applications', <id>)). Used only for request rows; change rows carry the
    exact record."""
    matches = _ENTITY_IN_PATH.findall(path)
    if not matches:
        return None, None
    collection, ident = matches[-1]
    return collection.replace("-", "_"), ident
