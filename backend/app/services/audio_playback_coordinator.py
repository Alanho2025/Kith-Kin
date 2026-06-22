"""Half-duplex audio playback event ordering."""

from dataclasses import dataclass
from typing import Protocol

from app.services.confirmed_action_executor import ApprovedSpeech


class RuntimeEventSink(Protocol):
    """Minimal sink used by playback tests and runtime adapters."""

    async def send_event(self, event_type: str, payload: dict[str, object]) -> None: ...

    async def send_audio(self, frame: bytes) -> None: ...


@dataclass(frozen=True)
class PlaybackOutcome:
    """Terminal playback state."""

    phase: str
    code: str | None = None


class AudioPlaybackCoordinator:
    """Emit mute/speaking/listening order around every approved audio frame."""

    async def play_confirmed(
        self,
        response: ApprovedSpeech,
        events: RuntimeEventSink,
    ) -> PlaybackOutcome:
        await events.send_event("audio.muted", {"muted": True, "reason": "tts_playback"})
        await events.send_event(
            "audio.speaking",
            {"phase": "started", "card_id": response.card_id},
        )
        try:
            await events.send_audio(response.text.encode("utf-8"))
            await events.send_event(
                "audio.speaking",
                {"phase": "completed", "card_id": response.card_id},
            )
            return PlaybackOutcome("completed")
        except Exception:
            await events.send_event(
                "fallback.show",
                {
                    "code": "TTS_UNAVAILABLE",
                    "message_zh": "Speech is unavailable; show the text to the pharmacist.",
                    "message_en": "Speech is unavailable; show the text to the pharmacist.",
                    "retryable": True,
                    "recovery_action": "show_to_pharmacist",
                    "related_event_id": response.confirmation_id,
                },
            )
            return PlaybackOutcome("failed", "TTS_UNAVAILABLE")
        finally:
            await events.send_event(
                "audio.muted",
                {"muted": False, "reason": "tts_playback"},
            )
            await events.send_event("audio.listening", {"active": True})
