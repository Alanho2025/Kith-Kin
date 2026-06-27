"""Notification stub audit rows."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    """Local-first notification stub result."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    summary: Mapped[dict[str, object]] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(40), default="stub")
    status: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
