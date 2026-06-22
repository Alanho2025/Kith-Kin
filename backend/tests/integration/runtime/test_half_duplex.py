from uuid import UUID

from app.domain.confirmation import CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.services.audio_playback_coordinator import AudioPlaybackCoordinator
from app.services.card_service import CardService
from app.services.confirmed_action_executor import ApprovedSpeech, ConfirmedActionExecutor
from tests.fixtures.audio_gateway import RecordingEventSink
from tests.fixtures.cards.approved_card_sets import approved_card_set
from tests.fixtures.clock import MutableClock

SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def context() -> TrustedRequestContext:
    return TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test")


async def test_confirmed_card_speech_is_half_duplex_ordered() -> None:
    clock = MutableClock()
    executor = ConfirmedActionExecutor()
    cards = CardService(clock.now, executor)
    card_set = approved_card_set(clock)
    card = card_set.cards[0]
    cards.register_card_set(card_set, context())

    selected = await cards.select(
        CardSelectCommand(card_set.card_set_id, card.card_id, card_set.revision),
        context(),
    )
    outcome = await cards.confirm_selected(selected.confirmation_id, context())

    sink = RecordingEventSink()
    playback = await AudioPlaybackCoordinator().play_confirmed(
        ApprovedSpeech(
            confirmation_id=outcome.confirmation_id,
            card_id=card.card_id,
            text=card.en_text,
            action_type=outcome.action_type,
        ),
        sink,
    )

    assert executor.action_count == 1
    assert playback.phase == "completed"
    assert [item[0] for item in sink.items] == [
        "audio.muted",
        "audio.speaking",
        "audio.frame",
        "audio.speaking",
        "audio.muted",
        "audio.listening",
    ]
    assert sink.items[0][1]["muted"] is True
    assert sink.items[-2][1]["muted"] is False
    assert sink.items[-1] == ("audio.listening", {"active": True})


async def test_confirmed_card_tts_failure_restores_listening() -> None:
    clock = MutableClock()
    cards = CardService(clock.now)
    card_set = approved_card_set(clock)
    card = card_set.cards[0]
    cards.register_card_set(card_set, context())

    selected = await cards.select(
        CardSelectCommand(card_set.card_set_id, card.card_id, card_set.revision),
        context(),
    )
    outcome = await cards.confirm_selected(selected.confirmation_id, context())

    sink = RecordingEventSink(fail_audio=True)
    playback = await AudioPlaybackCoordinator().play_confirmed(
        ApprovedSpeech(
            confirmation_id=outcome.confirmation_id,
            card_id=card.card_id,
            text=card.en_text,
            action_type=outcome.action_type,
        ),
        sink,
    )

    assert playback.code == "TTS_UNAVAILABLE"
    assert [item[0] for item in sink.items] == [
        "audio.muted",
        "audio.speaking",
        "fallback.show",
        "audio.muted",
        "audio.listening",
    ]
    assert sink.items[-2][1]["muted"] is False
    assert sink.items[-1] == ("audio.listening", {"active": True})
