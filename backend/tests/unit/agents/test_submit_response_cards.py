from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.agents.card_proposal_materializer import (
    materialize_companion_card_draft,
    proposal_hash_for_card_set,
)
from app.agents.companion_agent import _run_adk_runner_with_retries, make_submit_response_cards
from app.schemas.agent_outputs import CompanionCardDraftSet

NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=UTC)


def clock() -> datetime:
    return NOW


class MockToolContext:
    def __init__(self, state=None):
        self.state = state if state is not None else {}


class NoPopState:
    def __init__(self, initial=None):
        self._data = dict(initial or {})

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def __delitem__(self, key):
        del self._data[key]

    def __contains__(self, key):
        return key in self._data


class FakeRunner:
    def __init__(self, failures: list[BaseException]):
        self.failures = failures
        self.calls = 0

    async def run_async(self, **_kwargs: Any):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        yield object()


@pytest.fixture
def submit_tool():
    return make_submit_response_cards(clock)


def valid_draft_card() -> dict[str, object]:
    return {
        "card_type": "confirm_info",
        "zh_text": "请向药剂师确认我的过敏史",
        "en_text": "Please confirm my allergy history with the pharmacist.",
        "risk_level": "medical",
        "action": {"type": "speak"},
    }


@pytest.mark.anyio
async def test_submit_cards_accepts_semantic_draft_only(submit_tool):
    context = MockToolContext()

    result = await submit_tool({"cards": [valid_draft_card()]}, context)

    assert result["status"] == "success"
    assert "companion_card_draft" in context.state
    assert "companion_proposal" not in context.state
    draft = CompanionCardDraftSet.model_validate(context.state["companion_card_draft"])
    assert draft.cards[0].requires_backend_materialization is True


@pytest.mark.anyio
async def test_submit_cards_supports_adk_state_without_pop(submit_tool):
    state = NoPopState(
        {
            "companion_proposal": {"stale": True},
            "companion_proposal_error": {"stale": True},
        }
    )
    context = MockToolContext(state=state)

    result = await submit_tool({"cards": [valid_draft_card()]}, context)

    assert result["status"] == "success"
    assert "companion_card_draft" in state
    assert "companion_proposal" not in state
    assert "companion_proposal_error" not in state


def test_valid_draft_materializes_into_backend_owned_card_set():
    draft = CompanionCardDraftSet.model_validate({"cards": [valid_draft_card()]})

    proposal = materialize_companion_card_draft(
        draft,
        source_event_id="evt-source-1",
        generated_at=NOW,
        guardian_decision_id="guardian-review-1",
    )

    assert proposal.card_set.source_event_id == "evt-source-1"
    assert proposal.card_set.generated_at == NOW
    assert proposal.card_set.expires_at == NOW + timedelta(minutes=15)
    assert proposal.proposal_hash == proposal_hash_for_card_set(proposal.card_set)
    card = proposal.card_set.cards[0]
    assert card.card_id.startswith("card_")
    assert proposal.card_set.card_set_id.startswith("cards_")
    assert card.requires_guardian_approval is True
    assert card.requires_parent_confirmation is True
    assert card.guardian_decision_id == "guardian-review-1"
    assert card.zh_text == "请向药剂师确认我的过敏史"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "forged_field,forged_value",
    [
        ("card_id", "card-forged"),
        ("requires_guardian_approval", False),
        ("requires_parent_confirmation", False),
        ("guardian_decision_id", "guardian-forged"),
    ],
)
async def test_server_owned_card_fields_are_rejected(submit_tool, forged_field, forged_value):
    card = valid_draft_card()
    card[forged_field] = forged_value
    context = MockToolContext()

    result = await submit_tool({"cards": [card]}, context)

    assert result["status"] == "error"
    assert result["code"] == "COMPANION_CARD_DRAFT_INVALID"
    assert "companion_proposal_error" in context.state
    assert "companion_card_draft" not in context.state
    assert "companion_proposal" not in context.state


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "generated_at": "2023-01-01T00:00:00Z",
            "expires_at": "2023-01-01T00:00:00Z",
            "cards": [valid_draft_card()],
        },
        {"proposal_hash": "hash-forged", "cards": [valid_draft_card()]},
        {"card_set": {"cards": [valid_draft_card()]}},
    ],
)
async def test_server_owned_proposal_fields_are_rejected_not_rewritten(submit_tool, payload):
    context = MockToolContext()

    result = await submit_tool(payload, context)

    assert result["status"] == "error"
    assert result["retryable"] is True
    assert "companion_proposal_error" in context.state
    assert "companion_card_draft" not in context.state
    assert "companion_proposal" not in context.state


@pytest.mark.anyio
async def test_second_invalid_draft_is_not_retryable(submit_tool):
    context = MockToolContext()
    payload = {"cards": [{**valid_draft_card(), "proposal_hash": "hash-forged"}]}

    first = await submit_tool(payload, context)
    second = await submit_tool(payload, context)

    assert first["retryable"] is True
    assert second["retryable"] is False
    assert context.state["companion_proposal_error"]["attempts"] == 2


@pytest.mark.anyio
async def test_missing_semantic_fields_fail_closed(submit_tool):
    context = MockToolContext()

    result = await submit_tool(
        {"cards": [{"zh_text": "请药剂师重复一遍", "en_text": "Please repeat that."}]},
        context,
    )

    assert result["status"] == "error"
    assert "companion_card_draft" not in context.state
    assert "companion_proposal" not in context.state


@pytest.mark.anyio
async def test_empty_cards_fail_closed(submit_tool):
    context = MockToolContext()

    result = await submit_tool({"cards": []}, context)

    assert result["status"] == "error"
    assert "companion_card_draft" not in context.state
    assert "companion_proposal" not in context.state


@pytest.mark.anyio
async def test_live_adk_retries_transient_model_capacity_errors(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("app.agents.companion_agent.asyncio.sleep", fake_sleep)
    runner = FakeRunner(
        [
            RuntimeError("503 UNAVAILABLE high demand"),
            RuntimeError("429 RESOURCE_EXHAUSTED"),
        ]
    )

    await _run_adk_runner_with_retries(
        runner, user_id="u1", session_id="s1", new_message=None
    )

    assert runner.calls == 3
    assert delays == [2.0, 4.0]


@pytest.mark.anyio
async def test_live_adk_does_not_retry_non_transient_errors(monkeypatch):
    async def fake_sleep(_delay: float) -> None:
        raise AssertionError("non-transient errors must not sleep or retry")

    monkeypatch.setattr("app.agents.companion_agent.asyncio.sleep", fake_sleep)
    runner = FakeRunner([RuntimeError("draft schema validation failed")])

    with pytest.raises(RuntimeError, match="draft schema validation failed"):
        await _run_adk_runner_with_retries(
            runner, user_id="u1", session_id="s1", new_message=None
        )

    assert runner.calls == 1
