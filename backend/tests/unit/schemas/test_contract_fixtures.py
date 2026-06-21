import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.cards import CardSet, ResponseCard
from app.schemas.mcp import MemorySearchData, ToolResult
from app.schemas.runtime_events import TranscriptFinalEvent, parse_runtime_event

ROOT = Path(__file__).resolve().parents[4]


def load_fixture(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_runtime_fixture_parses_as_transcript_final() -> None:
    event = parse_runtime_event(load_fixture("specs/fixtures/runtime/transcript-final.json"))

    assert isinstance(event, TranscriptFinalEvent)


def test_card_fixture_enforces_both_confirmation_gates() -> None:
    card_set = CardSet.model_validate(load_fixture("specs/fixtures/cards/response-card-set.json"))

    assert card_set.cards[0].requires_parent_confirmation is True
    assert card_set.cards[0].requires_guardian_approval is True


def test_outward_card_without_parent_confirmation_is_invalid() -> None:
    card = load_fixture("specs/fixtures/cards/response-card-set.json")["cards"][0]
    assert isinstance(card, dict)
    card["requires_parent_confirmation"] = False

    with pytest.raises(ValidationError, match="PARENT_CONFIRMATION_REQUIRED"):
        ResponseCard.model_validate(card)


def test_mcp_success_fixture_parses_with_structured_data() -> None:
    result = ToolResult[MemorySearchData].model_validate(
        load_fixture("specs/fixtures/mcp/memory-search-success.json")
    )

    assert result.data is not None
    assert len(result.data.records) == 1


def test_mcp_failure_fixture_contains_no_data() -> None:
    result = ToolResult[MemorySearchData].model_validate(
        load_fixture("specs/fixtures/mcp/memory-unavailable.json")
    )

    assert result.data is None
    assert result.error is not None
    assert result.error.fallback_code == "memory_unavailable"
