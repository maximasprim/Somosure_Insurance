"""The event → rule → action engine (spec §27).

emit_event() is called from wherever something happens (policy issuance,
a renewal reminder becoming due, a quote going stale) - it never executes
an action inline. Instead it matches active AutomationRule rows against
the event name and conditions, and schedules an AutomationRun for
`delay_seconds` later. run_due_automations() is what actually executes
scheduled runs whose time has come.

There is no live background worker in this phase - no Celery/RQ wired up
yet (that's Phase 10 infrastructure). run_due_automations() is meant to be
called by a scheduled job once one exists; until then, the admin endpoint
POST /api/v1/admin/automation/run-due calls it on demand. The engine logic
itself doesn't change when a real scheduler is added - only what calls it.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.actions import ACTIONS
from app.models.automation import AutomationRule, AutomationRun

logger = logging.getLogger("somosure.automation")


def _conditions_match(conditions: dict, context: dict) -> bool:
    return all(context.get(key) == value for key, value in conditions.items())


async def emit_event(db: AsyncSession, event_name: str, entity_type: str, entity_id: str, context: dict) -> list[AutomationRun]:
    context = {**context, "event": event_name}

    rules = (
        await db.scalars(
            select(AutomationRule).where(AutomationRule.trigger_event == event_name, AutomationRule.is_active.is_(True))
        )
    ).all()

    runs: list[AutomationRun] = []
    for rule in rules:
        if not _conditions_match(rule.conditions, context):
            continue

        run = AutomationRun(
            rule_id=rule.id,
            trigger_event=event_name,
            entity_type=entity_type,
            entity_id=str(entity_id),
            context=context,
            status="scheduled",
            scheduled_for=datetime.now(timezone.utc) + timedelta(seconds=rule.delay_seconds),
        )
        db.add(run)
        runs.append(run)

    if runs:
        await db.flush()
    return runs


async def run_due_automations(db: AsyncSession, limit: int = 100) -> dict:
    now = datetime.now(timezone.utc)
    due_runs = (
        await db.scalars(
            select(AutomationRun)
            .where(AutomationRun.status == "scheduled", AutomationRun.scheduled_for <= now)
            .limit(limit)
        )
    ).all()

    executed, failed = 0, 0
    for run in due_runs:
        rule = await db.get(AutomationRule, run.rule_id)
        action_fn = ACTIONS.get(rule.action_type) if rule else None
        if not action_fn:
            run.status = "failed"
            run.error = f"No action handler for '{rule.action_type if rule else run.trigger_event}'"
            failed += 1
            continue

        try:
            result = await action_fn(db, run.context, rule.action_config)
            run.result = result
            run.status = "executed"
            run.executed_at = now
            executed += 1
        except Exception as e:
            logger.exception("Automation run %s failed", run.id)
            run.status = "failed"
            run.error = str(e)
            failed += 1

    await db.commit()
    return {"executed": executed, "failed": failed, "checked": len(due_runs)}
