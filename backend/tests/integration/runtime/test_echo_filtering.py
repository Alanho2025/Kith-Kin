from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.adapters.provider_schemas import (
    ProviderLiveEventType,
    ProviderTranscriptEvent,
)
from app.services.live_runtime_service import LiveRuntimeService
from app.services.runtime_command_service import RuntimeCommandEvent, RuntimeCommandService


def _get_mock_time() -> datetime:
    return datetime(2026, 6, 22, tzinfo=UTC)


@pytest.mark.anyio
async def test_standardized_echo_cancellation() -> None:
    # Set up mocks for dependencies
    card_service = MagicMock()
    fake_live = MagicMock()
    translation_service = AsyncMock()
    command_service = AsyncMock()
    turn_orchestrator = AsyncMock()
    user_id = UUID("00000000-0000-4000-8000-000000000001")
    session_id = UUID("00000000-0000-4000-8000-000000000101")

    service = LiveRuntimeService(
        card_service=card_service,
        fake_live=fake_live,
        clock=_get_mock_time,
        translation_service=translation_service,
        command_service=command_service,
        turn_orchestrator=turn_orchestrator,
        user_id=user_id,
    )

    # 1. Establish last spoken text (as if system spoke it)
    service._last_spoken_text[session_id] = (
        "Could you check whether this conflicts with my blood pressure medicine?"
    )

    # 2. Simulate incoming transcript event matching last spoken text (with different punctuation)
    provider_event = ProviderTranscriptEvent(
        event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
        provider_event_id="evt-echo-1",
        utterance_id="utt-echo-1",
        speaker="pharmacist",
        language="en",
        text="Could you check whether this conflicts with my blood pressure medicine...",
        revision=1,
    )

    # 3. Handle the event
    outcomes = await service.handle_provider_event(session_id, provider_event)

    # 4. Assert that the event is ignored (returns empty outcome, no translation/routing triggered)
    assert outcomes == ()
    translation_service.translate_final.assert_not_called()
    turn_orchestrator.process_final_turn.assert_not_called()


@pytest.mark.anyio
async def test_repeat_event_voices_generic_phrase() -> None:
    # Set up mocks
    card_service = MagicMock()
    fake_live = MagicMock()
    translation_service = AsyncMock()
    turn_orchestrator = AsyncMock()
    user_id = UUID("00000000-0000-4000-8000-000000000001")
    session_id = UUID("00000000-0000-4000-8000-000000000101")
    mock_port = AsyncMock()

    # We need command_service to construct RepeatEvent outcome, or we mock it
    command_service = AsyncMock(spec=RuntimeCommandService)
    command_service.handle.return_value = (
        RuntimeCommandEvent("audio.listening", {"active": True}, "evt-repeat-1"),
    )

    service = LiveRuntimeService(
        card_service=card_service,
        fake_live=fake_live,
        clock=_get_mock_time,
        translation_service=translation_service,
        command_service=command_service,
        turn_orchestrator=turn_orchestrator,
        user_id=user_id,
    )

    # Trigger RepeatEvent command via _handle_live_command helper
    websocket = AsyncMock()
    repeat_command_json = {
        "schema_version": "0.1",
        "event_id": "evt-repeat-1",
        "event_type": "control.repeat",
        "session_id": str(session_id),
        "sequence": 5,
        "timestamp": _get_mock_time().isoformat(),
        "correlation_id": None,
        "payload": {"target": "last_translation"},
    }

    await service._handle_live_command(
        websocket=websocket,
        session_id=session_id,
        text=json_dumps(repeat_command_json),
        port=mock_port,
    )

    # Assert that generic text "Could you please say that again?" is voiced
    mock_port.send_text.assert_awaited_with("Could you please say that again?")
    assert service._last_spoken_text[session_id] == "Could you please say that again?"


@pytest.mark.anyio
async def test_parent_chinese_to_english_translation_capture() -> None:
    # Set up mocks
    card_service = MagicMock()
    fake_live = MagicMock()
    translation_service = AsyncMock()
    turn_orchestrator = AsyncMock()
    user_id = UUID("00000000-0000-4000-8000-000000000001")
    session_id = UUID("00000000-0000-4000-8000-000000000101")

    service = LiveRuntimeService(
        card_service=card_service,
        fake_live=fake_live,
        clock=_get_mock_time,
        translation_service=translation_service,
        command_service=None,
        turn_orchestrator=turn_orchestrator,
        user_id=user_id,
    )

    # Simulate parent speaking Chinese (language="zh")
    provider_event = ProviderTranscriptEvent(
        event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
        provider_event_id="evt-parent-zh",
        utterance_id="utt-parent-zh",
        speaker="parent",
        language="zh",
        text="我不懂这句",
        revision=1,
    )

    _ = await service.handle_provider_event(session_id, provider_event)

    # Verify that turn orchestrator was NOT called for parent speaker
    turn_orchestrator.process_final_turn.assert_not_called()


@pytest.mark.anyio
async def test_mock_mode_always_proposes_three_cards() -> None:
    import uuid

    from app.agents.companion_agent import CompanionAgent
    from app.schemas.agent_outputs import RouteDecision
    from app.schemas.runtime_events import TranscriptFinalEvent, TranscriptPayload

    agent = CompanionAgent(clock=_get_mock_time)
    event = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=str(uuid.uuid4()),
        event_type="transcript.final",
        session_id=str(uuid.uuid4()),
        sequence=1,
        timestamp=_get_mock_time(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id="utt-1",
            text="Do you have Ibuprofen?",
            speaker="pharmacist",
            language="en",
            revision=1,
        ),
    )
    from app.schemas.agent_outputs import RouteReasonCode, RouteType
    route = RouteDecision(
        route_type=RouteType.RESPONSE_NEEDED,
        confidence=1.0,
        reason_code=RouteReasonCode.QUESTION_DETECTED,
    )

    proposal = await agent.propose_cards(event, route, "gd-1", mcp_adapter=None)

    assert len(proposal.card_set.cards) == 3


def test_companion_instruction_rules() -> None:
    from app.agents.companion_agent import load_companion_prompt_template
    prompt = load_companion_prompt_template()
    assert "exactly three cards" in prompt.lower()


def json_dumps(obj: object) -> str:
    import json
    return json.dumps(obj)
