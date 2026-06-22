"""Visit summary memory rows."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VisitSummary(Base):
    """Structured parent-confirmed visit summary."""

    __tablename__ = "visit_summaries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_visit_summaries_idempotency_key"),
        Index("ix_visit_summaries_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    session_id: Mapped[UUID]
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[dict[str, object]] = mapped_column(JSON)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
