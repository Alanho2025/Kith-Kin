"""Gemini Live adapter normalising provider messages behind a stable port."""

import asyncio
import base64
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal, cast
from uuid import uuid4

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

logger = logging.getLogger(__name__)


class GeminiLiveSessionPort(LiveSessionPort):
    """An open session port communicating with Gemini Live API over WebSockets."""

    def __init__(
        self,
        ctx: Any,
        session: Any,
        current_speaker: Callable[[], Literal["parent", "pharmacist", "unknown"]] | None = None,
    ) -> None:
        self._ctx = ctx
        self._session = session
        self._current_speaker = current_speaker
        self._queue: asyncio.Queue[ProviderLiveEvent | None] = asyncio.Queue()
        self._closed = False
        self._current_utterance_id = f"utt_{uuid4()}"
        self._current_transcript_text = ""
        self._revision = 1
        self._last_partial_at: float | None = None
        self._read_task = asyncio.create_task(self._read_loop())
        self._idle_flush_task = asyncio.create_task(self._idle_flush_loop())

    async def send_audio(self, frame: bytes) -> None:
        if self._closed:
            return
        try:
            from google.genai import types

            await self._session.send_realtime_input(
                media=types.Blob(data=frame, mime_type="audio/pcm;rate=16000")
            )
        except Exception as e:
            logger.warning(f"Error sending audio frame to Gemini Live: {e}")
            if not self._closed:
                await self._queue.put(
                    ProviderErrorEvent(
                        event_type=ProviderLiveEventType.ERROR,
                        provider_event_id=f"err_{uuid4()}",
                        code="LIVE_PROTOCOL_ERROR",
                        retryable=True,
                    )
                )

    async def send_text(self, text: str) -> None:
        """Send English response text to be voiced in the Live Translate session."""
        if self._closed:
            return
        try:
            from google.genai import types

            await self._session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )
        except Exception as e:
            logger.warning(f"Error sending text content to Gemini Live: {e}")

    def events(self) -> AsyncIterator[ProviderLiveEvent]:
        async def event_generator() -> AsyncIterator[ProviderLiveEvent]:
            while True:
                event = await self._queue.get()
                if event is None:
                    break
                yield event

        return event_generator()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._read_task.cancel()
        self._idle_flush_task.cancel()
        try:
            await self._ctx.__aexit__(None, None, None)
        except Exception:
            pass
        await self._queue.put(None)

    async def _idle_flush_loop(self) -> None:
        """Emit a TRANSCRIPT_FINAL when partials stop arriving (the live-translate
        model streams partials but never sets `finished`, so silence must finalize)."""
        idle_seconds = 1.5
        try:
            while not self._closed:
                await asyncio.sleep(0.2)
                if not self._current_transcript_text or self._last_partial_at is None:
                    continue
                if asyncio.get_event_loop().time() - self._last_partial_at >= idle_seconds:
                    await self._flush_current_transcript_final()
        except asyncio.CancelledError:
            pass

    async def _flush_current_transcript_final(self) -> None:
        if not self._current_transcript_text:
            return
        flat_msg = {
            "type": "input_transcription",
            "event_id": f"evt_{uuid4()}",
            "utterance_id": self._current_utterance_id,
            "speaker": self._input_speaker(),
            "language": "en",
            "text": self._current_transcript_text,
            "revision": self._revision,
            "final": True,
        }
        await self._queue.put(GeminiLiveAdapter.map_provider_message(flat_msg))
        self._current_utterance_id = f"utt_{uuid4()}"
        self._current_transcript_text = ""
        self._revision = 1
        self._last_partial_at = None

    async def _read_loop(self) -> None:
        try:
            # We loop because google-genai session.receive() yields until turn_complete,
            # then exits the generator. We must restart it to receive subsequent turns.
            while not self._closed:
                async for msg in self._session.receive():
                    await self._process_message(msg)
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Gemini Live session receive loop error: {e}")
            if not self._closed:
                await self._queue.put(
                    ProviderErrorEvent(
                        event_type=ProviderLiveEventType.ERROR,
                        provider_event_id=f"err_{uuid4()}",
                        code="LIVE_PROTOCOL_ERROR",
                        retryable=True,
                    )
                )
        finally:
            await self._queue.put(None)

    async def _process_message(self, msg: Any) -> None:
        # 1. Check for tool calls
        if msg.tool_call and msg.tool_call.function_calls:
            for call in msg.tool_call.function_calls:
                tool_event = ProviderToolCallEvent(
                    event_type=ProviderLiveEventType.TOOL_CALL,
                    provider_event_id=call.id,
                    name=call.name,
                    arguments=call.args or {},
                )
                await self._queue.put(tool_event)
            return

        # 2. Check for server content (transcriptions and audio)
        if msg.server_content:
            content = msg.server_content

            # English input transcript for whichever speaker the runtime selected.
            if content.input_transcription:
                text = content.input_transcription.text or ""
                finished = bool(content.input_transcription.finished)
                accumulated_text = _merge_transcript_text(self._current_transcript_text, text)
                self._current_transcript_text = accumulated_text
                flat_msg = {
                    "type": "input_transcription",
                    "event_id": f"evt_{uuid4()}",
                    "utterance_id": self._current_utterance_id,
                    "speaker": self._input_speaker(),
                    "language": "en",
                    "text": accumulated_text,
                    "revision": self._revision,
                    "final": finished,
                }
                transcript_event = GeminiLiveAdapter.map_provider_message(flat_msg)
                await self._queue.put(transcript_event)

                if finished:
                    self._current_utterance_id = f"utt_{uuid4()}"
                    self._current_transcript_text = ""
                    self._revision = 1
                    self._last_partial_at = None
                else:
                    self._revision += 1
                    self._last_partial_at = asyncio.get_event_loop().time()

            # Chinese generated audio
            if content.model_turn and content.model_turn.parts:
                for part in content.model_turn.parts:
                    if part.inline_data:
                        audio_data = part.inline_data.data
                        if audio_data:
                            encoded = base64.b64encode(audio_data).decode("utf-8")
                            flat_msg = {
                                "type": "audio",
                                "event_id": f"evt_{uuid4()}",
                                "data_b64": encoded,
                            }
                            audio_event = GeminiLiveAdapter.map_provider_message(flat_msg)
                            await self._queue.put(audio_event)
            if content.turn_complete:
                flat_msg = {
                    "type": "input_transcription",
                    "event_id": f"evt_{uuid4()}",
                    "utterance_id": "turn_complete",
                    "speaker": self._input_speaker(),
                    "language": "en",
                    "text": "",
                    "revision": 1,
                    "final": True,
                }
                turn_complete_event = GeminiLiveAdapter.map_provider_message(flat_msg)
                await self._queue.put(turn_complete_event)

    def _input_speaker(self) -> Literal["parent", "pharmacist", "unknown"]:
        if self._current_speaker is None:
            return "pharmacist"
        try:
            return _speaker(self._current_speaker())
        except Exception:
            logger.warning("Current speaker provider failed", exc_info=True)
            return "unknown"


