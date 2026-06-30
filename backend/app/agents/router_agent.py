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
    "过敏",
    "用药",
    "处方",
    "配药",
    "取药",
    "冲突",
    "衝突",
    "副作用",
    "布洛芬",
    "阿司匹林",
    "华法林",
    "華法林",
)
PRIVACY_MARKERS = (
    "credit card",
    "passport",
    "medicare",
    "home address",
    "residential address",
    "your address",
    "cvv",
    "bsb",
    "bank account",
    "account number",
    "api key",
    "password",
    "secret",
    "token",
    "ignore previous",
    "system prompt",
    "developer message",
    "信用卡",
    "护照",
    "地址",
    "身份证",
    "身分證",
    "银行",
    "銀行",
    "密码",
    "密碼",
    "医疗保险",
)
FAMILY_ACTION_MARKERS = (
    "save the summary",
    "save this",
    "send this to my daughter",
    "send this to my son",
    "send this to my family",
    "notify family",
    "保存",
    "发送",
    "發送",
    "通知",
    "女儿",
    "女兒",
    "儿子",
    "兒子",
    "家人",
)
FALLBACK_MARKERS = (
    "kk is speaking",
    "selected response card",
)
RESPONSE_NEEDED_MARKERS = (
    "prescription",
    "pick up",
    "refill",
    "你好",
    "怎么帮您",
    "有什么需要",
    "配药",
    "取药",
)
PASSIVE_TRANSLATION_MARKERS = (
    "may make you sleepy",
    "avoid driving",
)
SMALL_TALK_MARKERS = (
    "hi",
    "hello",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how can i help",
    "what can i help",
    "你好",
    "早上好",
    "下午好",
    "晚上好",
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
        if any(marker in text_lower for marker in PASSIVE_TRANSLATION_MARKERS):
            return RouteDecision(
                route_type=RouteType.PASSIVE_TRANSLATION,
                confidence=0.84,
                reason_code=RouteReasonCode.ROUTINE_TRANSLATION,
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
        if any(marker in text_lower for marker in SMALL_TALK_MARKERS):
            return RouteDecision(
                route_type=RouteType.PASSIVE_TRANSLATION,
                confidence=0.86,
                reason_code=RouteReasonCode.ROUTINE_TRANSLATION,
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
