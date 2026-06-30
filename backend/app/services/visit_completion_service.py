"""Visit completion service to compile and persist visit summaries and notifications."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.constants import CardActionType
from app.domain.confirmation import ConfirmationOutcome, StoredConfirmation
from app.domain.credentials import TrustedRequestContext
from app.repositories.confirmation_repository import InMemoryConfirmationRepository
from app.repositories.memory_repository import MemoryRepository
from app.schemas.cards import ResponseCard
from app.schemas.visit_summary import SummaryReview
from app.services.confirmed_action_executor import ConfirmedActionExecutor
from app.services.notification_service import NotificationService
from app.services.visit_summary_service import VisitSummaryService


class VisitCompletionService:
    """Compile session transcripts and execute approved actions (memory/notifications)."""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        visit_summary_service: VisitSummaryService,
        notification_service: NotificationService,
        clock: Callable[[], datetime],
        get_session_events: Callable[[UUID], list[dict[str, Any]]] | None = None,
        retention_days: int = 30,
    ) -> None:
        self._memory = memory_repository
        self._summary_service = visit_summary_service
        self._notification_service = notification_service
        self._clock = clock
        self._get_session_events = get_session_events
        self._retention_days = retention_days
        self._draft_summaries: dict[UUID, SummaryReview] = {}

    def discard_session(self, session_id: UUID) -> None:
        self._draft_summaries.pop(session_id, None)

    async def prepare_summary(
        self,
        session_id: UUID,
        context: TrustedRequestContext,
    ) -> SummaryReview:
        """Compile final transcript text and RAG context into a draft summary."""
        events = []
        if self._get_session_events is not None:
            events = self._get_session_events(session_id)

        summary = self._summary_service.compile_summary_from_events(events)
        self._draft_summaries[session_id] = summary
        return summary

    async def execute_confirmed_action(
        self,
        confirmation: StoredConfirmation,
        context: TrustedRequestContext,
    ) -> None:
        """Execute the confirmed card action using the prepared draft summary."""
        # 1. Retrieve draft summary or compile on-demand
        summary = self._draft_summaries.get(confirmation.session_id)
        if summary is None:
            summary = await self.prepare_summary(confirmation.session_id, context)

        # 2. Persist to SQLite memory or send to family notification stub
        if confirmation.action_type == CardActionType.SAVE_MEMORY:
            expires_at = self._clock() + timedelta(days=self._retention_days)
            await self._memory.write_visit_summary(
                summary=summary,
                context=context,
                key=f"visit_summary:{confirmation.session_id}",
                tags=("visit_summary",),
                idempotency_key=confirmation.idempotency_key,
                expires_at=expires_at,
            )
        elif confirmation.action_type == CardActionType.NOTIFY_FAMILY:
            await self._notification_service.send_family_notification(
                summary=summary,
                context=context,
                idempotency_key=confirmation.idempotency_key,
            )




class VisitCompletionExecutor(ConfirmedActionExecutor):
    """Subclass of ConfirmedActionExecutor that delegates SAVE_MEMORY and NOTIFY_FAMILY."""

    def __init__(
        self,
        completion_service: VisitCompletionService,
        repository: InMemoryConfirmationRepository,
    ) -> None:
        super().__init__()
        self._completion_service = completion_service
        self._repository = repository

    async def execute(
        self,
        confirmation_id: str,
        card: ResponseCard,
        context: TrustedRequestContext | None = None,
    ) -> ConfirmationOutcome:
        self.action_count += 1
        record = self._repository.get(confirmation_id)
        if record is not None and context is not None:
            await self._completion_service.execute_confirmed_action(record, context)
        return ConfirmationOutcome(
            confirmation_id=confirmation_id,
            action_type=card.action.type,
            replayed=False,
            phase="succeeded",
            code=None,
        )


