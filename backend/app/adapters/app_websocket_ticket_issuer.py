from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pydantic import SecretStr

from app.core.config import Settings
from app.core.errors import (
    SessionNotConnectableError,
    TicketInvalidError,
    TicketReplayError,
    TicketScopeError,
)
from app.domain.credentials import (
    AppWebSocketGrant,
    AppWebSocketTicketClaims,
    CredentialIssueRequest,
    TrustedRequestContext,
)
from app.repositories.session_store import SessionStore
from app.repositories.ticket_use_store import TicketUseStore


class TicketVerifier(Protocol):
    async def verify_and_consume(
        self,
        encoded_ticket: SecretStr,
        expected_session_id: UUID,
        origin: str,
    ) -> AppWebSocketTicketClaims: ...


class AppWebSocketTicketIssuer:
    def __init__(self, settings: Settings, clock: Callable[[], datetime]) -> None:
        self._settings = settings
        self._clock = clock

    async def issue(
        self,
        request: CredentialIssueRequest,
        context: TrustedRequestContext,
    ) -> AppWebSocketGrant:
        if request.session_id != context.session_id:
            raise TicketScopeError
        issued_at = self._clock()
        expires_at = issued_at + self._settings.app_ws_token_ttl_seconds_delta
        claims = {
            "session_id": str(context.session_id),
            "user_id": str(context.user_id),
            "jti": str(uuid4()),
            "purpose": "live_websocket",
            "iss": self._settings.app_ws_token_issuer,
            "aud": self._settings.app_ws_token_audience,
            "origin": context.origin,
            "iat": issued_at,
            "exp": expires_at,
            "max_uses": 1,
        }
        encoded = jwt.encode(
            claims,
            self._settings.app_ws_token_secret.get_secret_value(),
            algorithm="HS256",
        )
        return AppWebSocketGrant(
            encoded_ticket=SecretStr(encoded),
            expires_at=expires_at,
            session_id=context.session_id,
        )


class AppWebSocketTicketVerifier:
    _REQUIRED = {
        "session_id",
        "user_id",
        "jti",
        "purpose",
        "iss",
        "aud",
        "origin",
        "iat",
        "exp",
        "max_uses",
    }

    def __init__(
        self,
        settings: Settings,
        clock: Callable[[], datetime],
        sessions: SessionStore,
        uses: TicketUseStore,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._sessions = sessions
        self._uses = uses

    async def verify_and_consume(
        self,
        encoded_ticket: SecretStr,
        expected_session_id: UUID,
        origin: str,
    ) -> AppWebSocketTicketClaims:
        raw_ticket = encoded_ticket.get_secret_value()
        if not raw_ticket:
            raise TicketInvalidError
        try:
            decoded = jwt.decode(
                raw_ticket,
                self._settings.app_ws_token_secret.get_secret_value(),
                algorithms=["HS256"],
                options={"verify_aud": False, "verify_exp": False, "verify_iat": False},
            )
        except InvalidTokenError as exc:
            raise TicketInvalidError from exc
        if not self._REQUIRED.issubset(decoded):
            raise TicketInvalidError
        try:
            session_id = UUID(str(decoded["session_id"]))
            user_id = UUID(str(decoded["user_id"]))
            jti = UUID(str(decoded["jti"]))
            issued_at = datetime.fromtimestamp(float(decoded["iat"]), tz=UTC)
            expires_at = datetime.fromtimestamp(float(decoded["exp"]), tz=UTC)
        except (TypeError, ValueError) as exc:
            raise TicketInvalidError from exc
        if self._clock() >= expires_at or expires_at <= issued_at:
            raise TicketInvalidError
        if (
            session_id != expected_session_id
            or decoded["purpose"] != "live_websocket"
            or decoded["iss"] != self._settings.app_ws_token_issuer
            or decoded["aud"] != self._settings.app_ws_token_audience
            or decoded["origin"] != origin
            or decoded["max_uses"] != 1
        ):
            raise TicketScopeError
        session = await self._sessions.get(expected_session_id)
        if session is None or session.status == "ended":
            raise SessionNotConnectableError
        if session.user_id != user_id:
            raise TicketScopeError
        if not await self._uses.consume_once(jti):
            raise TicketReplayError
        return AppWebSocketTicketClaims(
            session_id=session_id,
            user_id=user_id,
            jti=jti,
            purpose="live_websocket",
            iss=cast(str, decoded["iss"]),
            aud=cast(str, decoded["aud"]),
            origin=cast(str, decoded["origin"]),
            iat=issued_at,
            exp=expires_at,
            max_uses=1,
        )
