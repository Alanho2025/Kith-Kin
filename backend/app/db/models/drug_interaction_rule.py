"""Drug interaction rule rows."""

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DrugInteractionRule(Base):
    """General class-level drug interaction rules."""

    __tablename__ = "drug_interaction_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    risk: Mapped[str] = mapped_column(String(20))  # "HIGH", "MODERATE", "LOW", "MONITOR"
    mechanism: Mapped[str] = mapped_column(String(1000))
    recommendation: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(200))
