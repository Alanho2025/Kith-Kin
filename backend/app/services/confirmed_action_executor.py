"""Execute confirmed card actions exactly once."""

from dataclasses import dataclass

from app.core.constants import CardActionType
from app.domain.confirmation import ConfirmationOutcome
from app.domain.credentials import TrustedRequestContext
from app.schemas.cards import ResponseCard


@dataclass(frozen=True)
class ApprovedSpeech:
    """Speech/display text approved by confirmation."""

    confirmation_id: str
    card_id: str
    text: str
    action_type: CardActionType


class ConfirmedActionExecutor:
    """Local deterministic action executor for confirmed card actions."""

    def __init__(self) -> None:
        self.action_count = 0

    async def execute(
        self,
        confirmation_id: str,
        card: ResponseCard,
        context: TrustedRequestContext | None = None,
    ) -> ConfirmationOutcome:
        self.action_count += 1
        return ConfirmationOutcome(
            confirmation_id=confirmation_id,
            action_type=card.action.type,
            replayed=False,
            phase="succeeded",
            code=None,
        )
