"""Immutable response-card lifecycle enforcing two-stage confirmation."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


class CardLifecycleState(StrEnum):
    """Canonical response-card states."""

    RENDERED = "rendered"
    SELECTED = "selected"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    BLOCKED = "blocked"


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not explicitly allowed."""


class StaleRevisionError(ValueError):
    """Raised when the client references a non-current card-set revision."""


class ConfirmationExpiredError(ValueError):
    """Raised when selecting or confirming after expiry."""


class ConfirmationReplayError(ValueError):
    """Raised when a one-time confirmation is consumed more than once."""


@dataclass(frozen=True)
class ResponseCardStateMachine:
    """Backend-owned card state; client text never enters this object."""

    card_set_id: str
    revision: int
    expires_at: datetime
    state: CardLifecycleState
    card_id: str | None = None
    confirmation_id: str | None = None

    @classmethod
    def render(
        cls,
        *,
        card_set_id: str,
        revision: int,
        expires_at: datetime,
    ) -> "ResponseCardStateMachine":
        """Create a rendered card set with no executable authority."""
        return cls(card_set_id, revision, expires_at, CardLifecycleState.RENDERED)

    def _require(self, expected: CardLifecycleState) -> None:
        if self.state is not expected:
            raise InvalidTransitionError(f"{self.state.value} cannot perform this transition")

    def select(self, *, card_id: str, revision: int, now: datetime) -> "ResponseCardStateMachine":
        """Select a current card without authorising its action."""
        self._require(CardLifecycleState.RENDERED)
        if revision != self.revision:
            raise StaleRevisionError("CARD_REVISION_STALE")
        if now >= self.expires_at:
            raise ConfirmationExpiredError("CARD_EXPIRED")
        return replace(self, state=CardLifecycleState.SELECTED, card_id=card_id)

    def await_confirmation(self, confirmation_id: str) -> "ResponseCardStateMachine":
        """Bind a short-lived confirmation identifier to the selection."""
        self._require(CardLifecycleState.SELECTED)
        return replace(
            self,
            state=CardLifecycleState.AWAITING_CONFIRMATION,
            confirmation_id=confirmation_id,
        )

    def confirm(self, *, now: datetime) -> "ResponseCardStateMachine":
        """Authorize the backend-stored action exactly once."""
        if self.state in {
            CardLifecycleState.CONFIRMED,
            CardLifecycleState.EXECUTING,
            CardLifecycleState.SUCCEEDED,
            CardLifecycleState.FAILED,
        }:
            # Confirmation IDs are single-use authority; any terminal or active
            # execution state is treated as a replay attempt.
            raise ConfirmationReplayError("CONFIRMATION_REPLAYED")
        self._require(CardLifecycleState.AWAITING_CONFIRMATION)
        if now >= self.expires_at:
            raise ConfirmationExpiredError("CONFIRMATION_EXPIRED")
        return replace(self, state=CardLifecycleState.CONFIRMED)

    def start_execution(self) -> "ResponseCardStateMachine":
        """Begin an action only after confirmation."""
        self._require(CardLifecycleState.CONFIRMED)
        return replace(self, state=CardLifecycleState.EXECUTING)

    def succeed(self) -> "ResponseCardStateMachine":
        """Record successful action completion."""
        self._require(CardLifecycleState.EXECUTING)
        return replace(self, state=CardLifecycleState.SUCCEEDED)

    def fail(self) -> "ResponseCardStateMachine":
        """Record safe action failure."""
        self._require(CardLifecycleState.EXECUTING)
        return replace(self, state=CardLifecycleState.FAILED)

    def cancel(self) -> "ResponseCardStateMachine":
        """Cancel before execution without side effects."""
        if self.state not in {
            CardLifecycleState.RENDERED,
            CardLifecycleState.SELECTED,
            CardLifecycleState.AWAITING_CONFIRMATION,
        }:
            raise InvalidTransitionError(f"{self.state.value} cannot be cancelled")
        return replace(self, state=CardLifecycleState.CANCELLED)

    def block(self) -> "ResponseCardStateMachine":
        """Apply a Guardian block before execution."""
        if self.state in {
            CardLifecycleState.EXECUTING,
            CardLifecycleState.SUCCEEDED,
            CardLifecycleState.FAILED,
        }:
            raise InvalidTransitionError(f"{self.state.value} cannot be blocked")
        return replace(self, state=CardLifecycleState.BLOCKED)
