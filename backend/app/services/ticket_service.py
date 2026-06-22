from uuid import UUID

from app.adapters.app_websocket_ticket_issuer import AppWebSocketTicketIssuer
from app.core.config import Settings
from app.core.errors import TicketScopeError
from app.domain.credentials import (
    AppWebSocketGrant,
    CredentialIssueRequest,
    TrustedRequestContext,
)
from app.services.session_service import SessionService


class TicketService:
    def __init__(
        self,
        settings: Settings,
        sessions: SessionService,
        issuer: AppWebSocketTicketIssuer,
    ) -> None:
        self._settings = settings
        self._sessions = sessions
        self._issuer = issuer

    async def issue(self, session_id: UUID, user_id: UUID, origin: str) -> AppWebSocketGrant:
        if origin not in self._settings.cors_allowed_origins:
            raise TicketScopeError
        await self._sessions.require_connectable(session_id, user_id)
        context = TrustedRequestContext(
            session_id=session_id,
            user_id=user_id,
            origin=origin,
        )
        return await self._issuer.issue(CredentialIssueRequest(session_id=session_id), context)
