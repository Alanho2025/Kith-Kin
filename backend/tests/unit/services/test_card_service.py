import pytest

from app.domain.confirmation import CardConfirmationError, CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.services.card_service import CardService
from app.services.confirmed_action_executor import ConfirmedActionExecutor
from tests.fixtures.cards.approved_card_sets import approved_card_set
from tests.fixtures.clock import MutableClock


def context() -> TrustedRequestContext:
    from uuid import UUID

    return TrustedRequestContext(
        session_id=UUID("00000000-0000-4000-8000-000000000101"),
        user_id=UUID("00000000-0000-4000-8000-000000000001"),
        origin="test",
    )


async def test_select_has_zero_side_effects() -> None:
    clock = MutableClock()
    executor = ConfirmedActionExecutor()
    service = CardService(clock.now, executor)
    card_set = approved_card_set(clock)
    service.register_card_set(card_set, context())

    result = await service.select(
        CardSelectCommand(card_set.card_set_id, card_set.cards[0].card_id, card_set.revision),
        context(),
    )

    assert result.confirmation_id
    assert executor.action_count == 0


async def test_duplicate_confirm_returns_stored_outcome() -> None:
    clock = MutableClock()
    executor = ConfirmedActionExecutor()
    service = CardService(clock.now, executor)
    card_set = approved_card_set(clock)
    service.register_card_set(card_set, context())
    selected = await service.select(
        CardSelectCommand(card_set.card_set_id, card_set.cards[0].card_id, card_set.revision),
        context(),
    )

    first = await service.confirm_selected(selected.confirmation_id, context())
    second = await service.confirm_selected(selected.confirmation_id, context())

    assert first.replayed is False
    assert second.replayed is True
    assert executor.action_count == 1


async def test_expired_confirmation_fails_stably() -> None:
    clock = MutableClock()
    service = CardService(clock.now)
    card_set = approved_card_set(clock)
    service.register_card_set(card_set, context())
    selected = await service.select(
        CardSelectCommand(card_set.card_set_id, card_set.cards[0].card_id, card_set.revision),
        context(),
    )
    clock.advance(seconds=181)

    with pytest.raises(CardConfirmationError) as error:
        await service.confirm_selected(selected.confirmation_id, context())

    assert error.value.code == "CONFIRMATION_EXPIRED"


async def test_stale_revision_is_rejected() -> None:
    clock = MutableClock()
    service = CardService(clock.now)
    card_set = approved_card_set(clock, revision=2)
    service.register_card_set(card_set, context())

    with pytest.raises(CardConfirmationError) as error:
        await service.select(
            CardSelectCommand(card_set.card_set_id, card_set.cards[0].card_id, 1),
            context(),
        )

    assert error.value.code == "CARD_REVISION_STALE"
