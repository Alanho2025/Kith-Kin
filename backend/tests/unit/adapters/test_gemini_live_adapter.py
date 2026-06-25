import json
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from google.genai import types

from app.adapters.gemini_live_adapter import GeminiLiveAdapter
from app.adapters.provider_schemas import (
    LiveSessionContext,
    ProviderAudioEvent,
    ProviderErrorEvent,
    ProviderLiveEventType,
    ProviderToolCallEvent,
    ProviderTranscriptEvent,
)
from app.core.config import Settings

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


class FakeSdkSession:
    def __init__(self, messages: tuple[types.LiveServerMessage, ...]) -> None:
        self.messages = messages
        self.audio: list[types.Blob] = []

    async def send_realtime_input(self, *, audio: types.Blob) -> None:
        self.audio.append(audio)

    async def receive(self) -> AsyncIterator[types.LiveServerMessage]:
        for message in self.messages:
            yield message


class FakeLiveConnection:
    def __init__(self, session: FakeSdkSession) -> None:
        self.session = session
        self.closed = False

    async def __aenter__(self) -> FakeSdkSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        self.closed = True


class FakeLiveApi:
    def __init__(self, connection: FakeLiveConnection) -> None:
        self.connection = connection
        self.model: str | None = None
        self.config: types.LiveConnectConfig | None = None

    def connect(
        self,
        *,
        model: str,
        config: types.LiveConnectConfig,
    ) -> FakeLiveConnection:
        self.model = model
        self.config = config
        return self.connection


class FakeAsyncClient:
    def __init__(self, live: FakeLiveApi) -> None:
        self.live = live
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeGenAiClient:
    def __init__(self, live: FakeLiveApi) -> None:
        self.aio = FakeAsyncClient(live)


async def test_opens_25_live_session_and_normalises_sdk_events() -> None:
    messages = (
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Have you",
                    finished=False,
                )
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Have you taken any new medication recently?",
                    finished=True,
                ),
                model_turn=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=b"\x01\x02",
                                mime_type="audio/pcm;rate=24000",
                            )
                        )
                    ],
                ),
            )
        ),
        types.LiveServerMessage(
            tool_call=types.LiveServerToolCall(
                function_calls=[
                    types.FunctionCall(
                        id="call_1",
                        name="memory_search",
                        args={"query": "profile"},
                    )
                ]
            )
        ),
    )
    sdk_session = FakeSdkSession(messages)
    connection = FakeLiveConnection(sdk_session)
    live_api = FakeLiveApi(connection)
    client = FakeGenAiClient(live_api)
    settings = Settings(
        environment="test",
        google_api_key="test-key",
    )
    adapter = GeminiLiveAdapter(settings, client_factory=lambda _: client)

    session = await adapter.open_session(
        LiveSessionContext(
            session_id=UUID("00000000-0000-4000-8000-000000000101"),
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            system_instruction="Help the parent communicate safely.",
        )
    )
    await session.send_audio(b"\x03\x04")
    events = []
    async for event in session.events():
        events.append(event)
        if len(events) == 4:
            break
    await session.close()

    assert live_api.model == "gemini-2.5-flash-native-audio-preview-12-2025"
    assert live_api.config is not None
    assert live_api.config.response_modalities == [types.Modality.AUDIO]
    assert live_api.config.system_instruction == "Help the parent communicate safely."
    assert live_api.config.input_audio_transcription is not None
    assert live_api.config.realtime_input_config is not None
    assert live_api.config.realtime_input_config.automatic_activity_detection is not None
    assert (
        live_api.config.realtime_input_config.automatic_activity_detection.silence_duration_ms
        == 800
    )
    assert sdk_session.audio[0].mime_type == "audio/pcm;rate=16000"
    assert sdk_session.audio[0].data == b"\x03\x04"
    assert isinstance(events[0], ProviderTranscriptEvent)
    assert events[0].event_type == ProviderLiveEventType.TRANSCRIPT_PARTIAL
    assert events[0].speaker == "pharmacist"
    assert events[0].language == "en"
    assert isinstance(events[1], ProviderTranscriptEvent)
    assert events[1].event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
    assert events[0].utterance_id == events[1].utterance_id
    assert isinstance(events[2], ProviderAudioEvent)
    assert events[2].audio == b"\x01\x02"
    assert isinstance(events[3], ProviderToolCallEvent)
    assert events[3].arguments == {"query": "profile"}
    assert connection.closed is True
    assert client.aio.closed is True


async def test_turn_complete_finalises_accumulated_partial_transcript() -> None:
    messages = (
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Hello, I would like to pick up my blood",
                    finished=False,
                )
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text=(
                        "Hello, I would like to pick up my blood pressure "
                        "medication, please."
                    ),
                    finished=False,
                )
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(turn_complete=True)
        ),
    )
    sdk_session = FakeSdkSession(messages)
    connection = FakeLiveConnection(sdk_session)
    client = FakeGenAiClient(FakeLiveApi(connection))
    adapter = GeminiLiveAdapter(
        Settings(environment="test", google_api_key="test-key"),
        client_factory=lambda _: client,
    )
    session = await adapter.open_session(
        LiveSessionContext(
            session_id=UUID("00000000-0000-4000-8000-000000000101"),
            user_id=UUID("00000000-0000-4000-8000-000000000001"),
            system_instruction="Translate safely.",
        )
    )

    events = []
    async for event in session.events():
        events.append(event)
        if len(events) == 3:
            break
    await session.close()

    assert [event.event_type for event in events] == [
        ProviderLiveEventType.TRANSCRIPT_PARTIAL,
        ProviderLiveEventType.TRANSCRIPT_PARTIAL,
        ProviderLiveEventType.TRANSCRIPT_FINAL,
    ]
    assert isinstance(events[-1], ProviderTranscriptEvent)
    assert events[-1].text.endswith("blood pressure medication, please.")
    assert events[-1].utterance_id == events[0].utterance_id
