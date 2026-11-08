from datetime import datetime, timedelta, timezone
from typing import Any
import hashlib
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_reset_token() -> str:
    """A high-entropy (256-bit) URL-safe random string - this is what
    goes in the emailed reset link, never stored anywhere itself."""
    return secrets.token_urlsafe(32)


def hash_reset_token(raw_token: str) -> str:
    """Reset tokens are already high-entropy random values (unlike a
    user-chosen password), so a fast deterministic hash is the right
    tool here rather than bcrypt - bcrypt also silently truncates input
    past 72 bytes, which a 43-character token could hit combined with
    any future prefixing. sha256 has no such limit and is the standard
    choice for this exact "hash a random token for DB lookup" pattern.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_token(subject: str, expires_delta: timedelta, extra_claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + expires_delta}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str, token_version: int = 0, must_change_password: bool = False) -> str:
    claims: dict[str, Any] = {"role": role, "type": "access", "tv": token_version}
    if must_change_password:
        # Lets the frontend send the user to the change-password screen; the server
        # enforces it independently (see get_current_claims).
        claims["mcp"] = True
    return create_token(user_id, timedelta(minutes=settings.access_token_expire_minutes), claims)


def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    return create_token(
        user_id,
        timedelta(days=settings.refresh_token_expire_days),
        {"type": "refresh", "tv": token_version},
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def token_matches_user(claims: dict[str, Any], user: Any) -> bool:
    """A token is only good while its account is active and its version is the
    account's current one. Tokens issued before versions existed carry no "tv" and
    count as version 0, so they keep working until the version is bumped."""
    return bool(user and user.is_active and int(claims.get("tv", 0)) == int(user.token_version or 0))


# While must_change_password is set, the only thing a signed-in user may do is change it.
PASSWORD_CHANGE_ALLOWED_PATHS = {"/api/v1/auth/change-password"}


async def get_current_claims(
    request: Request, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    from app.models.user import User  # local import: models import core.database

    claims = decode_token(token)
    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")

    user = await db.get(User, claims["sub"])
    if not token_matches_user(claims, user):
        # Signed out remotely, password changed/reset, role changed, or deactivated.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has ended - please sign in again")
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_change_required")
    return claims


def require_roles(*allowed_roles: str):
    """Dependency factory for RBAC on route handlers.

    Usage: Depends(require_roles("super_admin", "underwriter"))
    """

    async def _check(claims: dict[str, Any] = Depends(get_current_claims)) -> dict[str, Any]:
        if claims.get("role") not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return claims

    return _check
