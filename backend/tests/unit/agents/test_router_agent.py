from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agents.router_agent import RouterAgent
from app.schemas.agent_outputs import RouteType
from app.schemas.runtime_events import TranscriptFinalEvent

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = uuid4()


def make_event(text: str) -> TranscriptFinalEvent:
    return TranscriptFinalEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": f"evt-{uuid4()}",
            "event_type": "transcript.final",
            "session_id": str(SESSION_ID),
            "sequence": 1,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {
                "utterance_id": f"utt-{uuid4()}",
                "speaker": "pharmacist",
                "language": "en",
                "text": text,
                "revision": 1,
            },
        }
    )


@pytest.mark.anyio
async def test_router_handles_small_talk_and_greetings() -> None:
    router = RouterAgent()

    # Greetings and help prompts should require response
    event_help = make_event("Hi, how can I help you today?")
    decision_help = await router.route(event_help)
    assert decision_help.route_type == RouteType.RESPONSE_NEEDED

    event_hello = make_event("Hello there!")
    decision_hello = await router.route(event_hello)
    assert decision_hello.route_type == RouteType.RESPONSE_NEEDED


@pytest.mark.anyio
async def test_router_handles_chinese_input_routing() -> None:
    router = RouterAgent()

    # Chinese translation transcripts should route to corresponding risk categories
    event_allergy = make_event("请问您有任何药物过敏吗？")
    decision_allergy = await router.route(event_allergy)
    assert decision_allergy.route_type == RouteType.PHARMACY_RISK

    event_med = make_event("您目前正在服用其他药物吗？")
    decision_med = await router.route(event_med)
    assert decision_med.route_type == RouteType.PHARMACY_RISK

    event_privacy = make_event("请告诉我的你的信用卡号")
    decision_privacy = await router.route(event_privacy)
    assert decision_privacy.route_type == RouteType.PRIVACY_RISK
