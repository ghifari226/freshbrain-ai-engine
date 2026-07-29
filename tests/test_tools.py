import pytest

from app.chat.tools import execute_tool, scope_grants, tools_for_scopes


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
