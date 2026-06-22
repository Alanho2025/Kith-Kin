"""Visit-summary read repository."""

from uuid import UUID

from sqlalchemy import select

from app.db.models.visit_summary import VisitSummary
from app.db.session import AsyncSessionFactory


class VisitRepository:
    """Read persisted visit summaries for recall flows."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def recent_for_user(self, user_id: UUID, *, limit: int = 5) -> tuple[VisitSummary, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(VisitSummary)
                    .where(VisitSummary.user_id == user_id)
                    .order_by(VisitSummary.updated_at.desc(), VisitSummary.id)
                    .limit(limit)
                )
            ).all()
            return tuple(rows)
