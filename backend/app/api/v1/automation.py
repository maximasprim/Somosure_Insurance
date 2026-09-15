import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.engine import run_due_automations
from app.core.database import get_db
from app.core.security import require_roles
from app.models.automation import AutomationRule, AutomationRun
from app.schemas.automation import AutomationRuleCreate, AutomationRuleOut, AutomationRuleUpdate, AutomationRunOut
from app.services.quote_recovery_service import scan_abandoned_quotes
from app.services.renewal_service import scan_renewals

router = APIRouter(
    prefix="/api/v1/admin/automation",
    tags=["automation"],
    dependencies=[Depends(require_roles("super_admin", "operations", "management"))],
)


@router.get("/rules", response_model=list[AutomationRuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(AutomationRule))).all()


@router.post("/rules", response_model=AutomationRuleOut)
async def create_rule(payload: AutomationRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AutomationRule(id=uuid.uuid4(), **payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=AutomationRuleOut)
async def update_rule(rule_id: str, payload: AutomationRuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AutomationRule, rule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/runs", response_model=list[AutomationRunOut])
async def list_runs(db: AsyncSession = Depends(get_db), status_filter: str | None = None, limit: int = 50):
    stmt = select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(AutomationRun.status == status_filter)
    return (await db.scalars(stmt)).all()


@router.post("/run-due")
async def trigger_run_due(db: AsyncSession = Depends(get_db)):
    """No live scheduler exists yet (Phase 10 infra) - this executes
    whatever's currently due. Point a cron/Celery beat task at this same
    run_due_automations() call once one exists; nothing else changes."""
    return await run_due_automations(db)


@router.post("/scan-renewals")
async def trigger_scan_renewals(db: AsyncSession = Depends(get_db)):
    return await scan_renewals(db)


@router.post("/scan-abandoned-quotes")
async def trigger_scan_abandoned_quotes(db: AsyncSession = Depends(get_db)):
    return await scan_abandoned_quotes(db)
