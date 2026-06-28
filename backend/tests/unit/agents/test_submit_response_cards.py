from datetime import UTC, datetime

import pytest

from app.agents.companion_agent import make_submit_response_cards


class DummyToolContext:
    def __init__(self) -> None:
        self.state: dict[str, object] = {}


@pytest.mark.asyncio
async def test_submit_response_cards_forces_guardian_approval() -> None:
    submit = make_submit_response_cards(lambda: datetime(2026, 6, 28, tzinfo=UTC))
    context = DummyToolContext()

    await submit(
        {
            "proposal_hash": "valid-hash",
            "card_set": {
                "source_event_id": "evt-1",
                "cards": [
                    {
                        "zh_text": "请问我是否对青霉素过敏？",
                        "en_text": "Could you confirm whether I am allergic to penicillin?",
                        "requires_guardian_approval": False,
                    }
                ],
            },
        },
        context,
    )

    proposal = context.state["companion_proposal"]
    assert isinstance(proposal, dict)
    assert proposal["card_set"]["cards"][0]["requires_guardian_approval"] is True
