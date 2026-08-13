from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.models import ToolCallLog


class ToolCallLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        conversation_id: UUID | None,
        message_id: UUID | None,
        tool_name: str,
        tool_input: dict[str, Any] | None,
        status: str,
        duration_ms: float,
        user_id: UUID | None,
    ) -> ToolCallLog:
        log = ToolCallLog(
            conversation_id=conversation_id,
            message_id=message_id,
            tool_name=tool_name,
            tool_input=tool_input,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
        )
        self.session.add(log)
        await self.session.flush()
        return log
