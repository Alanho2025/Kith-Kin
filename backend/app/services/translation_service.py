"""Faithful final-utterance translation sidecar service."""

import asyncio
from dataclasses import dataclass

from app.adapters.provider_schemas import TranslationGateway, TranslationRequest, TranslationSegment


@dataclass(frozen=True)
class TranslationFallback:
    """Safe fallback when the faithful sidecar cannot produce Chinese text."""

    code: str
    related_event_id: str


@dataclass(frozen=True)
class TranslationResult:
    """Translation service output for one final transcript."""

    segment: TranslationSegment | None
    fallback: TranslationFallback | None
    duplicate: bool


class TranslationService:
    """Translate only immutable final utterances and deduplicate by utterance."""

    def __init__(
        self,
        gateway: TranslationGateway,
        *,
        timeout_ms: int,
    ) -> None:
        self._gateway = gateway
        self._timeout_ms = timeout_ms
        self._seen_utterances: set[str] = set()

    def has_seen(self, utterance_id: str) -> bool:
        """Return whether this final utterance already produced a sidecar attempt."""
        return utterance_id in self._seen_utterances

    async def translate_final(self, request: TranslationRequest) -> TranslationResult:
        if request.utterance_id in self._seen_utterances:
            return TranslationResult(segment=None, fallback=None, duplicate=True)
        self._seen_utterances.add(request.utterance_id)
        try:
            async with asyncio.timeout(self._timeout_ms / 1000):
                segment = await self._gateway.translate_final(request)
        except TimeoutError:
            return TranslationResult(
                segment=None,
                fallback=TranslationFallback("TRANSLATION_TIMEOUT", request.source_event_id),
                duplicate=False,
            )
        except Exception:
            return TranslationResult(
                segment=None,
                fallback=TranslationFallback("TRANSLATION_UNAVAILABLE", request.source_event_id),
                duplicate=False,
            )
        return TranslationResult(segment=segment, fallback=None, duplicate=False)
