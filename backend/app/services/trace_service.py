"""Trace service to manage privacy-safe logs and trace recording."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from app.domain.credentials import TrustedRequestContext
from app.repositories.trace_repository import TraceRepository
from app.services.redaction_service import RedactionService

logger = logging.getLogger(__name__)


class TraceService:
    """Orchestrate trace event redaction and write-out with retention expiration metadata."""

    def __init__(
        self,
        repository: TraceRepository,
        redaction_service: RedactionService,
        clock: Callable[[], datetime],
        retention_days: int = 30,
    ) -> None:
        self._repository = repository
        self._redaction = redaction_service
        self._clock = clock
        self._retention_days = retention_days

    async def record_event(
        self,
        context: TrustedRequestContext,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Sanitize payload PII and record audit trace with expiration metadata."""
        # 1. Redact any sensitive credentials/PII from the payload
        clean_payload = self._redaction.redact_payload(payload)

        # 2. Calculate expiration date based on retention policy
        now = self._clock()
        expires_at = now + timedelta(days=self._retention_days)

        # 3. Write to repository
        await self._repository.record(
            context,
            event_type=event_type,
            payload=clean_payload,
            expires_at=expires_at,
        )
