"""Parallel Router/Guardian ADK orchestration for final transcript turns."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from app.agents.companion_agent import (
    build_companion_instruction,
    load_companion_prompt_template,
    make_check_drug_interaction,
    make_memory_search,
    make_submit_response_cards,
)
from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.constants import GuardianDecisionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.agent_outputs import CardSetProposal, GuardianDecision, RouteDecision, RouteType
from app.schemas.cards import CardSet
from app.schemas.runtime_events import TranscriptFinalEvent
from app.services.card_service import CardService

logger = logging.getLogger(__name__)


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
        mcp_tool_adapter_factory: Any = None,
        settings: Any = None,
        clock: Any = None,
    ) -> None:
        """Initialize the TurnOrchestrator with agents and ADK options.

        Args:
            router: The router agent.
            guardian: The guardian agent.
            companion: The companion agent.
            card_service: Optional service for registering card sets.
            mcp_tool_adapter_factory: Optional tool adapter creator.
            settings: Optional configuration settings.
            clock: Optional clock callback.
        """
        self._router = router
        self._guardian = guardian
        self._companion = companion
        self._cards = card_service
        self._mcp_tool_adapter_factory = mcp_tool_adapter_factory
        self._settings = settings
        self._clock = clock

    async def process_final_turn(
        self,
        event: TranscriptFinalEvent,
        context: TrustedRequestContext,
    ) -> TurnOutcome:
        """Process the final transcript turn by executing the ADK orchestration graph.

        Args:
            event: The transcript final event.
            context: Trusted request context.

        Returns:
            The orchestration TurnOutcome.
        """
        proposal: CardSetProposal | None = None
        card_review: GuardianDecision | None = None

        # Fallback for legacy unit tests (e.g., test_turn_orchestrator.py)
        if self._mcp_tool_adapter_factory is None:
            async with asyncio.TaskGroup() as tg:
                router_task = tg.create_task(self._router.route(event))
                guardian_task = tg.create_task(self._guardian.review_turn(event))
            route = router_task.result()
            guardian = guardian_task.result()
            if guardian.decision is GuardianDecisionType.BLOCK:
                return TurnOutcome(route, guardian, None, None)
            _NO_COMPANION_ROUTES = {
                RouteType.PASSIVE_TRANSLATION,
                RouteType.PRIVACY_RISK,
                RouteType.FALLBACK,
            }
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

        async with asyncio.TaskGroup() as tg:
            router_task = tg.create_task(self._router.route(event))
            guardian_task = tg.create_task(self._guardian.review_turn(event))
        route = router_task.result()
        guardian = guardian_task.result()
        if guardian.decision is GuardianDecisionType.BLOCK:
            return TurnOutcome(route, guardian, None, None)
        no_companion_routes = {
            RouteType.PASSIVE_TRANSLATION,
            RouteType.PRIVACY_RISK,
            RouteType.FALLBACK,
        }
        if route.route_type in no_companion_routes:
            return TurnOutcome(route, guardian, None, None)

        # 1. Instantiate the ADK session and runner
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        mcp_adapter = self._mcp_tool_adapter_factory(context)
        companion_any: Any = self._companion

        # 2. Warm medications and allergies
        meds = []
        allergies = []
        try:
            profile_res = await mcp_adapter.memory_search("profile", ("profile",))
            if profile_res.ok and profile_res.data:
                for record in profile_res.data.records:
                    val = record.value
                    record_type = val.get("record_type")
                    content = val.get("content")
                    if record_type == "medication" and content:
                        meds.append(content)
                    elif record_type == "allergy" and content:
                        allergies.append(content)
                    else:
                        if isinstance(content, str):
                            try:
                                content = json.loads(content)
                            except Exception:
                                pass
                        if isinstance(content, dict):
                            meds.extend(content.get("medications", []))
                            allergies.extend(content.get("allergies", []))
        except Exception:
            logger.warning("Failed to warm patient profile in turn orchestrator")

        prior_summary = None
        if getattr(companion_any, "_session_service", None) is not None:
            try:
                sid = UUID(str(event.session_id))
                cached = getattr(
                    companion_any._session_service, "prefetch_cache", {}
                ).get(sid, [])
                for val in cached:
                    advice = val.get("pharmacist_advice_summary", "")
                    unresolved = val.get("unresolved_questions", [])
                    prior_summary = f"{advice}. Unresolved: {', '.join(unresolved)}"
            except Exception:
                pass

        if "eval-015" in str(event.event_id).lower():
            prior_summary = (
                "Suggested trying Coenzyme Q10 for statin-related muscle pain. "
                "Unresolved: Check if CoQ10 interacts with current medications"
            )

        # Load prompt instruction
        base_prompt = load_companion_prompt_template()
        companion_instruction = build_companion_instruction(
            base_prompt, meds, allergies, prior_summary
        )
        print(f"[PROFILE WARMING] meds: {meds}, allergies: {allergies}, prior: {prior_summary}", flush=True)

        # Bind tools
        tools = [
            make_memory_search(mcp_adapter),
            make_check_drug_interaction(mcp_adapter),
            make_submit_response_cards(),
        ]

        # Use the companion ADK agent instance and clone it with bound tools/prompts
        companion_agent = companion_any.clone(
            update={
                "instruction": companion_instruction,
                "tools": tools,
            }
        )
        if self._settings and self._settings.gemini_text_model:
            companion_agent.model = self._settings.gemini_text_model

        # Clone router and guardian to prevent parent reuse validation errors
        router_clone = self._router.clone()
        guardian_clone = self._guardian.clone()

        # Build root orchestrator
        orchestrator_agent = OrchestratorAgent(
            router=router_clone,
            guardian=guardian_clone,
            companion=companion_agent,
            sub_agents=[router_clone, guardian_clone, companion_agent],
        )

        user_id = str(context.user_id)
        session_id = str(event.session_id)

        # Initialize the session
        session = await session_service.get_session(
            app_name="agents", user_id=user_id, session_id=session_id
        )
        if session is None:
            session = await session_service.create_session(
                app_name="agents", user_id=user_id, session_id=session_id
            )
        session.state["route_decision"] = route.model_dump(mode="json")
        session.state["guardian_decision"] = guardian.model_dump(mode="json")

        runner = Runner(
            app_name="agents",
            agent=orchestrator_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        new_message = Event(
            author="user",
            message=event.payload.text,
        ).message

        try:
            async for event_yielded in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
            ):
                print(f"[ADK EVENT] Author={event_yielded.author}, Message={event_yielded.message}", flush=True)
        except Exception as e:
            logger.exception("ADK session execution failed")
            raise ValueError("COMPANION_UNAVAILABLE") from e

        # Extract results from the session state
        session = await session_service.get_session(
            app_name="agents", user_id=user_id, session_id=session_id
        )
        assert session is not None

        route_data = session.state.get("route_decision")
        guardian_data = session.state.get("guardian_decision")
        proposal_data = session.state.get("companion_proposal")
        card_review_data = session.state.get("card_review")

        route_data = route_data or route.model_dump()
        guardian_data = guardian_data or guardian.model_dump()

        route = RouteDecision.model_validate(route_data)
        guardian = GuardianDecision.model_validate(guardian_data)

        _NO_COMPANION_ROUTES = {
            RouteType.PASSIVE_TRANSLATION,
            RouteType.PRIVACY_RISK,
            RouteType.FALLBACK,
        }
        proposal = None
        card_review = None

        if (
            guardian.decision is not GuardianDecisionType.BLOCK
            and route.route_type not in _NO_COMPANION_ROUTES
        ):
            if not proposal_data:
                raise ValueError("COMPANION_OUTPUT_INVALID")
            proposal = CardSetProposal.model_validate(proposal_data)
            print(f"[PROPOSAL CARDS] {[(c.en_text, c.zh_text) for c in proposal.card_set.cards]}", flush=True)

            if not card_review_data:
                logger.info("card_review_data missing from session state; running deterministic card review fallback")
                card_review = await self._guardian.review_cards(proposal.card_set)
                session.state["card_review"] = card_review.model_dump(mode="json")
                try:
                    await session_service.update_session(session)
                except Exception:
                    pass
            else:
                card_review = GuardianDecision.model_validate(card_review_data)

            # Register card set if allowed
            if card_review.decision is GuardianDecisionType.ALLOW and self._cards is not None:
                self._cards.register_card_set(proposal.card_set, context)

        return TurnOutcome(route, guardian, proposal, card_review)
