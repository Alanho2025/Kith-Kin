"""ADK OrchestratorAgent fanning out Router, Guardian, and Companion agents."""

import sys
from collections.abc import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.parallel_agent import (
    _merge_agent_run,
    _merge_agent_run_pre_3_11,
)
from google.adk.events import Event
from google.adk.utils.context_utils import Aclosing

from app.agents.guardian_agent import GuardianAgent
from app.core.constants import GuardianDecisionType
from app.schemas.agent_outputs import CardSetProposal, GuardianDecision, RouteDecision, RouteType


def _create_branch_ctx(
    agent: BaseAgent,
    sub_agent: BaseAgent,
    invocation_context: InvocationContext,
) -> InvocationContext:
    ctx = invocation_context.model_copy()
    branch_suffix = f"{agent.name}.{sub_agent.name}"
    ctx.branch = f"{ctx.branch}.{branch_suffix}" if ctx.branch else branch_suffix
    return ctx


class OrchestratorAgent(BaseAgent):
    """Root ADK agent managing Router, Guardian, and Companion flows."""

    name: str = "Orchestrator"
    description: str = "Root orchestrator agent managing conversation turns."

    router: BaseAgent
    guardian: GuardianAgent
    companion: BaseAgent

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """ADK execution entrypoint fanning out the agent graph.

        Args:
            ctx: The ADK invocation context.

        Yields:
            ADK events from sub-agents and final status.
        """
        # 1. Run Router and Guardian in parallel
        router_ctx = _create_branch_ctx(self, self.router, ctx)
        guardian_ctx = _create_branch_ctx(self, self.guardian, ctx)

        agent_runs = [
            self.router.run_async(router_ctx),
            self.guardian.run_async(guardian_ctx),
        ]

        merge_func = _merge_agent_run if sys.version_info >= (3, 11) else _merge_agent_run_pre_3_11

        async with Aclosing(merge_func(agent_runs)) as merged:
            async for event in merged:
                yield event

        # 2. Extract decisions from the state
        route_dict = ctx.session.state.get("route_decision")
        guardian_dict = ctx.session.state.get("guardian_decision")

        if not route_dict or not guardian_dict:
            ctx.session.state["orchestration_error"] = "ROUTER_OR_GUARDIAN_UNAVAILABLE"
            return

        route = RouteDecision.model_validate(route_dict)
        guardian_decision = GuardianDecision.model_validate(guardian_dict)

        # short-circuit: if Guardian fail-closes (privacy/injection),
        # do NOT call Companion LLM at all
        if guardian_decision.decision == GuardianDecisionType.BLOCK:
            msg = f"Guardian fail-closed turn with {guardian_decision.decision}. Short-circuiting."
            yield Event(author=self.name, message=msg)
            return

        # Check if route doesn't invoke Companion (e.g. passive translation or privacy risk)
        _NO_COMPANION_ROUTES = {RouteType.PASSIVE_TRANSLATION, RouteType.PRIVACY_RISK}
        if route.route_type in _NO_COMPANION_ROUTES:
            yield Event(author=self.name, message=f"Route {route.route_type} skips Companion.")
            return

        # 3. Invoke Companion Agent (LLM-based)
        companion_ctx = _create_branch_ctx(self, self.companion, ctx)
        async with Aclosing(self.companion.run_async(companion_ctx)) as companion_run:
            async for event in companion_run:
                yield event

        # 4. Guardian reviews proposed cards if they were submitted by Companion
        proposal_dict = ctx.session.state.get("companion_proposal")
        if proposal_dict:
            from pydantic import ValidationError

            try:
                proposal = CardSetProposal.model_validate(proposal_dict)
                # Review cards deterministically (we call review_cards on the
                # guardian agent instance)
                card_review = await self.guardian.review_cards(proposal.card_set)
                ctx.session.state["card_review"] = card_review.model_dump()
                yield Event(
                    author=self.guardian.name,
                    message=f"Card review decision: {card_review.decision}",
                )
            except ValidationError as e:
                yield Event(
                    author=self.name,
                    message=f"Companion proposal failed validation: {e}. Reverting to fallback.",
                )
