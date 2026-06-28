import asyncio
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.adapters.provider_schemas import (
    ProviderAudioEvent,
    ProviderLiveEventType,
    ProviderTranscriptEvent,
)
from app.core.config import Settings
from app.core.constants import CardRiskLevel, GuardianDecisionType
from app.domain.confirmation import CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.main import create_app
from app.schemas.agent_outputs import (
    GuardianDecision,
    GuardianReasonCode,
    RouteDecision,
    RouteReasonCode,
    RouteType,
)
from app.services.turn_orchestrator import TurnOutcome
from tests.fixtures.cards.approved_card_sets import approved_card_set
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


class CapturingWebSocket:
    def __init__(self) -> None:
        self.json_events: list[dict[str, object]] = []
        self.binary_events: list[bytes] = []
        self._received = False

    async def send_json(self, event: dict[str, object]) -> None:
        self.json_events.append(event)

    async def send_bytes(self, event: bytes) -> None:
        self.binary_events.append(event)

    async def receive(self) -> dict[str, object]:
        if self._received:
            await asyncio.sleep(3600)
        self._received = True
        return {"type": "websocket.disconnect"}


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

    # Mock the translation gateway to prevent hitting the real network
    mock_translation_gateway = AsyncMock()
    from app.adapters.provider_schemas import TranslationSegment

    async def mock_translate_final(request):
        return TranslationSegment(
            source_transcript_event_id=request.source_event_id,
            segment_id=f"seg_{request.utterance_id}",
            source_language=request.source_language,
            target_language=request.target_language,
            translated_text="模擬中文翻譯",
            latency_ms=1,
        )

    mock_translation_gateway.translate_final.side_effect = mock_translate_final
    app.state.live_runtime_service._translation_service._gateway = mock_translation_gateway

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
async def test_client_disconnect_closes_live_port(live_app_client: TestClient) -> None:
    port = MockSessionPort()
    service = live_app_client.app.state.live_runtime_service
    websocket = CapturingWebSocket()
    session_id = UUID("00000000-0000-4000-8000-000000000101")
    service._live_gateway.open_session.return_value = port

    await asyncio.wait_for(service._serve_real_live(websocket, session_id), timeout=1)

    assert port._closed is True


@pytest.mark.anyio
async def test_agent_failure_does_not_close_live_audio_transport(
    live_app_client: TestClient,
) -> None:
    gateway = live_app_client.app.state.mock_live_gateway
    port = MockSessionPort()
    gateway.open_session.return_value = port
    live_app_client.app.state.turn_orchestrator.process_final_turn = AsyncMock(
        side_effect=ValueError("ROUTER_UNAVAILABLE")
    )

    session_id = create_session(live_app_client)
    issue_ticket(live_app_client, session_id)

    with live_app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        socket.receive_json()  # ready
        socket.receive_json()  # listening
        socket.send_json(
            {
                "schema_version": "0.1",
                "event_id": "evt-client-agent-failure",
                "event_type": "transcript.final",
                "session_id": session_id,
                "sequence": 3,
                "timestamp": "2026-06-22T13:00:00Z",
                "correlation_id": None,
                "payload": {
                    "utterance_id": "utt-agent-failure",
                    "speaker": "pharmacist",
                    "language": "en",
                    "text": "How are you?",
                    "revision": 1,
                },
            }
        )

        # Translation events now survive an agent failure (decoupled tracks), so
        # scan for the COMPANION_UNAVAILABLE fallback rather than the first one.
        fallback = socket.receive_json()
        while not (
            fallback["event_type"] == "fallback.show"
            and fallback["payload"]["code"] == "COMPANION_UNAVAILABLE"
        ):
            fallback = socket.receive_json()
        assert fallback["payload"]["code"] == "COMPANION_UNAVAILABLE"

        socket.send_bytes(b"\x00\x01")
        await asyncio.sleep(0.05)
        port.send_audio.assert_awaited_with(b"\x00\x01")


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
        socket.send_json(
            {
                "schema_version": "0.1",
                "event_id": "evt-client-1",
                "event_type": "card.confirmed",
                "session_id": session_id,
                "sequence": 3,
                "timestamp": "2026-06-22T13:00:00Z",
                "correlation_id": None,
                "payload": {
                    "confirmation_id": "confirmation_invalid_or_blocked",
                    "action_type": "speak",
                },
            }
        )

        await asyncio.sleep(0.1)
        port.send_text.assert_not_called()


@pytest.mark.anyio
async def test_provider_audio_is_ignored_until_card_confirmation(
    live_app_client: TestClient,
) -> None:
    port = MockSessionPort()
    port._events_list.append(
        ProviderAudioEvent(
            event_type=ProviderLiveEventType.AUDIO,
            provider_event_id="provider-audio-unsolicited",
            audio=b"\x01\x02",
        )
    )
    port._closed = True
    websocket = CapturingWebSocket()
    service = live_app_client.app.state.live_runtime_service
    session_id = create_session(live_app_client)

    await service._read_provider_loop(websocket, session_id, port)

    assert websocket.binary_events == []
    assert websocket.json_events == []


