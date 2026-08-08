from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tool_requests.models import ToolRequest


class ToolRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID, title: str, description: str, domain: str) -> ToolRequest:
        request = ToolRequest(
            user_id=user_id,
            title=title,
            description=description,
            domain=domain,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get(self, request_id: UUID) -> ToolRequest | None:
        return await self.session.scalar(select(ToolRequest).where(ToolRequest.id == request_id))

    async def list_all(self) -> list[ToolRequest]:
        result = await self.session.scalars(
            select(ToolRequest).order_by(ToolRequest.created_at.desc())
        )
        return list(result)
