from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.core.constants import PermissionTier, ToolName


def test_companion_cannot_call_write_or_notify() -> None:
    assert McpToolAdapter.companion_tool_names() == (
        ToolName.MEMORY_SEARCH.value,
        ToolName.CHECK_DRUG_INTERACTION.value,
    )
    assert ToolName.MEMORY_WRITE.value not in McpToolAdapter.companion_tool_names()
    assert ToolName.NOTIFY_FAMILY.value not in McpToolAdapter.companion_tool_names()
    assert McpToolAdapter.permission_tier(ToolName.NOTIFY_FAMILY) == PermissionTier.EXTERNAL_ACTION
