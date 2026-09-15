import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))

    registration_number: Mapped[str] = mapped_column(String(20), index=True)
    chassis_number: Mapped[str | None] = mapped_column(String(50))
    engine_number: Mapped[str | None] = mapped_column(String(50))
    make: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    usage: Mapped[str] = mapped_column(String(30))  # private, psv, commercial, ...

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsuredAsset(Base):
    """Generic insured-object record for non-motor products (home, business
    property, etc.) so applications aren't hard-coded to vehicles only."""

    __tablename__ = "insured_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(String(30))  # home, business_property, ...
    description: Mapped[str | None] = mapped_column(String(500))
    value: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
