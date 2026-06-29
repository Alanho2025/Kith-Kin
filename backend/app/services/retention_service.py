"""Retention service to purge expired traces and summaries."""

import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import delete

from app.db.models.trace_event import TraceEvent
from app.db.models.visit_summary import VisitSummary
from app.db.session import AsyncSessionFactory

logger = logging.getLogger(__name__)


class RetentionService:
    """Manage retention policies and purge expired privacy-sensitive database rows."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def purge_expired_records(self) -> int:
        """Hard delete all trace events and visit summaries past their retention expiration date."""
        now = self._clock()
        purged_count = 0

        async with self._session_factory() as session:
            # 1. Purge expired trace events
            trace_stmt = delete(TraceEvent).where(
                TraceEvent.expires_at.is_not(None),
                TraceEvent.expires_at < now,
            )
            trace_result = await session.execute(trace_stmt)
            purged_count += trace_result.rowcount

            # 2. Purge expired visit summaries
            summary_stmt = delete(VisitSummary).where(
                VisitSummary.expires_at.is_not(None),
                VisitSummary.expires_at < now,
            )
            summary_result = await session.execute(summary_stmt)
            purged_count += summary_result.rowcount

            await session.commit()

        logger.info("Retention sweep completed. Purged %d expired records.", purged_count)
        return purged_count
