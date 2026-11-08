import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
import app.models  # noqa: F401 - registers every model so the dependency scan below sees all of them
from app.core.database import Base, get_db
from app.core.security import get_current_claims, hash_password, require_roles
from app.models.customer import Customer
from app.models.password_reset_token import PasswordResetToken
from app.models.user import Role, User, UserRole
from app.schemas.user import (
    DeletionBlocker,
    RoleOut,
    StaffPasswordReset,
    StaffUserCreate,
    StaffUserOut,
    StaffUserUpdate,
    UserDeletionCheck,
)

# Managing who has admin access is the most sensitive action in the
# platform, so this is restricted to super_admin only - unlike most
# /admin/* routers, which are shared across a few relevant roles.
router = APIRouter(
    prefix="/api/v1/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(require_roles("super_admin"))],
)

roles_router = APIRouter(
    prefix="/api/v1/admin/roles",
    tags=["admin-users"],
    dependencies=[Depends(require_roles("super_admin"))],
)


async def _load_user_out(db: AsyncSession, user: User) -> StaffUserOut:
    role_name = await db.scalar(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    return StaffUserOut(
        id=user.id,
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=role_name or "customer",
        is_active=user.is_active,
        created_at=user.created_at,
        must_change_password=user.must_change_password,
    )


@roles_router.get("", response_model=list[RoleOut])
async def list_roles(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Role).order_by(Role.name))).all()


@router.get("", response_model=list[StaffUserOut])
async def list_users(
    search: str | None = Query(None, min_length=1),
    role: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User, Role.name).outerjoin(UserRole, UserRole.user_id == User.id).outerjoin(Role, Role.id == UserRole.role_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like), User.phone.ilike(like)))
    if role:
        stmt = stmt.where(Role.name == role)
    stmt = stmt.order_by(User.created_at.desc()).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        StaffUserOut(
            id=user.id,
            email=user.email,
            phone=user.phone,
            full_name=user.full_name,
            role=role_name or "customer",
            is_active=user.is_active,
            created_at=user.created_at,
            must_change_password=user.must_change_password,
        )
        for user, role_name in rows
    ]


