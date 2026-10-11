import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Partner types from spec §43: car dealers, vehicle importers, employers,
# SMEs, banks, SACCOs, agents, corporate partners.
PARTNER_TYPES = ("car_dealer", "vehicle_importer", "employer", "sme", "bank", "sacco", "agent", "corporate")


class Partner(Base):
    """A business partner who can generate leads or initiate applications
    on a customer's behalf (spec §43). This is the foundational record -
    a partner-specific portal/workflow (e.g. a dealer submitting a batch
    of new-car buyers) is a future capability this table supports but
    doesn't yet implement; today a partner's leads flow through the same
    Lead model as any other source, tagged with this partner's id via
    Lead.source='partner' and a note, since Lead has no partner_id column
    yet - adding one is a natural next step once a partner workflow
    actually needs to query leads by partner directly.
    """

    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    partner_type: Mapped[str] = mapped_column(String(30))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    managed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


PARTNER_WORKING_MODELS = ("referrals", "applications", "both")
PARTNER_VOLUME_BANDS = ("1-10", "11-50", "51-200", "200+")
APPLICATION_STATUSES = ("pending", "approved", "declined")


class PartnerApplication(Base):
    """Someone asking to become a partner, submitted from the public "Become a
    partner" page. Staff approve or decline it in the admin queue; approving
    creates the Partner record (and can enrol the contact as an affiliate) and
    links it back here. Nothing about a request is ever deleted - a declined
    application stays on file with the reason."""

    __tablename__ = "partner_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(30), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    town: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    working_model: Mapped[str] = mapped_column(String(20), nullable=False)  # referrals | applications | both
    monthly_clients: Mapped[str] = mapped_column(String(10), nullable=False)  # volume band
    products: Mapped[list | None] = mapped_column(JSON, nullable=True)  # product categories of interest
    message: Mapped[str] = mapped_column(Text, nullable=False)  # how they'd work with us

    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    partner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    affiliate_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

