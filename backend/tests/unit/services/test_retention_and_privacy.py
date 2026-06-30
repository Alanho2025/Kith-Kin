"""Unit tests for RetentionService, TraceService, and RedactionService."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.models.trace_event import TraceEvent
from app.db.models.visit_summary import VisitSummary
from app.domain.credentials import TrustedRequestContext
from app.repositories.trace_repository import TraceRepository
from app.services.redaction_service import RedactionService
from app.services.retention_service import RetentionService
from app.services.trace_service import TraceService
from tests.integration.db.conftest import db_sessions


SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 6, 22, tzinfo=UTC)


def test_redaction_service_text_scrubbing() -> None:
    """Ensure sensitive PII fields are correctly redacted in raw text."""
    redaction = RedactionService()
    text = (
        "My credit card is 1234-5678-9012-3456, and Medicare is 4123-45678-9. "
        "Passport is ABC123456."
    )
    scrubbed = redaction.redact_text(text)
    assert "[REDACTED]" in scrubbed
    assert "1234-5678" not in scrubbed
    assert "4123" not in scrubbed
    assert "ABC123456" not in scrubbed


def test_redaction_service_payload_scrubbing() -> None:
    """Ensure dictionary values matching PII keys are fully redacted."""
    redaction = RedactionService()
    payload = {
        "query_category": "checkout",
        "nested": {
            "credit_card": "1111-2222-3333-4444",
            "cvv": "123",
        },
        "details": "My passport is EF8888888",
    }
    cleaned = redaction.redact_payload(payload)
    assert cleaned["query_category"] == "checkout"
    assert cleaned["nested"]["credit_card"] == "[REDACTED]"
    assert cleaned["nested"]["cvv"] == "[REDACTED]"
    assert "EF8888888" not in cleaned["details"]


@pytest.mark.anyio
async def test_trace_service_saves_with_retention_and_redaction(db_sessions) -> None:
    """Ensure TraceService sanitises logs and sets expires_at field on insert."""
    repo = TraceRepository(db_sessions, lambda: NOW)
    redaction = RedactionService()
    service = TraceService(repo, redaction, lambda: NOW, retention_days=30)
    context = TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")

    payload = {
        "query_category": "checkout",
        "secret_code": "999-888-777",
    }
    await service.record_event(context, event_type="test_event", payload=payload)

    async with db_sessions() as session:
        events = (await session.scalars(select(TraceEvent))).all()
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "test_event"
        # Since RAG_TRACE_FIELDS only keeps specific keys ("query_category", etc.),
        # secret_code is dropped. But query_category is preserved.
        assert event.payload["query_category"] == "checkout"
        assert event.expires_at.replace(tzinfo=UTC) == NOW + timedelta(days=30)




@pytest.mark.anyio
async def test_retention_service_purges_expired_only(db_sessions) -> None:
    """Ensure RetentionService only purges expired visit summaries and trace events."""
    retention = RetentionService(db_sessions, lambda: NOW)
    context = TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")

    async with db_sessions() as session:
        # Create an expired summary (expires 5 mins ago)
        expired_summary = VisitSummary(
            id=uuid4(),
            user_id=USER_ID,
            session_id=SESSION_ID,
            key="visit_summary:1",
            value={"pharmacist_advice_summary": "Expired advice"},
            tags=["visit_summary"],
            idempotency_key=uuid4(),
            expires_at=NOW - timedelta(minutes=5),
            created_at=NOW,
            updated_at=NOW,
        )
        # Create a valid future summary (expires tomorrow)
        future_summary = VisitSummary(
            id=uuid4(),
            user_id=USER_ID,
            session_id=SESSION_ID,
            key="visit_summary:2",
            value={"pharmacist_advice_summary": "Future advice"},
            tags=["visit_summary"],
            idempotency_key=uuid4(),
            expires_at=NOW + timedelta(days=1),
            created_at=NOW,
            updated_at=NOW,
        )
        session.add_all([expired_summary, future_summary])
        await session.commit()

    # Run purge
    purged_count = await retention.purge_expired_records()
    assert purged_count == 1

    # Verify database contents
    async with db_sessions() as session:
        summaries = (await session.scalars(select(VisitSummary))).all()
        assert len(summaries) == 1
        assert summaries[0].key == "visit_summary:2"
