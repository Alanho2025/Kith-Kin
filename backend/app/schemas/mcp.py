"""Typed MVP MCP tool request and result envelopes."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolStatus(StrEnum):
    """Expected MCP domain outcomes."""

    SUCCESS = "success"
    NO_RESULT = "no_result"
    BLOCKED = "blocked"
    VALIDATION_ERROR = "validation_error"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


class ToolError(BaseModel):
    """Redacted application-safe tool error."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    retryable: bool
    fallback_code: str


TData = TypeVar("TData")


class ToolResult(BaseModel, Generic[TData]):
    """Common result envelope for all four MVP tools."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    status: ToolStatus
    data: TData | None
    error: ToolError | None

    @model_validator(mode="after")
    def validate_envelope(self) -> "ToolResult[TData]":
        """Keep success data and safe errors mutually coherent."""
        if self.status in {ToolStatus.SUCCESS, ToolStatus.NO_RESULT}:
            if not self.ok or self.data is None or self.error is not None:
                raise ValueError("TOOL_RESULT_ENVELOPE_INVALID")
        elif self.ok or self.data is not None or self.error is None:
            raise ValueError("TOOL_RESULT_ENVELOPE_INVALID")
        return self


class MemorySearchRequest(BaseModel):
    """Arguments accepted by `memory_search`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: Annotated[str, Field(min_length=1, max_length=200)]
    tags: Annotated[tuple[str, ...], Field(max_length=10)]


class MemoryRecord(BaseModel):
    """Authorised structured memory returned by a read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    key: str
    value: dict[str, object]
    tags: tuple[str, ...]
    updated_at: datetime


class MemorySearchData(BaseModel):
    """Data returned by `memory_search`, including an empty no-result list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: tuple[MemoryRecord, ...]


class MemoryWriteData(BaseModel):
    """Data returned after an idempotent confirmed memory write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_record_id: str
    key: str
    tags: tuple[str, ...]
    replayed: bool


class VisitSummaryValue(BaseModel):
    """Only structured visit facts accepted by `memory_write`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mentioned_drugs: Annotated[tuple[str, ...], Field(max_length=20)]
    pharmacist_advice_summary: Annotated[str, Field(min_length=1, max_length=1000)]
    unresolved_questions: Annotated[tuple[str, ...], Field(max_length=20)]
    follow_up_needed: bool
    family_notification_requested: bool


class MemoryWriteRequest(BaseModel):
    """Arguments accepted by the confirmation-gated `memory_write`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Annotated[str, Field(pattern=r"^visit_summary:[A-Za-z0-9_-]{1,64}$")]
    value: VisitSummaryValue
    tags: Annotated[tuple[str, ...], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def require_visit_summary_tag(self) -> "MemoryWriteRequest":
        """Prevent this endpoint from becoming a generic memory mutation."""
        if "visit_summary" not in self.tags:
            raise ValueError("VISIT_SUMMARY_TAG_REQUIRED")
        return self


class DrugInteractionRisk(StrEnum):
    """Non-prescriptive interaction classifications."""

    NONE = "none"
    CAUTION = "caution"
    NEEDS_PHARMACIST_CONFIRMATION = "needs_pharmacist_confirmation"
    UNKNOWN = "unknown"


class DrugInteractionRequest(BaseModel):
    """Arguments accepted only after a concrete drug name is detected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    new_drug: Annotated[str, Field(min_length=1, max_length=120)]
    current_meds: Annotated[tuple[str, ...], Field(max_length=50)]


class DrugInteractionData(BaseModel):
    """Safe pharmacist-question support, never dosing advice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_level: DrugInteractionRisk
    reason_code: str
    matched_current_meds: tuple[str, ...]
    source_type: str


class NotifyFamilyRequest(BaseModel):
    """Structured family summary; destination is resolved by the backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: VisitSummaryValue


class NotifyFamilyData(BaseModel):
    """Provider-independent result for the notification stub."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notification_id: str
    delivered: bool
    provider: str
    replayed: bool
