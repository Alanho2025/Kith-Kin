"""Proposal tool that validates Companion card drafts without side effects."""

from app.schemas.agent_outputs import CompanionCardDraftSet


def submit_response_cards(payload: dict[str, object]) -> CompanionCardDraftSet:
    """Parse one semantic card draft set; rendering and actions happen elsewhere."""
    return CompanionCardDraftSet.model_validate(payload)