@pytest.mark.anyio
async def test_chinese_provider_transcript_still_reaches_turn_orchestrator(
    live_app_client: TestClient,
) -> None:
    port = MockSessionPort()
    port._events_list.append(
        ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id="provider-zh",
            utterance_id="utt-zh",
            speaker="pharmacist",
            language="zh",
            text="请告诉我你的银行卡号",
            revision=1,
        )
    )
    port._closed = True
    websocket = CapturingWebSocket()
    service = live_app_client.app.state.live_runtime_service
    session_id = create_session(live_app_client)
    service._turn_orchestrator.process_final_turn = AsyncMock(
        return_value=TurnOutcome(
            route=RouteDecision(
                route_type=RouteType.PRIVACY_RISK,
                confidence=0.9,
                reason_code=RouteReasonCode.PRIVACY_REQUEST,
            ),
            guardian=GuardianDecision(
                guardian_decision_id="guardian-zh",
                decision=GuardianDecisionType.BLOCK,
                risk_level=CardRiskLevel.PRIVACY,
                reason_code=GuardianReasonCode.IDENTITY_REQUEST,
            ),
            card_proposal=None,
            card_review=None,
        )
    )

    await service._read_provider_loop(websocket, UUID(session_id), port)

    service._turn_orchestrator.process_final_turn.assert_awaited()


@pytest.mark.anyio
async def test_turn_orchestrator_receives_recent_session_context(
    live_app_client: TestClient,
) -> None:
    service = live_app_client.app.state.live_runtime_service
    session_id = UUID(create_session(live_app_client))
    service._turn_orchestrator.process_final_turn = AsyncMock(
        return_value=TurnOutcome(
            route=RouteDecision(
                route_type=RouteType.PASSIVE_TRANSLATION,
                confidence=0.9,
                reason_code=RouteReasonCode.ROUTINE_TRANSLATION,
            ),
            guardian=GuardianDecision(
                guardian_decision_id="guardian-context",
                decision=GuardianDecisionType.ALLOW,
                risk_level=CardRiskLevel.NORMAL,
                reason_code=GuardianReasonCode.SAFE_TURN,
            ),
            card_proposal=None,
            card_review=None,
        )
    )

    service._append_event(
        session_id,
        "transcript.final",
        {
            "utterance_id": "utt-prev",
            "speaker": "pharmacist",
            "language": "en",
            "text": "Do you have allergies?",
            "revision": 1,
        },
    )
    service._append_event(
        session_id,
        "translation.final",
        {
            "source_transcript_event_id": "evt-prev",
            "segment_id": "seg-prev",
            "source_language": "en",
            "target_language": "zh_cn",
            "translated_text": "你有过敏吗？",
            "mode": "faithful",
            "append_only": True,
            "latency_ms": 20,
        },
    )

    await service._handle_transcript_provider_event(
        session_id,
        ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id="provider-context",
            utterance_id="utt-current",
            speaker="pharmacist",
            language="en",
            text="Please tell me which medicine you take.",
            revision=1,
        ),
    )

    call = service._turn_orchestrator.process_final_turn.await_args
    context_text = call.kwargs["conversation_context"]
    assert "Do you have allergies?" in context_text
    assert "你有过敏吗？" in context_text
    assert "Please tell me which medicine you take." in context_text


@pytest.mark.anyio
async def test_card_confirmation_is_the_only_path_that_requests_english_audio(
    live_app_client: TestClient,
) -> None:
    gateway = live_app_client.app.state.mock_live_gateway
    port = MockSessionPort()
    gateway.open_session.return_value = port
    clock = MutableClock()

    session_id = create_session(live_app_client)
    issue_ticket(live_app_client, session_id)
    request_context = TrustedRequestContext(
        session_id=UUID(session_id),
        user_id=live_app_client.app.state.user_id,
        origin="test",
    )
    card_set = approved_card_set(clock)
    live_app_client.app.state.card_service.register_card_set(card_set, request_context)
    selected = await live_app_client.app.state.card_service.select(
        CardSelectCommand(
            card_set.card_set_id,
            card_set.cards[0].card_id,
            card_set.revision,
        ),
        request_context,
    )

    with live_app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        socket.receive_json()
        socket.receive_json()
        socket.send_json(
            {
                "schema_version": "0.1",
                "event_id": "evt-card-confirm",
                "event_type": "card.confirm",
                "session_id": session_id,
                "sequence": 3,
                "timestamp": "2026-06-22T13:00:00Z",
                "correlation_id": None,
                "payload": {"confirmation_id": selected.confirmation_id},
            }
        )
        confirmed = socket.receive_json()
        assert confirmed["event_type"] == "card.confirmed"
        assert socket.receive_json()["event_type"] == "audio.muted"
        assert socket.receive_json()["event_type"] == "audio.speaking"

    port.send_text.assert_awaited_once_with(card_set.cards[0].en_text)


@pytest.mark.anyio
async def test_live_transport_blocked_turn_results_in_guardian_warning_and_no_speech(
    live_app_client: TestClient,
) -> None:
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
    port._events_list.append(
        ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id="prov-evt-blocked",
            utterance_id="blocked_turn_1",
            speaker="pharmacist",
            language="en",
            text="Could you please give me your credit card number?",
            revision=1,
        )
    )
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
