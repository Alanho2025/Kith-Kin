from app.core.constants import CardActionType
from app.services.audio_playback_coordinator import AudioPlaybackCoordinator
from app.services.confirmed_action_executor import ApprovedSpeech
from tests.fixtures.audio_gateway import RecordingEventSink


async def test_mute_wraps_every_audio_frame() -> None:
    sink = RecordingEventSink()
    coordinator = AudioPlaybackCoordinator()

    outcome = await coordinator.play_confirmed(
        ApprovedSpeech("confirmation-1", "card-1", "hello", CardActionType.SPEAK),
        sink,
    )

    assert outcome.phase == "completed"
    assert [item[0] for item in sink.items] == [
        "audio.muted",
        "audio.speaking",
        "audio.frame",
        "audio.speaking",
        "audio.muted",
        "audio.listening",
    ]


async def test_tts_failure_restores_listening() -> None:
    sink = RecordingEventSink(fail_audio=True)
    coordinator = AudioPlaybackCoordinator()

    outcome = await coordinator.play_confirmed(
        ApprovedSpeech("confirmation-1", "card-1", "hello", CardActionType.SPEAK),
        sink,
    )

    assert outcome.code == "TTS_UNAVAILABLE"
    assert sink.items[-2][0] == "audio.muted"
    assert sink.items[-2][1]["muted"] is False
    assert sink.items[-1] == ("audio.listening", {"active": True})
