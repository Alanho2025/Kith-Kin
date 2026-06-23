"""Card selection, confirmation, replay, and cancellation workflow."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from app.domain.confirmation import (
    CardConfirmationError,
    CardSelectCommand,
    CardSelectedResult,
    ConfirmationOutcome,
    StoredConfirmation,
)
from app.domain.credentials import TrustedRequestContext
from app.repositories.confirmation_repository import InMemoryConfirmationRepository
from app.schemas.cards import CardSet, ResponseCard
from app.services.confirmed_action_executor import ConfirmedActionExecutor


class CardService:
    """Own server-side card revisions and one-time confirmation state."""

    def __init__(
        self,
        clock: Callable[[], datetime] | None = None,
        executor: ConfirmedActionExecutor | None = None,
        repository: InMemoryConfirmationRepository | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._executor = executor or ConfirmedActionExecutor()
        self._repository = repository or InMemoryConfirmationRepository()
        self._card_sets: dict[tuple[str, str], CardSet] = {}
        self._card_contexts: dict[str, TrustedRequestContext] = {}
        self._lock = asyncio.Lock()
        self._confirm_lock = asyncio.Lock()

    def register_card_set(self, card_set: CardSet, context: TrustedRequestContext) -> None:
        """Store an approved card set for later selection; no action is executed."""
        # register_card_set is called from synchronous orchestrator context; the asyncio.Lock
        # is not needed here because dict mutation is GIL-protected and this method does not
        # await. Use direct assignment — callers that need serialisation must do so externally.
        self._card_sets[(str(context.session_id), card_set.card_set_id)] = card_set
        self._card_contexts[card_set.card_set_id] = context

    async def select(
        self,
        command: CardSelectCommand,
        context: TrustedRequestContext,
    ) -> CardSelectedResult:
        """Select a card and mint one confirmation ID without side effects."""
        async with self._lock:
            card_set = self._card_sets.get((str(context.session_id), command.card_set_id))
            if card_set is None:
                raise CardConfirmationError("CARD_NOT_FOUND")
            if card_set.revision != command.revision:
                raise CardConfirmationError("CARD_REVISION_STALE")
            if card_set.expires_at <= self._clock():
                raise CardConfirmationError("CARD_EXPIRED")
            card = _find_card(card_set, command.card_id)
            confirmation_id = f"confirmation_{uuid4()}"
            record = StoredConfirmation(
                confirmation_id=confirmation_id,
                session_id=context.session_id,
                user_id=context.user_id,
                card_set_id=card_set.card_set_id,
                card_id=card.card_id,
                revision=card_set.revision,
                action_type=card.action.type,
                action_hash=_action_hash(card),
                guardian_decision_id=card.guardian_decision_id,
                expires_at=card_set.expires_at,
                idempotency_key=uuid4(),
                state="pending",
            )
            self._repository.add(record)
        return CardSelectedResult(
            card_set_id=card_set.card_set_id,
            card_id=card.card_id,
            revision=card_set.revision,
            confirmation_id=confirmation_id,
            confirmation_expires_at=record.expires_at,
        )

    async def confirm_selected(
        self,
        confirmation_id: str,
        context: TrustedRequestContext,
    ) -> ConfirmationOutcome:
        """Confirm and execute one stored action, replaying the stored outcome."""
        async with self._confirm_lock:
            record = self._repository.get(confirmation_id)
            if record is None:
                raise CardConfirmationError("CARD_NOT_FOUND")
            if record.session_id != context.session_id or record.user_id != context.user_id:
                raise CardConfirmationError("CONFIRMATION_SCOPE_INVALID")
            if record.state == "cancelled":
                raise CardConfirmationError("ACTION_BLOCKED")
            if record.terminal_outcome is not None:
                return replace(record.terminal_outcome, replayed=True)
            if record.expires_at <= self._clock():
                raise CardConfirmationError("CONFIRMATION_EXPIRED")
            card_set = self._card_sets.get((str(context.session_id), record.card_set_id))
            if card_set is None:
                raise CardConfirmationError("CARD_NOT_FOUND")
            card = _find_card(card_set, record.card_id)
            if _action_hash(card) != record.action_hash:
                raise CardConfirmationError("ACTION_INTEGRITY_FAILED")
            outcome = await self._executor.execute(confirmation_id, card, context)
            self._repository.update(replace(record, state="confirmed", terminal_outcome=outcome))
            return outcome

    async def cancel(self, confirmation_id: str, context: TrustedRequestContext) -> None:
        """Cancel one pending confirmation without executing an action."""
        async with self._confirm_lock:
            record = self._repository.get(confirmation_id)
            if record is None:
                return
            if record.session_id != context.session_id or record.user_id != context.user_id:
                raise CardConfirmationError("CONFIRMATION_SCOPE_INVALID")
            if record.terminal_outcome is None:
                self._repository.update(replace(record, state="cancelled"))

    async def cancel_all_pending(self, context: TrustedRequestContext) -> None:
        """Cancel all pending confirmations for the session."""
        pending = self._repository.find_pending_by_session(context.session_id)
        for record in pending:
            if record.user_id == context.user_id:
                self._repository.update(replace(record, state="cancelled"))


def _find_card(card_set: CardSet, card_id: str) -> ResponseCard:
    for card in card_set.cards:
        if card.card_id == card_id:
            return card
    raise CardConfirmationError("CARD_NOT_FOUND")


def _action_hash(card: ResponseCard) -> str:
    return sha256(card.model_dump_json().encode("utf-8")).hexdigest()