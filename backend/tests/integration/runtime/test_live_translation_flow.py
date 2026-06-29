import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.adapters.provider_schemas import (
    ProviderLiveEventType,
    ProviderTranscriptEvent,
    TranslationRequest,
    TranslationSegment,
)
from app.agents.card_proposal_materializer import materialize_companion_card_draft
from app.agents.companion_agent import CompanionAgent
from app.agents.guardian_agent import GuardianAgent
from app.agents.router_agent import RouterAgent
from app.core.constants import CardRiskLevel, GuardianDecisionType
from app.schemas.agent_outputs import (
    CompanionCardDraftSet,
    GuardianDecision,
    GuardianReasonCode,
    RouteDecision,
    RouteReasonCode,
    RouteType,
)
from app.services.card_service import CardService
from app.services.live_runtime_service import LiveRuntimeService
from app.services.runtime_command_service import RuntimeCommandService
from app.services.task_supervisor import TaskSupervisor
from app.services.translation_service import TranslationService
from app.services.turn_orchestrator import TurnOrchestrator, TurnOutcome
from app.services.visit_completion_service import VisitCompletionService

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class CapturingTranslationGateway:
    def __init__(self, *, delay_seconds: float = 0) -> None:
        self.requests: list[TranslationRequest] = []
        self.delay_seconds = delay_seconds

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return TranslationSegment(
            source_transcript_event_id=request.source_event_id,
            segment_id=f"seg_{request.utterance_id}",
            source_language=request.source_language,
            target_language="zh_cn",
            translated_text="\u4f60\u5bf9\u6297\u751f\u7d20\u8fc7\u654f\u5417\uff1f",
            latency_ms=10,
        )


class CapturingCommandWebSocket:
    def __init__(self) -> None:
        self.json_events: list[dict[str, object]] = []

    async def send_json(self, event: dict[str, object]) -> None:
        self.json_events.append(event)


def runtime(
    gateway: CapturingTranslationGateway,
    *,
    timeout_ms: int = 1000,
    with_turn_orchestrator: bool = False,
    with_command_service: bool = False,
    with_completion_service: bool = False,
) -> LiveRuntimeService:
    cards = CardService(lambda: NOW)
    turn_orchestrator = (
        TurnOrchestrator(
            RouterAgent(),
            GuardianAgent(),
            CompanionAgent(lambda: NOW),
            cards,
        )
        if with_turn_orchestrator
        else None
    )
    command_service = RuntimeCommandService(cards, USER_ID) if with_command_service else None
    service = LiveRuntimeService(
        cards,
        FakeLiveAdapter(),
        lambda: NOW,
        TranslationService(gateway, timeout_ms=timeout_ms),
        command_service=command_service,
        turn_orchestrator=turn_orchestrator,
        user_id=USER_ID if turn_orchestrator is not None else None,
    )
    if with_completion_service:
        service._completion_service = VisitCompletionService(
            memory_repository=None,
            notification_repository=None,
            get_session_events=lambda sid: service._buffers.get(sid, []),
        )
    return service


def provider_transcript(*, final: bool, utterance_id: str = "utt_1") -> ProviderTranscriptEvent:
    return ProviderTranscriptEvent(
        event_type=(
            ProviderLiveEventType.TRANSCRIPT_FINAL
            if final
            else ProviderLiveEventType.TRANSCRIPT_PARTIAL
        ),
        provider_event_id="provider_evt_1",
        utterance_id=utterance_id,
        speaker="pharmacist",
        language="en",
        text="Do you have any allergies to antibiotics?",
        revision=2 if final else 1,
    )


def provider_transcript_text(
    text: str,
    *,
    utterance_id: str,
    speaker: str = "pharmacist",
    language: str = "en",
) -> ProviderTranscriptEvent:
    return ProviderTranscriptEvent(
        event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
        provider_event_id=f"provider_{utterance_id}",
        utterance_id=utterance_id,
        speaker=speaker,
        language=language,
        text=text,
        revision=1,
    )


async def test_partial_never_calls_translation() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=False),
    )

    assert gateway.requests == []
    assert events[-1]["event_type"] == "transcript.partial"


async def test_final_appends_one_faithful_segment() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    assert [event["event_type"] for event in events] == [
        "transcript.final",
        "translation.pending",
        "translation.final",
    ]
    assert events[-1]["payload"]["append_only"] is True
    assert events[-1]["payload"]["mode"] == "faithful"


