import json
from importlib.resources import files
from typing import Any


def load_schema(name: str) -> dict[str, Any]:
    resource = files("app.resources.tools").joinpath(f"{name}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


# Catalog adalah sumber kebenaran tool yang boleh diperlihatkan kepada model.
INBOUND_TOOL = load_schema("inbound")
RENAME_TOOL = load_schema("rename_conversation")
ALL_TOOLS = [INBOUND_TOOL]
TOOL_SCOPES = {"get_inbound_count": "wms.inbound"}
TOOL_CATALOG_METADATA: dict[str, dict[str, str]] = {
    "get_inbound_count": {"domain": "wms", "status": "production", "version": "1.0.0"},
}


def _validate_catalog_consistency(
    tools: list[dict[str, Any]],
    scopes: dict[str, str],
    metadata: dict[str, dict[str, str]],
) -> None:
    names = {tool["name"] for tool in tools}
    missing_scopes = names - scopes.keys()
    missing_metadata = names - metadata.keys()
    if missing_scopes or missing_metadata:
        raise RuntimeError(
            "Tool catalog drift: "
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
    # Least privilege berarti model hanya melihat tool yang diizinkan untuk pengguna ini.
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
