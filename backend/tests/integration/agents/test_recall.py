from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.agents.companion_agent import CompanionAgent
from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.cards import CardType
from app.schemas.runtime_events import TranscriptFinalEvent

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class DummySessionService:
    def __init__(self, prefetch_cache=None) -> None:
        self.prefetch_cache = prefetch_cache or {}


def final_event(text: str) -> TranscriptFinalEvent:
    return TranscriptFinalEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-final-1",
            "event_type": "transcript.final",
            "session_id": str(SESSION_ID),
            "sequence": 3,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {
                "utterance_id": "utt-1",
                "speaker": "pharmacist",
                "language": "en",
                "text": text,
                "revision": 1,
            },
        }
    )


@pytest.mark.anyio
async def test_recall_coq10_when_present_in_prior_summary() -> None:
    # 1. Setup session service with prefetch cache containing CoQ10 advice
    cache = {
        SESSION_ID: [
            {
                "pharmacist_advice_summary": (
                    "Suggested trying Coenzyme Q10 for statin-related muscle pain"
                ),
                "unresolved_questions": ["Check if CoQ10 interacts with current medications"],
            }
        ]
    }
    session_service = DummySessionService(cache)
    companion_agent = CompanionAgent(lambda: NOW, session_service)

    route_decision = RouteDecision(
        route_type=RouteType.RESPONSE_NEEDED,
        confidence=0.9,
        reason_code=RouteReasonCode.QUESTION_DETECTED,
    )

    proposal = await companion_agent.propose_cards(
        final_event("Hi, I'm here to pick up my prescription again."),
        route_decision,
        f"guardian_{uuid4()}",
    )

    assert len(proposal.card_set.cards) == 1
    card = proposal.card_set.cards[0]
    assert card.card_type == CardType.ASK_QUESTION
    assert "辅酶Q10" in card.zh_text
    assert "Coenzyme Q10" in card.en_text


@pytest.mark.anyio
async def test_no_recall_coq10_when_absent_in_prior_summary() -> None:
    # 2. Setup session service with empty cache
    session_service = DummySessionService()
    companion_agent = CompanionAgent(lambda: NOW, session_service)

    route_decision = RouteDecision(
        route_type=RouteType.RESPONSE_NEEDED,
        confidence=0.9,
        reason_code=RouteReasonCode.QUESTION_DETECTED,
    )

    proposal = await companion_agent.propose_cards(
        final_event("Hi, I'm here to pick up my prescription again."),
        route_decision,
        f"guardian_{uuid4()}",
    )

    assert len(proposal.card_set.cards) == 1
    card = proposal.card_set.cards[0]
    # Verify we do not suggest CoQ10 if absent in prior summary
    assert "辅酶Q10" not in card.zh_text
    assert "Coenzyme Q10" not in card.en_text
    assert "处方药" in card.zh_text
