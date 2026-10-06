"""Automatic change capture.

Hooks into SQLAlchemy's session so EVERY create, update and delete of a
tracked record is audited with before/after values, who did it, when and (when
the staff member gave one) why - without each service having to remember to
log. The audit rows are added to the same session, so they are committed or
rolled back together with the change itself.

Limits worth knowing:
  * Bulk SQL statements that bypass the ORM (delete(Model).where(...)) are not
    seen here. The one place the app does that (deleting a provider and its
    dependents) records an explicit summary event instead.
  * Pure history tables that already record what happened (…_events,
    lead_activities, communications, notifications, raw gateway payloads) and
    secrets (reset tokens) are skipped by default to keep the trail readable;
    adjust with AUDIT_EXCLUDED_TABLES / DEFAULT_EXCLUDED_TABLES.
"""

import logging
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.audit.context import AuditContext, current_context
from app.core.config import get_settings
from app.models.audit import AuditLog

logger = logging.getLogger("somosure.audit")

DEFAULT_EXCLUDED_TABLES = {
    "audit_logs",
    # already-a-history tables
    "application_events",
    "policy_events",
    "financing_events",
    "claim_events",
    "renewal_events",
    "sticker_events",
    "lead_activities",
    "communications",
    "notifications",
    "whatsapp_messages",
    "whatsapp_conversations",
    "automation_runs",
    # raw gateway payloads and per-quote line items (derived, very chatty)
    "payment_transactions",
    "quote_items",
    "quotes",
    # contains secrets
    "password_reset_tokens",
}

IGNORED_COLUMNS = {"updated_at", "created_at"}
SENSITIVE_KEY = re.compile(r"(password|hashed|secret|token|api_?key|otp|credential|signature|private)", re.I)
MAX_VALUE_CHARS = 300
NOT_RECORDED = "(not recorded)"
LABEL_FIELDS = ("reference", "name", "title", "email", "full_name", "code", "phone")
PENDING_KEY = "_audit_pending"

_installed = False


def _excluded_tables() -> set[str]:
    extra = {t.strip() for t in (get_settings().audit_excluded_tables or "").split(",") if t.strip()}
    return DEFAULT_EXCLUDED_TABLES | extra


def _tracked(obj: Any) -> bool:
    table = getattr(obj, "__tablename__", None)
    return bool(table) and table not in _excluded_tables()


# ---------------------------------------------------------------- values


def clean_value(key: str, value: Any, _depth: int = 0) -> Any:
    """JSON-safe, secret-redacted, length-limited rendering of a column value."""
    if SENSITIVE_KEY.search(key or ""):
        return "[redacted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, bytes):
        return f"[{len(value)} bytes]"
    if isinstance(value, dict):
        if _depth >= 3:
            return "[nested]"
        return {str(k): clean_value(str(k), v, _depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, (list, tuple, set)):
        if _depth >= 3:
            return "[nested]"
        return [clean_value(key, v, _depth + 1) for v in list(value)[:50]]
    text = str(value)
    return text if len(text) <= MAX_VALUE_CHARS else text[:MAX_VALUE_CHARS] + "…"


def _fmt(value: Any) -> str:
    text = "∅" if value is None else str(value)
    return text if len(text) <= 40 else text[:40] + "…"


def _entity_label(state) -> str | None:
    for key in LABEL_FIELDS:
        val = state.dict.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:255]
    return None


def _entity_id(obj: Any, state) -> str | None:
    try:
        pk = state.mapper.primary_key_from_instance(obj)
    except Exception:
        return None
    parts = [str(p) for p in pk if p is not None]
    return "/".join(parts) if parts else None


def _related_customer(obj: Any, state) -> str | None:
    if getattr(obj, "__tablename__", None) == "customers":
        return _entity_id(obj, state)
    val = state.dict.get("customer_id")
    return str(val) if val else None


def _diff(obj: Any, state) -> dict[str, list]:
    changes: dict[str, list] = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in IGNORED_COLUMNS:
            continue
        hist = state.attrs[key].history
        if not hist.has_changes():
            continue
        old = clean_value(key, hist.deleted[0]) if hist.deleted else NOT_RECORDED
        new = clean_value(key, hist.added[0]) if hist.added else None
        if old == new:
            continue
        changes[key] = [old, new]
    return changes


