"""Canonical stdio MCP tool manifest for Kith&Kin memory tools."""

import json
from typing import Any

from app.core.constants import PermissionTier, ToolName
from app.schemas.mcp import (
    DrugInteractionRequest,
    MemorySearchRequest,
    MemoryWriteRequest,
    NotifyFamilyRequest,
)


def tool_manifest() -> tuple[dict[str, Any], ...]:
    """Return the exact four tool declarations and permission tiers."""
    return (
        _tool(ToolName.MEMORY_SEARCH, PermissionTier.READ_ONLY, MemorySearchRequest),
        _tool(ToolName.MEMORY_WRITE, PermissionTier.WRITE_LOCAL, MemoryWriteRequest),
        _tool(
            ToolName.CHECK_DRUG_INTERACTION,
            PermissionTier.READ_ONLY,
            DrugInteractionRequest,
        ),
        _tool(ToolName.NOTIFY_FAMILY, PermissionTier.EXTERNAL_ACTION, NotifyFamilyRequest),
    )


def _tool(tool_name: ToolName, tier: PermissionTier, schema_model: type[Any]) -> dict[str, Any]:
    return {
        "name": tool_name.value,
        "permission_tier": tier.value,
        "input_schema": schema_model.model_json_schema(),
    }


def main() -> int:
    """Print a manifest for stdio smoke checks.

    The production ADK McpToolset can wrap the same declarations. Tool execution
    remains backend-owned because trusted context and confirmations are not stdio
    arguments.
    """
    print(json.dumps({"tools": tool_manifest()}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
