import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.gemini_tts_adapter import GeminiTextToSpeechAdapter
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError


def wav_bytes(payload: bytes, *, sample_rate: int = 24000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(payload)
    return out.getvalue()


def audio_response(data: bytes, mime_type: str):
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(
                            inline_data=SimpleNamespace(data=data, mime_type=mime_type)
                        )
                    ]
                )
            )
        ]
    )


@pytest.mark.anyio
async def test_synthesize_uses_gemini_tts_and_strips_wav_header() -> None:
    adapter = GeminiTextToSpeechAdapter(
        Settings(google_api_key="dummy", gemini_tts_voice_name="charon")
    )
    pcm = b"\x01\x00\x02\x00"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=audio_response(wav_bytes(pcm), "audio/wav")
    )

    with patch("google.genai.Client", return_value=mock_client):
        result = await adapter.synthesize("Could you please repeat that?")

    assert result.audio == pcm
    assert result.mime_type == "audio/pcm"
    assert result.sample_rate_hz == 24000
    call = mock_client.aio.models.generate_content.await_args.kwargs
    assert call["model"] == "gemini-2.5-flash-preview-tts"
    assert "Could you please repeat that?" in call["contents"]


@pytest.mark.anyio
async def test_synthesize_accepts_raw_24k_pcm() -> None:
    adapter = GeminiTextToSpeechAdapter(Settings(google_api_key="dummy"))
    pcm = b"\x01\x00\x02\x00"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=audio_response(pcm, "audio/l16;rate=24000")
    )

    with patch("google.genai.Client", return_value=mock_client):
        result = await adapter.synthesize("Hello.")

    assert result.audio == pcm


@pytest.mark.anyio
async def test_synthesize_fails_closed_when_no_audio_part() -> None:
    adapter = GeminiTextToSpeechAdapter(Settings(google_api_key="dummy"))
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=SimpleNamespace(candidates=[])
    )

    with patch("google.genai.Client", return_value=mock_client):
        with pytest.raises(ProviderUnavailableError, match="TTS_NO_AUDIO"):
            await adapter.synthesize("Hello.")


@pytest.mark.anyio
async def test_synthesize_rejects_unsupported_wav_format() -> None:
    adapter = GeminiTextToSpeechAdapter(Settings(google_api_key="dummy"))
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=audio_response(wav_bytes(b"\x01\x00", sample_rate=16000), "audio/wav")
    )

    with patch("google.genai.Client", return_value=mock_client):
        with pytest.raises(ProviderUnavailableError, match="TTS_AUDIO_FORMAT_UNSUPPORTED"):
            await adapter.synthesize("Hello.")
