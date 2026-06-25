import pytest
from google.genai import types

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


class FakeModels:
    def __init__(self) -> None:
        self.model: str | None = None
        self.contents: str | None = None
        self.config: types.GenerateContentConfig | None = None

    async def generate_content(
        self,
        *,
        model: str,
        contents: str,
        config: types.GenerateContentConfig,
    ) -> object:
        self.model = model
        self.contents = contents
        self.config = config
        return type("Response", (), {"text": "你最近有服用任何新药吗？"})()


class FakeAsyncClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models

    async def aclose(self) -> None:
        return None


class FakeGenAiClient:
    def __init__(self, models: FakeModels) -> None:
        self.aio = FakeAsyncClient(models)


async def test_sdk_translation_uses_25_flash_with_low_thinking() -> None:
    models = FakeModels()
    client = FakeGenAiClient(models)
    settings = Settings(environment="test", google_api_key="test-key")
    adapter = GeminiTextAdapter(settings, client_factory=lambda _: client)

    result = await adapter.translate_final(REQUEST)

    assert result.translated_text == "你最近有服用任何新药吗？"
    assert models.model == "gemini-2.5-flash"
    assert models.contents is not None
    assert REQUEST.text in models.contents
    assert models.config is not None
    assert models.config.temperature == 0
    assert models.config.thinking_config is not None
    assert models.config.thinking_config.thinking_level == types.ThinkingLevel.LOW
