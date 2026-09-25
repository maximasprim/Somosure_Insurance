import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.renewal import Renewal
from app.models.support import SupportTicket
from app.models.crm import Task
from app.models.user import User
from app.schemas.admin_records import (
    PaymentListOut,
    PolicyListOut,
    RenewalListOut,
    RenewalUpdate,
    SupportTicketListOut,
    SupportTicketUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)

# --- Policies -----------------------------------------------------------
policies_router = APIRouter(
    prefix="/api/v1/admin/policies",
    tags=["admin-records"],
    dependencies=[Depends(require_roles("super_admin", "management", "finance_officer", "operations"))],
)


@policies_router.get("", response_model=list[PolicyListOut])
async def list_policies(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None, min_length=1),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Policy, Customer.full_name, InsuranceProvider.name)
        .join(Customer, Customer.id == Policy.customer_id)
        .join(InsuranceProvider, InsuranceProvider.id == Policy.provider_id)
    )
    if status_filter:
        stmt = stmt.where(Policy.status == status_filter)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Policy.policy_number.ilike(like), Customer.full_name.ilike(like)))
    stmt = stmt.order_by(Policy.created_at.desc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        PolicyListOut(
            id=policy.id,
            policy_number=policy.policy_number,
            customer_name=customer_name,
            provider_name=provider_name,
            status=policy.status,
            payment_status=policy.payment_status,
            premium=policy.premium,
            start_date=policy.start_date,
            end_date=policy.end_date,
            is_mock=policy.is_mock,
            created_at=policy.created_at,
        )
        for policy, customer_name, provider_name in rows
    ]


# --- Payments -------------------------------------------------------------
payments_router = APIRouter(
    prefix="/api/v1/admin/payments",
    tags=["admin-records"],
    dependencies=[Depends(require_roles("super_admin", "management", "finance_officer"))],
)


@payments_router.get("", response_model=list[PaymentListOut])
async def list_payments(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None, min_length=1),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Payment, Customer.full_name).join(Customer, Customer.id == Payment.customer_id)
    if status_filter:
        stmt = stmt.where(Payment.status == status_filter)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Payment.reference.ilike(like), Customer.full_name.ilike(like)))
    stmt = stmt.order_by(Payment.created_at.desc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        PaymentListOut(
            id=payment.id,
            reference=payment.reference,
            customer_name=customer_name,
            amount=payment.amount,
            currency=payment.currency,
            method=payment.method,
            status=payment.status,
            created_at=payment.created_at,
        )
        for payment, customer_name in rows
    ]


# --- Renewals ---------------------------------------------------------------
renewals_router = APIRouter(
    prefix="/api/v1/admin/renewals",
    tags=["admin-records"],
    dependencies=[Depends(require_roles("super_admin", "management", "operations", "sales_agent"))],
)


@renewals_router.get("", response_model=list[RenewalListOut])
async def list_renewals(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Renewal, Policy.policy_number, Customer.full_name)
        .join(Policy, Policy.id == Renewal.policy_id)
        .join(Customer, Customer.id == Policy.customer_id)
    )
    if status_filter:
        stmt = stmt.where(Renewal.status == status_filter)
    stmt = stmt.order_by(Renewal.due_date.asc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        RenewalListOut(
            id=renewal.id,
            policy_number=policy_number,
            customer_name=customer_name,
            due_date=renewal.due_date,
            status=renewal.status,
            created_at=renewal.created_at,
        )
        for renewal, policy_number, customer_name in rows
    ]


@renewals_router.patch("/{renewal_id}", response_model=RenewalListOut)
async def update_renewal(renewal_id: uuid.UUID, payload: RenewalUpdate, db: AsyncSession = Depends(get_db)):
    renewal = await db.get(Renewal, renewal_id)
    if not renewal:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Renewal not found")
    renewal.status = payload.status
    await db.commit()
    await db.refresh(renewal)

    row = (
        await db.execute(
            select(Policy.policy_number, Customer.full_name)
            .join(Customer, Customer.id == Policy.customer_id)
            .where(Policy.id == renewal.policy_id)
        )
    ).one()
    return RenewalListOut(
        id=renewal.id,
        policy_number=row[0],
        customer_name=row[1],
        due_date=renewal.due_date,
        status=renewal.status,
        created_at=renewal.created_at,
    )


