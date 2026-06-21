"""HTTP session and app WebSocket ticket DTOs."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionRequest(BaseModel):
    """Start a pharmacy or GP companion session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encounter_type: Literal["pharmacy", "gp"] = "pharmacy"


class CreateSessionResponse(BaseModel):
    """Identifiers and status returned for a new session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    status: Literal["created"] = "created"


class AppWebSocketTicketResponse(BaseModel):
    """Safe ticket metadata; the ticket itself is delivered by HttpOnly cookie."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    expires_at: datetime
    max_uses: Literal[1] = 1


class EndSessionRequest(BaseModel):
    """Explicit user session-end reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: Literal["user_completed", "user_cancelled"]


class EndSessionResponse(BaseModel):
    """Terminal session acknowledgement."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: UUID
    status: Literal["ended"] = "ended"
    ended_at: datetime


SessionIdentifier = Annotated[str, Field(min_length=1, max_length=80)]
