"""Confirmation audit rows."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Confirmation(Base):
    """Parent-confirmed action authority."""

    __tablename__ = "confirmations"
    __table_args__ = (
        UniqueConstraint("session_id", "confirmation_id", name="uq_confirmations_session_id"),
        Index("ix_confirmations_session_sequence", "session_id", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    confirmation_id: Mapped[str] = mapped_column(String(80))
    action_type: Mapped[str] = mapped_column(String(40))
    sequence: Mapped[int]
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
