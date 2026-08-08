from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.chat.schemas import ChatRequest
from app.chat.service import ChatService


async def test_existing_conversation_lookup_is_ownership_scoped() -> None:
    session = AsyncMock()
    service = ChatService(session)
    service.conversations = AsyncMock()
    service.conversations.get_owned.return_value = None
    conversation_id = uuid4()
    user_id = uuid4()

    with pytest.raises(HTTPException) as error:
        await service.chat(
            ChatRequest(message="hello", conversation_id=str(conversation_id)),
            str(user_id),
            [],
        )

    service.conversations.get_owned.assert_awaited_once_with(conversation_id, user_id)
    assert error.value.status_code == 404


async def test_chat_persists_new_turn_and_final_answer() -> None:
    session = AsyncMock()
    session.scalar.return_value = 0
    service = ChatService(session)
    service.conversations = AsyncMock()
    conversation_id = uuid4()
    message_id = uuid4()
    conversation = SimpleNamespace(
        id=conversation_id,
        title=None,
        last_active_at=None,
        messages=[],
        rolling_summary=None,
        summarized_through_count=0,
    )
    service.conversations.create.return_value = conversation
    service.conversations.add_message.side_effect = [
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(id=message_id),
    ]

    with patch(
        "app.chat.service.run_chat_loop",
        new=AsyncMock(
            return_value=(
                [{"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}],
                None,
            )
        ),
    ):
        response = await service.chat(ChatRequest(message="hello"), str(uuid4()), [])

    assert response.answer == "Hi"
    assert response.conversation_id == str(conversation_id)
    assert response.message_id == str(message_id)
    session.commit.assert_awaited_once()
