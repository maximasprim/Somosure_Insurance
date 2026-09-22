from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.models.customer import Customer
from app.models.password_reset_token import PasswordResetToken
from app.models.user import Role, User, UserRole
from app.notifications.registry import get_dispatcher
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

# Long enough that a customer opening an email an hour later isn't
# punished, short enough that a leaked/intercepted link doesn't stay
# useful indefinitely.
RESET_TOKEN_TTL = timedelta(minutes=30)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    user = User(
        email=payload.email,
        phone=payload.phone,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    customer_role = await db.scalar(select(Role).where(Role.name == "customer"))
    if customer_role:
        db.add(UserRole(user_id=user.id, role_id=customer_role.id))

    # Every self-registered user is also a Customer record - this is what
    # /api/v1/me/* resolves against. Staff accounts (created by an admin,
    # not via this endpoint) won't get one, which is intentional: a
    # customer profile shouldn't exist for an operations user.
    customer = Customer(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone or "",
        lead_source="referral" if payload.referral_code else "website",
    )
    db.add(customer)
    await db.flush()

    if payload.referral_code:
        from app.services.referral_service import redeem_referral_code

        await redeem_referral_code(db, payload.referral_code, str(customer.id))

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Tighter than the app-wide default (200/min) since login is the
    # actual brute-force target (spec §30).
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    role_row = await db.scalar(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    role_name = role_row or "customer"

    return TokenResponse(
        access_token=create_access_token(str(user.id), role_name),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    claims = decode_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not a refresh token")

    user = await db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    role_row = await db.scalar(
        select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    role_name = role_row or "customer"

    return TokenResponse(
        access_token=create_access_token(str(user.id), role_name),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("5/minute")
async def forgot_password(request: Request, payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Always returns the same generic response whether or not the email
    is registered - this is deliberate (see ForgotPasswordResponse) and
    is not a bug if you're testing with an email that doesn't exist.

    No real email provider is configured in this codebase yet (see
    app/notifications/base.py) - MockDispatcher logs the reset link at
    INFO level instead of delivering it. Check the backend's console
    output for a line starting "[MOCK EMAIL]" to get the link while
    testing. Configuring a real email dispatcher later requires no
    changes here - only a new NotificationDispatcher implementation and
    a registry.py update, exactly like AfricasTalkingDispatcher for SMS.
    """
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user and user.is_active:
        raw_token = generate_reset_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_reset_token(raw_token),
                expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
            )
        )
        await db.commit()

        reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
        await get_dispatcher().send_email(
            user.email,
            "Reset your Somosure password",
            f"Hi {user.full_name},\n\nUse the link below to set a new password. "
            f"It expires in 30 minutes and can only be used once.\n\n{reset_link}\n\n"
            "If you didn't request this, you can safely ignore this email.",
        )

    return ForgotPasswordResponse()


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def reset_password(request: Request, payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_row = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(payload.token))
    )
    now = datetime.now(timezone.utc)
    if not token_row or token_row.used_at is not None or token_row.expires_at < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired")

    user = await db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired")

    user.hashed_password = hash_password(payload.new_password)
    token_row.used_at = now
    await db.commit()
