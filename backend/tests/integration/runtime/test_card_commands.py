from datetime import UTC, datetime
from uuid import UUID

from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import CardConfirmEvent, CardSelectEvent, SelfSpeakEvent
from app.services.card_service import CardService
from app.services.confirmed_action_executor import ConfirmedActionExecutor
from app.services.runtime_command_service import RuntimeCommandService
from tests.fixtures.cards.approved_card_sets import approved_card_set
from tests.fixtures.clock import MutableClock

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def context() -> TrustedRequestContext:
    return TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")


def card_select_event() -> CardSelectEvent:
    return CardSelectEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-select-1",
            "event_type": "card.select",
            "session_id": str(SESSION_ID),
            "sequence": 10,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {
                "card_set_id": "cards-approved-1",
                "card_id": "card-ask-1",
                "revision": 1,
            },
        }
    )


def card_confirm_event(confirmation_id: str, event_id: str = "evt-confirm-1") -> CardConfirmEvent:
    return CardConfirmEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": event_id,
            "event_type": "card.confirm",
            "session_id": str(SESSION_ID),
            "sequence": 11,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {"confirmation_id": confirmation_id},
        }
    )


def self_speak_event() -> SelfSpeakEvent:
    return SelfSpeakEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-self-speak-1",
            "event_type": "control.self_speak",
            "session_id": str(SESSION_ID),
            "sequence": 12,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {},
        }
    )


async def test_card_select_confirm_and_replay_are_idempotent() -> None:
    clock = MutableClock()
    executor = ConfirmedActionExecutor()
    cards = CardService(clock.now, executor)
    cards.register_card_set(approved_card_set(clock), context())
    commands = RuntimeCommandService(cards, USER_ID)

    selected = await commands.handle(card_select_event(), session_id=SESSION_ID)
    assert selected[0].event_type == "card.selected"
    assert executor.action_count == 0

    confirmation_id = str(selected[0].payload["confirmation_id"])
    confirmed = await commands.handle(card_confirm_event(confirmation_id), session_id=SESSION_ID)
    replayed = await commands.handle(
        card_confirm_event(confirmation_id, "evt-confirm-2"),
        session_id=SESSION_ID,
    )

    assert confirmed[0].event_type == "card.confirmed"
    assert confirmed[0].payload["replayed"] is False
    assert replayed[0].payload["replayed"] is True
    assert executor.action_count == 1


async def test_self_speak_restores_listening_without_card_action() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    events = await commands.handle(self_speak_event(), session_id=SESSION_ID)

    assert events[0].event_type == "audio.listening"
    assert events[0].payload == {"active": True}
    assert executor.action_count == 0
