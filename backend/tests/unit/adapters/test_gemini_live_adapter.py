import json
from pathlib import Path

from app.adapters.gemini_live_adapter import GeminiLiveAdapter
from app.adapters.provider_schemas import (
    ProviderAudioEvent,
    ProviderErrorEvent,
    ProviderLiveEventType,
    ProviderToolCallEvent,
    ProviderTranscriptEvent,
)

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
