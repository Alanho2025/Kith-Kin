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

    model_config = ConfigDict(extra="ignore", frozen=True)

    card_id: Annotated[str, Field(min_length=1, max_length=80)]
    card_type: CardType
    zh_text: Annotated[str, Field(min_length=1, max_length=120)]
    en_text: Annotated[str, Field(min_length=1, max_length=240)]
    risk_level: CardRiskLevel
    action: CardAction
    requires_parent_confirmation: bool
    requires_guardian_approval: bool
    guardian_decision_id: Annotated[str, Field(min_length=1, max_length=80)]

    @model_validator(mode="before")
    @classmethod
    def sanitize_card_fields(cls, data: "Any") -> "Any":
        if isinstance(data, dict):
            from uuid import uuid4
            if not data.get("card_id"):
                data["card_id"] = f"card_{uuid4()}"
            if not data.get("card_type"):
                data["card_type"] = "ask_question"
            if not data.get("risk_level"):
                data["risk_level"] = "normal"
            if not data.get("action"):
                data["action"] = {"type": "no_action"}
            data["requires_parent_confirmation"] = True
            data["requires_guardian_approval"] = True
            if not data.get("guardian_decision_id"):
                data["guardian_decision_id"] = "default_guardian_id"
        return data

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

    model_config = ConfigDict(extra="ignore", frozen=True)

    card_set_id: Annotated[str, Field(min_length=1, max_length=80)]
    revision: Annotated[int, Field(ge=1)]
    source_event_id: Annotated[str, Field(min_length=1, max_length=80)]
    generated_at: datetime
    expires_at: datetime
    cards: Annotated[tuple[ResponseCard, ...], Field(min_length=1, max_length=3)]

    @model_validator(mode="before")
    @classmethod
    def sanitize_set_fields(cls, data: "Any") -> "Any":
        if isinstance(data, dict):
            from uuid import uuid4
            from datetime import datetime, UTC, timedelta
            if not data.get("card_set_id"):
                data["card_set_id"] = f"cards_{uuid4()}"
            if "revision" not in data:
                data["revision"] = 1
            if not data.get("source_event_id"):
                data["source_event_id"] = "evt_source"
            
            now = datetime.now(UTC)
            data["generated_at"] = now.isoformat().replace("+00:00", "Z")
            data["expires_at"] = (now + timedelta(minutes=3)).isoformat().replace("+00:00", "Z")
        return data

    @model_validator(mode="after")
    def validate_expiry(self) -> "CardSet":
        """Require a strictly positive review window."""
        if self.expires_at <= self.generated_at:
            raise ValueError("CARD_SET_EXPIRY_INVALID")
        return self
