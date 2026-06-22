"""Deterministic Router boundary used until ADK model calls are enabled."""

from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.runtime_events import TranscriptFinalEvent

PHARMACY_MARKERS = (
    "medicine",
    "medication",
    "drug",
    "allergy",
    "allergies",
    "antibiotic",
    "lisinopril",
    "ibuprofen",
    "dose",
)
PRIVACY_MARKERS = (
    "credit card",
    "passport",
    "medicare",
    "home address",
    "cvv",
    "ignore previous",
    "system prompt",
    "developer message",
)


class RouterAgent:
    """Classify final turns into stable route types."""

    async def route(self, event: TranscriptFinalEvent) -> RouteDecision:
        text = event.payload.text.lower()
        if any(marker in text for marker in PRIVACY_MARKERS):
            return RouteDecision(
                route_type=RouteType.PRIVACY_RISK,
                confidence=0.96,
                reason_code=RouteReasonCode.PRIVACY_REQUEST,
            )
        if any(marker in text for marker in PHARMACY_MARKERS):
            return RouteDecision(
                route_type=RouteType.PHARMACY_RISK,
                confidence=0.9,
                reason_code=RouteReasonCode.PHARMACY_TERM,
            )
        if "?" in text or text.startswith(("do ", "does ", "can ", "would ")):
            return RouteDecision(
                route_type=RouteType.RESPONSE_NEEDED,
                confidence=0.72,
                reason_code=RouteReasonCode.QUESTION_DETECTED,
            )
        return RouteDecision(
            route_type=RouteType.PASSIVE_TRANSLATION,
            confidence=0.8,
            reason_code=RouteReasonCode.ROUTINE_TRANSLATION,
        )
