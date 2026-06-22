from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_session_service, get_ticket_service, get_user_id
from app.core.config import Settings
from app.schemas.session_schemas import (
    AppWebSocketTicketResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionRequest,
    EndSessionResponse,
)
from app.services.session_service import SessionService
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    user_id: Annotated[UUID, Depends(get_user_id)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> CreateSessionResponse:
    record = await sessions.create(user_id=user_id, encounter_type=body.encounter_type)
    return CreateSessionResponse(session_id=record.session_id)


@router.post(
    "/{session_id}/ticket",
    response_model=AppWebSocketTicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_ticket(
    session_id: UUID,
    request: Request,
    response: Response,
    user_id: Annotated[UUID, Depends(get_user_id)],
    tickets: Annotated[TicketService, Depends(get_ticket_service)],
) -> AppWebSocketTicketResponse:
    origin = request.headers.get("origin", "")
    grant = await tickets.issue(session_id, user_id, origin)
    settings: Settings = request.app.state.settings
    response.set_cookie(
        key=settings.app_ws_cookie_name,
        value=grant.encoded_ticket.get_secret_value(),
        max_age=settings.app_ws_token_ttl_seconds,
        httponly=True,
        secure=settings.app_ws_cookie_secure,
        samesite="strict",
        path=f"/api/sessions/{session_id}/live",
    )
    return AppWebSocketTicketResponse(
        session_id=session_id,
        expires_at=grant.expires_at,
    )


@router.post("/{session_id}/end", response_model=EndSessionResponse)
async def end_session(
    session_id: UUID,
    _body: EndSessionRequest,
    user_id: Annotated[UUID, Depends(get_user_id)],
    sessions: Annotated[SessionService, Depends(get_session_service)],
) -> EndSessionResponse:
    ended = await sessions.end(session_id, user_id)
    assert ended.ended_at is not None
    return EndSessionResponse(
        session_id=ended.session_id,
        ended_at=ended.ended_at,
    )
