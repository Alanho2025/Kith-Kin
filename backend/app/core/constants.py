"""Shared public constants for the Kith&Kin contracts."""

from enum import StrEnum

SCHEMA_VERSION = "0.1"
SUPPORTED_SCHEMA_MAJOR = 0


class RuntimeEventType(StrEnum):
    """Known runtime event and command names."""

    SESSION_READY = "session.ready"
    AUDIO_LISTENING = "audio.listening"
    AUDIO_MUTED = "audio.muted"
    AUDIO_SPEAKING = "audio.speaking"
    TRANSCRIPT_PARTIAL = "transcript.partial"
    TRANSCRIPT_FINAL = "transcript.final"
    TRANSLATION_PENDING = "translation.pending"
    TRANSLATION_FINAL = "translation.final"
    ROUTE_DECISION = "route.decision"
    TOOL_STATUS = "tool.status"
    GUARDIAN_WARNING = "guardian.warning"
    CARDS_RENDER = "cards.render"
    CARD_SELECTED = "card.selected"
    CARD_CONFIRMED = "card.confirmed"
    CARD_ACTION_STATUS = "card.action.status"
    SUMMARY_RENDER = "summary.render"
    MEMORY_WRITE_STATUS = "memory.write.status"
    NOTIFICATION_STATUS = "notification.status"
    FALLBACK_SHOW = "fallback.show"
    ERROR_SHOW = "error.show"
    SESSION_ENDED = "session.ended"
    CARD_SELECT = "card.select"
    CARD_CONFIRM = "card.confirm"
    CARD_CANCEL = "card.cancel"
    CONTROL_SELF_SPEAK = "control.self_speak"
    CONTROL_PLEASE_WAIT = "control.please_wait"
    CONTROL_REPEAT = "control.repeat"
    SESSION_END = "session.end"


class CardActionType(StrEnum):
    """Backend-owned action selected by a response card."""

    SPEAK = "speak"
    SHOW_TO_PHARMACIST = "show_to_pharmacist"
    SAVE_MEMORY = "save_memory"
    NOTIFY_FAMILY = "notify_family"
    NO_ACTION = "no_action"


class CardRiskLevel(StrEnum):
    """Response-card risk classifications."""

    NORMAL = "normal"
    CAUTION = "caution"
    PRIVACY = "privacy"
    MEDICAL = "medical"
    URGENT = "urgent"


class GuardianDecisionType(StrEnum):
    """Stable Guardian policy outcomes."""

    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_PARENT_CONFIRMATION = "require_parent_confirmation"
    REDACT = "redact"
    FALLBACK = "fallback"


class PermissionTier(StrEnum):
    """MCP permission tiers."""

    READ_ONLY = "read_only"
    WRITE_LOCAL = "write_local"
    EXTERNAL_ACTION = "external_action"


class ToolName(StrEnum):
    """MVP MCP tool names."""

    MEMORY_SEARCH = "memory_search"
    MEMORY_WRITE = "memory_write"
    CHECK_DRUG_INTERACTION = "check_drug_interaction"
    NOTIFY_FAMILY = "notify_family"
