"""Drug knowledge entity rows."""

from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DrugKnowledgeEntity(Base):
    """General drug or substance knowledge profiles."""

    __tablename__ = "drug_knowledge_entities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(30))  # "prescription", "otc", "substance"
    class_name: Mapped[str] = mapped_column(String(120))
    brands_or_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    indications_or_use: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings_or_notes: Mapped[list[str]] = mapped_column(JSON, default=list)
    common_in_elderly: Mapped[bool] = mapped_column(Boolean, default=False)
