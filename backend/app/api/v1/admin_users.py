import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, hash_password, require_roles
from app.models.user import Role, User, UserRole
from app.schemas.user import RoleOut, StaffUserCreate, StaffUserOut, StaffUserUpdate

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
        stmt = stmt.where(or_(User.full_name.ilike(like), User.email.ilike(like)))
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
        user.full_name = data["full_name"]
    if "is_active" in data:
        user.is_active = data["is_active"]
    if "role" in data:
        role = await db.scalar(select(Role).where(Role.name == data["role"]))
        if not role:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown role '{data['role']}'")
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)
    return await _load_user_out(db, user)
