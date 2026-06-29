"""Notification stub adapter."""

import logging
from uuid import UUID

from app.domain.credentials import TrustedRequestContext
from app.schemas.visit_summary import SummaryReview

logger = logging.getLogger(__name__)


class NotificationAdapter:
    """Stub notification adapter acting as gateway boundary to third-party SMS/email providers."""

    async def deliver_stub_notification(
        self,
        summary: SummaryReview,
        context: TrustedRequestContext,
        idempotency_key: UUID,
    ) -> bool:
        """Deliver the visit summary to a stub external family contact."""
        logger.info(
            "Delivering stub family notification. Session: %s, User: %s, Key: %s",
            context.session_id,
            context.user_id,
            idempotency_key,
        )
        return True
