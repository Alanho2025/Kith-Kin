"""Single-use WebSocket ticket JTI rows."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketUse(Base):
    """Atomic record of consumed app WebSocket tickets."""

    __tablename__ = "ticket_uses"
    __table_args__ = (UniqueConstraint("issuer", "jti", name="uq_ticket_uses_issuer_jti"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(120))
    jti: Mapped[UUID]
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
