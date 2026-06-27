from datetime import UTC, datetime
from uuid import UUID

from app.core.constants import CardActionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import (
    CardConfirmEvent,
    CardSelectEvent,
    PleaseWaitEvent,
    RepeatEvent,
    SelfSpeakEvent,
    SessionEndEvent,
)
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


async def test_invalid_confirm_fails_closed_without_legacy_execution() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    events = await commands.handle(
        card_confirm_event("confirmation-not-issued"),
        session_id=SESSION_ID,
    )

    assert events[0].event_type == "card.action.status"
    assert events[0].payload == {
        "confirmation_id": "confirmation-not-issued",
        "action_type": CardActionType.NO_ACTION.value,
        "phase": "blocked",
        "code": "CARD_NOT_FOUND",
    }
    assert executor.action_count == 0


async def test_self_speak_restores_listening_without_card_action() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    events = await commands.handle(self_speak_event(), session_id=SESSION_ID)

    # 1. unmuting event should be emitted
    assert len(events) == 2
    assert events[0].event_type == "audio.muted"
    assert events[0].payload == {"muted": False, "reason": "user_control"}
    assert events[1].event_type == "audio.listening"
    assert events[1].payload == {"active": True}
    assert executor.action_count == 0


async def test_please_wait_button_triggers_hold() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    event = PleaseWaitEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-wait-1",
            "event_type": "control.please_wait",
            "session_id": str(SESSION_ID),
            "sequence": 15,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {},
        }
    )
    events = await commands.handle(event, session_id=SESSION_ID)
    assert len(events) == 2
    assert events[0].event_type == "audio.muted"
    assert events[0].payload == {"muted": True, "reason": "user_control"}
    assert events[1].event_type == "audio.listening"
    assert events[1].payload == {"active": False}


async def test_repeat_button_replays_last_translation() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    event = RepeatEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-repeat-1",
            "event_type": "control.repeat",
            "session_id": str(SESSION_ID),
            "sequence": 16,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {"target": "last_translation"},
        }
    )
    events = await commands.handle(event, session_id=SESSION_ID)
    # The command should succeed and return some feedback
    assert len(events) > 0


async def test_session_end_terminates_session() -> None:
    executor = ConfirmedActionExecutor()
    commands = RuntimeCommandService(CardService(lambda: NOW, executor), USER_ID)

    event = SessionEndEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": "evt-end-1",
            "event_type": "session.end",
            "session_id": str(SESSION_ID),
            "sequence": 17,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {"reason": "user_completed"},
        }
    )
    events = await commands.handle(event, session_id=SESSION_ID)
    assert len(events) == 1
    assert events[0].event_type == "session.ended"
    assert events[0].payload["reason"] == "user_completed"
