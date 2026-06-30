"""Provider-independent WebSocket runtime event schemas and parser."""

from datetime import datetime
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import SUPPORTED_SCHEMA_MAJOR, CardActionType, ToolName
from app.schemas.cards import CardSet
from app.schemas.guardian import GuardianWarning

Identifier = Annotated[str, Field(min_length=1, max_length=80)]


class RuntimeEventBase(BaseModel):
    """Common snake_case event envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    event_id: Identifier
    event_type: str
    session_id: Identifier
    sequence: Annotated[int, Field(ge=1)]
    timestamp: datetime
    correlation_id: Annotated[str, Field(max_length=80)] | None


class AudioFormat(BaseModel):
    """Negotiated PCM format for one binary-frame direction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encoding: Literal["pcm_s16le"]
    sample_rate_hz: Annotated[int, Field(gt=0)]
    channels: Literal[1]


class SessionReadyPayload(BaseModel):
    """Connection and audio-format negotiation payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resumption_supported: bool
    next_sequence: Annotated[int, Field(ge=1)]
    input_audio_format: AudioFormat
    output_audio_format: AudioFormat


class SessionReadyEvent(RuntimeEventBase):
    """Server acknowledgement for an accepted Live socket."""

    event_type: Literal["session.ready"]
    payload: SessionReadyPayload


class AudioListeningPayload(BaseModel):
    """Whether microphone frames are currently accepted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    active: bool


class AudioListeningEvent(RuntimeEventBase):
    """Explicit listening state."""

    event_type: Literal["audio.listening"]
    payload: AudioListeningPayload


class AudioMutedPayload(BaseModel):
    """Explicit microphone gate and stable reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    muted: bool
    reason: Literal["tts_playback", "user_control", "safety", "reconnecting", "session_end"]


class AudioMutedEvent(RuntimeEventBase):
    """Microphone mute transition."""

    event_type: Literal["audio.muted"]
    payload: AudioMutedPayload


class AudioSpeakingPayload(BaseModel):
    """TTS playback lifecycle without audio embedded in JSON."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    phase: Literal["started", "completed", "interrupted"]
    card_id: Identifier | None


class AudioSpeakingEvent(RuntimeEventBase):
    """Approved system or card speech state."""

    event_type: Literal["audio.speaking"]
    payload: AudioSpeakingPayload


class AudioSpeakerChangedPayload(BaseModel):
    """Client-selected microphone speaker context for subsequent audio frames."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    speaker: Literal["parent", "pharmacist"]


class AudioSpeakerChangedEvent(RuntimeEventBase):
    """Client command announcing who subsequent microphone audio belongs to."""

    event_type: Literal["audio.speaker_changed"]
    payload: AudioSpeakerChangedPayload


class TranscriptPayload(BaseModel):
    """Replaceable partial or immutable final source transcript."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    utterance_id: Identifier
    speaker: Literal["parent", "pharmacist", "unknown"]
    language: Literal["en", "zh", "unknown"]
    text: Annotated[str, Field(min_length=1)]
    revision: Annotated[int, Field(ge=1)]


class TranscriptPartialEvent(RuntimeEventBase):
    """Known replaceable transcript event."""

    event_type: Literal["transcript.partial"]
    payload: TranscriptPayload


class TranscriptFinalEvent(RuntimeEventBase):
    """Known immutable source transcript event."""

    event_type: Literal["transcript.final"]
    payload: TranscriptPayload


class TranslationFinalPayload(BaseModel):
    """Append-only faithful Chinese segment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_transcript_event_id: Identifier
    segment_id: Identifier
    source_language: Literal["en", "zh", "unknown"]
    target_language: Literal["zh_cn"]
    translated_text: Annotated[str, Field(min_length=1)]
    mode: Literal["faithful"]
    append_only: Literal[True]
    latency_ms: Annotated[int, Field(ge=0)]


class TranslationFinalEvent(RuntimeEventBase):
    """Known faithful translation event."""

    event_type: Literal["translation.final"]
    payload: TranslationFinalPayload


class TranslationPendingPayload(BaseModel):
    """Faithful translation work started for one immutable source event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_transcript_event_id: Identifier
    segment_id: Identifier


class TranslationPendingEvent(RuntimeEventBase):
    """Translation pending event."""

    event_type: Literal["translation.pending"]
    payload: TranslationPendingPayload


class RouteDecisionPayload(BaseModel):
    """Safe routing metadata without prompts or reasoning text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_transcript_event_id: Identifier
    route_type: Literal[
        "passive_translation",
        "pharmacy_risk",
        "privacy_risk",
        "response_needed",
        "family_action",
        "fallback",
    ]
    confidence: Annotated[float, Field(ge=0, le=1)]
    reason_code: Identifier


class RouteDecisionEvent(RuntimeEventBase):
    """Router result safe for frontend diagnostics."""

    event_type: Literal["route.decision"]
    payload: RouteDecisionPayload


class ToolStatusPayload(BaseModel):
    """Tool progress without inputs, outputs, or profile values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: Identifier
    tool_name: ToolName
    phase: Literal["started", "succeeded", "failed", "blocked"]
    fallback_code: str | None


