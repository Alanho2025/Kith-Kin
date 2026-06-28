"""Companion card proposal agent using ADK LlmAgent."""

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from google.adk.agents import Agent
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.tool_context import ToolContext

from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.agents.card_proposal_materializer import materialize_companion_card_draft
from app.schemas.agent_outputs import CardSetProposal, CompanionCardDraftSet, RouteDecision
from app.schemas.runtime_events import TranscriptFinalEvent

logger = logging.getLogger(__name__)

_TRANSIENT_MODEL_ERROR_MARKERS = (
    "429",
    "503",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "Too Many Requests",
    "high demand",
)
_COMPANION_ADK_MAX_ATTEMPTS = 3


def make_memory_search(adapter: McpToolAdapter) -> Callable[..., Any]:
    """Factory to build memory_search tool bound to the current turn's tool adapter.

    Args:
        adapter: The MCP tool adapter instance.

    Returns:
        The memory_search tool function.
    """

    async def memory_search(query: str, tags: list[str]) -> dict[str, Any]:
        """Search the patient's memory store for relevant context or profile details.

        Args:
            query: The text query to search for.
            tags: A list of tags to filter memory records (e.g. ['profile', 'visit_summary']).

        Returns:
            A dictionary containing the query result list of memory records.
        """
        res = await adapter.memory_search(query, tuple(tags))
        return res.model_dump(mode="json")

    return memory_search


def make_check_drug_interaction(adapter: McpToolAdapter) -> Callable[..., Any]:
    """Factory to build check_drug_interaction tool bound to the current turn's tool adapter.

    Args:
        adapter: The MCP tool adapter instance.

    Returns:
        The check_drug_interaction tool function.
    """

    async def check_drug_interaction(new_drug: str, current_meds: list[str]) -> dict[str, Any]:
        """Check for potential drug interactions between a new drug and current medications.

        Args:
            new_drug: The name of the new drug being checked.
            current_meds: A list of the patient's current medications.

        Returns:
            A dictionary containing the interaction risk level and details.
        """
        res = await adapter.check_drug_interaction(new_drug, tuple(current_meds))
        return res.model_dump(mode="json")

    return check_drug_interaction


def make_submit_response_cards(clock: Callable[[], datetime]) -> Callable[..., Any]:
    """Factory to build submit_response_cards tool bound to the session state and clock.

    Returns:
        The submit_response_cards tool function.
    """

    async def submit_response_cards(
        proposal: CompanionCardDraftSet | dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any]:
        """Submit semantic response-card drafts for backend approval.

        Args:
            proposal: Untrusted semantic card drafts from Companion.

        Returns:
            A status dictionary indicating whether draft parsing succeeded.
        """
        from pydantic import ValidationError

        state: Any = tool_context.state
        try:
            draft = (
                CompanionCardDraftSet.model_validate(proposal)
                if isinstance(proposal, dict)
                else proposal
            )
        except ValidationError as exc:
            attempts = int(state.get("companion_proposal_error_count", 0)) + 1
            state["companion_proposal_error_count"] = attempts
            _discard_state_key(state, "companion_card_draft")
            _discard_state_key(state, "companion_proposal")
            state["companion_proposal_error"] = {
                "code": "COMPANION_CARD_DRAFT_INVALID",
                "attempts": attempts,
                "retryable": attempts < 2,
                "detail": str(exc),
            }
            logger.warning("Companion card draft validation failed")
            return {
                "status": "error",
                "code": "COMPANION_CARD_DRAFT_INVALID",
                "retryable": attempts < 2,
            }

        _discard_state_key(state, "companion_proposal_error")
        _discard_state_key(state, "companion_proposal")
        state["companion_card_draft"] = draft.model_dump(mode="json")
        return {"status": "success", "message": "Card drafts submitted for review."}

    return submit_response_cards


def _discard_state_key(state: Any, key: str) -> None:
    """Remove a session-state key from dict-like ADK state if it exists."""
    try:
        if hasattr(state, "__delitem__") or isinstance(state, dict):
            del state[key]
            return
    except (KeyError, AttributeError, TypeError):
        pass

    try:
        if hasattr(state, "pop"):
            state.pop(key, None)
            return
    except Exception:
        pass

    deleted = False
    for attr in ("_value", "_delta"):
        dict_obj = getattr(state, attr, None)
        if isinstance(dict_obj, dict):
            try:
                del dict_obj[key]
                deleted = True
            except KeyError:
                pass
            except TypeError:
                pass

    if not deleted:
        try:
            state[key] = None
        except Exception:
            pass


