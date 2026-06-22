from app.agents.companion_agent import CompanionAgent
from app.core.constants import ToolName


def test_companion_has_read_only_tools_only() -> None:
    names = CompanionAgent.tool_names()

    assert ToolName.MEMORY_SEARCH.value in names
    assert ToolName.CHECK_DRUG_INTERACTION.value in names
    assert "submit_response_cards" in names
    assert ToolName.MEMORY_WRITE.value not in names
    assert ToolName.NOTIFY_FAMILY.value not in names
