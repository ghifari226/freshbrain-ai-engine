from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.conversations.models import Conversation, Message
from app.db.types import ClaudeContent


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID) -> Conversation:
        conversation = Conversation(user_id=user_id)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_owned(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .options(selectinload(Conversation.messages))
        )

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        # Unscoped by user_id — used by the background worker, which isn't
        # acting on behalf of a specific request-bound user (unlike get_owned).
        return await self.session.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )

    async def list_for_user(self, user_id: UUID) -> list[Conversation]:
        result = await self.session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.last_active_at.desc())
        )
        return list(result)

    async def rename(self, conversation_id: UUID, user_id: UUID, title: str) -> bool:
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .values(title=title)
            .returning(Conversation.id)
        )
        return result.scalar_one_or_none() is not None

    async def delete(self, conversation_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            delete(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .returning(Conversation.id)
        )
        return result.scalar_one_or_none() is not None

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: ClaudeContent,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        await self.session.flush()
        return message
