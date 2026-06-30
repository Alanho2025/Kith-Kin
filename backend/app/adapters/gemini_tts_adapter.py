"""Gemini text-to-speech adapter for confirmed-card speech."""

from __future__ import annotations

import io
import re
import wave
from typing import Any

from app.adapters.provider_schemas import SynthesizedSpeech, TextToSpeechGateway
from app.core.config import Settings
from app.core.conversation_debug import conversation_log
from app.core.errors import ProviderUnavailableError

TARGET_SAMPLE_RATE_HZ = 24000
TARGET_MIME_TYPE = "audio/pcm"
MAX_TTS_TEXT_CHARS = 500


class GeminiTextToSpeechAdapter(TextToSpeechGateway):
    """Synthesize confirmed English utterances using Gemini's TTS model."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def synthesize(self, text: str) -> SynthesizedSpeech:
        clean_text = " ".join(text.split())
        if not clean_text:
            raise ProviderUnavailableError("TTS_TEXT_EMPTY")
        if len(clean_text) > MAX_TTS_TEXT_CHARS:
            raise ProviderUnavailableError("TTS_TEXT_TOO_LONG")
        key_val = self._settings.google_api_key.get_secret_value()
        if not key_val:
            if self._settings.environment in ("development", "test"):
                # Return dummy PCM audio for deterministic/offline testing
                return SynthesizedSpeech(
                    audio=b"\x00" * 48000,  # 1 second of silence at 24kHz 16-bit mono
                    mime_type=TARGET_MIME_TYPE,
                    sample_rate_hz=TARGET_SAMPLE_RATE_HZ,
                )
            raise ProviderUnavailableError("TTS_UNAVAILABLE")

        conversation_log(
            "gemini_tts.synthesize.start",
            model=self._settings.gemini_tts_model,
            voice_name=self._settings.gemini_tts_voice_name,
            spoken_text=clean_text,
        )
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key_val)
            response = await client.aio.models.generate_content(
                model=self._settings.gemini_tts_model,
                contents=(
                    "Read the following English sentence aloud exactly once. "
                    "Do not add, omit, translate, explain, or role-play. "
                    f"Sentence: {clean_text}"
                ),
                config=types.GenerateContentConfig(
                    response_modalities=["audio"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self._settings.gemini_tts_voice_name,
                            )
                        )
                    ),
                ),
            )
        except Exception as exc:
            conversation_log(
                "gemini_tts.synthesize.failed",
                error=type(exc).__name__,
                spoken_text=clean_text,
            )
            raise ProviderUnavailableError("TTS_UNAVAILABLE") from exc

        audio_data, mime_type = _first_audio_part(response)
        if not audio_data:
            conversation_log("gemini_tts.synthesize.no_audio", spoken_text=clean_text)
            raise ProviderUnavailableError("TTS_NO_AUDIO")
        pcm_audio = _to_pcm_24k(audio_data, mime_type)
        conversation_log(
            "gemini_tts.synthesize.ok",
            byte_length=len(pcm_audio),
            source_mime_type=mime_type,
            sample_rate_hz=TARGET_SAMPLE_RATE_HZ,
            spoken_text=clean_text,
        )
        return SynthesizedSpeech(
            audio=pcm_audio,
            mime_type=TARGET_MIME_TYPE,
            sample_rate_hz=TARGET_SAMPLE_RATE_HZ,
        )


def _first_audio_part(response: Any) -> tuple[bytes, str | None]:
    for candidate in getattr(response, "candidates", None) or ():
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or ():
            inline_data = getattr(part, "inline_data", None)
            if inline_data is None:
                continue
            data = getattr(inline_data, "data", None)
            if data:
                return bytes(data), getattr(inline_data, "mime_type", None)
    return b"", None


def _to_pcm_24k(audio: bytes, mime_type: str | None) -> bytes:
    normalized_mime = (mime_type or "").lower()
    if audio.startswith(b"RIFF") or "wav" in normalized_mime:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            if (
                sample_rate != TARGET_SAMPLE_RATE_HZ
                or channels != 1
                or sample_width != 2
            ):
                raise ProviderUnavailableError("TTS_AUDIO_FORMAT_UNSUPPORTED")
            return wav.readframes(wav.getnframes())

    rate = _rate_from_mime(normalized_mime)
    if rate is not None and rate != TARGET_SAMPLE_RATE_HZ:
        raise ProviderUnavailableError("TTS_AUDIO_FORMAT_UNSUPPORTED")
    return audio


def _rate_from_mime(mime_type: str) -> int | None:
    match = re.search(r"(?:rate|sample_rate)=(\d+)", mime_type)
    return int(match.group(1)) if match else None
