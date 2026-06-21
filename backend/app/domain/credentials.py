"""Credential type boundaries for backend-proxied Live sessions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr, model_validator


@dataclass(frozen=True)
class TrustedRequestContext:
    """Identity resolved by backend authentication, never caller parameters."""

    session_id: UUID
    user_id: UUID
    origin: str


@dataclass(frozen=True)
class CredentialIssueRequest:
    """Request to issue a ticket for one existing session."""

    session_id: UUID


@dataclass(frozen=True)
class AppWebSocketGrant:
    """Short-lived Kith&Kin backend WebSocket grant."""

    encoded_ticket: SecretStr
    expires_at: datetime
    session_id: UUID


class AppWebSocketTicketClaims(BaseModel):
    """JWT claims fixed to the Kith&Kin backend WebSocket audience."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    user_id: UUID
    jti: UUID
    purpose: Literal["live_websocket"]
    iss: str
    aud: str
    origin: str
    iat: datetime
    exp: datetime
    max_uses: Literal[1]

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppWebSocketTicketClaims":
        """Require a positive, bounded lifetime before adapter encoding."""
        if self.exp <= self.iat:
            raise ValueError("TICKET_TIME_RANGE_INVALID")
        return self


TGrant = TypeVar("TGrant", covariant=True)


class LiveCredentialIssuer(Protocol[TGrant]):
    """Generic issuer boundary; MVP implements only app WebSocket grants."""

    async def issue(
        self,
        request: CredentialIssueRequest,
        context: TrustedRequestContext,
    ) -> TGrant:
        """Issue a purpose-specific grant after trusted-context validation."""
        ...
