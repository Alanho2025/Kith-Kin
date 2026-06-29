"""Provider-normalised Live and translation schemas."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID


class ProviderLiveEventType(StrEnum):
    """Normalised provider event categories consumed by the runtime."""

    TRANSCRIPT_PARTIAL = "transcript_partial"
    TRANSCRIPT_FINAL = "transcript_final"
    AUDIO = "audio"
    TOOL_CALL = "tool_call"
    ERROR = "error"


@dataclass(frozen=True)
class LiveSessionContext:
    """Trusted context needed to open exactly one provider Live session."""

    session_id: UUID
    user_id: UUID
    system_instruction: str
    current_speaker: Callable[[], Literal["parent", "pharmacist", "unknown"]] | None = None


@dataclass(frozen=True)
class ProviderTranscriptEvent:
    """Normalised input transcription event from Gemini Live."""

    event_type: ProviderLiveEventType
    provider_event_id: str
    utterance_id: str
    speaker: Literal["parent", "pharmacist", "unknown"]
    language: Literal["en", "zh", "unknown"]
    text: str
    revision: int


@dataclass(frozen=True)
class ProviderAudioEvent:
    """Normalised provider audio bytes."""

    event_type: ProviderLiveEventType
    provider_event_id: str
    audio: bytes


@dataclass(frozen=True)
class ProviderToolCallEvent:
    """Normalised tool-call request without provider internals."""

    event_type: ProviderLiveEventType
    provider_event_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ProviderErrorEvent:
    """Provider failure mapped to a stable application code."""

    event_type: ProviderLiveEventType
    provider_event_id: str
    code: str
    retryable: bool


ProviderLiveEvent = (
    ProviderTranscriptEvent | ProviderAudioEvent | ProviderToolCallEvent | ProviderErrorEvent
)


class LiveSessionPort(Protocol):
    """One open Live provider session."""

    async def send_audio(self, frame: bytes) -> None:
        """Send one microphone frame to the provider."""
        ...

    def events(self) -> AsyncIterator[ProviderLiveEvent]:
        """Yield normalised provider events."""
        ...

    async def close(self) -> None:
        """Close the provider session exactly once."""
        ...


class GeminiLiveGateway(Protocol):
    """Boundary for opening provider Live sessions."""

    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort:
        """Open one provider session for a trusted runtime context."""
        ...


@dataclass(frozen=True)
class TranslationRequest:
    """One immutable final utterance to translate faithfully."""

    source_event_id: str
    utterance_id: str
    text: str
    source_language: Literal["en", "zh", "unknown"]
    target_language: Literal["zh_cn"] = "zh_cn"


@dataclass(frozen=True)
class TranslationSegment:
    """One append-only faithful translation segment."""

    source_transcript_event_id: str
    segment_id: str
    source_language: Literal["en", "zh", "unknown"]
    target_language: Literal["zh_cn"]
    translated_text: str
    latency_ms: int


class TranslationGateway(Protocol):
    """Faithful text translation boundary."""

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        """Translate an immutable final source utterance."""
        ...