async def test_template_product_options_emit_neutral_product_snapshot() -> None:
    gateway = CapturingTranslationGateway()
    service = runtime(gateway)

    first = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            (
                "I can show you three options. This one is paracetamol, "
                "this one is ibuprofen, and this one is a cold and flu tablet."
            ),
            utterance_id="utt_options",
        ),
    )
    first_snapshot = next(
        event for event in first if event["event_type"] == "product.options.render"
    )
    assert [option["name"] for option in first_snapshot["payload"]["options"]] == [
        "paracetamol",
        "ibuprofen",
        "cold and flu tablet",
    ]

    second = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "The prices are 6 dollars, 9 dollars, and 12 dollars.",
            utterance_id="utt_prices",
        ),
    )
    second_snapshot = next(
        event for event in second if event["event_type"] == "product.options.render"
    )
    assert [option["price"] for option in second_snapshot["payload"]["options"]] == [
        "6 dollars",
        "9 dollars",
        "12 dollars",
    ]


async def test_successful_translation_runs_router_guardian_trace() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway, with_turn_orchestrator=True).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    event_types = [event["event_type"] for event in events]
    assert event_types[:3] == [
        "transcript.final",
        "translation.pending",
        "translation.final",
    ]
    assert event_types.index("route.decision") > event_types.index("translation.final")
    assert event_types[-1] == "cards.render"
    route = next(event for event in events if event["event_type"] == "route.decision")
    assert route["payload"]["route_type"] == "pharmacy_risk"
    assert route["payload"]["reason_code"] == "pharmacy_term"


async def test_template_pharmacy_e2e_uses_real_backend_flow_without_mock_mode(
    monkeypatch,
) -> None:
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    gateway = CapturingTranslationGateway()
    service = runtime(
        gateway,
        with_turn_orchestrator=True,
        with_command_service=True,
        with_completion_service=True,
    )

    small_talk = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "Hi, good morning. How are you today?",
            utterance_id="utt_small_talk",
        ),
    )
    assert "cards.render" not in [event["event_type"] for event in small_talk]
    small_talk_route = next(
        event for event in small_talk if event["event_type"] == "route.decision"
    )
    assert small_talk_route["payload"]["route_type"] == "passive_translation"

    help_prompt = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text("How can I help you?", utterance_id="utt_help"),
    )
    assert "cards.render" not in [event["event_type"] for event in help_prompt]

    parent_request = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "I used a pain medicine before. Could you help me find a similar local option?",
            utterance_id="utt_parent_request",
            speaker="parent",
        ),
    )
    assert "route.decision" not in [event["event_type"] for event in parent_request]

    allergy_question = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "Do you have any allergies to medicines?",
            utterance_id="utt_allergies",
        ),
    )
    allergy_cards = next(
        event for event in allergy_question if event["event_type"] == "cards.render"
    )
    allergy_card_texts = [
        card["en_text"] for card in allergy_cards["payload"]["card_set"]["cards"]
    ]
    assert all("Ask pharmacist" not in text for text in allergy_card_texts)
    assert all("Should I take" not in text for text in allergy_card_texts)

    options = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            (
                "I can show you three options. This one is paracetamol, "
                "this one is ibuprofen, and this one is a cold and flu tablet."
            ),
            utterance_id="utt_options_e2e",
        ),
    )
    option_snapshot = next(
        event for event in options if event["event_type"] == "product.options.render"
    )
    assert [option["name"] for option in option_snapshot["payload"]["options"]] == [
        "paracetamol",
        "ibuprofen",
        "cold and flu tablet",
    ]

    prices = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "The prices are 6 dollars, 9 dollars, and 12 dollars.",
            utterance_id="utt_prices_e2e",
        ),
    )
    price_snapshot = next(
        event for event in prices if event["event_type"] == "product.options.render"
    )
    assert [option["price"] for option in price_snapshot["payload"]["options"]] == [
        "6 dollars",
        "9 dollars",
        "12 dollars",
    ]

    parent_purchase = await service.handle_provider_event(
        SESSION_ID,
        provider_transcript_text(
            "I would like to buy paracetamol.",
            utterance_id="utt_parent_purchase",
            speaker="parent",
        ),
    )
    assert "route.decision" not in [event["event_type"] for event in parent_purchase]

    websocket = CapturingCommandWebSocket()
    await service._handle_live_command(
        websocket,
        SESSION_ID,
        json.dumps(
            {
                "schema_version": "0.1",
                "event_id": "evt-session-end-e2e",
                "event_type": "session.end",
                "session_id": str(SESSION_ID),
                "sequence": 99,
                "timestamp": NOW.isoformat(),
                "correlation_id": None,
                "payload": {"reason": "user_completed"},
            }
        ),
        AsyncMock(),
    )
    summary = next(
        event for event in websocket.json_events if event["event_type"] == "summary.render"
    )
    summary_body = summary["payload"]["summary"]
    assert summary_body["mentioned_drugs"] == ["ibuprofen", "paracetamol"]
    assert summary_body["pharmacist_advice_summary_zh"].startswith("药师原话摘要：")
    assert "Panadol" not in summary_body["pharmacist_advice_summary_zh"]