class ToolStatusEvent(RuntimeEventBase):
    """Visible tool status event."""

    event_type: Literal["tool.status"]
    payload: ToolStatusPayload


class GuardianWarningEvent(RuntimeEventBase):
    """Safe Guardian warning visible to the parent."""

    event_type: Literal["guardian.warning"]
    payload: GuardianWarning


class CardsRenderPayload(BaseModel):
    """Approved card set ready for rendering."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_set: CardSet


class CardsRenderEvent(RuntimeEventBase):
    """Render-only card event with no execution authority."""

    event_type: Literal["cards.render"]
    payload: CardsRenderPayload


class CardSelectedPayload(BaseModel):
    """Session-bound one-time confirmation issued after selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_set_id: Identifier
    card_id: Identifier
    revision: Annotated[int, Field(ge=1)]
    confirmation_id: Identifier
    confirmation_expires_at: datetime


class CardSelectedEvent(RuntimeEventBase):
    """Selection acknowledgement; never an action trigger."""

    event_type: Literal["card.selected"]
    payload: CardSelectedPayload


class CardConfirmedPayload(BaseModel):
    """Accepted confirmation acknowledgement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confirmation_id: Identifier
    action_type: CardActionType
    replayed: bool


class CardConfirmedEvent(RuntimeEventBase):
    """Server-confirmed action authority."""

    event_type: Literal["card.confirmed"]
    payload: CardConfirmedPayload


class CardActionStatusPayload(BaseModel):
    """Execution status for the backend-stored approved action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confirmation_id: Identifier
    action_type: CardActionType
    phase: Literal["started", "succeeded", "failed", "blocked"]
    code: str | None


class CardActionStatusEvent(RuntimeEventBase):
    """Response-card action status."""

    event_type: Literal["card.action.status"]
    payload: CardActionStatusPayload


class VisitSummaryPayload(BaseModel):
    """Structured Chinese summary displayed before save or notification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title_zh: str
    mentioned_drugs: tuple[str, ...]
    pharmacist_advice_summary_zh: str
    unresolved_questions_zh: tuple[str, ...]
    follow_up_needed: bool
    pharmacist_stated_advice_zh: str | None = None
    unresolved_follow_up_questions_zh: tuple[str, ...] = ()
    confirmed_family_follow_up: bool = False


class SummaryRenderPayload(BaseModel):
    """Summary review payload with no write or send authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary_id: Identifier
    summary: VisitSummaryPayload
    card_set_id: Identifier


class SummaryRenderEvent(RuntimeEventBase):
    """Structured visit summary ready for parent review."""

    event_type: Literal["summary.render"]
    payload: SummaryRenderPayload


class OperationStatusPayload(BaseModel):
    """Idempotent write or external-action status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: Identifier
    phase: Literal["started", "succeeded", "failed", "blocked"]
    code: str | None
    replayed: bool


class MemoryWriteStatusEvent(RuntimeEventBase):
    """Confirmed memory persistence status."""

    event_type: Literal["memory.write.status"]
    payload: OperationStatusPayload


class NotificationStatusEvent(RuntimeEventBase):
    """Confirmed family notification status."""

    event_type: Literal["notification.status"]
    payload: OperationStatusPayload


class SafeMessagePayload(BaseModel):
    """Actionable safe message with no provider debug content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Identifier
    message_zh: str
    message_en: str
    retryable: bool
    recovery_action: Literal[
        "retry_automatically",
        "retry_manually",
        "ask_pharmacist_to_confirm",
        "show_to_pharmacist",
        "reconnect",
        "return_to_listening",
        "end_session",
    ]
    related_event_id: Identifier | None


class FallbackShowEvent(RuntimeEventBase):
    """Visible degraded but safe product path."""

    event_type: Literal["fallback.show"]
    payload: SafeMessagePayload


class ErrorShowEvent(RuntimeEventBase):
    """Visible runtime or contract failure."""

    event_type: Literal["error.show"]
    payload: SafeMessagePayload


class SessionEndedPayload(BaseModel):
    """Terminal session details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: Literal["user_completed", "user_cancelled", "runtime_error", "expired"]
    ended_at: datetime


class SessionEndedEvent(RuntimeEventBase):
    """Terminal server event."""

    event_type: Literal["session.ended"]
    payload: SessionEndedPayload


class CardSelectPayload(BaseModel):
    """Identifier-only selection command with no side-effect authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_set_id: Identifier
    card_id: Identifier
    revision: Annotated[int, Field(ge=1)]


class CardSelectEvent(RuntimeEventBase):
    """Client card-selection command."""

    event_type: Literal["card.select"]
    payload: CardSelectPayload


