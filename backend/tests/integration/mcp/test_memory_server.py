from app.core.constants import PermissionTier, ToolName
from app.mcp_servers.memory_server import tool_manifest


def test_four_tool_names_and_schemas() -> None:
    manifest = tool_manifest()

    assert [item["name"] for item in manifest] == [
        ToolName.MEMORY_SEARCH.value,
        ToolName.MEMORY_WRITE.value,
        ToolName.CHECK_DRUG_INTERACTION.value,
        ToolName.NOTIFY_FAMILY.value,
    ]
    assert manifest[0]["permission_tier"] == PermissionTier.READ_ONLY.value
    assert manifest[1]["input_schema"]["additionalProperties"] is False
