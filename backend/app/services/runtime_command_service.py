"""Shared runtime command handling for card confirmation flows."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.core.constants import CardActionType
from app.domain.confirmation import CardConfirmationError, CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import (
    CardCancelEvent,
    CardConfirmEvent,
    CardSelectEvent,
    PleaseWaitEvent,
    RepeatEvent,
    RuntimeEvent,
    SelfSpeakEvent,
    SessionEndEvent,
)
from app.services.card_service import CardService


@dataclass(frozen=True)
class RuntimeCommandEvent:
    """One server event produced by a runtime command."""

    event_type: str
    payload: dict[str, object]
    correlation_id: str | None


class RuntimeCommandService:
    """Process client commands without duplicating HTTP and WS logic."""

    def __init__(self, cards: CardService, user_id: UUID) -> None:
        self._cards = cards
        self._user_id = user_id

    async def handle(
        self,
        event: RuntimeEvent,
        *,
        session_id: UUID,
        origin: str = "runtime",
    ) -> tuple[RuntimeCommandEvent, ...]:
        context = TrustedRequestContext(session_id=session_id, user_id=self._user_id, origin=origin)
        if isinstance(event, CardSelectEvent):
            selected = await self._cards.select(
                CardSelectCommand(
                    card_set_id=event.payload.card_set_id,
                    card_id=event.payload.card_id,
                    revision=event.payload.revision,
                ),
                context,
            )
            return (
                RuntimeCommandEvent(
                    "card.selected",
                    {
                        "card_set_id": selected.card_set_id,
                        "card_id": selected.card_id,
                        "revision": selected.revision,
                        "confirmation_id": selected.confirmation_id,
                        "confirmation_expires_at": selected.confirmation_expires_at.isoformat(),
                    },
                    event.event_id,
                ),
            )
        if isinstance(event, CardConfirmEvent):
            payload: dict[str, object]
            try:
                outcome = await self._cards.confirm_selected(event.payload.confirmation_id, context)
                payload = {
                    "confirmation_id": outcome.confirmation_id,
                    "action_type": outcome.action_type.value,
                    "replayed": outcome.replayed,
                }
            except CardConfirmationError as error:
                payload = {
                    "confirmation_id": event.payload.confirmation_id,
                    "action_type": CardActionType.NO_ACTION.value,
                    "phase": "blocked",
                    "code": error.code,
                }
                return (RuntimeCommandEvent("card.action.status", payload, event.event_id),)
            return (RuntimeCommandEvent("card.confirmed", payload, event.event_id),)
        if isinstance(event, CardCancelEvent):
            await self._cards.cancel(event.payload.confirmation_id, context)
            return (
                RuntimeCommandEvent(
                    "card.action.status",
                    {
                        "confirmation_id": event.payload.confirmation_id,
                        "action_type": CardActionType.NO_ACTION.value,
                        "phase": "blocked",
                        "code": "ACTION_BLOCKED",
                    },
                    event.event_id,
                ),
            )
        if isinstance(event, SelfSpeakEvent):
            await self._cards.cancel_all_pending(context)
            return (
                RuntimeCommandEvent(
                    "audio.muted",
                    {"muted": False, "reason": "user_control"},
                    event.event_id,
                ),
                RuntimeCommandEvent(
                    "audio.listening",
                    {"active": True},
                    event.event_id,
                ),
            )
        if isinstance(event, PleaseWaitEvent):
            await self._cards.cancel_all_pending(context)
            return (
                RuntimeCommandEvent(
                    "audio.muted",
                    {"muted": True, "reason": "user_control"},
                    event.event_id,
                ),
                RuntimeCommandEvent(
                    "audio.listening",
                    {"active": False},
                    event.event_id,
                ),
            )
        if isinstance(event, RepeatEvent):
            # Acknowledge the repeat request by signaling that we are listening
            return (
                RuntimeCommandEvent(
                    "audio.listening",
                    {"active": True},
                    event.event_id,
                ),
            )
        if isinstance(event, SessionEndEvent):
            await self._cards.cancel_all_pending(context)
            return (
                RuntimeCommandEvent(
                    "session.ended",
                    {
                        "reason": event.payload.reason,
                        "ended_at": datetime.now(UTC).isoformat(),
                    },
                    event.event_id,
                ),
            )
        return ()