class ConfirmationPayload(BaseModel):
    """One-time confirmation identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confirmation_id: Identifier


class CardConfirmEvent(RuntimeEventBase):
    """Client card-confirmation command."""

    event_type: Literal["card.confirm"]
    payload: ConfirmationPayload


class CardCancelEvent(RuntimeEventBase):
    """Client cancellation command."""

    event_type: Literal["card.cancel"]
    payload: ConfirmationPayload


class EmptyPayload(BaseModel):
    """Strictly empty command payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SelfSpeakEvent(RuntimeEventBase):
    """Immediate no-side-effect escape control."""

    event_type: Literal["control.self_speak"]
    payload: EmptyPayload


class PleaseWaitEvent(RuntimeEventBase):
    """Request an approved wait-response flow."""

    event_type: Literal["control.please_wait"]
    payload: EmptyPayload


class RepeatPayload(BaseModel):
    """Repeat only previously approved or already-rendered content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: Literal["last_translation", "last_approved_response", "last_audio"]


class RepeatEvent(RuntimeEventBase):
    """Client repeat command."""

    event_type: Literal["control.repeat"]
    payload: RepeatPayload


class SessionEndPayload(BaseModel):
    """Explicit user end reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: Literal["user_completed", "user_cancelled"]


class SessionEndEvent(RuntimeEventBase):
    """Client session-end command."""

    event_type: Literal["session.end"]
    payload: SessionEndPayload


class UnknownRuntimeEvent(RuntimeEventBase):
    """Forward-compatible event preserved only within the supported major."""

    payload: dict[str, object]


RuntimeEvent = (
    SessionReadyEvent
    | AudioListeningEvent
    | AudioMutedEvent
    | AudioSpeakingEvent
    | AudioSpeakerChangedEvent
    | TranscriptPartialEvent
    | TranscriptFinalEvent
    | TranslationPendingEvent
    | TranslationFinalEvent
    | RouteDecisionEvent
    | ToolStatusEvent
    | GuardianWarningEvent
    | CardsRenderEvent
    | CardSelectedEvent
    | CardConfirmedEvent
    | CardActionStatusEvent
    | SummaryRenderEvent
    | MemoryWriteStatusEvent
    | NotificationStatusEvent
    | FallbackShowEvent
    | ErrorShowEvent
    | SessionEndedEvent
    | CardSelectEvent
    | CardConfirmEvent
    | CardCancelEvent
    | SelfSpeakEvent
    | PleaseWaitEvent
    | RepeatEvent
    | SessionEndEvent
    | UnknownRuntimeEvent
)


_KNOWN_EVENT_MODELS: dict[str, type[RuntimeEventBase]] = {
    "session.ready": SessionReadyEvent,
    "audio.listening": AudioListeningEvent,
    "audio.muted": AudioMutedEvent,
    "audio.speaking": AudioSpeakingEvent,
    "audio.speaker_changed": AudioSpeakerChangedEvent,
    "transcript.partial": TranscriptPartialEvent,
    "transcript.final": TranscriptFinalEvent,
    "translation.pending": TranslationPendingEvent,
    "translation.final": TranslationFinalEvent,
    "route.decision": RouteDecisionEvent,
    "tool.status": ToolStatusEvent,
    "guardian.warning": GuardianWarningEvent,
    "cards.render": CardsRenderEvent,
    "card.selected": CardSelectedEvent,
    "card.confirmed": CardConfirmedEvent,
    "card.action.status": CardActionStatusEvent,
    "summary.render": SummaryRenderEvent,
    "memory.write.status": MemoryWriteStatusEvent,
    "notification.status": NotificationStatusEvent,
    "fallback.show": FallbackShowEvent,
    "error.show": ErrorShowEvent,
    "session.ended": SessionEndedEvent,
    "card.select": CardSelectEvent,
    "card.confirm": CardConfirmEvent,
    "card.cancel": CardCancelEvent,
    "control.self_speak": SelfSpeakEvent,
    "control.please_wait": PleaseWaitEvent,
    "control.repeat": RepeatEvent,
    "session.end": SessionEndEvent,
}


def parse_runtime_event(value: dict[str, object]) -> RuntimeEvent:
    """Validate a known event or preserve an unknown same-major event."""
    schema_version = value.get("schema_version")
    if not isinstance(schema_version, str):
        raise ValueError("SCHEMA_VERSION_INVALID")
    try:
        major = int(schema_version.split(".", maxsplit=1)[0])
    except (ValueError, IndexError) as exc:
        raise ValueError("SCHEMA_VERSION_INVALID") from exc
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise ValueError("SCHEMA_VERSION_UNSUPPORTED")
    event_type = value.get("event_type")
    if not isinstance(event_type, str):
        raise ValueError("EVENT_TYPE_INVALID")
    model = _KNOWN_EVENT_MODELS.get(event_type, UnknownRuntimeEvent)
    return cast(RuntimeEvent, model.model_validate(value))
