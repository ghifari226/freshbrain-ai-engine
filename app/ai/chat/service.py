import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, NamedTuple
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.content import extract_final_text
from app.ai.chat.context import build_chat_context
from app.ai.chat.orchestration import ChatStatus, run_chat_loop
from app.ai.chat.schemas import ChatRequest, ChatResponse
from app.ai.chat.sse import sse_event
from app.conversations.models import Conversation, Message
from app.conversations.repository import ConversationRepository
from app.conversations.service import parse_uuid
from app.core.config import get_settings
from app.jobs.repository import JobRepository
from app.tool_call_logs.repository import ToolCallRepository

logger = structlog.get_logger(__name__)


class _ChatContext(NamedTuple):
    conversation: Conversation
    conversation_id: UUID
    history: list[dict[str, Any]]
    is_new: bool


# Chat service menghubungkan percakapan, model AI, tool call, dan penyimpanan hasil.
class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = ConversationRepository(session)
        self.tool_call_logs = ToolCallRepository(session)

    def _tool_call_logger(self, conversation_id: UUID, user_id: UUID) -> Any:
        async def record(tool_name: str, tool_input: dict, status: str, duration_ms: float) -> None:
            await self.tool_call_logs.record(
                conversation_id=conversation_id,
                message_id=None,
                tool_name=tool_name,
                tool_input=tool_input,
                status=status,
                duration_ms=duration_ms,
                user_id=user_id,
            )

        return record

    async def chat(
        self, request: ChatRequest, user_id: str, allowed_scopes: list[str]
    ) -> ChatResponse:
        context = await self._prepare(request, user_id)
        new_messages, renamed_title = await run_chat_loop(
            context.history + [{"role": "user", "content": request.message}],
            allowed_scopes=allowed_scopes,
            allow_rename=not context.is_new,
            on_tool_call=self._tool_call_logger(
                context.conversation_id, parse_uuid(user_id, "Invalid user_id")
            ),
        )
        return await self._finalize(
            context.conversation, context.conversation_id, new_messages, renamed_title
        )

    async def chat_stream(
        self, request: ChatRequest, user_id: str, allowed_scopes: list[str]
    ) -> AsyncIterator[str]:
        context = await self._prepare(request, user_id)
        return self._stream_events(context, request.message, user_id, allowed_scopes)

    async def _prepare(self, request: ChatRequest, user_id: str) -> _ChatContext:
        parsed_user_id = parse_uuid(user_id, "Invalid user_id")
        is_new = request.conversation_id is None

        if request.conversation_id:
            conversation_id = parse_uuid(
                request.conversation_id,
                "Invalid conversation_id",
            )
            conversation = await self.conversations.get_owned(conversation_id, parsed_user_id)
            if conversation is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            history = build_chat_context(
                conversation.messages,
                conversation.rolling_summary,
                get_settings().context_window_messages,
            )
        else:
            conversation = await self.conversations.create(parsed_user_id)
            conversation_id = conversation.id
            history = []

        await self.conversations.add_message(
            conversation_id,
            "user",
            request.message,
        )
        return _ChatContext(conversation, conversation_id, history, is_new)

    async def _stream_events(
        self, context: _ChatContext, message: str, user_id: str, allowed_scopes: list[str]
    ) -> AsyncIterator[str]:
        # Async generator mengirim progres sedikit demi sedikit melalui SSE.
        start = time.perf_counter()

        queue: asyncio.Queue[ChatStatus | None] = asyncio.Queue()

        async def emit(status: ChatStatus) -> None:
            await queue.put(status)

        async def run() -> tuple[list[dict[str, Any]], str | None]:
            try:
                return await run_chat_loop(
                    context.history + [{"role": "user", "content": message}],
                    allowed_scopes=allowed_scopes,
                    allow_rename=not context.is_new,
                    on_status=emit,
                    on_tool_call=self._tool_call_logger(
                        context.conversation_id, parse_uuid(user_id, "Invalid user_id")
                    ),
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        while (status := await queue.get()) is not None:
            yield sse_event("status", {"status": status.value})

        new_messages, renamed_title = await task
        response = await self._finalize(
            context.conversation, context.conversation_id, new_messages, renamed_title
        )
        yield sse_event("done", response.model_dump())

        logger.info(
            "chat_stream_completed",
            conversation_id=str(context.conversation_id),
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    async def _finalize(
        self,
        conversation: Conversation,
        conversation_id: UUID,
        new_messages: list[dict[str, Any]],
        renamed_title: str | None,
    ) -> ChatResponse:
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

        settings = get_settings()
        total = await self.session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        if (
            total > settings.summary_trigger_messages
            and (total - conversation.summarized_through_count) >= settings.context_window_messages
        ):
            await JobRepository(self.session).enqueue(
                "summarize_conversation", {"conversation_id": str(conversation_id)}
            )
            await self.session.commit()

        return ChatResponse(
            answer=extract_final_text(new_messages[-1]["content"]),
            conversation_id=str(conversation_id),
            message_id=str(final_message_id),
            title=renamed_title,
        )
