from collections.abc import Callable
from typing import cast
from uuid import UUID

from fastapi import Request, WebSocket

from app.adapters.app_websocket_ticket_issuer import TicketVerifier
from app.services.card_service import CardService
from app.services.live_runtime_service import LiveRuntimeService
from app.services.session_service import SessionService
from app.services.ticket_service import TicketService


def get_user_id(request: Request) -> UUID:
    return cast(UUID, request.app.state.user_id)


def get_session_service(request: Request) -> SessionService:
    return cast(SessionService, request.app.state.session_service)


def get_ticket_service(request: Request) -> TicketService:
    return cast(TicketService, request.app.state.ticket_service)


def get_card_service(request: Request) -> CardService:
    return cast(CardService, request.app.state.card_service)


def websocket_dependencies(
    websocket: WebSocket,
) -> tuple[TicketVerifier, LiveRuntimeService, Callable[[UUID], object]]:
    return (
        websocket.app.state.ticket_verifier,
        websocket.app.state.live_runtime_service,
        websocket.app.state.session_store.get,
    )
