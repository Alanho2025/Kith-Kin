"""Gemini Live adapter normalising provider messages behind a stable port."""

import base64
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal, Protocol, cast

from google import genai
from google.genai import types

from app.adapters.provider_schemas import (
    GeminiLiveGateway,
    LiveSessionContext,
    LiveSessionPort,
    ProviderAudioEvent,
    ProviderErrorEvent,
    ProviderLiveEvent,
    ProviderLiveEventType,
    ProviderToolCallEvent,
    ProviderTranscriptEvent,
)
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError


class SdkLiveSession(Protocol):
    """Subset of the Google GenAI Live session used by the adapter."""

    async def send_realtime_input(self, *, audio: types.Blob) -> None:
        """Send one PCM audio frame."""
        ...

    def receive(self) -> AsyncIterator[types.LiveServerMessage]:
        """Receive provider messages for the current model turn."""
        ...


class SdkLiveApi(Protocol):
    """Subset of the async Live API used to open a session."""

    def connect(
        self,
        *,
        model: str,
        config: types.LiveConnectConfig,
    ) -> AbstractAsyncContextManager[SdkLiveSession]:
        """Create an async Live connection context."""
        ...


class SdkAsyncClient(Protocol):
    """Async Google GenAI client surface used by this adapter."""

    live: SdkLiveApi

    async def aclose(self) -> None:
        """Release SDK HTTP resources."""
        ...


class SdkClient(Protocol):
    """Google GenAI client surface used by this adapter."""

    aio: SdkAsyncClient


ClientFactory = Callable[[Settings], SdkClient]


