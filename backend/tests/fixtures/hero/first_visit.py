import pytest

from app.adapters.provider_schemas import ProviderLiveEventType, ProviderTranscriptEvent


@pytest.fixture
def first_visit_transcript() -> list[ProviderTranscriptEvent]:
    """Mock transcript events for the first visit where Coenzyme Q10 is recommended."""
    return [
        ProviderTranscriptEvent(
            event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
            provider_event_id="evt_1",
            utterance_id="utt_1",
            speaker="pharmacist",
            language="en",
            text="You should try Coenzyme Q10 for your muscle aches.",
            revision=1,
        )
    ]
