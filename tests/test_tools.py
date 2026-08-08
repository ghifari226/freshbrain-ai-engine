import httpx
import pytest

from app.chat.tools import catalog_for_scopes, execute_tool, scope_grants, tools_for_scopes
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
