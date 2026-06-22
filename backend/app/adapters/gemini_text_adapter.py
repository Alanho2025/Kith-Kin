"""Gemini text adapter for faithful final-turn translation."""

from collections.abc import Awaitable, Callable
from time import perf_counter

from app.adapters.provider_schemas import TranslationGateway, TranslationRequest, TranslationSegment
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError

TranslateCallable = Callable[[TranslationRequest], Awaitable[str]]

ADVICE_CONTAMINATION_MARKERS = (
    "you should",
    "i recommend",
    "建议你",
    "你应该",
    "请服用",
)


class GeminiTextAdapter(TranslationGateway):
    """Translate final English utterances through a Gemini text model."""

    def __init__(
        self,
        settings: Settings,
        translator: TranslateCallable | None = None,
    ) -> None:
        self._settings = settings
        self._translator = translator

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        started = perf_counter()
        if self._translator is None:
            if not self._settings.google_api_key.get_secret_value():
                raise ProviderUnavailableError("TRANSLATION_UNAVAILABLE")
            raise ProviderUnavailableError("TRANSLATION_SDK_NOT_CONFIGURED")
        translated = await self._translator(request)
        if _looks_like_advice(translated):
            raise ProviderUnavailableError("TRANSLATION_ADVICE_CONTAMINATION")
        return TranslationSegment(
            source_transcript_event_id=request.source_event_id,
            segment_id=f"seg_{request.utterance_id}",
            source_language=request.source_language,
            target_language=request.target_language,
            translated_text=translated,
            latency_ms=int((perf_counter() - started) * 1000),
        )


def _looks_like_advice(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ADVICE_CONTAMINATION_MARKERS)
