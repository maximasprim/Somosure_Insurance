import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Categories from spec §21.
CONTENT_CATEGORIES = (
    "insurance_basics",
    "motor_insurance",
    "claims",
    "renewals",
    "policy_exclusions",
    "premiums",
    "financial_literacy",
    "risk_management",
    "business_insurance",
)


class ContentCategory(Base):
    __tablename__ = "content_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Content(Base):
    """An article/guide (spec §21). Kept deliberately simple - title,
    body, category - rather than a full page-builder; the platform needs
    plain-language educational content, not a general CMS."""

    __tablename__ = "content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(150), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(20000))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_categories.id"), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(String(500))
    answer: Mapped[str] = mapped_column(String(5000))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("content_categories.id"), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
