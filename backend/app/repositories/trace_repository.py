"""Redacted trace repository."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import func, select

from app.db.models.trace_event import TraceEvent
from app.db.session import AsyncSessionFactory
from app.domain.credentials import TrustedRequestContext

RAG_TRACE_FIELDS = {"query_category", "record_count", "latency_ms", "outcome", "truncated"}


class TraceRepository:
    """Persist only explicit allowlisted trace metadata."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def record(
        self,
        context: TrustedRequestContext,
        *,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        safe_payload = {key: payload[key] for key in sorted(payload) if key in RAG_TRACE_FIELDS}
        async with self._session_factory() as session:
            next_sequence = (
                await session.scalar(
                    select(func.count()).select_from(TraceEvent).where(
                        TraceEvent.session_id == context.session_id
                    )
                )
            ) or 0
            session.add(
                TraceEvent(
                    session_id=context.session_id,
                    user_id=context.user_id,
                    sequence=next_sequence + 1,
                    event_type=event_type,
                    payload=safe_payload,
                    created_at=self._clock(),
                )
            )
            await session.commit()
