import pytest

from app.adapters.gemini_text_adapter import GeminiTextAdapter
from app.adapters.provider_schemas import TranslationRequest
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError

REQUEST = TranslationRequest(
    source_event_id="evt_source_1",
    utterance_id="utt_demo_1",
    text="Do you have any allergies to antibiotics?",
    source_language="en",
)


async def test_translate_final_uses_injected_provider_and_keeps_segment_ids() -> None:
    async def translate(request: TranslationRequest) -> str:
        return "\u4f60\u5bf9\u6297\u751f\u7d20\u8fc7\u654f\u5417\uff1f"

    adapter = GeminiTextAdapter(Settings(environment="test"), translate)

    result = await adapter.translate_final(REQUEST)

    assert result.segment_id == "seg_utt_demo_1"
    assert result.translated_text == "\u4f60\u5bf9\u6297\u751f\u7d20\u8fc7\u654f\u5417\uff1f"


async def test_advice_contamination_is_rejected() -> None:
    async def translate(request: TranslationRequest) -> str:
        return "\u5efa\u8bae\u4f60\u670d\u7528\u8fd9\u4e2a\u836f"

    adapter = GeminiTextAdapter(Settings(environment="test"), translate)

    with pytest.raises(ProviderUnavailableError):
        await adapter.translate_final(REQUEST)
