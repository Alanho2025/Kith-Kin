from app.core.conversation_debug import (
    conversation_log,
    observe_conversation_logs,
    text_fingerprint,
)


def test_text_fingerprint_redacts_date_like_values() -> None:
    summary = text_fingerprint("My birthday is 12/05/1940 and I have a note.")

    assert summary["chars"] == 44
    assert summary["preview"] == "My birthday is [date] and I have a note."
    assert len(summary["sha256_12"]) == 12


def test_conversation_log_redacts_secrets_and_summarises_text() -> None:
    observed = []

    with observe_conversation_logs(lambda label, payload: observed.append((label, payload))):
        conversation_log(
            "test.event",
            session="session-1",
            api_key="secret-value",
            spoken_text="Could you please note my birthday is 12/05/1940?",
        )

    assert len(observed) == 1
    label, payload = observed[0]
    assert label == "test.event"
    assert payload["api_key"] == "[redacted]"
    assert "12/05/1940" not in str(payload)
    assert payload["spoken_text"]["sha256_12"]
