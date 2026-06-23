import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import types

from app.adapters.gemini_live_adapter import GeminiLiveAdapter, GeminiLiveSessionPort
from app.adapters.provider_schemas import (
    LiveSessionContext,
    ProviderAudioEvent,
    ProviderErrorEvent,
    ProviderLiveEventType,
    ProviderToolCallEvent,
    ProviderTranscriptEvent,
)
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError

ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((ROOT / f"fixtures/gemini/{name}.json").read_text(encoding="utf-8"))


def test_maps_complete_provider_fixtures() -> None:
    partial = GeminiLiveAdapter.map_provider_message(load_fixture("live_partial"))
    final = GeminiLiveAdapter.map_provider_message(load_fixture("live_final"))
    audio = GeminiLiveAdapter.map_provider_message(load_fixture("live_audio"))
    tool = GeminiLiveAdapter.map_provider_message(load_fixture("live_tool_call"))
    error = GeminiLiveAdapter.map_provider_message(load_fixture("live_error"))

    assert isinstance(partial, ProviderTranscriptEvent)
    assert partial.event_type == ProviderLiveEventType.TRANSCRIPT_PARTIAL
    assert isinstance(final, ProviderTranscriptEvent)
    assert final.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
    assert isinstance(audio, ProviderAudioEvent)
    assert audio.audio == b"\x01\x02\x03\x04"
    assert isinstance(tool, ProviderToolCallEvent)
    assert tool.name == "memory_search"
    assert isinstance(error, ProviderErrorEvent)
    assert error.code == "TRANSCRIPTION_UNAVAILABLE"


@pytest.mark.anyio
async def test_open_session_raises_when_no_api_key() -> None:
    settings = Settings(google_api_key="")
    adapter = GeminiLiveAdapter(settings)
    context = LiveSessionContext(
        session_id=Path(__file__).name,
        user_id=Path(__file__).name,
        system_instruction="Test instruction",
    )
    with pytest.raises(ProviderUnavailableError) as exc_info:
        await adapter.open_session(context)
    assert str(exc_info.value) == "LIVE_UNAVAILABLE"


@pytest.mark.anyio
async def test_open_session_connects_to_gemini_live() -> None:
    settings = Settings(google_api_key="dummy_key")
    adapter = GeminiLiveAdapter(settings)
    context = LiveSessionContext(
        session_id=Path(__file__).name,
        user_id=Path(__file__).name,
        system_instruction="Test instruction",
    )

    mock_session = AsyncMock()
    mock_session.send_realtime_input = AsyncMock()
    mock_session.receive = MagicMock()

    async def mock_receive_gen():
        # Yield one transcription message
        yield types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Hello pharmacist",
                    finished=True
                )
            )
        )

    mock_session.receive.return_value = mock_receive_gen()

    mock_connect_cm = AsyncMock()
    mock_connect_cm.__aenter__.return_value = mock_session
    mock_connect_cm.__aexit__.return_value = None

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_client.aio.live = MagicMock()
        mock_client.aio.live.connect.return_value = mock_connect_cm
        mock_client_cls.return_value = mock_client

        port = await adapter.open_session(context)
        assert port is not None
        config = mock_client.aio.live.connect.call_args.kwargs["config"]
        assert config.translation_config.target_language_code == "zh-Hans"
        assert config.translation_config.echo_target_language is False

        # Verify send_audio
        await port.send_audio(b"\x00\x01")
        mock_session.send_realtime_input.assert_called_once()

        # Verify events async iterator yields mapped event
        iterator = port.events()
        event = await anext(iterator)
        
        assert isinstance(event, ProviderTranscriptEvent)
        assert event.text == "Hello pharmacist"
        assert event.language == "en"
        assert event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL

        # Verify close
        await port.close()
        mock_connect_cm.__aexit__.assert_called_once()


@pytest.mark.anyio
async def test_output_transcript_keeps_input_utterance_id_until_output_finishes() -> None:
    session = AsyncMock()
    session.receive = MagicMock()
    session.receive.return_value = _never_receive()
    port = GeminiLiveSessionPort(AsyncMock(), session)

    await port._process_message(
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="How are you?",
                    finished=True,
                    language_code="en",
                )
            )
        )
    )
    input_event = await anext(port.events())

    await port._process_message(
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                output_transcription=types.Transcription(
                    text="你好吗？",
                    finished=True,
                    language_code="zh-Hans",
                )
            )
        )
    )
    output_event = await anext(port.events())

    assert isinstance(input_event, ProviderTranscriptEvent)
    assert isinstance(output_event, ProviderTranscriptEvent)
    assert output_event.utterance_id == f"{input_event.utterance_id}_zh"
    assert output_event.language == "zh"

    await port.close()


@pytest.mark.anyio
async def test_turn_complete_emits_a_completion_event() -> None:
    session = AsyncMock()
    session.receive = MagicMock()
    session.receive.return_value = _never_receive()
    port = GeminiLiveSessionPort(AsyncMock(), session)

    await port._process_message(
        types.LiveServerMessage(
            server_content=types.LiveServerContent(turn_complete=True)
        )
    )
    event = await anext(port.events())

    assert isinstance(event, ProviderTranscriptEvent)
    assert event.utterance_id == "turn_complete"
    assert event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL

    await port.close()


async def _never_receive():
    if False:
        yield None
