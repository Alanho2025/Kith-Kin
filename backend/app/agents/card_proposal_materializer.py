"""Backend-owned materialization for Companion card drafts."""

from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from app.schemas.agent_outputs import CardSetProposal, CompanionCardDraftSet, GuardianDecision
from app.schemas.cards import CardSet, ResponseCard

CARD_SET_TTL_MINUTES = 15


def materialize_companion_card_draft(
    draft_set: CompanionCardDraftSet,
    *,
    source_event_id: str,
    generated_at: datetime,
    guardian_decision_id: str,
) -> CardSetProposal:
    """Build a canonical card proposal from untrusted semantic draft content.

    The LLM owns only card semantics. The backend owns IDs, lifecycle fields,
    confirmation gates, and proposal integrity hash.
    """
    card_set = CardSet(
        card_set_id=f"cards_{uuid4()}",
        revision=1,
        source_event_id=source_event_id,
        generated_at=generated_at,
        expires_at=generated_at + timedelta(minutes=CARD_SET_TTL_MINUTES),
        cards=tuple(
            ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=draft.card_type,
                zh_text=draft.zh_text,
                en_text=draft.en_text,
                speak_zh=draft.speak_zh,
                risk_level=draft.risk_level,

                action=draft.action,
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=guardian_decision_id,
            )
            for draft in draft_set.cards
        ),
    )
    return CardSetProposal(card_set=card_set, proposal_hash=proposal_hash_for_card_set(card_set))


def approve_card_proposal(
    proposal: CardSetProposal,
    guardian_decision: GuardianDecision,
) -> CardSetProposal:
    """Stamp approved cards with the card-review Guardian decision ID."""
    card_set = proposal.card_set.model_copy(
        update={
            "cards": tuple(
                card.model_copy(
                    update={"guardian_decision_id": guardian_decision.guardian_decision_id}
                )
                for card in proposal.card_set.cards
            )
        }
    )
    return CardSetProposal(card_set=card_set, proposal_hash=proposal_hash_for_card_set(card_set))


def proposal_hash_for_card_set(card_set: CardSet) -> str:
    """Return a deterministic integrity hash for one canonical card set."""
    return sha256(card_set.model_dump_json().encode("utf-8")).hexdigest()
