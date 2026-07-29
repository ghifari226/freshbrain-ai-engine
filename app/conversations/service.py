from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.content import extract_final_text
from app.conversations.models import Conversation, Message
from app.conversations.repository import ConversationRepository
from app.conversations.schemas import (
    ConversationMessageOut,
    ConversationOut,
    ConversationsListResponse,
)


def parse_uuid(value: str, detail: str = "Invalid id") -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=detail) from exc


def message_to_output(message: Message) -> ConversationMessageOut | None:
    content = message.content
    if message.role == "user":
        if not isinstance(content, str):
            return None
        text = content
    else:
        text = extract_final_text(content) if isinstance(content, list) else str(content)
        if not text:
            return None
    return ConversationMessageOut(
        id=str(message.id),
        role=message.role,
        text=text,
        createdAt=message.created_at.isoformat(),
    )


def conversation_to_output(conversation: Conversation) -> ConversationOut:
    messages = [
        output
        for output in (message_to_output(message) for message in conversation.messages)
        if output is not None
    ]
    return ConversationOut(
        id=str(conversation.id),
        title=conversation.title or "",
        timestamp=conversation.last_active_at.isoformat(),
        messages=messages,
    )


class ConversationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ConversationRepository(session)

    async def list(self, user_id: str) -> ConversationsListResponse:
        conversations = await self.repository.list_for_user(parse_uuid(user_id, "Invalid user_id"))
        return ConversationsListResponse(
            conversations=[conversation_to_output(item) for item in conversations]
        )

    async def rename(self, conversation_id: str, user_id: str, title: str) -> None:
        renamed = await self.repository.rename(
            parse_uuid(conversation_id),
            parse_uuid(user_id),
            title,
        )
        if not renamed:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await self.session.commit()

    async def delete(self, conversation_id: str, user_id: str) -> None:
        deleted = await self.repository.delete(
            parse_uuid(conversation_id),
            parse_uuid(user_id),
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await self.session.commit()
