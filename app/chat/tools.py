import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.integrations.wms import WmsClient

ToolFunction = Callable[..., Awaitable[dict[str, Any]]]
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "tools" / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / f"{name}.json").open(encoding="utf-8") as file:
        return json.load(file)


INBOUND_TOOL = load_schema("inbound")
RENAME_TOOL = load_schema("rename_conversation")
ALL_TOOLS = [INBOUND_TOOL]
TOOL_SCOPES = {"get_inbound_count": "wms.inbound"}

# Catalog-only metadata (domain grouping, deploy status, version) — kept
# separate from the tool schemas above, which are sent to Claude verbatim
# as `tools=` and must only contain fields the Anthropic API accepts
# (name/description/input_schema). The codebase is the source of truth for
# what's "live" — there is no DB table backing this; a tool goes live by
# being implemented and registered here, not by a database write.
TOOL_CATALOG_METADATA: dict[str, dict[str, str]] = {
    "get_inbound_count": {"domain": "wms", "status": "production", "version": "1.0.0"},
}


def _validate_catalog_consistency(
    tools: list[dict[str, Any]],
    scopes: dict[str, str],
    metadata: dict[str, dict[str, str]],
) -> None:
    # Both TOOL_SCOPES and TOOL_CATALOG_METADATA are plain dicts indexed by
    # tool name, not `.get()`-guarded — a tool registered in `tools`
    # without matching entries here would otherwise only surface as a
    # KeyError the first time a request happens to hit that code path.
    # Failing at import time instead means a drift is caught at startup.
    names = {tool["name"] for tool in tools}
    missing_scopes = names - scopes.keys()
    missing_metadata = names - metadata.keys()
    if missing_scopes or missing_metadata:
        raise RuntimeError(
            "Tool registry drift: "
            f"missing TOOL_SCOPES for {sorted(missing_scopes) or 'none'}, "
            f"missing TOOL_CATALOG_METADATA for {sorted(missing_metadata) or 'none'}"
        )


_validate_catalog_consistency(ALL_TOOLS, TOOL_SCOPES, TOOL_CATALOG_METADATA)


def scope_grants(allowed_scopes: list[str], required_scope: str) -> bool:
    return any(
        granted == "*" or granted == required_scope or required_scope.startswith(f"{granted}.")
        for granted in allowed_scopes
    )


def tools_for_scopes(allowed_scopes: list[str]) -> list[dict[str, Any]]:
    return [tool for tool in ALL_TOOLS if scope_grants(allowed_scopes, TOOL_SCOPES[tool["name"]])]


def catalog_for_scopes(allowed_scopes: list[str]) -> list[dict[str, Any]]:
    entries = []
    for tool in ALL_TOOLS:
        name = tool["name"]
        if not scope_grants(allowed_scopes, TOOL_SCOPES[name]):
            continue
        metadata = TOOL_CATALOG_METADATA[name]
        entries.append(
            {
                "name": name,
                "description": tool["description"],
                "domain": metadata["domain"],
                "status": metadata["status"],
                "version": metadata["version"],
            }
        )
    return entries


async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    allowed_scopes: list[str],
) -> dict[str, Any]:
    required_scope = TOOL_SCOPES.get(name)
    if required_scope is None:
        return {"error": f"Unknown tool: {name}"}
    if not scope_grants(allowed_scopes, required_scope):
        return {"error": f"Not authorized to use tool: {name}"}
    if name == "get_inbound_count":
        return await WmsClient().get_inbound_count(**tool_input)
    return {"error": f"Unknown tool: {name}"}
