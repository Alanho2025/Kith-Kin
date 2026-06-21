from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.core.constants import RuntimeEventType
from app.schemas.runtime_events import (
    TranscriptFinalEvent,
    UnknownRuntimeEvent,
    parse_runtime_event,
)


def envelope(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "event_id": "evt-1",
        "event_type": event_type,
        "session_id": "session-1",
        "sequence": 1,
        "timestamp": datetime(2026, 6, 22, tzinfo=UTC).isoformat(),
        "correlation_id": None,
        "payload": payload,
    }


def test_parses_known_transcript_final_event() -> None:
    event = parse_runtime_event(
        envelope(
            "transcript.final",
            {
                "utterance_id": "utterance-1",
                "speaker": "pharmacist",
                "language": "en",
                "text": "Do you have allergies?",
                "revision": 1,
            },
        )
    )

    assert isinstance(event, TranscriptFinalEvent)
    assert event.model_dump(mode="json")["event_type"] == "transcript.final"


def test_rejects_invalid_known_event_payload() -> None:
    with pytest.raises(ValidationError):
        parse_runtime_event(envelope("transcript.final", {"text": "missing fields"}))


def test_rejects_unsupported_major_schema_version() -> None:
    value = envelope("future.event", {}) | {"schema_version": "1.0"}

    with pytest.raises(ValueError, match="SCHEMA_VERSION_UNSUPPORTED"):
        parse_runtime_event(value)


def test_preserves_unknown_event_for_supported_major() -> None:
    event = parse_runtime_event(envelope("future.event", {"new_field": True}))

    assert event.event_type == "future.event"


@pytest.mark.parametrize("event_type", [item.value for item in RuntimeEventType])
def test_every_contract_event_has_a_typed_payload_model(event_type: str) -> None:
    value = envelope(event_type, {"unexpected": True})

    try:
        event = parse_runtime_event(value)
    except ValidationError:
        return

    assert not isinstance(event, UnknownRuntimeEvent), event_type
