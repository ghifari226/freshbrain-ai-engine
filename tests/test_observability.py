from uuid import UUID, uuid4

from sqlalchemy import select

from app.chat.schemas import ChatRequest
from app.chat.service import ChatService
from app.observability.models import ToolCallLog


async def test_tool_call_is_logged_alongside_structlog_event(db_session) -> None:
    user_id = uuid4()
    service = ChatService(db_session)
    request = ChatRequest(message="ada berapa pengiriman inbound hari ini")

    response = await service.chat(request, str(user_id), ["wms"])
    conversation_id = UUID(response.conversation_id)

    rows = list(
        await db_session.scalars(
            select(ToolCallLog).where(ToolCallLog.conversation_id == conversation_id)
        )
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.tool_name == "get_inbound_count"
    assert row.status == "SUCCESS"
    assert row.duration_ms is not None
    assert row.duration_ms >= 0
    assert str(row.user_id) == str(user_id)
    assert str(row.conversation_id) == response.conversation_id
    assert row.message_id is None
