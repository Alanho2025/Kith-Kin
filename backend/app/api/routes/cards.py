from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_card_service
from app.schemas.session_schemas import CardConfirmRecoveryRequest, CardConfirmRecoveryResponse
from app.services.card_service import CardService

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.post("/confirm", response_model=CardConfirmRecoveryResponse)
async def confirm_card(
    body: CardConfirmRecoveryRequest,
    cards: Annotated[CardService, Depends(get_card_service)],
) -> CardConfirmRecoveryResponse:
    result = cards.confirm(body.confirmation_id)
    return CardConfirmRecoveryResponse(
        confirmation_id=result.confirmation_id,
        replayed=result.replayed,
    )
