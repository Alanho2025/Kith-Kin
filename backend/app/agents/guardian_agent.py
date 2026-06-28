"""Guardian safety agent inheriting from ADK BaseAgent."""

from collections.abc import AsyncGenerator
from uuid import uuid4

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from app.core.constants import CardRiskLevel, GuardianDecisionType
from app.domain.safety_policy import (
    BackstopReason,
    SafetyBackstopResult,
    screen_turn_text,
)
from app.schemas.agent_outputs import GuardianDecision, GuardianReasonCode
from app.schemas.cards import CardSet
from app.schemas.runtime_events import TranscriptFinalEvent

REASON_MAP = {
    BackstopReason.PAYMENT_REQUEST: GuardianReasonCode.PAYMENT_REQUEST,
    BackstopReason.IDENTITY_REQUEST: GuardianReasonCode.IDENTITY_REQUEST,
    BackstopReason.ADDRESS_REQUEST: GuardianReasonCode.ADDRESS_REQUEST,
    BackstopReason.PROMPT_INJECTION: GuardianReasonCode.PROMPT_INJECTION,
    BackstopReason.MEDICAL_ADVICE: GuardianReasonCode.MEDICAL_CONFIRMATION_REQUIRED,
}

RISK_PRIORITY = {
    CardRiskLevel.NORMAL: 0,
    CardRiskLevel.CAUTION: 1,
    CardRiskLevel.PRIVACY: 2,
    CardRiskLevel.MEDICAL: 3,
    CardRiskLevel.URGENT: 4,
}


class GuardianAgent(BaseAgent):
    """Inspect every final turn and proposed card set for safety policy violations."""

    name: str = "Guardian"
    description: str = "Fail-closed safety backstop agent."

    async def review_turn(self, event: TranscriptFinalEvent) -> GuardianDecision:
        """Inspect a final transcript directly without ADK session.

        Args:
            event: The transcript final event.

        Returns:
            The guardian decision.
        """
        return self._review_text(event.payload.text)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK execution entrypoint for sequential/parallel safety flows.

        Args:
            ctx: The ADK invocation context.

        Yields:
            ADK Event indicating safety outcomes.
        """
        text = ""
        if ctx.user_content and ctx.user_content.parts:
            text = "".join(part.text for part in ctx.user_content.parts if part.text)

        decision = self._review_text(text)
        ctx.session.state["guardian_decision"] = decision.model_dump()

        yield Event(author=self.name, message=f"Guardian decision: {decision.decision}")

    def _review_text(self, text: str) -> GuardianDecision:
        result, risk, reason = screen_turn_text(text)
        if result is SafetyBackstopResult.BLOCK:
            return GuardianDecision(
                guardian_decision_id=f"guardian_{uuid4()}",
                decision=GuardianDecisionType.BLOCK,
                risk_level=CardRiskLevel.PRIVACY,
                reason_code=REASON_MAP[reason],
            )
        if result is SafetyBackstopResult.REQUIRE_CONFIRMATION:
            return GuardianDecision(
                guardian_decision_id=f"guardian_{uuid4()}",
                decision=GuardianDecisionType.REQUIRE_PARENT_CONFIRMATION,
                risk_level=CardRiskLevel.MEDICAL,
                reason_code=GuardianReasonCode.MEDICAL_CONFIRMATION_REQUIRED,
            )
        return GuardianDecision(
            guardian_decision_id=f"guardian_{uuid4()}",
            decision=GuardianDecisionType.ALLOW,
            risk_level=CardRiskLevel(risk.value),
            reason_code=GuardianReasonCode.SAFE_TURN,
        )

    async def review_cards(self, card_set: CardSet) -> GuardianDecision:
        """Inspect a proposed card set for safety compliance.

        Args:
            card_set: The proposed response card set.

        Returns:
            The final review decision.
        """
        if any(not card.requires_guardian_approval for card in card_set.cards):
            return self._blocked_card_review()
        if any(_card_text_is_unsafe(f"{card.zh_text}\n{card.en_text}") for card in card_set.cards):
            return self._blocked_card_review()
        return GuardianDecision(
            guardian_decision_id=f"guardian_{uuid4()}",
            decision=GuardianDecisionType.ALLOW,
            risk_level=max(
                (card.risk_level for card in card_set.cards),
                key=lambda risk: RISK_PRIORITY[risk],
                default=CardRiskLevel.NORMAL,
            ),
            reason_code=GuardianReasonCode.CARD_REVIEW_PASSED,
        )

    @staticmethod
    def _blocked_card_review() -> GuardianDecision:
        """Return a fail-closed card-review decision."""
        return GuardianDecision(
            guardian_decision_id=f"guardian_{uuid4()}",
            decision=GuardianDecisionType.BLOCK,
            risk_level=CardRiskLevel.PRIVACY,
            reason_code=GuardianReasonCode.CARD_REVIEW_FAILED,
        )


def _card_text_is_unsafe(text: str) -> bool:
    """Detect unsafe proposed card text before rendering."""
    result, _, _ = screen_turn_text(text)
    if result is SafetyBackstopResult.BLOCK:
        return True
    lowered = text.lower()
    unsafe_markers = (
        "you can take this medicine",
        "you should take",
        "do not take",
        "don't take",
        "stop taking",
        "change your dose",
        "take double",
        "definitely safe",
        "definitely dangerous",
        "i recommend you buy",
        "you can eat this medicine",
        "你可以吃这个药",
        "你可以吃這個藥",
        "你不能吃这个药",
        "你不能吃這個藥",
        "停止吃",
        "改变剂量",
        "改變劑量",
        "一定安全",
        "一定有危险",
        "一定有危險",
        "直接买这个药",
        "直接買這個藥",
    )
    return any(marker in lowered for marker in unsafe_markers)
