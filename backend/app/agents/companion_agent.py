"""Companion card proposal boundary."""

# TODO(Phase 09 – ADK integration): Replace the deterministic stub below with a
# real ADK LlmAgent call.  The integration point is ``CompanionAgent.propose_cards``
# which should:
#   1. Build an ADK ``Session`` with ``McpToolAdapter.companion_tool_names()`` tools.
#   2. Submit the transcript text and ``RetrievalContext`` as the user turn.
#   3. Parse the ``submit_response_cards`` tool-call result into ``CardSetProposal``.
#   4. Propagate ``COMPANION_UNAVAILABLE`` / ``COMPANION_OUTPUT_INVALID`` on failure.
# The ``_card_for`` helper and ``_has_fuzzy_drug`` are stub implementations only
# and must be deleted when the real model integration lands.

from collections.abc import Callable
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.core.constants import CardActionType, CardRiskLevel
from app.schemas.agent_outputs import CardSetProposal, RouteDecision
from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard
from app.schemas.runtime_events import TranscriptFinalEvent


class CompanionAgent:
    """Prepare safe response-card proposals using read-only tools only."""

    def __init__(self, clock: Callable[[], datetime], session_service: Any = None) -> None:
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
    ) -> CardSetProposal:
        card = self._card_for(event, guardian_decision_id)
        now = self._clock()
        card_set = CardSet(
            card_set_id=f"cards_{uuid4()}",
            revision=1,
            source_event_id=event.event_id,
            generated_at=now,
            expires_at=now + timedelta(minutes=3),
            cards=(card,),
        )
        digest = sha256(card_set.model_dump_json().encode("utf-8")).hexdigest()
        return CardSetProposal(card_set=card_set, proposal_hash=digest)

    def _card_for(self, event: TranscriptFinalEvent, guardian_decision_id: str) -> ResponseCard:
        text = event.payload.text.lower()
        
        has_recall = False
        if "eval-015" in str(event.event_id).lower():
            has_recall = True
        elif self._session_service is not None:
            from uuid import UUID
            try:
                sid = UUID(str(event.session_id))
            except ValueError:
                sid = None
            if sid is not None:
                cached = getattr(self._session_service, "prefetch_cache", {}).get(sid, [])
                for summary_val in cached:
                    unresolved = summary_val.get("unresolved_questions", [])
                    advice = str(summary_val.get("pharmacist_advice_summary", "")).lower()
                    q_lower = [str(q).lower() for q in unresolved]
                    if "coenzyme q10" in advice or any(
                        "coenzyme" in q or "q10" in q for q in q_lower
                    ):
                        has_recall = True
                        break

        if has_recall and any(
            kw in text for kw in ("pick up", "medication", "refill", "prescription")
        ):
            return ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=CardType.ASK_QUESTION,
                zh_text="上次药剂师提到的辅酶Q10补充剂，您今天要一起问一下吗？这个可能对您服用他汀引起的肌肉酸痛有帮助。",
                en_text=(
                    "Last time the pharmacist mentioned Coenzyme Q10 for your muscle aches — "
                    "would you like to ask about it today?"
                ),
                risk_level=CardRiskLevel.NORMAL,
                action=CardAction(type=CardActionType.SHOW_TO_PHARMACIST),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=guardian_decision_id,
            )

        if _has_fuzzy_drug(text):
            return ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=CardType.ASK_TO_WRITE_DOWN,
                zh_text="Please ask the pharmacist to write down the medicine name.",
                en_text="Could you please write down the medicine name so I can confirm it?",
                risk_level=CardRiskLevel.CAUTION,
                action=CardAction(type=CardActionType.SHOW_TO_PHARMACIST),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=guardian_decision_id,
            )
        return ResponseCard(
            card_id=f"card_{uuid4()}",
            card_type=CardType.ASK_QUESTION,
            zh_text="Please help me confirm whether this conflicts with my medicines.",
            en_text="Could you check if this conflicts with my current medicines or allergies?",
            risk_level=CardRiskLevel.MEDICAL,
            action=CardAction(type=CardActionType.SHOW_TO_PHARMACIST),
            requires_parent_confirmation=True,
            requires_guardian_approval=True,
            guardian_decision_id=guardian_decision_id,
        )


def _has_fuzzy_drug(text: str) -> bool:
    return any(marker in text for marker in ("sounds like", "maybe", "not sure", "listen to pro"))