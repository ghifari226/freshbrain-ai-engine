from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.tools import scope_grants
from app.conversations.service import parse_uuid
from app.core.database import get_session
from app.core.security import TokenClaims, get_current_claims
from app.tool_requests.schemas import (
    ToolRequestCreate,
    ToolRequestListResponse,
    ToolRequestOut,
    ToolRequestStatusUpdate,
    ToolRequestUpdate,
)
from app.tool_requests.service import ToolRequestService

router = APIRouter(prefix="/tool-requests", tags=["tool-requests"])
Session = Annotated[AsyncSession, Depends(get_session)]
Claims = Annotated[TokenClaims, Depends(get_current_claims)]


def _require_scope(claims: TokenClaims, required_scope: str) -> None:
    if not scope_grants(claims.allowed_scopes, required_scope):
        raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")


@router.post("", response_model=ToolRequestOut)
async def create_tool_request(
    body: ToolRequestCreate,
    session: Session,
    claims: Claims,
) -> ToolRequestOut:
    _require_scope(claims, "tools.request_add")
    return await ToolRequestService(session).create(parse_uuid(claims.user_id), body)


@router.get("", response_model=ToolRequestListResponse)
async def list_tool_requests(
    session: Session,
    claims: Claims,
) -> ToolRequestListResponse:
    _require_scope(claims, "tools.request_view")
    return ToolRequestListResponse(requests=await ToolRequestService(session).list_all())


@router.patch("/{request_id}", response_model=ToolRequestOut)
async def update_tool_request(
    request_id: str,
    body: ToolRequestUpdate,
    session: Session,
    claims: Claims,
) -> ToolRequestOut:
    _require_scope(claims, "tools.request_edit")
    return await ToolRequestService(session).update_content(parse_uuid(request_id), body)


@router.post("/{request_id}/status", response_model=ToolRequestOut)
async def update_tool_request_status(
    request_id: str,
    body: ToolRequestStatusUpdate,
    session: Session,
    claims: Claims,
) -> ToolRequestOut:
    # The only status-changing endpoint — a plain setter (draft/posted/live),
    # no promote/fulfill ceremony. See ToolRequestService.set_status().
    _require_scope(claims, "tools.request_status")
    return await ToolRequestService(session).set_status(parse_uuid(request_id), body.status)
