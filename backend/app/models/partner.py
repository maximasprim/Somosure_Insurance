import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
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
