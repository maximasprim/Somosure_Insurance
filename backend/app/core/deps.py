from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token, get_current_claims
from app.models.customer import Customer
from app.models.user import User


async def get_current_customer(
    claims: dict = Depends(get_current_claims), db: AsyncSession = Depends(get_db)
) -> Customer:
    user_id = claims["sub"]
    customer = await db.scalar(select(Customer).where(Customer.user_id == user_id))
    if customer:
        return customer

    # Safety net: an account created before this field existed, or one
    # whose Customer row wasn't created for some other reason. Backfill it
    # rather than 404ing a legitimate logged-in user out of their own
    # dashboard.
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    customer = Customer(user_id=user.id, full_name=user.full_name, email=user.email, phone=user.phone or "")
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


_optional_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_optional_customer_id(
    token: str | None = Depends(_optional_oauth2), db: AsyncSession = Depends(get_db)
) -> str | None:
    """The logged-in customer's id if a valid access token was sent, else
    None - never an error. For endpoints that are open to guests but may do
    a little more for a verified, logged-in customer (e.g. reusing the
    identity documents that customer uploaded on an earlier application).
    A missing, expired or malformed token simply means "treat as a guest"."""
    if not token:
        return None
    try:
        claims = decode_token(token)
    except HTTPException:
        return None
    if claims.get("type") != "access":
        return None
    customer = await db.scalar(select(Customer).where(Customer.user_id == claims["sub"]))
    return str(customer.id) if customer else None
