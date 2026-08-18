from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.tool_call_logs.models import ToolCall


# Tool call menyimpan jejak terstruktur untuk debugging dan evaluasi perilaku AI.
class ToolCallRepository:
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
    ) -> ToolCall:
        tool_call = ToolCall(
            conversation_id=conversation_id,
            message_id=message_id,
            tool_name=tool_name,
            tool_input=tool_input,
            status=status,
            duration_ms=duration_ms,
            user_id=user_id,
        )
        self.session.add(tool_call)
        await self.session.flush()
        return tool_call
