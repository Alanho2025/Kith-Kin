"""Confirmation lifecycle domain types."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.constants import CardActionType


class CardConfirmationError(Exception):
    """Stable card confirmation failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CardSelectCommand:
    """Identifier-only card selection command."""

    card_set_id: str
    card_id: str
    revision: int


@dataclass(frozen=True)
class CardSelectedResult:
    """Selection acknowledgement with no action side effect."""

    card_set_id: str
    card_id: str
    revision: int
    confirmation_id: str
    confirmation_expires_at: datetime


@dataclass(frozen=True)
class ConfirmationOutcome:
    """Terminal confirmation result."""

    confirmation_id: str
    action_type: CardActionType
    replayed: bool
    phase: str
    code: str | None


@dataclass(frozen=True)
class StoredConfirmation:
    """Server-owned confirmation state."""

    confirmation_id: str
    session_id: UUID
    user_id: UUID
    card_set_id: str
    card_id: str
    revision: int
    action_type: CardActionType
    action_hash: str
    guardian_decision_id: str
    expires_at: datetime
    idempotency_key: UUID
    state: str
    terminal_outcome: ConfirmationOutcome | None = None
