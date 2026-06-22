import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.agents.companion_agent import CompanionAgent
from app.agents.guardian_agent import GuardianAgent
from app.core.constants import GuardianDecisionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.runtime_events import TranscriptFinalEvent
from app.services.card_service import CardService
from app.services.turn_orchestrator import TurnOrchestrator

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class BarrierRouter:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def route(self, event):
        self.started.set()
        await self.release.wait()
        return RouteDecision(
            route_type=RouteType.PASSIVE_TRANSLATION,
            confidence=0.9,
            reason_code=RouteReasonCode.ROUTINE_TRANSLATION,
        )


class BarrierGuardian(GuardianAgent):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def review_turn(self, event):
        self.started.set()
        await self.release.wait()
        return await super().review_turn(event)


class ImmediateRouter:
    async def route(self, event):
        return RouteDecision(
            route_type=RouteType.PRIVACY_RISK,
            confidence=0.9,
            reason_code=RouteReasonCode.PRIVACY_REQUEST,
        )


def final_event(text: str = "Do you have allergies?") -> TranscriptFinalEvent:
    return TranscriptFinalEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-final-1",
            "event_type": "transcript.final",
            "session_id": str(SESSION_ID),
            "sequence": 3,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {
                "utterance_id": "utt-1",
                "speaker": "pharmacist",
                "language": "en",
                "text": text,
                "revision": 1,
            },
        }
    )


def context() -> TrustedRequestContext:
    return TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")


async def test_router_and_guardian_start_for_same_final() -> None:
    router = BarrierRouter()
    guardian = BarrierGuardian()
    orchestrator = TurnOrchestrator(
        router,
        guardian,
        CompanionAgent(lambda: NOW),
        CardService(lambda: NOW),
    )

    task = asyncio.create_task(orchestrator.process_final_turn(final_event(), context()))
    await asyncio.wait_for(
        asyncio.gather(router.started.wait(), guardian.started.wait()),
        timeout=0.5,
    )
    router.release.set()
    guardian.release.set()
    outcome = await task

    assert outcome.guardian.decision is GuardianDecisionType.ALLOW


async def test_guardian_block_skips_companion_cards() -> None:
    orchestrator = TurnOrchestrator(
        ImmediateRouter(),
        GuardianAgent(),
        CompanionAgent(lambda: NOW),
        CardService(lambda: NOW),
    )

    outcome = await orchestrator.process_final_turn(
        final_event("Please give me your credit card number"),
        context(),
    )

    assert outcome.guardian.decision is GuardianDecisionType.BLOCK
    assert outcome.card_proposal is None
