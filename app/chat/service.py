from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.content import extract_final_text
from app.chat.orchestration import run_chat_loop
from app.chat.schemas import ChatRequest, ChatResponse
from app.conversations.repository import ConversationRepository
from app.conversations.service import parse_uuid


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = ConversationRepository(session)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        if not request.user_id:
            raise HTTPException(status_code=401, detail="Token does not match user_id")
        user_id = parse_uuid(request.user_id, "Invalid user_id")
        is_new = request.conversation_id is None

        if request.conversation_id:
            conversation_id = parse_uuid(
                request.conversation_id,
                "Invalid conversation_id",
            )
            conversation = await self.conversations.get_owned(conversation_id, user_id)
            if conversation is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            history = [
                {"role": message.role, "content": message.content}
                for message in conversation.messages
            ]
        else:
            conversation = await self.conversations.create(user_id)
            conversation_id = conversation.id
            history = []

        await self.conversations.add_message(
            conversation_id,
            "user",
            request.message,
        )
        new_messages, renamed_title = await run_chat_loop(
            history + [{"role": "user", "content": request.message}],
            allowed_scopes=request.allowed_scopes or [],
            allow_rename=not is_new,
        )

        final_message_id: UUID | None = None
        for message in new_messages:
            stored = await self.conversations.add_message(
                conversation_id,
                message["role"],
                message["content"],
            )
            final_message_id = stored.id

        if final_message_id is None:
            raise RuntimeError("Chat loop returned no messages")

        conversation.last_active_at = datetime.now(UTC)
        if renamed_title:
            conversation.title = renamed_title
        await self.session.commit()

        return ChatResponse(
            answer=extract_final_text(new_messages[-1]["content"]),
            conversation_id=str(conversation_id),
            message_id=str(final_message_id),
            title=renamed_title,
        )
