from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import LEAD_STAGES, Lead, LeadActivity


async def update_lead(db: AsyncSession, lead_id: str, stage: str | None, assigned_agent_id: str | None) -> Lead:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    if stage is not None:
        if stage not in LEAD_STAGES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Stage must be one of {LEAD_STAGES}")
        if stage != lead.stage:
            db.add(LeadActivity(lead_id=lead.id, activity_type="stage_changed", notes=f"{lead.stage} → {stage}"))
        lead.stage = stage

    if assigned_agent_id is not None:
        lead.assigned_agent_id = assigned_agent_id
        db.add(LeadActivity(lead_id=lead.id, activity_type="assigned", notes=f"Assigned to agent {assigned_agent_id}"))

    await db.commit()
    await db.refresh(lead)
    return lead


async def add_activity(db: AsyncSession, lead_id: str, activity_type: str, notes: str | None, actor_user_id: str | None) -> LeadActivity:
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    activity = LeadActivity(lead_id=lead_id, activity_type=activity_type, notes=notes, actor_user_id=actor_user_id)
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def get_funnel(db: AsyncSession) -> dict:
    rows = (await db.execute(select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage))).all()
    counts = {stage: count for stage, count in rows}
    stages = [{"stage": s, "count": counts.get(s, 0)} for s in LEAD_STAGES]
    return {"stages": stages, "total": sum(counts.values())}