@router.post("", response_model=StaffUserOut, status_code=status.HTTP_201_CREATED)
async def create_staff_user(payload: StaffUserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    role = await db.scalar(select(Role).where(Role.name == payload.role))
    if not role:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown role '{payload.role}'")

    # Staff accounts are pre-verified since an admin, not the user
    # themself, is vouching for the email address - matches how
    # auth.register only marks self-registered customers unverified.
    user = User(
        email=payload.email,
        phone=payload.phone,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_verified=True,
        must_change_password=payload.require_password_change,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.commit()
    await db.refresh(user)
    return await _load_user_out(db, user)


@router.patch("/{user_id}", response_model=StaffUserOut)
async def update_staff_user(
    user_id: uuid.UUID,
    payload: StaffUserUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    data = payload.model_dump(exclude_unset=True)
    is_self = str(user.id) == str(claims.get("sub"))
    if is_self and ("is_active" in data and not data["is_active"] or ("role" in data and data["role"] != "super_admin")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't change your own role or deactivate your own account")

    if "full_name" in data:
        name = (data["full_name"] or "").strip()
        if len(name) < 2:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Full name must be at least 2 characters")
        user.full_name = name

    if "email" in data:
        if not data["email"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email can't be empty")
        new_email = str(data["email"]).strip()
        clash = await db.scalar(
            select(User.id).where(func.lower(User.email) == new_email.lower(), User.id != user.id)
        )
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Another account already uses this email")
        user.email = new_email

    if "phone" in data:
        user.phone = (data["phone"] or "").strip() or None

    if "is_active" in data and data["is_active"] is not None:
        if user.is_active and not data["is_active"]:
            # Deactivating ends every session they have open, not just future sign-ins.
            user.token_version = (user.token_version or 0) + 1
        user.is_active = data["is_active"]

    if "role" in data:
        if not data["role"]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Role can't be empty")
        role = await db.scalar(select(Role).where(Role.name == data["role"]))
        if not role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown role '{data['role']}'")
        current_role = await db.scalar(
            select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
        )
        if current_role != role.name:
            # Tokens carry the role they were issued with, so a changed role ends old sessions
            # (a demoted user must not keep acting with the previous role until it expires).
            user.token_version = (user.token_version or 0) + 1
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id))

    # Keep the linked customer profile (what the customer sees on their own
    # dashboard) in step with the account details an admin just corrected.
    # A customer's phone is mandatory, so a cleared phone is not copied over.
    if {"full_name", "email", "phone"} & data.keys():
        customer = await db.scalar(select(Customer).where(Customer.user_id == user.id))
        if customer:
            if "full_name" in data:
                customer.full_name = user.full_name
            if "email" in data:
                customer.email = user.email
            if "phone" in data and user.phone:
                customer.phone = user.phone

    await db.commit()
    await db.refresh(user)
    return await _load_user_out(db, user)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: uuid.UUID,
    payload: StaffPasswordReset,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Sets a new password for another account and signs that user out of every
    device. By default they must choose their own password at next sign-in. The
    password is never stored in the audit trail (only that a reset happened, by
    whom, and the reason sent in the X-Audit-Reason header). Password-reset email
    links they had already requested are cancelled so they can't override this."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if str(user.id) == str(claims.get("sub")):
        # Resetting yourself here would sign you out of this very session.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use 'Change my password' to change your own password")

    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = payload.require_password_change
    user.token_version = (user.token_version or 0) + 1
    await db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=datetime.now(timezone.utc))
    )
    record_event(
        "user.password_reset",
        entity_type="users",
        entity_id=user.id,
        entity_label=user.email,
        summary=f"Password reset by an administrator for {user.full_name}",
        must_change_password=payload.require_password_change,
    )
    await db.commit()


@router.post("/{user_id}/revoke-sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_sessions(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Signs the user out of every device without changing anything else. They can
    sign straight back in with their current password."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.token_version = (user.token_version or 0) + 1
    record_event(
        "user.sessions_revoked",
        entity_type="users",
        entity_id=user.id,
        entity_label=user.email,
        summary=f"All sessions ended by an administrator for {user.full_name}",
    )
    await db.commit()


# --------------------------------------------------------------------------- deletion
#
# Deleting an account is permanent, so it is only allowed when nothing else in the
# system depends on it. The dependency scan reads the database schema itself (every
# foreign key that points at users or customers), so a table added in future is
# protected automatically. Anything that blocks deletion can still be handled by
# deactivating the account, which keeps every record intact.

# Convenience data that belongs to a customer and goes with them.
CUSTOMER_OWNED_TABLES = {"customer_contacts", "notifications"}
# Rows that exist only to describe the account itself and go with it.
ACCOUNT_OWNED_COLUMNS = {("user_roles", "user_id"), ("password_reset_tokens", "user_id"), ("customers", "user_id")}

_LABELS = {
    "applications": "insurance applications",
    "policies": "policies",
    "payments": "payments",
    "claims": "claims",
    "financing_applications": "financing applications",
    "quote_requests": "quotes",
    "leads": "leads",
    "support_tickets": "support tickets",
    "insured_assets": "insured assets",
    "vehicles": "vehicles",
    "communications": "communications",
    "affiliates": "affiliate profiles",
    "affiliate_commissions": "affiliate commissions",
    "referrals": "referrals",
    "referral_discounts": "referral discounts",
    "partner_applications": "partner applications",
    "partners": "partners they manage",
    "whatsapp_conversations": "WhatsApp conversations",
    "customer_anniversaries": "policy anniversaries",
    "tasks": "tasks",
    "content": "content they authored",
    "application_events": "application history entries",
    "claim_events": "claim history entries",
    "financing_events": "financing history entries",
    "policy_events": "policy history entries",
    "sticker_events": "sticker history entries",
    "lead_activities": "lead activity entries",
    "financing_settings": "financing settings changes",
}


def _label(table_name: str) -> str:
    return _LABELS.get(table_name, table_name.replace("_", " "))


async def _deletion_check(db: AsyncSession, user: User, caller_id: str | None) -> tuple[UserDeletionCheck, list[uuid.UUID]]:
    reasons: list[str] = []
    if caller_id and str(user.id) == str(caller_id):
        reasons.append("You can't delete your own account.")
    role_name = await db.scalar(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    if role_name == "super_admin":
        reasons.append("Super admin accounts can't be deleted. Change their role first.")

    customer_ids = list((await db.scalars(select(Customer.id).where(Customer.user_id == user.id))).all())

    counts: dict[tuple[str, str], int] = {}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target == "users":
                if (table.name, fk.parent.name) in ACCOUNT_OWNED_COLUMNS:
                    continue
                condition, kind = fk.parent == user.id, "staff"
            elif target == "customers":
                if not customer_ids or table.name in CUSTOMER_OWNED_TABLES:
                    continue
                condition, kind = fk.parent.in_(customer_ids), "customer"
            else:
                continue
            n = await db.scalar(select(func.count()).select_from(table).where(condition))
            if n:
                key = (table.name, kind)
                counts[key] = counts.get(key, 0) + int(n)

    blockers = [
        DeletionBlocker(label=_label(table_name), count=n, kind=kind)
        for (table_name, kind), n in sorted(counts.items(), key=lambda item: item[0])
    ]
    check = UserDeletionCheck(
        can_delete=not reasons and not blockers,
        reasons=reasons,
        blockers=blockers,
        removes_customer_profile=bool(customer_ids),
    )
    return check, customer_ids


@router.get("/{user_id}/deletion-check", response_model=UserDeletionCheck)
async def check_user_deletion(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """What stands in the way of deleting this account (nothing is changed)."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    check, _ = await _deletion_check(db, user, claims.get("sub"))
    return check


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    confirm_email: str = Query(..., description="The account's email, typed out to confirm"),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Permanently deletes an account that nothing else depends on. Refused (409)
    if it has any policies, payments, claims, applications, assignments or other
    records - deactivate it instead. An unused customer profile goes with it. The
    deletion is recorded in the audit trail, which outlives the account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if str(user.id) == str(claims.get("sub")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't delete your own account")
    if confirm_email.strip().lower() != user.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The email you typed doesn't match this account")

    check, customer_ids = await _deletion_check(db, user, claims.get("sub"))
    if not check.can_delete:
        parts = list(check.reasons) + [f"{b.count} {b.label}" for b in check.blockers]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This account can't be deleted: " + "; ".join(parts) + ". Deactivate it instead to keep those records.",
        )

    role_name = await db.scalar(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    email, full_name = user.email, user.full_name
    try:
        if customer_ids:
            for table_name in CUSTOMER_OWNED_TABLES:
                table = Base.metadata.tables.get(table_name)
                if table is not None:
                    await db.execute(delete(table).where(table.c.customer_id.in_(customer_ids)))
            await db.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
        await db.execute(delete(User).where(User.id == user.id))
        # Bulk deletes bypass the automatic change capture, so say what happened explicitly.
        record_event(
            "user.deleted",
            entity_type="users",
            entity_id=user_id,
            entity_label=email,
            summary=f"Deleted {role_name or 'user'} account for {full_name}",
            role=role_name,
            removed_customer_profile=bool(customer_ids),
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Records were linked to this account while it was being deleted. Deactivate it instead.",
        )