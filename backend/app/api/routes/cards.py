from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_card_service
from app.domain.confirmation import CardConfirmationError
from app.domain.credentials import TrustedRequestContext
from app.schemas.session_schemas import CardConfirmRecoveryRequest, CardConfirmRecoveryResponse
from app.services.card_service import CardService

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.post("/confirm", response_model=CardConfirmRecoveryResponse)
async def confirm_card(
    request: Request,
    body: CardConfirmRecoveryRequest,
    cards: Annotated[CardService, Depends(get_card_service)],
) -> CardConfirmRecoveryResponse:
    record = cards._repository.get(body.confirmation_id)
    if not record:
        raise CardConfirmationError("CARD_NOT_FOUND")
    
    context = TrustedRequestContext(
        session_id=record.session_id,
        user_id=request.app.state.user_id,
        origin="http_recovery",
    )
    
    result = await cards.confirm_selected(body.confirmation_id, context)
    return CardConfirmRecoveryResponse(
        confirmation_id=result.confirmation_id,
        replayed=result.replayed,
    )
