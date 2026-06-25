"""Deterministic Router agent inheriting from ADK BaseAgent."""

from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.runtime_events import TranscriptFinalEvent

PHARMACY_MARKERS = (
    "medicine",
    "medication",
    "drug",
    "take this",
    "headache",
    "allergy",
    "allergies",
    "antibiotic",
    "lisinopril",
    "ibuprofen",
    "dose",
    "药",
    "降血压",
)
PRIVACY_MARKERS = (
    "credit card",
    "passport",
    "medicare",
    "home address",
    "cvv",
    "api key",
    "password",
    "secret",
    "token",
    "ignore previous",
    "system prompt",
    "developer message",
)
FAMILY_ACTION_MARKERS = (
    "save the summary",
    "save this",
    "send this to my daughter",
    "send this to my son",
    "send this to my family",
    "notify family",
)
FALLBACK_MARKERS = (
    "kk is speaking",
    "selected response card",
)
RESPONSE_NEEDED_MARKERS = (
    "prescription",
    "pick up",
    "refill",
)


class RouterAgent(BaseAgent):
    """Classify final turns into stable route types using keyword patterns."""

    name: str = "Router"
    description: str = "Keyword-based route classifier."

    async def route(self, event: TranscriptFinalEvent) -> RouteDecision:
        """Classify a final event directly without ADK session.

        Args:
            event: The transcript event containing English text.

        Returns:
            The route decision.
        """
        return self._classify(event.payload.text)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK execution entrypoint for sequential/parallel flows.

        Args:
            ctx: The ADK invocation context.

        Yields:
            ADK Event indicating classification outcomes.
        """
        text = ""
        if ctx.user_content and ctx.user_content.parts:
            text = "".join(part.text for part in ctx.user_content.parts if part.text)

        decision = self._classify(text)
        ctx.session.state["route_decision"] = decision.model_dump()

        yield Event(author=self.name, message=f"Route classified as {decision.route_type}")

    def _classify(self, text: str) -> RouteDecision:
        text_lower = text.lower()
        if any(marker in text_lower for marker in FALLBACK_MARKERS):
            return RouteDecision(
                route_type=RouteType.FALLBACK,
                confidence=0.95,
                reason_code=RouteReasonCode.ROUTER_FALLBACK,
            )
        if any(marker in text_lower for marker in PRIVACY_MARKERS):
            return RouteDecision(
                route_type=RouteType.PRIVACY_RISK,
                confidence=0.96,
                reason_code=RouteReasonCode.PRIVACY_REQUEST,
            )
        if any(marker in text_lower for marker in FAMILY_ACTION_MARKERS):
            return RouteDecision(
                route_type=RouteType.FAMILY_ACTION,
                confidence=0.9,
                reason_code=RouteReasonCode.FAMILY_SUMMARY,
            )
        if any(marker in text_lower for marker in PHARMACY_MARKERS):
            return RouteDecision(
                route_type=RouteType.PHARMACY_RISK,
                confidence=0.9,
                reason_code=RouteReasonCode.PHARMACY_TERM,
            )
        if (
            any(marker in text_lower for marker in RESPONSE_NEEDED_MARKERS)
            or "?" in text_lower
            or text_lower.startswith(("do ", "does ", "can ", "would "))
        ):
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
