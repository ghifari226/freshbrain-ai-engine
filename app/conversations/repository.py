from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.conversations.models import ClaudeContent, Conversation, Message

Cursor = tuple[datetime, UUID]


# Repository memusatkan query database agar service tidak bergantung pada detail SQL.
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
                Conversation.deleted_at.is_(None),
            )
            .options(selectinload(Conversation.messages))
        )

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.deleted_at.is_(None),
            )
            .options(selectinload(Conversation.messages))
        )

    async def list_for_user(self, user_id: UUID) -> list[Conversation]:
        result = await self.session.scalars(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
            .order_by(Conversation.last_active_at.desc())
        )
        return list(result)

    async def get_conversation_cursor(self, conversation_id: UUID, user_id: UUID) -> Cursor | None:
        row = (
            await self.session.execute(
                select(Conversation.last_active_at, Conversation.id).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                    Conversation.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        return (row.last_active_at, row.id) if row is not None else None

    async def list_for_user_page(
        self, user_id: UUID, limit: int, cursor: Cursor | None
    ) -> tuple[list[Conversation], UUID | None]:
        query = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.deleted_at.is_(None),
        )
        if cursor is not None:
            query = query.where(
                tuple_(Conversation.last_active_at, Conversation.id) < tuple_(*cursor)
            )
        query = query.order_by(Conversation.last_active_at.desc(), Conversation.id.desc()).limit(
            limit
        )
        items = list(await self.session.scalars(query))
        next_cursor = items[-1].id if len(items) == limit else None
        return items, next_cursor

    async def exists_owned(self, conversation_id: UUID, user_id: UUID) -> bool:
        result = await self.session.scalar(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        return result is not None

    async def get_message_cursor(self, message_id: UUID, conversation_id: UUID) -> Cursor | None:
        row = (
            await self.session.execute(
                select(Message.created_at, Message.id).where(
                    Message.id == message_id,
                    Message.conversation_id == conversation_id,
                )
            )
        ).one_or_none()
        return (row.created_at, row.id) if row is not None else None

    async def list_messages_page(
        self, conversation_id: UUID, limit: int, cursor: Cursor | None
    ) -> tuple[list[Message], UUID | None]:
        query = select(Message).where(Message.conversation_id == conversation_id)
        if cursor is not None:
            query = query.where(tuple_(Message.created_at, Message.id) < tuple_(*cursor))
        query = query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
        items = list(await self.session.scalars(query))
        next_cursor = items[-1].id if len(items) == limit else None
        return items, next_cursor

    async def rename(self, conversation_id: UUID, user_id: UUID, title: str) -> bool:
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
            .values(title=title)
            .returning(Conversation.id)
        )
        return result.scalar_one_or_none() is not None

    async def delete(self, conversation_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
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
