"""Structured outputs for Router, Guardian, and Companion."""

import json
from enum import StrEnum
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.constants import CardRiskLevel, GuardianDecisionType
from app.schemas.cards import CardAction, CardSet, CardType


class RouteType(StrEnum):
    """Stable route types from the runtime event contract."""

    PASSIVE_TRANSLATION = "passive_translation"
    PHARMACY_RISK = "pharmacy_risk"
    PRIVACY_RISK = "privacy_risk"
    RESPONSE_NEEDED = "response_needed"
    FAMILY_ACTION = "family_action"
    FALLBACK = "fallback"


class RouteReasonCode(StrEnum):
    """Allowlisted Router reason codes."""

    ROUTINE_TRANSLATION = "routine_translation"
    PHARMACY_TERM = "pharmacy_term"
    PRIVACY_REQUEST = "privacy_request"
    QUESTION_DETECTED = "question_detected"
    FAMILY_SUMMARY = "family_summary"
    ROUTER_FALLBACK = "router_fallback"


class GuardianReasonCode(StrEnum):
    """Allowlisted Guardian reason codes."""

    SAFE_TURN = "safe_turn"
    PAYMENT_REQUEST = "payment_request"
    IDENTITY_REQUEST = "identity_request"
    ADDRESS_REQUEST = "address_request"
    PROMPT_INJECTION = "prompt_injection"
    MEDICAL_CONFIRMATION_REQUIRED = "medical_confirmation_required"
    CARD_REVIEW_PASSED = "card_review_passed"
    CARD_REVIEW_FAILED = "card_review_failed"


class RouteDecision(BaseModel):
    """Structured Router output with no chain-of-thought."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_type: RouteType
    confidence: Annotated[float, Field(ge=0, le=1)]
    reason_code: RouteReasonCode


class GuardianDecision(BaseModel):
    """Structured Guardian output used by the orchestrator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    guardian_decision_id: Annotated[str, Field(min_length=1, max_length=80)]
    decision: GuardianDecisionType
    risk_level: CardRiskLevel
    reason_code: GuardianReasonCode


class CompanionCardDraft(BaseModel):
    """Untrusted Companion card content before backend materialization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_type: CardType
    zh_text: Annotated[str, Field(min_length=1, max_length=120)]
    en_text: Annotated[str, Field(min_length=1, max_length=240)]
    speak_zh: Annotated[str | None, Field(default=None, min_length=1, max_length=240)] = None
    risk_level: CardRiskLevel
    action: CardAction


    @property
    def requires_backend_materialization(self) -> bool:
        """Signal that IDs, lifecycle fields, and approval gates are backend-owned."""
        return True


class CompanionCardDraftSet(BaseModel):
    """LLM-owned semantic card draft submitted through submit_response_cards."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cards: Annotated[tuple[CompanionCardDraft, ...], Field(min_length=1, max_length=3)]


class CardSetProposal(BaseModel):
    """Companion card proposal before Guardian review."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    card_set: CardSet
    proposal_hash: Annotated[str, Field(min_length=8, max_length=128)]


TModel = TypeVar("TModel", bound=BaseModel)


def parse_structured_output(model: type[TModel], payload: str | dict[str, Any]) -> TModel:
    """Parse agent output and fail closed on free-form or malformed values."""
    try:
        value = json.loads(payload) if isinstance(payload, str) else payload
        return model.model_validate(value)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("AGENT_OUTPUT_INVALID") from exc
