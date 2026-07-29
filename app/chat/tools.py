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


def scope_grants(allowed_scopes: list[str], required_scope: str) -> bool:
    return any(
        granted == "*" or granted == required_scope or required_scope.startswith(f"{granted}.")
        for granted in allowed_scopes
    )


def tools_for_scopes(allowed_scopes: list[str]) -> list[dict[str, Any]]:
    return [tool for tool in ALL_TOOLS if scope_grants(allowed_scopes, TOOL_SCOPES[tool["name"]])]


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
