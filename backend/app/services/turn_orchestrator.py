"""Parallel Router/Guardian ADK orchestration for final transcript turns."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from app.agents.card_proposal_materializer import (
    approve_card_proposal,
    materialize_companion_card_draft,
)
from app.agents.companion_agent import (
    _run_adk_runner_with_retries,
    build_companion_instruction,
    load_companion_prompt_template,
    make_check_drug_interaction,
    make_memory_search,
    make_submit_response_cards,
)
from app.agents.orchestrator_agent import OrchestratorAgent
from app.core.constants import GuardianDecisionType
from app.core.conversation_debug import conversation_log, session_ref
from app.domain.credentials import TrustedRequestContext
from app.schemas.agent_outputs import (
    CardSetProposal,
    CompanionCardDraftSet,
    GuardianDecision,
    RouteDecision,
    RouteType,
)
from app.schemas.cards import CardSet
from app.schemas.runtime_events import TranscriptFinalEvent
from app.services.card_service import CardService

logger = logging.getLogger(__name__)

# Specific drug names (not class words like "nsaid"/"antibiotic") that, when
# named in a turn, must trigger a drug-interaction check deterministically rather
# than relying on the companion LLM to remember to call the tool. Safety backstop.
INTERACTION_DRUG_NAMES: frozenset[str] = frozenset(
    {
        "ibuprofen",
        "diclofenac",
        "naproxen",
        "aspirin",
        "warfarin",
        "lisinopril",
        "perindopril",
        "ramipril",
        "candesartan",
        "telmisartan",
        "irbesartan",
        "amlodipine",
        "atorvastatin",
        "rosuvastatin",
    }
)


class RouterPort(Protocol):
    async def route(self, event: TranscriptFinalEvent) -> RouteDecision: ...

    def clone(self) -> Any: ...


class GuardianPort(Protocol):
    async def review_turn(self, event: TranscriptFinalEvent) -> GuardianDecision: ...

    async def review_cards(self, card_set: CardSet) -> GuardianDecision: ...

    def clone(self) -> Any: ...


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
        conversation_context: str | None = None,
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
        conversation_log(
            "turn.process.start",
            session=session_ref(event.session_id),
            event_id=event.event_id,
            speaker=event.payload.speaker,
            language=event.payload.language,
            transcript_text=event.payload.text,
        )

        # Fallback for legacy unit tests (e.g., test_turn_orchestrator.py)
        if self._mcp_tool_adapter_factory is None:
            async with asyncio.TaskGroup() as tg:
                router_task = tg.create_task(self._router.route(event))
                guardian_task = tg.create_task(self._guardian.review_turn(event))
            route = router_task.result()
            guardian = guardian_task.result()
            conversation_log(
                "turn.route_guardian.result",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                route_type=route.route_type.value,
                route_reason=route.reason_code.value,
                guardian_decision=guardian.decision.value,
                guardian_reason=guardian.reason_code.value,
                legacy_path=True,
            )
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
            conversation_log(
                "turn.cards.proposed",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                card_count=len(proposal.card_set.cards),
                action_types=tuple(card.action.type.value for card in proposal.card_set.cards),
                card_review=card_review.decision.value,
                legacy_path=True,
            )
            if card_review.decision is GuardianDecisionType.ALLOW:
                proposal = approve_card_proposal(proposal, card_review)
            if card_review.decision is GuardianDecisionType.ALLOW and self._cards is not None:
                self._cards.register_card_set(proposal.card_set, context)
            return TurnOutcome(route, guardian, proposal, card_review)

        async with asyncio.TaskGroup() as tg:
            router_task = tg.create_task(self._router.route(event))
            guardian_task = tg.create_task(self._guardian.review_turn(event))
        route = router_task.result()
        guardian = guardian_task.result()
        conversation_log(
            "turn.route_guardian.result",
            session=session_ref(event.session_id),
            event_id=event.event_id,
            route_type=route.route_type.value,
            route_reason=route.reason_code.value,
            guardian_decision=guardian.decision.value,
            guardian_reason=guardian.reason_code.value,
            legacy_path=False,
        )
        if guardian.decision is GuardianDecisionType.BLOCK:
            return TurnOutcome(route, guardian, None, None)
        no_companion_routes = {
            RouteType.PASSIVE_TRANSLATION,
            RouteType.PRIVACY_RISK,
            RouteType.FALLBACK,
        }
        if route.route_type in no_companion_routes:
            conversation_log(
                "turn.companion.skipped",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                route_type=route.route_type.value,
            )
            return TurnOutcome(route, guardian, None, None)

        # 1. Instantiate the ADK session and runner
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        mcp_adapter = self._mcp_tool_adapter_factory(context)
        companion_any: Any = self._companion

        # 2. Warm medications and allergies — only for medication-risk turns.
        # The pharmacy_risk route is the router's risk trigger (dose, allergy,
        # interaction, medicine name, recall), so we retrieve the patient profile
        # only when it is actually relevant — not on every companion turn.
        meds: list[Any] = []
        allergies: list[Any] = []
        if route.route_type is RouteType.PHARMACY_RISK:
            try:
                conversation_log(
                    "turn.profile_lookup.start",
                    session=session_ref(event.session_id),
                    event_id=event.event_id,
                    route_type=route.route_type.value,
                )
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
                conversation_log(
                    "turn.profile_lookup.result",
                    session=session_ref(event.session_id),
                    event_id=event.event_id,
                    ok=profile_res.ok,
                    status=getattr(profile_res.status, "value", str(profile_res.status)),
                    medication_count=len(meds),
                    allergy_count=len(allergies),
                )
            except Exception:
                logger.warning("Failed to warm patient profile in turn orchestrator")
                conversation_log(
                    "turn.profile_lookup.failed",
                    session=session_ref(event.session_id),
                    event_id=event.event_id,
                )

            # Deterministic drug-interaction safety check: if the turn names a
            # specific drug, always run check_drug_interaction — don't rely on the
            # companion LLM to remember to call it. The result is traced; the
            # companion still produces the confirmation card.
            text_lower = event.payload.text.lower()
            named_drugs = [name for name in INTERACTION_DRUG_NAMES if name in text_lower]
            if named_drugs:
                new_drug = named_drugs[0]
                current_meds = tuple([*named_drugs[1:], *meds])
                try:
                    conversation_log(
                        "turn.deterministic_drug_check.start",
                        session=session_ref(event.session_id),
                        event_id=event.event_id,
                        new_drug=new_drug,
                        current_med_count=len(current_meds),
                    )
                    await mcp_adapter.check_drug_interaction(new_drug, current_meds)
                except Exception:
                    logger.warning("Deterministic drug-interaction check failed")
                    conversation_log(
                        "turn.deterministic_drug_check.failed",
                        session=session_ref(event.session_id),
                        event_id=event.event_id,
                        new_drug=new_drug,
                    )

        prior_summary = None
        if getattr(companion_any, "_session_service", None) is not None:
            try:
                sid = UUID(str(event.session_id))
                cached = getattr(companion_any._session_service, "prefetch_cache", {}).get(sid, [])
                for val in cached:
                    advice = val.get("pharmacist_advice_summary", "")
                    unresolved = val.get("unresolved_questions", [])
                    prior_summary = f"{advice}. Unresolved: {', '.join(unresolved)}"
            except Exception:
                pass

        # Load prompt instruction
        base_prompt = load_companion_prompt_template()
        companion_instruction = build_companion_instruction(
            base_prompt, meds, allergies, prior_summary, conversation_context
        )
        logger.debug("Companion context warmed for route %s", route.route_type.value)

        # Bind tools
        submit_clock = self._clock or (lambda: datetime.now(UTC))

        tools = [
            make_memory_search(mcp_adapter),
            make_check_drug_interaction(mcp_adapter),
            make_submit_response_cards(clock=submit_clock),
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
            conversation_log(
                "turn.companion.run.start",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                medication_count=len(meds),
                allergy_count=len(allergies),
                has_prior_summary=prior_summary is not None,
            )
            await _run_adk_runner_with_retries(
                runner,
                user_id=user_id,
                session_id=session_id,
                new_message=new_message,
            )
        except Exception as e:
            logger.exception("ADK session execution failed")
            conversation_log(
                "turn.companion.run.failed",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                error=type(e).__name__,
            )
            raise ValueError("COMPANION_UNAVAILABLE") from e

        # Extract results from the session state
        session = await session_service.get_session(
            app_name="agents", user_id=user_id, session_id=session_id
        )
        assert session is not None

        route_data = session.state.get("route_decision")
        guardian_data = session.state.get("guardian_decision")
        proposal_data = session.state.get("companion_proposal")
        draft_data = session.state.get("companion_card_draft")
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
            if not proposal_data and not draft_data:
                raise ValueError("COMPANION_OUTPUT_INVALID")
            if proposal_data:
                proposal = CardSetProposal.model_validate(proposal_data)
            else:
                draft = CompanionCardDraftSet.model_validate(draft_data)
                proposal = materialize_companion_card_draft(
                    draft,
                    source_event_id=event.event_id,
                    generated_at=submit_clock(),
                    guardian_decision_id="guardian_pending",
                )

            if not card_review_data:
                logger.info(
                    "card_review_data missing from session state; "
                    "running deterministic card review fallback"
                )
                card_review = await self._guardian.review_cards(proposal.card_set)
                session.state["card_review"] = card_review.model_dump(mode="json")
            else:
                card_review = GuardianDecision.model_validate(card_review_data)

            if card_review.decision is GuardianDecisionType.ALLOW:
                proposal = approve_card_proposal(proposal, card_review)
            conversation_log(
                "turn.cards.proposed",
                session=session_ref(event.session_id),
                event_id=event.event_id,
                card_count=len(proposal.card_set.cards),
                action_types=tuple(card.action.type.value for card in proposal.card_set.cards),
                card_review=card_review.decision.value,
            )
            # Register card set if allowed
            if card_review.decision is GuardianDecisionType.ALLOW and self._cards is not None:
                self._cards.register_card_set(proposal.card_set, context)
                conversation_log(
                    "turn.cards.registered",
                    session=session_ref(event.session_id),
                    event_id=event.event_id,
                    card_set_id=proposal.card_set.card_set_id,
                    card_count=len(proposal.card_set.cards),
                )

        conversation_log(
            "turn.process.complete",
            session=session_ref(event.session_id),
            event_id=event.event_id,
            route_type=route.route_type.value,
            guardian_decision=guardian.decision.value,
            has_card_proposal=proposal is not None,
            card_review=card_review.decision.value if card_review is not None else None,
        )
        return TurnOutcome(route, guardian, proposal, card_review)
