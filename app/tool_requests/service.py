from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.tool_requests.models import ToolRequest
from app.tool_requests.repository import ToolRequestRepository
from app.tool_requests.schemas import ToolRequestCreate, ToolRequestOut, ToolRequestUpdate

# No transition legality beyond "target is one of these" — set_status() is
# a plain setter, not a state machine. draft->live directly is legal; the
# only enforced rule is content freezing once live (see update_content()).
_VALID_STATUSES = {"draft", "posted", "live"}


def _to_out(request: ToolRequest) -> ToolRequestOut:
    return ToolRequestOut(
        id=str(request.id),
        user_id=str(request.user_id),
        title=request.title,
        description=request.description,
        domain=request.domain,
        status=request.status,
        created_at=request.created_at,
        updated_at=request.updated_at,
    )


class ToolRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ToolRequestRepository(session)

    async def create(self, user_id: UUID, body: ToolRequestCreate) -> ToolRequestOut:
        request = await self.repository.create(user_id, body.title, body.description, body.domain)
        await self.session.commit()
        return _to_out(request)

    async def list_all(self) -> list[ToolRequestOut]:
        requests = await self.repository.list_all()
        return [_to_out(request) for request in requests]

    async def update_content(self, request_id: UUID, body: ToolRequestUpdate) -> ToolRequestOut:
        request = await self._get_or_404(request_id)
        if request.status == "live":
            raise HTTPException(status_code=409, detail="Live requests are read-only")
        request.title = body.title
        request.description = body.description
        request.domain = body.domain
        await self._touch_and_commit(request)
        return _to_out(request)

    async def set_status(self, request_id: UUID, target_status: str) -> ToolRequestOut:
        if target_status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=400, detail="status must be one of 'draft', 'posted', 'live'"
            )
        request = await self._get_or_404(request_id)
        request.status = target_status
        await self._touch_and_commit(request)
        return _to_out(request)

    async def _touch_and_commit(self, request: ToolRequest) -> None:
        # Set explicitly rather than relying on the model's onupdate=func.now()
        # — a DB-computed onupdate value expires the attribute after flush
        # (same reason app/chat/service.py sets Conversation.last_active_at
        # explicitly), which would force an unsafe lazy-refresh the moment
        # _to_out() reads it back synchronously right after commit().
        request.updated_at = datetime.now(UTC)
        await self.session.commit()

    async def _get_or_404(self, request_id: UUID) -> ToolRequest:
        request = await self.repository.get(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Tool request not found")
        return request