# --- Support tickets ----------------------------------------------------
support_router = APIRouter(
    prefix="/api/v1/admin/support-tickets",
    tags=["admin-records"],
    dependencies=[Depends(require_roles("super_admin", "management", "customer_support", "operations"))],
)

_assignee = User.__table__.alias("assignee")


@support_router.get("", response_model=list[SupportTicketListOut])
async def list_support_tickets(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SupportTicket, Customer.full_name, _assignee.c.full_name)
        .join(Customer, Customer.id == SupportTicket.customer_id)
        .outerjoin(_assignee, _assignee.c.id == SupportTicket.assigned_to_user_id)
    )
    if status_filter:
        stmt = stmt.where(SupportTicket.status == status_filter)
    if category:
        stmt = stmt.where(SupportTicket.category == category)
    stmt = stmt.order_by(SupportTicket.created_at.desc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        SupportTicketListOut(
            id=ticket.id,
            reference=ticket.reference,
            customer_name=customer_name,
            category=ticket.category,
            subject=ticket.subject,
            message=ticket.message,
            status=ticket.status,
            assigned_to_name=assignee_name,
            created_at=ticket.created_at,
        )
        for ticket, customer_name, assignee_name in rows
    ]


@support_router.patch("/{ticket_id}", response_model=SupportTicketListOut)
async def update_support_ticket(ticket_id: uuid.UUID, payload: SupportTicketUpdate, db: AsyncSession = Depends(get_db)):
    ticket = await db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        ticket.status = data["status"]
    if "assigned_to_user_id" in data:
        ticket.assigned_to_user_id = data["assigned_to_user_id"]
    await db.commit()
    await db.refresh(ticket)

    customer_name = await db.scalar(select(Customer.full_name).where(Customer.id == ticket.customer_id))
    assignee_name = None
    if ticket.assigned_to_user_id:
        assignee_name = await db.scalar(select(User.full_name).where(User.id == ticket.assigned_to_user_id))
    return SupportTicketListOut(
        id=ticket.id,
        reference=ticket.reference,
        customer_name=customer_name or "",
        category=ticket.category,
        subject=ticket.subject,
        message=ticket.message,
        status=ticket.status,
        assigned_to_name=assignee_name,
        created_at=ticket.created_at,
    )


# --- Tasks ----------------------------------------------------------------
# Task (models/crm.py) had a table and a docstring but no routes anywhere
# in the codebase - this is the first thing to ever read or write it.
tasks_router = APIRouter(
    prefix="/api/v1/admin/tasks",
    tags=["admin-records"],
    dependencies=[Depends(require_roles("super_admin", "management", "sales_agent", "operations", "marketing"))],
)


@tasks_router.get("", response_model=list[TaskOut])
async def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    assigned_to_user_id: uuid.UUID | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Task, User.full_name).outerjoin(User, User.id == Task.assigned_to_user_id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if assigned_to_user_id:
        stmt = stmt.where(Task.assigned_to_user_id == assigned_to_user_id)
    stmt = stmt.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        TaskOut(
            id=task.id,
            title=task.title,
            lead_id=task.lead_id,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_name=assignee_name,
            due_at=task.due_at,
            status=task.status,
            created_at=task.created_at,
        )
        for task, assignee_name in rows
    ]


@tasks_router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(id=uuid.uuid4(), **payload.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    assignee_name = None
    if task.assigned_to_user_id:
        assignee_name = await db.scalar(select(User.full_name).where(User.id == task.assigned_to_user_id))
    return TaskOut(
        id=task.id,
        title=task.title,
        lead_id=task.lead_id,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_to_name=assignee_name,
        due_at=task.due_at,
        status=task.status,
        created_at=task.created_at,
    )


@tasks_router.patch("/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    assignee_name = None
    if task.assigned_to_user_id:
        assignee_name = await db.scalar(select(User.full_name).where(User.id == task.assigned_to_user_id))
    return TaskOut(
        id=task.id,
        title=task.title,
        lead_id=task.lead_id,
        assigned_to_user_id=task.assigned_to_user_id,
        assigned_to_name=assignee_name,
        due_at=task.due_at,
        status=task.status,
        created_at=task.created_at,
    )
