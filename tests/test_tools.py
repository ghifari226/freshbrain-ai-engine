import httpx
import pytest

from app.ai.tools.catalog import (
    ALL_TOOLS,
    TOOL_CATALOG_METADATA,
    TOOL_SCOPES,
    _validate_catalog_consistency,
    catalog_for_scopes,
    scope_grants,
    tools_for_scopes,
)
from app.ai.tools.executor import execute_tool
from app.core.security import encode_token
from app.main import app


@pytest.mark.parametrize(
    ("grants", "required", "expected"),
    [
        ([], "wms.inbound", False),
        (["*"], "wms.inbound", True),
        (["wms"], "wms.inbound", True),
        (["wms.inbound"], "wms.inbound", True),
        (["wms.outbound"], "wms.inbound", False),
        (["wms.inbound"], "wms", False),
    ],
)
def test_scope_matching(grants: list[str], required: str, expected: bool) -> None:
    assert scope_grants(grants, required) is expected


def test_only_authorized_tools_are_visible() -> None:
    assert tools_for_scopes([]) == []
    assert [tool["name"] for tool in tools_for_scopes(["wms"])] == ["get_inbound_count"]


async def test_execute_tool_checks_scope_again() -> None:
    result = await execute_tool(
        "get_inbound_count",
        {"date": "2026-07-29", "status": "pending"},
        [],
    )
    assert result == {"error": "Not authorized to use tool: get_inbound_count"}


def test_catalog_for_scopes_is_scope_filtered() -> None:
    assert catalog_for_scopes([]) == []
    entries = catalog_for_scopes(["wms"])
    assert entries == [
        {
            "name": "get_inbound_count",
            "description": entries[0]["description"],
            "domain": "wms",
            "status": "production",
            "version": "1.0.0",
        }
    ]


async def test_tools_endpoint_groups_by_domain() -> None:
    token = encode_token("user-id", "Superuser", ["wms"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/tools", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert [d["domain"] for d in body["domains"]] == ["wms"]
    assert [t["name"] for t in body["domains"][0]["tools"]] == ["get_inbound_count"]


async def test_tools_endpoint_filters_by_domain_query_param() -> None:
    token = encode_token("user-id", "Superuser", ["wms"])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/tools",
            params={"domain": "odoo"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"domains": []}


async def test_tools_endpoint_requires_token() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/tools")

    assert response.status_code == 401


def test_real_catalog_is_internally_consistent() -> None:
    # Proves the module-load-time call in catalog.py didn't just get lucky —
    # re-running it here against the real catalog must also pass clean.
    _validate_catalog_consistency(ALL_TOOLS, TOOL_SCOPES, TOOL_CATALOG_METADATA)


def test_validate_catalog_consistency_catches_missing_scope() -> None:
    with pytest.raises(RuntimeError, match="missing TOOL_SCOPES for \\['new_tool'\\]"):
        _validate_catalog_consistency(
            [{"name": "new_tool"}],
            {},
            {"new_tool": {"domain": "wms", "status": "production", "version": "1.0.0"}},
        )


def test_validate_catalog_consistency_catches_missing_metadata() -> None:
    with pytest.raises(RuntimeError, match="missing TOOL_CATALOG_METADATA for \\['new_tool'\\]"):
        _validate_catalog_consistency(
            [{"name": "new_tool"}],
            {"new_tool": "wms.new_tool"},
            {},
        )
