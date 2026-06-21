"""Guardian decision and UI warning schemas."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import GuardianDecisionType


class GuardianDecision(BaseModel):
    """Traceable policy outcome generated for every final turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    guardian_decision_id: Annotated[str, Field(min_length=1, max_length=80)]
    source_event_id: Annotated[str, Field(min_length=1, max_length=80)]
    decision: GuardianDecisionType
    risk_level: str
    reason_code: Annotated[str, Field(min_length=1, max_length=80)]


class GuardianWarning(GuardianDecision):
    """Safe warning fields that may be exposed to React."""

    warning_type: str
    zh_title: Annotated[str, Field(min_length=1, max_length=120)]
    zh_message: Annotated[str, Field(min_length=1, max_length=300)]
    safe_card_set_id: str | None = None