def _snapshot(state, *, as_new: bool) -> dict[str, list]:
    out: dict[str, list] = {}
    for attr in state.mapper.column_attrs:
        key = attr.key
        if key in IGNORED_COLUMNS or key not in state.dict:
            continue
        value = state.dict.get(key)
        if value is None:
            continue
        cleaned = clean_value(key, value)
        out[key] = [None, cleaned] if as_new else [cleaned, None]
    return out


def _summary(action: str, entity_type: str, label: str | None, entity_id: str | None, changes: dict) -> str:
    name = entity_type.replace("_", " ")
    ident = label or entity_id or ""
    head = {"created": "Created", "updated": "Updated", "deleted": "Deleted"}[action]
    text = f"{head} {name} {ident}".strip()
    if action == "updated" and changes:
        parts = [f"{k}: {_fmt(v[0])} → {_fmt(v[1])}" for k, v in list(changes.items())[:3]]
        text += " (" + "; ".join(parts) + (" …" if len(changes) > 3 else "") + ")"
    return text[:500]


# ------------------------------------------------------------- listeners


def _before_flush(session: Session, flush_context, instances) -> None:
    try:
        if not get_settings().audit_enabled:
            return
        pending: list[dict] = session.info.setdefault(PENDING_KEY, [])
        for obj in list(session.new):
            if _tracked(obj):
                pending.append({"action": "created", "obj": obj})
        for obj in list(session.dirty):
            if not _tracked(obj) or not session.is_modified(obj, include_collections=False):
                continue
            state = inspect(obj)
            changes = _diff(obj, state)
            if changes:
                pending.append(
                    {
                        "action": "updated",
                        "obj": obj,
                        "changes": changes,
                        "entity_id": _entity_id(obj, state),
                        "label": _entity_label(state),
                        "customer": _related_customer(obj, state),
                    }
                )
        for obj in list(session.deleted):
            if not _tracked(obj):
                continue
            state = inspect(obj)
            pending.append(
                {
                    "action": "deleted",
                    "obj": obj,
                    "changes": _snapshot(state, as_new=False),
                    "entity_id": _entity_id(obj, state),
                    "label": _entity_label(state),
                    "customer": _related_customer(obj, state),
                }
            )
    except Exception:  # auditing must never break the change it observes
        logger.exception("audit: failed while collecting changes")


def _write_rows(session: Session, flush_context) -> None:
    try:
        pending: list[dict] = session.info.pop(PENDING_KEY, None) or []
        if not pending:
            return
        ctx = current_context()
        now = datetime.now(timezone.utc)
        for item in pending:
            obj = item["obj"]
            state = inspect(obj)
            entity_type = obj.__tablename__
            if item["action"] == "created":
                changes = _snapshot(state, as_new=True)
                entity_id = _entity_id(obj, state)
                label = _entity_label(state)
                customer = _related_customer(obj, state)
            else:
                changes = item["changes"]
                entity_id, label, customer = item["entity_id"], item["label"], item["customer"]
            session.add(_build_row("change", item["action"], now, ctx, entity_type, entity_id, label, customer,
                                   _summary(item["action"], entity_type, label, entity_id, changes), changes))
    except Exception:
        logger.exception("audit: failed while writing change rows")


def _discard(*args, **kwargs) -> None:
    session = args[0]
    session.info.pop(PENDING_KEY, None)


def _build_row(
    kind: str,
    action: str,
    when: datetime,
    ctx: AuditContext | None,
    entity_type: str | None,
    entity_id: str | None,
    label: str | None,
    customer: str | None,
    summary: str | None,
    changes: dict | None,
    reason: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        occurred_at=when,
        kind=kind,
        action=action,
        actor_type=ctx.actor_type if ctx else "system",
        actor_user_id=ctx.actor_user_id if ctx else None,
        actor_name=(ctx.actor_name if ctx else None) or ("System" if not ctx else None),
        actor_email=ctx.actor_email if ctx else None,
        actor_role=ctx.actor_role if ctx else None,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=label,
        related_customer_id=customer,
        summary=summary,
        reason=(reason if reason is not None else (ctx.reason if ctx else None)),
        changes=changes,
        details=details,
        request_id=ctx.request_id if ctx else None,
        method=ctx.method if ctx else None,
        path=(ctx.path[:500] if ctx and ctx.path else None),
        ip=ctx.ip if ctx else None,
        user_agent=(ctx.user_agent[:300] if ctx and ctx.user_agent else None),
    )


def install() -> None:
    """Attach the listeners (once)."""
    global _installed
    if _installed:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "after_flush_postexec", _write_rows)
    event.listen(Session, "after_soft_rollback", lambda session, previous: _discard(session))
    _installed = True
