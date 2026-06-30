"""Notification service to manage family communication workflows."""

import logging
from uuid import UUID

from app.adapters.notification_adapter import NotificationAdapter
from app.domain.credentials import TrustedRequestContext
from app.repositories.notification_repository import NotificationOutcome, NotificationRepository
from app.schemas.mcp import VisitSummaryValue
from app.schemas.visit_summary import SummaryReview

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrate family notification delivery and database trace logging."""

    def __init__(
        self,
        repository: NotificationRepository,
        adapter: NotificationAdapter,
    ) -> None:
        self._repository = repository
        self._adapter = adapter

    async def send_family_notification(
        self,
        summary: SummaryReview,
        context: TrustedRequestContext,
        idempotency_key: UUID,
    ) -> NotificationOutcome:
        """Deliver the notification stub and persist the transaction."""
        # Convert SummaryReview to VisitSummaryValue
        mcp_summary = VisitSummaryValue(
            mentioned_drugs=summary.mentioned_drugs,
            pharmacist_advice_summary=summary.pharmacist_advice_summary,
            unresolved_questions=summary.unresolved_questions,
            follow_up_needed=summary.follow_up_needed,
            family_notification_requested=summary.family_notification_requested,
            pharmacist_stated_advice=summary.pharmacist_stated_advice,
            unresolved_follow_up_questions=summary.unresolved_follow_up_questions,
            confirmed_family_follow_up=summary.confirmed_family_follow_up,
        )

        # Call third-party stub adapter
        await self._adapter.deliver_stub_notification(
            summary=summary,
            context=context,
            idempotency_key=idempotency_key,
        )

        # Persist transaction to repository
        outcome = await self._repository.send_stub(
            summary=mcp_summary,
            context=context,
            idempotency_key=idempotency_key,
        )
        return outcome
