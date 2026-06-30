"""Pydantic wire schemas for response cards."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import CardActionType, CardRiskLevel


class CardType(StrEnum):
    """Supported parent-facing card purposes."""

    ASK_QUESTION = "ask_question"
    CONFIRM_INFO = "confirm_info"
    REFUSE_SENSITIVE_REQUEST = "refuse_sensitive_request"
    ASK_TO_WRITE_DOWN = "ask_to_write_down"
    MEMORY_ACTION = "memory_action"
    FAMILY_ACTION = "family_action"


class CardAction(BaseModel):
    """Public action descriptor; sensitive arguments remain server-side."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: CardActionType


class ResponseCard(BaseModel):
    """Guardian-approved response card rendered by the client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_id: Annotated[str, Field(min_length=1, max_length=80)]
    card_type: CardType
    zh_text: Annotated[str, Field(min_length=1, max_length=120)]
    en_text: Annotated[str, Field(min_length=1, max_length=240)]
    speak_zh: Annotated[str | None, Field(default=None, min_length=1, max_length=240)] = None
    risk_level: CardRiskLevel
    action: CardAction

    requires_parent_confirmation: bool
    requires_guardian_approval: bool
    guardian_decision_id: Annotated[str, Field(min_length=1, max_length=80)]

    @model_validator(mode="after")
    def validate_confirmation_gates(self) -> "ResponseCard":
        """Fail closed for every outward or persistent action."""
        if not self.requires_guardian_approval:
            raise ValueError("GUARDIAN_APPROVAL_REQUIRED")
        if (
            self.action.type is not CardActionType.NO_ACTION
            and not self.requires_parent_confirmation
        ):
            raise ValueError("PARENT_CONFIRMATION_REQUIRED")
        return self


class CardSet(BaseModel):
    """One current revision of one to three approved cards."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_set_id: Annotated[str, Field(min_length=1, max_length=80)]
    revision: Annotated[int, Field(ge=1)]
    source_event_id: Annotated[str, Field(min_length=1, max_length=80)]
    generated_at: datetime
    expires_at: datetime
    cards: Annotated[tuple[ResponseCard, ...], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def validate_expiry(self) -> "CardSet":
        """Require a strictly positive review window."""
        if self.expires_at <= self.generated_at:
            raise ValueError("CARD_SET_EXPIRY_INVALID")
        return self