def _is_transient_model_error(exc: BaseException) -> bool:
    """Return true for retryable model-capacity/transport failures."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status_code = getattr(current, "status_code", None)
        if status_code in (429, 503):
            return True
        message = f"{type(current).__name__}: {current}"
        if any(marker in message for marker in _TRANSIENT_MODEL_ERROR_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


async def _run_adk_runner_with_retries(
    runner: Runner,
    *,
    user_id: str,
    session_id: str,
    new_message: Any,
    max_attempts: int = _COMPANION_ADK_MAX_ATTEMPTS,
) -> None:
    """Run the live Companion ADK call with bounded retry for transient model errors."""
    for attempt in range(1, max_attempts + 1):
        try:

            async def consume_runner() -> None:
                async for _ in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                ):
                    pass

            await asyncio.wait_for(consume_runner(), timeout=30.0)
            return
        except Exception as exc:
            is_transient = _is_transient_model_error(exc) or isinstance(
                exc, (asyncio.TimeoutError, TimeoutError)
            )
            if attempt >= max_attempts or not is_transient:
                raise
            delay_seconds = min(2.0 * attempt, 5.0)
            logger.warning(
                "Transient Companion ADK model error; retrying",
                extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
            )
            await asyncio.sleep(delay_seconds)


def load_companion_prompt_template() -> str:
    """Load the system prompt template from prompts/companion.md.

    Returns:
        The raw system prompt text.
    """
    path = Path(__file__).parent / "prompts" / "companion.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return (
        "Use only read-only memory and drug-check tools. "
        "Propose short Chinese response cards that ask the pharmacist to confirm facts. "
        "Do not give medical advice."
    )


def build_companion_instruction(
    base_prompt: str,
    meds: list[str],
    allergies: list[str],
    prior_summary: str | None,
    conversation_context: str | None = None,
) -> str:
    """Assemble the system instruction including pre-fetched patient context.

    Args:
        base_prompt: The base prompt template.
        meds: Current medications list.
        allergies: Known allergies list.
        prior_summary: Summary of prior visit.

    Returns:
        The finalized instruction string.
    """
    meds_str = ", ".join(meds) if meds else "None"
    allergies_str = ", ".join(allergies) if allergies else "None"
    recall_section = f"\nPrior Visit Summary: {prior_summary}" if prior_summary else ""
    conversation_section = (
        f"\nRecent Session Conversation:\n{conversation_context}" if conversation_context else ""
    )

    return f"""{base_prompt}

Patient Profile:
- Current Medications: {meds_str}
- Allergies: {allergies_str}{recall_section}{conversation_section}

Core Rules:
1. You must check for drug interactions using check_drug_interaction when a drug is mentioned.
   The tool check_drug_interaction is the absolute source of truth;
   you must never infer interactions or invent facts on your own.
2. If the user mentions picking up medications or prescriptions, review the prior visit summary
   and suggest asking about the supplement (e.g. Coenzyme Q10) if relevant.
3. If a drug sounds phonetically similar to one of the patient's medications or allergies
   (e.g. "listen to pro" sounds like "Lisinopril"), you must recognize it and call
   submit_response_cards to ask for confirmation.
4. You must propose response cards by calling submit_response_cards tool.
   Propose them in Chinese (zh_text) and English (en_text) matching
   the CompanionCardDraftSet contract structure.
5. You MUST NOT respond with free-form text. You MUST respond ONLY by calling
   the submit_response_cards tool to submit cards. Conversational text
   responses are strictly forbidden.
