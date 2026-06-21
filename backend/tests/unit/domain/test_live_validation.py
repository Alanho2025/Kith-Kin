from app.domain.live_validation import LiveProbeSample, ValidationStatus, evaluate_live_probe


def make_sample(
    *,
    final: bool = True,
    transcription_latency_ms: int = 500,
    translation_latency_ms: int = 300,
    contains_advice: bool = False,
) -> LiveProbeSample:
    return LiveProbeSample(
        source_text="Do you have any allergies?",
        translation_text="您有什么过敏吗？",
        final=final,
        transcription_latency_ms=transcription_latency_ms,
        translation_latency_ms=translation_latency_ms,
        contains_advice=contains_advice,
    )


def test_passes_at_validation_thresholds() -> None:
    samples = [make_sample() for _ in range(9)] + [make_sample(final=False)]

    result = evaluate_live_probe(samples)

    assert result.status is ValidationStatus.PASS
    assert result.usable_final_count == 9
    assert result.reasons == ()


def test_fails_when_fewer_than_nine_finals_are_usable() -> None:
    samples = [make_sample() for _ in range(8)] + [make_sample(final=False) for _ in range(2)]

    result = evaluate_live_probe(samples)

    assert result.status is ValidationStatus.FAIL
    assert "insufficient_usable_finals" in result.reasons


def test_fails_when_latency_exceeds_limit() -> None:
    samples = [make_sample(transcription_latency_ms=1600) for _ in range(10)]

    result = evaluate_live_probe(samples)

    assert result.status is ValidationStatus.FAIL
    assert "transcription_latency_exceeded" in result.reasons


def test_fails_when_translation_contains_agent_advice() -> None:
    samples = [make_sample() for _ in range(9)] + [make_sample(contains_advice=True)]

    result = evaluate_live_probe(samples)

    assert result.status is ValidationStatus.FAIL
    assert result.advice_contamination_count == 1
    assert "translation_advice_contamination" in result.reasons
