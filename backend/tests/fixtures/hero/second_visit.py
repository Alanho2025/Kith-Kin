import pytest

from app.adapters.provider_schemas import ProviderLiveEventType, ProviderTranscriptEvent


@pytest.fixture
def second_visit_transcript() -> list[ProviderTranscriptEvent]:
    """Mock transcript events for the second visit where parent asks for refill."""
    return [
        ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id="evt_2",
            utterance_id="utt_2",
            speaker="parent",
            language="en",
            text="I am here to pick up my blood pressure medication.",
            revision=1,
        )
    ]