async def test_card_review_block_surfaces_fallback_without_rendering_cards() -> None:
    class BlockingCardReviewOrchestrator:
        async def process_final_turn(self, event, context, conversation_context=None):
            draft = CompanionCardDraftSet.model_validate(
                {
                    "cards": [
                        {
                            "card_type": "ask_question",
                            "zh_text": "你可以吃这个药。",
                            "en_text": "You can take this medicine.",
                            "risk_level": "medical",
                            "action": {"type": "speak"},
                        }
                    ]
                }
            )
            proposal = materialize_companion_card_draft(
                draft,
                source_event_id=event.event_id,
                generated_at=NOW,
                guardian_decision_id="guardian-pending",
            )
            return TurnOutcome(
                route=RouteDecision(
                    route_type=RouteType.PHARMACY_RISK,
                    confidence=0.9,
                    reason_code=RouteReasonCode.PHARMACY_TERM,
                ),
                guardian=GuardianDecision(
                    guardian_decision_id="guardian-turn",
                    decision=GuardianDecisionType.ALLOW,
                    risk_level=CardRiskLevel.NORMAL,
                    reason_code=GuardianReasonCode.SAFE_TURN,
                ),
                card_proposal=proposal,
                card_review=GuardianDecision(
                    guardian_decision_id="guardian-card",
                    decision=GuardianDecisionType.BLOCK,
                    risk_level=CardRiskLevel.MEDICAL,
                    reason_code=GuardianReasonCode.CARD_REVIEW_FAILED,
                ),
            )

    gateway = CapturingTranslationGateway()
    service = LiveRuntimeService(
        CardService(lambda: NOW),
        FakeLiveAdapter(),
        lambda: NOW,
        TranslationService(gateway, timeout_ms=1000),
        turn_orchestrator=BlockingCardReviewOrchestrator(),
        user_id=USER_ID,
    )

    events = await service.handle_provider_event(SESSION_ID, provider_transcript(final=True))
    event_types = [event["event_type"] for event in events]

    assert "cards.render" not in event_types
    assert events[-1]["event_type"] == "fallback.show"
    assert events[-1]["payload"]["code"] == "CARD_REVIEW_FAILED"


async def test_partial_with_orchestrator_never_runs_router_guardian() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway, with_turn_orchestrator=True).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=False),
    )

    assert gateway.requests == []
    assert [event["event_type"] for event in events] == ["transcript.partial"]


async def test_duplicate_final_is_idempotent() -> None:
    gateway = CapturingTranslationGateway()
    service = runtime(gateway)

    first = await service.handle_provider_event(SESSION_ID, provider_transcript(final=True))
    second = await service.handle_provider_event(SESSION_ID, provider_transcript(final=True))

    assert sum(1 for event in first if event["event_type"] == "translation.final") == 1
    assert all(event["event_type"] != "translation.final" for event in second)
    assert len(gateway.requests) == 1


async def test_translation_timeout_keeps_english() -> None:
    gateway = CapturingTranslationGateway(delay_seconds=0.05)

    events = await runtime(gateway, timeout_ms=1).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    assert events[0]["event_type"] == "transcript.final"
    assert events[-1]["event_type"] == "fallback.show"
    assert events[-1]["payload"]["code"] == "TRANSLATION_TIMEOUT"


async def test_disconnect_cancels_all_owned_tasks() -> None:
    supervisor = TaskSupervisor()
    supervisor.create(asyncio.sleep(60))

    await supervisor.cancel_all()

    assert supervisor.pending_count == 0
