"""Gemini Live adapter normalising provider messages behind a stable port."""

import base64
from typing import Any, Literal, cast

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


class GeminiLiveAdapter(GeminiLiveGateway):
    """Open and normalise a single Gemini Live session.

    Real SDK calls are isolated here. Unit tests exercise `map_provider_message`
    with sanitised fixtures so the default suite never needs credentials.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort:
        if not self._settings.google_api_key.get_secret_value():
            raise ProviderUnavailableError("LIVE_UNAVAILABLE")
        raise ProviderUnavailableError("LIVE_SDK_SESSION_NOT_CONFIGURED")

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