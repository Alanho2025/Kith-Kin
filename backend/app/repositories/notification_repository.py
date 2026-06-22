"""Notification stub repository with idempotency."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.errors import IdempotencyConflictError
from app.db.models.notification import Notification
from app.db.session import AsyncSessionFactory
from app.domain.credentials import TrustedRequestContext
from app.schemas.mcp import VisitSummaryValue


@dataclass(frozen=True)
class NotificationOutcome:
    """Result of a local notification stub send."""

    notification_id: UUID
    provider: str
    delivered: bool
    replayed: bool


class NotificationRepository:
    """Persist parent-approved notification attempts without a real provider."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def send_stub(
        self,
        summary: VisitSummaryValue,
        context: TrustedRequestContext,
        *,
        idempotency_key: UUID,
    ) -> NotificationOutcome:
        payload = summary.model_dump(mode="json")
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(Notification).where(Notification.idempotency_key == idempotency_key)
            )
            if existing is not None:
                if existing.summary == payload:
                    return NotificationOutcome(existing.id, existing.provider, True, True)
                raise IdempotencyConflictError
            row = Notification(
                id=uuid4(),
                user_id=context.user_id,
                session_id=context.session_id,
                summary=payload,
                provider="stub",
                status="delivered",
                idempotency_key=idempotency_key,
                created_at=self._clock(),
            )
            session.add(row)
            await session.commit()
            return NotificationOutcome(row.id, row.provider, True, False)
