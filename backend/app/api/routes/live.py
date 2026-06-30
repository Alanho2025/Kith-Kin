from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket
from pydantic import SecretStr

from app.core.errors import (
    SessionNotConnectableError,
    TicketInvalidError,
    TicketReplayError,
    TicketScopeError,
)

router = APIRouter(prefix="/api/sessions", tags=["live"])


@router.websocket("/{session_id}/live")
async def live_socket(
    websocket: WebSocket,
    session_id: UUID,
    last_seen_sequence: Annotated[int | None, Query(ge=0)] = None,
) -> None:
    settings = websocket.app.state.settings
    verifier = websocket.app.state.ticket_verifier
    runtime = websocket.app.state.live_runtime_service
    ticket = websocket.cookies.get(settings.app_ws_cookie_name, "")
    origin = websocket.headers.get("origin", "")
    try:
        # Validate the one-time ticket before accepting the socket so invalid
        # clients never get an upgraded runtime connection.
        await verifier.verify_and_consume(SecretStr(ticket), session_id, origin)
    except TicketInvalidError:
        await websocket.close(code=4401, reason="TICKET_INVALID")
        return
    except TicketScopeError:
        await websocket.close(code=4403, reason="TICKET_SCOPE_INVALID")
        return
    except TicketReplayError:
        await websocket.close(code=4409, reason="TICKET_REPLAYED")
        return
    except SessionNotConnectableError:
        await websocket.close(code=4410, reason="SESSION_NOT_CONNECTABLE")
        return
    # Session state changes only after ticket verification has established scope.
    await websocket.app.state.session_store.mark_active(session_id)
    await websocket.accept()
    await runtime.serve(
        websocket,
        session_id,
        last_seen_sequence=last_seen_sequence,
    )
