"""Pure evaluation of sanitised Gemini Live transcription probe samples."""

from collections.abc import Sequence
from enum import StrEnum
from math import ceil

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(StrEnum):
    """Possible Live validation outcomes."""

    PASS = "pass"
    FAIL = "fail"
    BLOCKED_MISSING_CREDENTIALS = "blocked_missing_credentials"


class LiveProbeSample(BaseModel):
    """Provider-independent measurements for one sanitised utterance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_text: str
    translation_text: str
    final: bool
    transcription_latency_ms: int = Field(ge=0)
    translation_latency_ms: int = Field(ge=0)
    contains_advice: bool = False


class LiveValidationResult(BaseModel):
    """Deterministic output from the Live probe evaluator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ValidationStatus
    utterance_count: int
    usable_final_count: int
    transcription_p95_ms: int | None
    translation_p95_ms: int | None
    advice_contamination_count: int
    reasons: tuple[str, ...]


def _nearest_rank_p95(values: Sequence[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[ceil(0.95 * len(ordered)) - 1]


def evaluate_live_probe(samples: Sequence[LiveProbeSample]) -> LiveValidationResult:
    """Evaluate the Phase 00 thresholds without provider or credential access."""
    usable = [
        sample
        for sample in samples
        if sample.final and sample.source_text.strip() and sample.translation_text.strip()
    ]
    transcription_p95 = _nearest_rank_p95([sample.transcription_latency_ms for sample in usable])
    translation_p95 = _nearest_rank_p95([sample.translation_latency_ms for sample in usable])
    advice_count = sum(sample.contains_advice for sample in samples)
    reasons: list[str] = []
    if len(usable) < 9:
        reasons.append("insufficient_usable_finals")
    if transcription_p95 is not None and transcription_p95 > 1500:
        reasons.append("transcription_latency_exceeded")
    if translation_p95 is not None and translation_p95 > 1000:
        reasons.append("translation_latency_exceeded")
    if advice_count:
        reasons.append("translation_advice_contamination")
    return LiveValidationResult(
        status=ValidationStatus.FAIL if reasons else ValidationStatus.PASS,
        utterance_count=len(samples),
        usable_final_count=len(usable),
        transcription_p95_ms=transcription_p95,
        translation_p95_ms=translation_p95,
        advice_contamination_count=advice_count,
        reasons=tuple(reasons),
    )


def missing_credentials_result() -> LiveValidationResult:
    """Return an honest result for an opt-in real probe without credentials."""
    return LiveValidationResult(
        status=ValidationStatus.BLOCKED_MISSING_CREDENTIALS,
        utterance_count=0,
        usable_final_count=0,
        transcription_p95_ms=None,
        translation_p95_ms=None,
        advice_contamination_count=0,
        reasons=("google_api_key_missing",),
    )
