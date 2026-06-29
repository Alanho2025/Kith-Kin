from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.credentials import TrustedRequestContext
from app.services.visit_completion_service import VisitCompletionService

SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 6, 22, tzinfo=UTC)


def transcript_event(
    *,
    speaker: str,
    text: str,
    event_id: str,
) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "event_id": event_id,
        "event_type": "transcript.final",
        "session_id": str(SESSION_ID),
        "sequence": 1,
        "timestamp": NOW.isoformat(),
        "correlation_id": None,
        "payload": {
            "utterance_id": f"utt-{event_id}",
            "speaker": speaker,
            "language": "en",
            "text": text,
            "revision": 1,
        },
    }


@pytest.mark.anyio
async def test_summary_uses_only_pharmacist_transcript_without_inventing_advice() -> None:
    service = VisitCompletionService(
        memory_repository=None,
        notification_repository=None,
        get_session_events=lambda _sid: [
            transcript_event(
                speaker="pharmacist",
                text="You should try Coenzyme Q10 for your muscle aches.",
                event_id="evt-coq10",
            )
        ],
    )
    context = TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")

    summary = await service.prepare_summary(SESSION_ID, context)

    assert summary.mentioned_drugs == ("coenzyme q10",)
    assert summary.pharmacist_advice_summary == (
        "Pharmacist said: You should try Coenzyme Q10 for your muscle aches."
    )
    assert summary.unresolved_questions == ()
    assert summary.follow_up_needed is False
    assert summary.family_notification_requested is False


@pytest.mark.anyio
async def test_summary_does_not_add_interaction_or_alternative_not_spoken_by_pharmacist() -> None:
    service = VisitCompletionService(
        memory_repository=None,
        notification_repository=None,
        get_session_events=lambda _sid: [
            transcript_event(
                speaker="parent",
                text="I am taking perindopril.",
                event_id="evt-parent-medicine",
            ),
            transcript_event(
                speaker="pharmacist",
                text="I can show you ibuprofen for pain. The price is 9 dollars.",
                event_id="evt-ibuprofen-price",
            ),
        ],
    )
    context = TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")

    summary = await service.prepare_summary(SESSION_ID, context)

    assert summary.mentioned_drugs == ("ibuprofen", "perindopril")
    assert summary.pharmacist_advice_summary == (
        "Pharmacist said: I can show you ibuprofen for pain. The price is 9 dollars."
    )
    assert "Panadol" not in summary.pharmacist_advice_summary
    assert "interaction" not in summary.pharmacist_advice_summary.lower()
