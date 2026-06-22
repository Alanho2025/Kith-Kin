"""Proposal tool that validates Companion card submissions without side effects."""

from app.schemas.agent_outputs import CardSetProposal


def submit_response_cards(payload: dict[str, object]) -> CardSetProposal:
    """Parse one card-set proposal; rendering and actions happen elsewhere."""
    return CardSetProposal.model_validate(payload)
