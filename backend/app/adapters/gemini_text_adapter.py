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
            key_val = self._settings.google_api_key.get_secret_value()
            if not key_val:
                raise ProviderUnavailableError("TRANSLATION_UNAVAILABLE")
            try:
                from google import genai
                client = genai.Client(api_key=key_val)
                model_name = self._settings.gemini_text_model or "gemini-2.5-flash"
                prompt = (
                    "You are a faithful translator. Translate the following English medical/pharmacy transcript "
                    "into Chinese. Retain the original meaning exactly without adding any medical advice, "
                    "recommendations, diagnoses, or extra information. Only return the direct translation:\n\n"
                    f"{request.text}"
                )
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                translated = response.text.strip() if response.text else ""
            except Exception as e:
                raise ProviderUnavailableError("TRANSLATION_UNAVAILABLE") from e
        else:
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