class GeminiLiveAdapter(GeminiLiveGateway):
    """Open and normalise a single Gemini Live session.

    Real SDK calls are isolated here. Unit tests exercise `map_provider_message`
    with sanitised fixtures so the default suite never needs credentials.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory or _create_client

    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort:
        if not self._settings.google_api_key.get_secret_value():
            raise ProviderUnavailableError("LIVE_UNAVAILABLE")
        client = self._client_factory(self._settings)
        connection = client.aio.live.connect(
            model=self._settings.gemini_live_model,
            config=types.LiveConnectConfig(
                response_modalities=[types.Modality.AUDIO],
                system_instruction=context.system_instruction,
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        disabled=False,
                        silence_duration_ms=800,
                    )
                ),
            ),
        )
        try:
            session = await connection.__aenter__()
        except Exception:
            await client.aio.aclose()
            raise ProviderUnavailableError("LIVE_UNAVAILABLE") from None
        return GeminiSdkLiveSession(session, connection, client)

    @staticmethod
    def map_provider_message(message: dict[str, Any]) -> ProviderLiveEvent:
        """Map a complete sanitised provider message to a runtime-safe event."""
        message_type = str(message.get("type", ""))
        provider_event_id = str(message.get("event_id", "provider_event"))
        if message_type == "input_transcription":
            final = bool(message.get("final", False))
            return ProviderTranscriptEvent(
                event_type=(
                    ProviderLiveEventType.TRANSCRIPT_FINAL
                    if final
                    else ProviderLiveEventType.TRANSCRIPT_PARTIAL
                ),
                provider_event_id=provider_event_id,
                utterance_id=str(message["utterance_id"]),
                speaker=_speaker(message.get("speaker")),
                language=_language(message.get("language")),
                text=str(message["text"]),
                revision=int(message.get("revision", 1)),
            )
        if message_type == "audio":
            encoded = str(message.get("data_b64", ""))
            return ProviderAudioEvent(
                event_type=ProviderLiveEventType.AUDIO,
                provider_event_id=provider_event_id,
                audio=base64.b64decode(encoded),
            )
        if message_type == "tool_call":
            arguments = message.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            return ProviderToolCallEvent(
                event_type=ProviderLiveEventType.TOOL_CALL,
                provider_event_id=provider_event_id,
                name=str(message.get("name", "")),
                arguments=arguments,
            )
        if message_type == "error":
            return ProviderErrorEvent(
                event_type=ProviderLiveEventType.ERROR,
                provider_event_id=provider_event_id,
                code=_stable_error_code(message.get("code")),
                retryable=bool(message.get("retryable", True)),
            )
        return ProviderErrorEvent(
            event_type=ProviderLiveEventType.ERROR,
            provider_event_id=provider_event_id,
            code="LIVE_PROTOCOL_ERROR",
            retryable=False,
        )

class GeminiSdkLiveSession(LiveSessionPort):
    """Own one open SDK Live session and expose normalised runtime events."""

    def __init__(
        self,
        session: SdkLiveSession,
        connection: AbstractAsyncContextManager[SdkLiveSession],
        client: SdkClient,
    ) -> None:
        self._session = session
        self._connection = connection
        self._client = client
        self._closed = False
        self._event_sequence = 0
        self._utterance_sequence = 0
        self._current_utterance_id: str | None = None
        self._current_transcript = ""
        self._current_revision = 0

    async def send_audio(self, frame: bytes) -> None:
        if self._closed:
            raise ProviderUnavailableError("LIVE_UNAVAILABLE")
        await self._session.send_realtime_input(
            audio=types.Blob(
                data=frame,
                mime_type="audio/pcm;rate=16000",
            )
        )

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._connection.__aexit__(None, None, None)
        finally:
            await self._client.aio.aclose()

    async def _event_iterator(self) -> AsyncIterator[ProviderLiveEvent]:
        try:
            while not self._closed:
                async for message in self._session.receive():
                    for event in self._map_sdk_message(message):
                        yield event
        except Exception:
            yield ProviderErrorEvent(
                event_type=ProviderLiveEventType.ERROR,
                provider_event_id=self._next_event_id("error"),
                code="LIVE_UNAVAILABLE",
                retryable=True,
            )

    def events(self) -> AsyncIterator[ProviderLiveEvent]:
        return self._event_iterator()

    def _map_sdk_message(
        self,
        message: types.LiveServerMessage,
    ) -> tuple[ProviderLiveEvent, ...]:
        events: list[ProviderLiveEvent] = []
        content = message.server_content
        if content is not None and content.input_transcription is not None:
            transcript = self._map_transcription(content.input_transcription)
            if transcript is not None:
                events.append(transcript)
        if content is not None and content.turn_complete:
            transcript = self._finalize_current_transcript()
            if transcript is not None:
                events.append(transcript)
        if content is not None and content.model_turn is not None:
            events.extend(self._map_audio_parts(content.model_turn.parts or []))
        if message.tool_call is not None:
            events.extend(self._map_tool_calls(message.tool_call.function_calls or []))
        return tuple(events)

    def _map_transcription(
        self,
        transcription: types.Transcription,
    ) -> ProviderTranscriptEvent | None:
        text = (transcription.text or "").strip()
        if not text:
            return None
        if self._current_utterance_id is None:
            self._utterance_sequence += 1
            self._current_utterance_id = f"utt_{self._utterance_sequence}"
            self._current_transcript = ""
            self._current_revision = 0
        self._current_revision += 1
        self._current_transcript = _merge_transcript(self._current_transcript, text)
        is_final = transcription.finished is not False
        language, speaker = _language_and_speaker(self._current_transcript)
        event = ProviderTranscriptEvent(
            event_type=(
                ProviderLiveEventType.TRANSCRIPT_FINAL
                if is_final
                else ProviderLiveEventType.TRANSCRIPT_PARTIAL
            ),
            provider_event_id=self._next_event_id("transcript"),
            utterance_id=self._current_utterance_id,
            speaker=speaker,
            language=language,
            text=self._current_transcript,
            revision=self._current_revision,
        )
        if is_final:
            self._current_utterance_id = None
            self._current_transcript = ""
            self._current_revision = 0
        return event

    def _finalize_current_transcript(self) -> ProviderTranscriptEvent | None:
        if self._current_utterance_id is None or not self._current_transcript:
            return None
        self._current_revision += 1
        language, speaker = _language_and_speaker(self._current_transcript)
        event = ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id=self._next_event_id("transcript"),
            utterance_id=self._current_utterance_id,
            speaker=speaker,
            language=language,
            text=self._current_transcript,
            revision=self._current_revision,
        )
        self._current_utterance_id = None
        self._current_transcript = ""
        self._current_revision = 0
        return event

    def _map_audio_parts(self, parts: list[types.Part]) -> list[ProviderAudioEvent]:
        events: list[ProviderAudioEvent] = []
        for part in parts:
            inline_data = part.inline_data
            if inline_data is None or inline_data.data is None:
                continue
            audio = inline_data.data
            if isinstance(audio, str):
                audio = base64.b64decode(audio)
            events.append(
                ProviderAudioEvent(
                    event_type=ProviderLiveEventType.AUDIO,
                    provider_event_id=self._next_event_id("audio"),
                    audio=audio,
                )
            )
        return events

    def _map_tool_calls(
        self,
        function_calls: list[types.FunctionCall],
    ) -> list[ProviderToolCallEvent]:
        events: list[ProviderToolCallEvent] = []
        for function_call in function_calls:
            arguments = function_call.args or {}
            events.append(
                ProviderToolCallEvent(
                    event_type=ProviderLiveEventType.TOOL_CALL,
                    provider_event_id=(
                        function_call.id or self._next_event_id("tool_call")
                    ),
                    name=function_call.name or "",
                    arguments=dict(arguments),
                )
            )
        return events

    def _next_event_id(self, category: str) -> str:
        self._event_sequence += 1
        return f"gemini_{category}_{self._event_sequence}"


class FixtureLiveSession(LiveSessionPort):
    """Contract fake for tests and fixture-driven probes."""

    def __init__(self, events: tuple[ProviderLiveEvent, ...]) -> None:
        self.sent_audio: list[bytes] = []
        self.closed = False
        self._events = events

    async def send_audio(self, frame: bytes) -> None:
        self.sent_audio.append(frame)

    async def close(self) -> None:
        self.closed = True

    async def _event_iterator(self) -> AsyncIterator[ProviderLiveEvent]:
        for event in self._events:
            yield event

    def events(self) -> AsyncIterator[ProviderLiveEvent]:
        return self._event_iterator()


def _speaker(value: object) -> Literal["parent", "pharmacist", "unknown"]:
    if value in {"parent", "pharmacist", "unknown"}:
        return cast(Literal["parent", "pharmacist", "unknown"], value)
    return "unknown"


def _language(value: object) -> Literal["en", "zh", "unknown"]:
    if value in {"en", "zh", "unknown"}:
        return cast(Literal["en", "zh", "unknown"], value)
    return "unknown"


def _stable_error_code(value: object) -> str:
    code = str(value or "")
    if code in {
        "LIVE_UNAVAILABLE",
        "LIVE_PROTOCOL_ERROR",
        "LIVE_SESSION_LIMIT",
        "TRANSCRIPTION_UNAVAILABLE",
    }:
        return code
    return "LIVE_UNAVAILABLE"


def _merge_transcript(existing: str, incoming: str) -> str:
    if not existing or incoming.startswith(existing):
        return incoming
    if existing.endswith(incoming):
        return existing
    return f"{existing.rstrip()} {incoming.lstrip()}"


def _language_and_speaker(
    text: str,
) -> tuple[Literal["en", "zh"], Literal["parent", "pharmacist"]]:
    if any("\u3400" <= character <= "\u9fff" for character in text):
        return "zh", "parent"
    return "en", "pharmacist"


def _create_client(settings: Settings) -> SdkClient:
    return cast(
        SdkClient,
        genai.Client(
            api_key=settings.google_api_key.get_secret_value(),
            http_options=types.HttpOptions(api_version=settings.gemini_api_version),
        ),
    )
