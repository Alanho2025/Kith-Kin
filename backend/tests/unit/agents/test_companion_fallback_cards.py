from datetime import UTC, datetime

import pytest

from app.agents.companion_agent import CompanionAgent
from app.agents.guardian_agent import GuardianAgent
from app.core.constants import GuardianDecisionType
from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.runtime_events import TranscriptFinalEvent, TranscriptPayload

NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


def event(text: str, *, event_id: str = "evt-fallback-1") -> TranscriptFinalEvent:
    return TranscriptFinalEvent(
        schema_version="0.1",
        event_id=event_id,
        event_type="transcript.final",
        session_id="session-fallback-1",
        sequence=1,
        timestamp=NOW,
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id="utt-fallback-1",
            speaker="pharmacist",
            language="en",
            text=text,
            revision=1,
        ),
    )


def route() -> RouteDecision:
    return RouteDecision(
        route_type=RouteType.PHARMACY_RISK,
        confidence=0.98,
        reason_code=RouteReasonCode.PHARMACY_TERM,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("text", "event_id"),
    [
        ("Would ibuprofen be okay?", "evt-ibuprofen"),
        ("Do you have any allergies to medicines?", "evt-allergies"),
        ("I am here to pick up my prescription.", "eval-015-prescription"),
    ],
)
async def test_no_key_companion_fallback_proposes_guardian_safe_cards(
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    event_id: str,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    companion = CompanionAgent(lambda: NOW)
    guardian = GuardianAgent()

    proposal = await companion.propose_cards(
        event(text, event_id=event_id),
        route(),
        guardian_decision_id="guardian-pending",
        mcp_adapter=None,
    )
    decision = await guardian.review_cards(proposal.card_set)

    assert decision.decision is GuardianDecisionType.ALLOW
    assert all("Ask pharmacist" not in card.en_text for card in proposal.card_set.cards)
    assert all("Should I take" not in card.en_text for card in proposal.card_set.cards)
