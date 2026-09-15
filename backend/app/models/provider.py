import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InsuranceProvider(Base):
    """A licensed insurer or broker integrated into the marketplace.

    API credentials are NEVER stored here in plaintext - this table holds
    a reference (secret name) resolved at runtime from environment/secret
    manager, never a value returned to the frontend.
    """

    __tablename__ = "insurance_providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(30))  # insurer, broker, mga
    logo_url: Mapped[str | None] = mapped_column(String(500))

    integration_mode: Mapped[str] = mapped_column(String(20), default="mock")
    # mock | rest | soap | manual | csv_import
    api_base_url: Mapped[str | None] = mapped_column(String(500))
    credentials_secret_ref: Mapped[str | None] = mapped_column(String(255))
    # name of the secret in the secret manager / env var - never the value itself

    supports_quote: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_policy: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_claims: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_webhooks: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(20), default="inactive")
    # active | inactive | maintenance | manual_only
    integration_version: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class InsuranceProduct(Base):
    __tablename__ = "insurance_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"))
    category: Mapped[str] = mapped_column(String(30))  # motor, medical, life, travel, home, business, ...
    subtype: Mapped[str | None] = mapped_column(String(50))  # comprehensive, third_party, tpft, ...
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Admin-configurable required question set / document set for this product,
    # so quote forms don't need code changes per product (spec §34).
    required_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    required_documents: Mapped[dict] = mapped_column(JSON, default=dict)


class InsuranceProductPlan(Base):
    __tablename__ = "insurance_product_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_products.id"))
    name: Mapped[str] = mapped_column(String(150))
    coverage_summary: Mapped[dict] = mapped_column(JSON, default=dict)
