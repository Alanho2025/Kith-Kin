from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import SessionNotConnectableError, TicketScopeError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotConnectableError)
    async def session_not_connectable(
        _request: Request,
        _exc: SessionNotConnectableError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"code": "SESSION_NOT_CONNECTABLE"})

    @app.exception_handler(TicketScopeError)
    async def ticket_scope_error(
        _request: Request,
        _exc: TicketScopeError,
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"code": "TICKET_SCOPE_INVALID"})