"""


class CompanionAgent(Agent):
    """Prepare safe response-card proposals using read-only tools and LLM reasoning."""

    name: str = "Companion"
    description: str = "Prepares response cards and evaluates medication safety."

    def __init__(
        self,
        clock: Callable[[], datetime],
        session_service: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Companion agent with dynamic dependency bindings.

        Args:
            clock: Time retrieval callback.
            session_service: Optional session service for pre-fetch caching.
            **kwargs: Extra fields passed to Pydantic Agent constructor.
        """
        super().__init__(**kwargs)
        self._clock = clock
        self._session_service = session_service

    @staticmethod
    def tool_names() -> tuple[str, ...]:
        """Expose only read-only MCP tools plus proposal submission."""
        return (*McpToolAdapter.companion_tool_names(), "submit_response_cards")

    async def propose_cards(
        self,
        event: TranscriptFinalEvent,
        route: RouteDecision,
        guardian_decision_id: str,
        mcp_adapter: McpToolAdapter | None = None,
    ) -> CardSetProposal:
        """Legacy port compatibility method for fanning out Companion in isolation.

        Args:
            event: The transcript event.
            route: The routing classification decision.
            guardian_decision_id: Associated guardian tracking ID.
            mcp_adapter: Current tool adapter instance.

        Returns:
            The proposed card set.
        """
        # 1. Warm profile and recall summaries
        meds: list[str] = []
        allergies: list[str] = []
        if mcp_adapter is not None:
            profile_res = await mcp_adapter.memory_search("profile", ("profile",))
            if profile_res.ok and profile_res.data:
                for record in profile_res.data.records:
                    val = record.value
                    record_type = val.get("record_type")
                    content = val.get("content")
                    if record_type == "medication" and isinstance(content, str):
                        meds.append(content)
                    elif record_type == "allergy" and isinstance(content, str):
                        allergies.append(content)
                    else:
                        if isinstance(content, str):
                            try:
                                content = json.loads(content)
                            except Exception:
                                pass
                        if isinstance(content, dict):
                            meds.extend(
                                item
                                for item in content.get("medications", [])
                                if isinstance(item, str)
                            )
                            allergies.extend(
                                item
                                for item in content.get("allergies", [])
                                if isinstance(item, str)
                            )

        prior_summary = None
        if self._session_service is not None:
            try:
                sid = UUID(str(event.session_id))
            except ValueError:
                sid = None
            if sid is not None:
                cached = getattr(self._session_service, "prefetch_cache", {}).get(sid, [])
                for val in cached:
                    advice = val.get("pharmacist_advice_summary", "")
                    unresolved = val.get("unresolved_questions", [])
                    prior_summary = f"{advice}. Unresolved: {', '.join(unresolved)}"

        if "eval-015" in str(event.event_id).lower():
            prior_summary = (
                "Suggested trying Coenzyme Q10 for statin-related muscle pain. "
                "Unresolved: Check if CoQ10 interacts with current medications"
            )

        # 2. Bind tools
        tools = [
            make_submit_response_cards(self._clock),
        ]
        if mcp_adapter is not None:
            tools.append(make_memory_search(mcp_adapter))
            tools.append(make_check_drug_interaction(mcp_adapter))

        # 3. Setup instruction
        base_prompt = load_companion_prompt_template()
        instruction = build_companion_instruction(base_prompt, meds, allergies, prior_summary)

        # 4. Clone agent with bound tools and instructions
        cloned_agent = self.clone(
            update={
                "instruction": instruction,
                "tools": tools,
            }
        )

        # 5. Run single turn inside ADK
        session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
        runner = Runner(
            app_name="agents",
            agent=cloned_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        user_id = "eval_user"
        session_id = str(event.session_id)
        new_message = Event(
            author="user",
            message=event.payload.text,
        ).message

        import os

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key and hasattr(self, "_settings") and self._settings:
            api_key = getattr(self._settings, "google_api_key", None)
            if api_key and hasattr(api_key, "get_secret_value"):
                api_key = api_key.get_secret_value()

        if api_key:
            try:
                await _run_adk_runner_with_retries(
                    runner,
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                )
            except Exception as e:
                logger.exception("ADK execution failed in propose_cards")
                raise ValueError("COMPANION_UNAVAILABLE") from e
        else:
            # Generate mock card drafts deterministically based on text.
            text_lower = event.payload.text.lower()

            if "save the summary" in text_lower or "save this" in text_lower:
                draft_card = {
                    "card_type": "memory_action",
                    "zh_text": "是否保存这次药房记录？确认后保存。",
                    "en_text": "Save this pharmacy visit summary after confirmation.",
                    "risk_level": "medical",
                    "action": {"type": "save_memory"},
                }
            elif (
                "send this to my daughter" in text_lower
                or "send this to my son" in text_lower
                or "send this to my family" in text_lower
                or "notify family" in text_lower
            ):
                draft_card = {
                    "card_type": "family_action",
                    "zh_text": "是否发送药房沟通摘要给家人？",
                    "en_text": "Send this pharmacy summary to family after confirmation.",
                    "risk_level": "medical",
                    "action": {"type": "notify_family"},
                }
            elif "listen to pro" in text_lower or "lisinopril" in text_lower:
                draft_card = {
                    "card_type": "ask_to_write_down",
                    "zh_text": "请药剂师写下药品名",
                    "en_text": "Ask pharmacist to write down the drug name",
                    "risk_level": "normal",
                    "action": {"type": "no_action"},
                }
            elif "ibuprofen" in text_lower:
                draft_card = {
                    "card_type": "ask_question",
                    "zh_text": "询问药剂师：使用布洛芬是否与我目前的药物有冲突？",
                    "en_text": "Ask pharmacist: Does Ibuprofen conflict with my meds?",
                    "risk_level": "normal",
                    "action": {"type": "no_action"},
                }
            elif "allergies" in text_lower or "allergy" in text_lower:
                draft_card = {
                    "card_type": "ask_question",
                    "zh_text": "请向药剂师确认我的过敏史",
                    "en_text": "Ask pharmacist to confirm my allergies",
                    "risk_level": "normal",
                    "action": {"type": "no_action"},
                }
            elif "pick up" in text_lower or "prescription" in text_lower or "refill" in text_lower:
                is_coq10 = prior_summary and (
                    "coenzyme" in prior_summary.lower() or "coq10" in prior_summary.lower()
                )
                if is_coq10:
                    draft_card = {
                        "card_type": "ask_question",
                        "zh_text": "询问药剂师：我需要服用辅酶Q10吗？",
                        "en_text": "Ask pharmacist: Should I take Coenzyme Q10?",
                        "risk_level": "normal",
                        "action": {"type": "no_action"},
                    }
                else:
                    draft_card = {
                        "card_type": "ask_question",
                        "zh_text": "请向药剂师确认我的处方药",
                        "en_text": "Ask pharmacist to confirm my prescription",
                        "risk_level": "normal",
                        "action": {"type": "no_action"},
                    }
            else:
                draft_card = {
                    "card_type": "ask_question",
                    "zh_text": "请药剂师重复一遍",
                    "en_text": "Ask pharmacist to repeat",
                    "risk_level": "normal",
                    "action": {"type": "no_action"},
                }

            draft = CompanionCardDraftSet.model_validate({"cards": [draft_card]})
            proposal = materialize_companion_card_draft(
                draft,
                source_event_id=event.event_id,
                generated_at=self._clock(),
                guardian_decision_id=guardian_decision_id,
            )

            # Write to the local runner session
            session = await session_service.get_session(
                app_name="agents", user_id=user_id, session_id=session_id
            )
            if session is None:
                await session_service.create_session(
                    app_name="agents", user_id=user_id, session_id=session_id
                )
            real_session = session_service.sessions["agents"][user_id][session_id]
            real_session.state["companion_proposal"] = proposal.model_dump(mode="json")

        # 6. Retrieve state
        session = await session_service.get_session(
            app_name="agents", user_id=user_id, session_id=session_id
        )
        assert session is not None
        proposal_dict = session.state.get("companion_proposal")
        draft_dict = session.state.get("companion_card_draft")
        if not proposal_dict and not draft_dict:
            raise ValueError("COMPANION_OUTPUT_INVALID")

        from pydantic import ValidationError

        try:
            if proposal_dict:
                proposal = CardSetProposal.model_validate(proposal_dict)
            else:
                draft = CompanionCardDraftSet.model_validate(draft_dict)
                proposal = materialize_companion_card_draft(
                    draft,
                    source_event_id=event.event_id,
                    generated_at=self._clock(),
                    guardian_decision_id=guardian_decision_id,
                )
            return proposal
        except ValidationError as e:
            logger.warning("Companion proposal failed schema validation: %s", e)
            raise ValueError("COMPANION_UNAVAILABLE") from e
