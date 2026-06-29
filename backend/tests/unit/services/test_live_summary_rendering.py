from app.services.live_runtime_service import _get_chinese_advice, _get_chinese_question


def test_summary_advice_renderer_does_not_invent_medical_alternatives() -> None:
    rendered = _get_chinese_advice(
        "Pharmacist said: I can show you ibuprofen for pain. The price is 9 dollars."
    )

    assert rendered == (
        "药师原话摘要：Pharmacist said: I can show you ibuprofen for pain. "
        "The price is 9 dollars."
    )
    assert "Panadol" not in rendered
    assert "相互作用" not in rendered


def test_summary_question_renderer_preserves_source_question_without_rewriting_as_advice() -> None:
    rendered = _get_chinese_question("Should I start taking Coenzyme Q10 for muscle aches?")

    assert rendered == "待确认问题：Should I start taking Coenzyme Q10 for muscle aches?"
    assert "我应该" not in rendered
