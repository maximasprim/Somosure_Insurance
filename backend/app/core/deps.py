from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims
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
