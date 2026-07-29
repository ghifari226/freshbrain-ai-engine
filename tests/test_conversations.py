from datetime import UTC, datetime
from uuid import uuid4

from app.conversations.models import Conversation, Message
from app.conversations.service import conversation_to_output


def test_conversation_projection_hides_synthetic_tool_messages() -> None:
    conversation = Conversation(
        id=uuid4(),
        user_id=uuid4(),
        title=None,
        last_active_at=datetime.now(UTC),
    )
    conversation.messages = [
        Message(
            id=uuid4(),
            role="user",
            content="hello",
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="assistant",
            content=[{"type": "tool_use", "name": "lookup"}],
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="user",
            content=[{"type": "tool_result", "content": "{}"}],
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            role="assistant",
            content=[{"type": "text", "text": "hi"}],
            created_at=datetime.now(UTC),
        ),
    ]

    output = conversation_to_output(conversation)

    assert output.title == ""
    assert [message.text for message in output.messages] == ["hello", "hi"]
