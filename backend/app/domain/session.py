"""Pure session lifecycle types."""

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

from app.domain.response_card import InvalidTransitionError


class SessionStatus(StrEnum):
    """Conversation session lifecycle."""

    CREATED = "created"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ENDING = "ending"
    ENDED = "ended"


@dataclass(frozen=True)
class ConversationSession:
    """Minimal provider-independent session state."""

    session_id: UUID
    user_id: UUID
    status: SessionStatus = SessionStatus.CREATED

    def transition(self, target: SessionStatus) -> "ConversationSession":
        """Move through the only allowed forward session transitions."""
        allowed = {
            SessionStatus.CREATED: {SessionStatus.CONNECTING},
            SessionStatus.CONNECTING: {SessionStatus.ACTIVE, SessionStatus.ENDED},
            SessionStatus.ACTIVE: {SessionStatus.ENDING},
            SessionStatus.ENDING: {SessionStatus.ENDED},
            SessionStatus.ENDED: set(),
        }
        if target not in allowed[self.status]:
            raise InvalidTransitionError(f"{self.status.value} cannot transition to {target.value}")
        return replace(self, status=target)