class GeminiLiveAdapter(GeminiLiveGateway):
    """Open and normalise a single Gemini Live session.

    Real SDK calls are isolated here. Unit tests exercise `map_provider_message`
    with sanitised fixtures so the default suite never needs credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort:
        key_val = self._settings.google_api_key.get_secret_value()
        if not key_val:
            raise ProviderUnavailableError("LIVE_UNAVAILABLE")

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key_val)

            # Configure LiveConnectConfig
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                system_instruction=context.system_instruction,
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                realtime_input_config=types.RealtimeInputConfig(
                    automatic_activity_detection=types.AutomaticActivityDetection(
                        disabled=False,
                        silence_duration_ms=800,
                    )
                ),
            )

            # Connect using gemini-3.5-live-translate-preview
            model_name = (
                self._settings.gemini_live_translate_model or "gemini-3.5-live-translate-preview"
            )
            ctx = client.aio.live.connect(model=model_name, config=config)
            session = await ctx.__aenter__()

            return GeminiLiveSessionPort(ctx, session, context.current_speaker)
        except Exception as e:
            logger.exception("Failed to connect to Gemini Live session")
            raise ProviderUnavailableError(f"LIVE_UNAVAILABLE: {e}") from e

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


def _speaker(value: object) -> Literal["parent", "pharmacist", "unknown"]:
    if value in {"parent", "pharmacist", "unknown"}:
        return cast(Literal["parent", "pharmacist", "unknown"], value)
    return "unknown"


def _language(value: object) -> Literal["en", "zh", "unknown"]:
    if value in {"en", "zh", "unknown"}:
        return cast(Literal["en", "zh", "unknown"], value)
    return "unknown"


def _merge_transcript_text(existing: str, incoming: str) -> str:
    """Merge provider transcript deltas or cumulative partials into one utterance."""
    current = existing.strip()
    next_text = incoming.strip()
    if not current:
        return next_text
    if not next_text:
        return current
    if next_text.startswith(current):
        return next_text
    if current.endswith(next_text):
        return current
    separator = "" if next_text[:1] in {".", ",", "?", "!", ":", ";"} else " "
    return f"{current}{separator}{next_text}"


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
