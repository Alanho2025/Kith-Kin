"""SQLite memory repository for bounded RAG and confirmed writes."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.errors import IdempotencyConflictError
from app.db.models.allergy import Allergy
from app.db.models.medication import Medication
from app.db.models.visit_summary import VisitSummary
from app.db.session import AsyncSessionFactory
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalCategory, RetrievalRequest, RetrievalSnippet
from app.schemas.mcp import VisitSummaryValue


@dataclass(frozen=True)
class MemoryWriteOutcome:
    """Result of an idempotent visit-summary write."""

    record_id: UUID
    key: str
    tags: tuple[str, ...]
    replayed: bool


class MemoryRepository:
    """Repository boundary for authorised memory reads and writes."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def search(
        self,
        request: RetrievalRequest,
        context: TrustedRequestContext,
    ) -> Sequence[RetrievalSnippet]:
        async with self._session_factory() as session:
            rows: list[RetrievalSnippet] = []
            if _includes(request, RetrievalCategory.MEDICATIONS):
                medications = (
                    await session.scalars(
                        select(Medication).where(Medication.user_id == context.user_id)
                    )
                ).all()
                rows.extend(_medication_snippet(item, request) for item in medications)
            if _includes(request, RetrievalCategory.ALLERGIES):
                allergies = (
                    await session.scalars(select(Allergy).where(Allergy.user_id == context.user_id))
                ).all()
                rows.extend(_allergy_snippet(item, request) for item in allergies)
            if _includes(request, RetrievalCategory.VISIT_SUMMARY):
                visits = (
                    await session.scalars(
                        select(VisitSummary).where(VisitSummary.user_id == context.user_id)
                    )
                ).all()
                rows.extend(_visit_snippet(item, request) for item in visits)
            return tuple(item for item in rows if item.tag_match_count > 0 or request.query)

    async def write_visit_summary(
        self,
        summary: VisitSummaryValue,
        context: TrustedRequestContext,
        *,
        key: str,
        tags: tuple[str, ...],
        idempotency_key: UUID,
        expires_at: datetime | None = None,
    ) -> MemoryWriteOutcome:
        payload = summary.model_dump(mode="json")
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(VisitSummary).where(VisitSummary.idempotency_key == idempotency_key)
            )
            if existing is not None:
                if (
                    existing.key == key
                    and existing.value == payload
                    and tuple(existing.tags) == tags
                ):
                    return MemoryWriteOutcome(existing.id, existing.key, tuple(existing.tags), True)
                raise IdempotencyConflictError
            now = self._clock()
            row = VisitSummary(
                id=uuid4(),
                user_id=context.user_id,
                session_id=context.session_id,
                key=key,
                value=payload,
                tags=list(tags),
                idempotency_key=idempotency_key,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.commit()
            return MemoryWriteOutcome(row.id, row.key, tuple(row.tags), False)



def _includes(request: RetrievalRequest, category: RetrievalCategory) -> bool:
    return (
        request.category in {RetrievalCategory.PROFILE, category} or category.value in request.tags
    )


def _tag_match_count(row_tags: Sequence[str], request: RetrievalRequest, content: str) -> int:
    requested_tags = {tag.lower() for tag in request.tags}
    tags = {tag.lower() for tag in row_tags}
    count = len(requested_tags & tags)
    if request.query.lower() in content.lower():
        count += 1
    return count


def _medication_snippet(row: Medication, request: RetrievalRequest) -> RetrievalSnippet:
    content = (
        f"Medication: {row.name}. Dose: {row.dose or 'unknown'}. Notes: {row.notes or 'none'}."
    )
    return RetrievalSnippet(
        record_id=row.id,
        record_type="medication",
        content=content,
        updated_at=row.updated_at,
        tag_match_count=_tag_match_count(row.tags, request, content),
    )


def _allergy_snippet(row: Allergy, request: RetrievalRequest) -> RetrievalSnippet:
    content = f"Allergy: {row.substance}. Reaction: {row.reaction or 'unknown'}."
    return RetrievalSnippet(
        record_id=row.id,
        record_type="allergy",
        content=content,
        updated_at=row.updated_at,
        tag_match_count=_tag_match_count(row.tags, request, content),
    )


def _visit_snippet(row: VisitSummary, request: RetrievalRequest) -> RetrievalSnippet:
    summary = str(row.value.get("pharmacist_advice_summary", ""))
    raw_drugs = row.value.get("mentioned_drugs", [])
    drugs = ", ".join(str(item) for item in raw_drugs) if isinstance(raw_drugs, list) else ""
    content = f"Visit summary: {summary}. Mentioned drugs: {drugs or 'none'}."
    return RetrievalSnippet(
        record_id=row.id,
        record_type="visit_summary",
        content=content,
        updated_at=row.updated_at,
        tag_match_count=_tag_match_count(row.tags, request, content),
    )
