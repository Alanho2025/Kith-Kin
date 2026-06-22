from datetime import timedelta

from app.core.constants import CardActionType, CardRiskLevel
from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard
from tests.fixtures.clock import MutableClock


def approved_card_set(clock: MutableClock, *, revision: int = 1) -> CardSet:
    now = clock.now()
    return CardSet(
        card_set_id="cards-approved-1",
        revision=revision,
        source_event_id="evt-final-1",
        generated_at=now,
        expires_at=now + timedelta(minutes=3),
        cards=(
            ResponseCard(
                card_id="card-ask-1",
                card_type=CardType.ASK_QUESTION,
                zh_text="Please help me confirm whether this is safe.",
                en_text="Could you please confirm whether this is safe for me?",
                risk_level=CardRiskLevel.MEDICAL,
                action=CardAction(type=CardActionType.SHOW_TO_PHARMACIST),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id="guardian-1",
            ),
        ),
    )
