"""Fallback translation adapter placeholder for the dedicated Live-translate model."""

from app.adapters.provider_schemas import TranslationGateway, TranslationRequest, TranslationSegment
from app.core.config import Settings
from app.core.errors import ProviderUnavailableError


class GeminiLiveTranslateAdapter(TranslationGateway):
    """Dedicated translation fallback selected only by settings.

    It is intentionally separate from the primary agent-mode Live session and is
    inactive unless the user opts into the documented fallback path.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        if not self._settings.live_translation_fallback_enabled:
            raise ProviderUnavailableError("TRANSLATION_UNAVAILABLE")
        raise ProviderUnavailableError("TRANSLATION_FALLBACK_NOT_CONFIGURED")
