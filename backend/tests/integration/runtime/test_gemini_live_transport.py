import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.adapters.provider_schemas import ProviderLiveEventType, ProviderTranscriptEvent
from app.core.config import Settings
from app.main import create_app
from tests.fixtures.clock import MutableClock
from tests.fixtures.signing import TEST_SIGNING_KEY
from tests.integration.api.conftest import ORIGIN, create_session, issue_ticket


class MockSessionPort(AsyncMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._events_list = []
        self._closed = False

    def events(self):
        async def event_generator():
            for e in self._events_list:
                yield e
            if not self._closed:
                await asyncio.sleep(3600)
        return event_generator()

    async def close(self) -> None:
        self._closed = True


@pytest.fixture
def live_app_client() -> TestClient:
    clock = MutableClock()
    settings = Settings(
        environment="test",
        cors_allowed_origins=[ORIGIN],
        app_ws_token_secret=TEST_SIGNING_KEY,
        app_ws_cookie_secure=False,
        live_transport="gemini_live",
        google_api_key="test_api_key",
    )
    
    app = create_app(settings=settings, clock=clock.now)
    app.state.mock_live_gateway = AsyncMock()
    app.state.live_runtime_service._live_gateway = app.state.mock_live_gateway
    
    with TestClient(app) as client:
        yield client


@pytest.mark.anyio
async def test_live_transport_fails_gracefully_on_open_error(live_app_client: TestClient) -> None:
    gateway = live_app_client.app.state.mock_live_gateway
    gateway.open_session.side_effect = Exception("Live API connection refused")

    session_id = create_session(live_app_client)
    issue_ticket(live_app_client, session_id)

    with live_app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        ready = socket.receive_json()
        assert ready["event_type"] == "session.ready"
        listening = socket.receive_json()
        assert listening["event_type"] == "audio.listening"
        
        fallback = socket.receive_json()
        assert fallback["event_type"] == "fallback.show"
        assert fallback["payload"]["code"] == "LIVE_UNAVAILABLE"


@pytest.mark.anyio
async def test_live_transport_guardian_gates_before_speak(live_app_client: TestClient) -> None:
    gateway = live_app_client.app.state.mock_live_gateway
    port = MockSessionPort()
    gateway.open_session.return_value = port

    session_id = create_session(live_app_client)
    issue_ticket(live_app_client, session_id)

    with live_app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        socket.receive_json()  # ready
        socket.receive_json()  # listening

        # Send a forged confirm event for a non-existent card
        socket.send_json({
            "schema_version": "0.1",
            "event_id": "evt-client-1",
            "event_type": "card.confirmed",
            "session_id": session_id,
            "sequence": 3,
            "timestamp": "2026-06-22T13:00:00Z",
            "correlation_id": None,
            "payload": {
                "confirmation_id": "confirmation_invalid_or_blocked",
                "action_type": "speak"
            }
        })

        await asyncio.sleep(0.1)
        port.send_text.assert_not_called()


@pytest.mark.anyio
async def test_live_transport_blocked_turn_results_in_guardian_warning_and_no_speech(live_app_client: TestClient) -> None:
    from app.services.turn_orchestrator import TurnOutcome
    from app.schemas.agent_outputs import GuardianDecision, RouteDecision, RouteType, RouteReasonCode, GuardianReasonCode
    from app.core.constants import GuardianDecisionType, CardRiskLevel

    gateway = live_app_client.app.state.mock_live_gateway
    port = MockSessionPort()
    
    # Mock TurnOrchestrator to return a blocked turn outcome to avoid calling the real LLM/network
    live_app_client.app.state.turn_orchestrator.process_final_turn = AsyncMock(
        return_value=TurnOutcome(
            route=RouteDecision(
                route_type=RouteType.PRIVACY_RISK,
                confidence=1.0,
                reason_code=RouteReasonCode.PRIVACY_REQUEST,
            ),
            guardian=GuardianDecision(
                guardian_decision_id="guardian-decision-blocked",
                decision=GuardianDecisionType.BLOCK,
                risk_level=CardRiskLevel.PRIVACY,
                reason_code=GuardianReasonCode.PAYMENT_REQUEST,
            ),
            card_proposal=None,
            card_review=None,
        )
    )

    # Simulate a provider final transcript that violates privacy
    port._events_list.append(ProviderTranscriptEvent(
        event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
        provider_event_id="prov-evt-blocked",
        utterance_id="blocked_turn_1",
        speaker="pharmacist",
        language="en",
        text="Could you please give me your credit card number?",
        revision=1,
    ))
    gateway.open_session.return_value = port

    session_id = create_session(live_app_client)
    issue_ticket(live_app_client, session_id)

    with live_app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        socket.receive_json()  # ready
        socket.receive_json()  # listening

        # Wait for the event loop in background reader task to process it
        # We should read the events from the socket
        events = []
        for _ in range(5):
            events.append(socket.receive_json())

        event_types = [e["event_type"] for e in events]
        assert "transcript.final" in event_types
        assert "translation.pending" in event_types
        assert "route.decision" in event_types
        assert "guardian.warning" in event_types

        # Find the guardian warning event and check it is block
        warning_event = next(e for e in events if e["event_type"] == "guardian.warning")
        assert warning_event["payload"]["decision"] == "block"

        # Verify that no cards were rendered (no cards.render event)
        # And that no text was sent to be voiced
        port.send_text.assert_not_called()
