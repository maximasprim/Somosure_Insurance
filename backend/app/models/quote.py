import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuoteRequest(Base):
    """One customer request, e.g. 'quote my motor insurance'.

    Fans out into multiple QuoteItems, one per provider that responds.
    """

    __tablename__ = "quote_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # e.g. SOM-2026-000123
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(String(30))  # motor, medical, ...
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)  # raw answers from the smart form
    status: Mapped[str] = mapped_column(String(30), default="collecting")
    # collecting | routed | quoted | partial_failure | abandoned | expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Quote(Base):
    """A single provider's normalized quote against a QuoteRequest.

    This is the NormalizedQuote from spec §5 - every provider adapter must
    return data shaped to fit this table, regardless of the provider's own
    API response format.
    """

    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quote_requests.id"))
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_products.id"))

    premium: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    taxes: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0)
    fees: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="KES")

    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    exclusions: Mapped[dict] = mapped_column(JSON, default=dict)
    deductibles: Mapped[dict] = mapped_column(JSON, default=dict)
    payment_options: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    underlying_provider_name: Mapped[str | None] = mapped_column(String(150))
    # Set when this quote came through an aggregator (e.g. provider_id
    # points at the "Lami Technologies" row, this holds "Britam"). None
    # for a direct insurer, where the provider row IS the insurer.

    is_mock: Mapped[bool] = mapped_column(default=True)
    # True until a real provider adapter with real credentials produced this row

    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="available")
    # available | selected | expired | withdrawn

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuoteItem(Base):
    """Line items within a quote, e.g. add-on covers, if the platform later
    needs to itemize beyond the single premium/total on Quote."""

    __tablename__ = "quote_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"))
    label: Mapped[str] = mapped_column(String(150))
    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
