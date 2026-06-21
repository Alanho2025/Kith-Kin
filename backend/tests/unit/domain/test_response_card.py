from datetime import UTC, datetime, timedelta

import pytest

from app.domain.response_card import (
    CardLifecycleState,
    ConfirmationExpiredError,
    ConfirmationReplayError,
    InvalidTransitionError,
    ResponseCardStateMachine,
    StaleRevisionError,
)

NOW = datetime(2026, 6, 22, tzinfo=UTC)


def machine() -> ResponseCardStateMachine:
    return ResponseCardStateMachine.render(
        card_set_id="set-1",
        revision=1,
        expires_at=NOW + timedelta(minutes=1),
    )


def test_completes_valid_card_lifecycle() -> None:
    state = machine().select(card_id="card-1", revision=1, now=NOW)
    state = state.await_confirmation("confirm-1")
    state = state.confirm(now=NOW)
    state = state.start_execution()
    state = state.succeed()

    assert state.state is CardLifecycleState.SUCCEEDED


def test_rejects_stale_card_revision() -> None:
    with pytest.raises(StaleRevisionError):
        machine().select(card_id="card-1", revision=2, now=NOW)


def test_rejects_expired_card() -> None:
    with pytest.raises(ConfirmationExpiredError):
        machine().select(card_id="card-1", revision=1, now=NOW + timedelta(minutes=2))


def test_selection_cannot_start_execution() -> None:
    selected = machine().select(card_id="card-1", revision=1, now=NOW)

    with pytest.raises(InvalidTransitionError):
        selected.start_execution()


def test_rejects_replayed_confirmation_with_stable_error() -> None:
    confirmed = (
        machine()
        .select(card_id="card-1", revision=1, now=NOW)
        .await_confirmation("confirm-1")
        .confirm(now=NOW)
    )

    with pytest.raises(ConfirmationReplayError, match="CONFIRMATION_REPLAYED"):
        confirmed.confirm(now=NOW)
