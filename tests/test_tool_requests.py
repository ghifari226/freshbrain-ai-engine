from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.core.security import encode_token
from app.main import app
from app.tool_requests.repository import ToolRequestRepository
from app.tool_requests.schemas import ToolRequestCreate, ToolRequestUpdate
from app.tool_requests.service import ToolRequestService


async def _create(service: ToolRequestService, user_id) -> str:
    out = await service.create(
        user_id,
        ToolRequestCreate(title="New WMS lookup", description="...", domain="wms"),
    )
    return out.id


async def test_create_starts_as_draft(db_session) -> None:
    service = ToolRequestService(db_session)
    out = await service.create(uuid4(), ToolRequestCreate(title="X", description="Y", domain="wms"))
    assert out.status == "draft"


async def test_toggle_between_draft_and_posted(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())

    posted = await service.set_status(UUID(request_id), "posted")
    assert posted.status == "posted"

    draft = await service.set_status(UUID(request_id), "draft")
    assert draft.status == "draft"


async def test_set_status_rejects_non_toggle_target(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())

    with pytest.raises(HTTPException) as error:
        await service.set_status(UUID(request_id), "staging")
    assert error.value.status_code == 400


async def test_promote_requires_posted(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())

    with pytest.raises(HTTPException) as error:
        await service.promote(UUID(request_id))
    assert error.value.status_code == 409

    await service.set_status(UUID(request_id), "posted")
    promoted = await service.promote(UUID(request_id))
    assert promoted.status == "staging"

    # Once staging, the draft<->posted toggle no longer applies.
    with pytest.raises(HTTPException):
        await service.set_status(UUID(request_id), "posted")


async def test_fulfill_requires_staging(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())

    with pytest.raises(HTTPException) as error:
        await service.fulfill(UUID(request_id))
    assert error.value.status_code == 409

    await service.set_status(UUID(request_id), "posted")
    await service.promote(UUID(request_id))
    fulfilled = await service.fulfill(UUID(request_id))
    assert fulfilled.status == "live"


async def test_edit_rejected_once_live(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())
    await service.set_status(UUID(request_id), "posted")
    await service.promote(UUID(request_id))
    await service.fulfill(UUID(request_id))

    with pytest.raises(HTTPException) as error:
        await service.update_content(
            UUID(request_id),
            ToolRequestUpdate(title="new", description="new", domain="wms"),
        )
    assert error.value.status_code == 409


async def test_edit_allowed_before_live(db_session) -> None:
    service = ToolRequestService(db_session)
    request_id = await _create(service, uuid4())

    updated = await service.update_content(
        UUID(request_id),
        ToolRequestUpdate(title="Renamed", description="new desc", domain="odoo"),
    )
    assert updated.title == "Renamed"
    assert updated.domain == "odoo"


async def test_list_all_includes_requests_regardless_of_owner(db_session) -> None:
    service = ToolRequestService(db_session)
    repo = ToolRequestRepository(db_session)
    marker_a = str(uuid4())
    marker_b = str(uuid4())
    await repo.create(uuid4(), marker_a, "d", "wms")
    await repo.create(uuid4(), marker_b, "d", "odoo")
    await db_session.commit()

    titles = {r.title for r in await service.list_all()}
    assert marker_a in titles
    assert marker_b in titles


@pytest.mark.parametrize(
    ("method", "path", "scope"),
    [
        ("POST", "/tool-requests", "tools.request_add"),
        ("GET", "/tool-requests", "tools.request_view"),
        ("PATCH", f"/tool-requests/{uuid4()}", "tools.request_edit"),
        ("POST", f"/tool-requests/{uuid4()}/status", "tools.request_status"),
        ("POST", f"/tool-requests/{uuid4()}/promote", "tools.request_promote"),
        ("POST", f"/tool-requests/{uuid4()}/fulfill", "tools.request_fulfill"),
    ],
)
async def test_endpoints_require_their_scope(method: str, path: str, scope: str) -> None:
    token = encode_token("user-id", "Superuser", [])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "x", "description": "y", "domain": "wms", "status": "posted"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": f"Missing scope: {scope}"}
