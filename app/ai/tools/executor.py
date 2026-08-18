from typing import Any

from app.ai.tools.catalog import TOOL_SCOPES, scope_grants
from app.integrations.wms import WmsClient


async def execute_tool(
    name: str,
    tool_input: dict[str, Any],
    allowed_scopes: list[str],
) -> dict[str, Any]:
    # Executor memvalidasi nama dan izin sebelum menyentuh sistem eksternal.
    required_scope = TOOL_SCOPES.get(name)
    if required_scope is None:
        return {"error": f"Unknown tool: {name}"}
    if not scope_grants(allowed_scopes, required_scope):
        return {"error": f"Not authorized to use tool: {name}"}
    if name == "get_inbound_count":
        return await WmsClient().get_inbound_count(**tool_input)
    return {"error": f"Unknown tool: {name}"}
