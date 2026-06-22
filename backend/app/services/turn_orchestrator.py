"""Parallel Router/Guardian orchestration for final transcript turns."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from app.core.constants import GuardianDecisionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.agent_outputs import CardSetProposal, GuardianDecision, RouteDecision, RouteType
from app.schemas.cards import CardSet
from app.schemas.runtime_events import TranscriptFinalEvent
from app.services.card_service import CardService


class RouterPort(Protocol):
    async def route(self, event: TranscriptFinalEvent) -> RouteDecision: ...


class GuardianPort(Protocol):
    async def review_turn(self, event: TranscriptFinalEvent) -> GuardianDecision: ...

    async def review_cards(self, card_set: CardSet) -> GuardianDecision: ...


class CompanionPort(Protocol):
    async def propose_cards(
        self,
        event: TranscriptFinalEvent,
        route: RouteDecision,
        guardian_decision_id: str,
    ) -> CardSetProposal: ...


@dataclass(frozen=True)
class TurnOutcome:
    """Safe structured result for one final turn."""

    route: RouteDecision
    guardian: GuardianDecision
    card_proposal: CardSetProposal | None
    card_review: GuardianDecision | None


class TurnOrchestrator:
    """Run Router and Guardian concurrently, then gate Companion proposals."""

    def __init__(
        self,
        router: RouterPort,
        guardian: GuardianPort,
        companion: CompanionPort,
        card_service: CardService | None = None,
    ) -> None:
        self._router = router
        self._guardian = guardian
        self._companion = companion
        self._cards = card_service

    async def process_final_turn(
        self,
        event: TranscriptFinalEvent,
        context: TrustedRequestContext,
    ) -> TurnOutcome:
        async with asyncio.TaskGroup() as tg:
            router_task = tg.create_task(self._router.route(event))
            guardian_task = tg.create_task(self._guardian.review_turn(event))
        route = router_task.result()
        guardian = guardian_task.result()
        if guardian.decision is GuardianDecisionType.BLOCK:
            return TurnOutcome(route, guardian, None, None)
        # Privacy-risk and passive-translation routes do not invoke Companion.
        _NO_COMPANION_ROUTES = {RouteType.PASSIVE_TRANSLATION, RouteType.PRIVACY_RISK}
        if route.route_type in _NO_COMPANION_ROUTES:
            return TurnOutcome(route, guardian, None, None)

        proposal = await self._companion.propose_cards(
            event,
            route,
            guardian.guardian_decision_id,
        )
        card_review = await self._guardian.review_cards(proposal.card_set)
        if card_review.decision is GuardianDecisionType.ALLOW and self._cards is not None:
            self._cards.register_card_set(proposal.card_set, context)
        return TurnOutcome(route, guardian, proposal, card_review)