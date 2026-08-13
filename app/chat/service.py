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

from app.chat.content import extract_final_text
from app.chat.context import build_chat_context
from app.chat.orchestration import ChatStatus, run_chat_loop
from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.sse import sse_event
from app.conversations.models import Conversation, Message
from app.conversations.repository import ConversationRepository
from app.conversations.service import parse_uuid
from app.core.config import get_settings
from app.observability.repository import ToolCallLogRepository
from app.worker.repository import JobRepository

logger = structlog.get_logger(__name__)


class _ChatContext(NamedTuple):
    conversation: Conversation
    conversation_id: UUID
    history: list[dict[str, Any]]
    is_new: bool


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversations = ConversationRepository(session)
        self.tool_call_logs = ToolCallLogRepository(session)

    def _tool_call_logger(self, conversation_id: UUID, user_id: UUID) -> Any:
        # message_id is left unset here — the message containing this tool
        # call hasn't been persisted yet at this point (that only happens in
        # _finalize, once run_chat_loop returns), so there's no id to
        # correlate against.
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
        # user_id/allowed_scopes come from the verified JWT (see
        # chat/router.py), not the request body — see ChatRequest's comment.
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
        # Prepared eagerly (not inside the generator below) so a bad
        # conversation_id raises HTTPException before StreamingResponse
        # starts sending a 200 — once streaming begins the status code is
        # already committed, so any validation that should produce a real
        # 4xx has to happen here, before this coroutine returns.
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
        # RequestLoggingMiddleware's duration_ms is wrong for this endpoint:
        # Starlette's BaseHTTPMiddleware.call_next() returns as soon as
        # response headers are sent, which for a StreamingResponse happens
        # before this generator's body (the actual multi-second chat turn)
        # has run — so its "request_completed" log only measures
        # time-to-first-byte here. This logs the real end-to-end duration
        # instead.
        start = time.perf_counter()

        # A queue bridges run_chat_loop's synchronous-looking on_status
        # callback (invoked from inside the background task below) to this
        # generator's yields — the callback can't yield directly since it
        # isn't lexically inside this generator function.
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
        # Fresh COUNT(*), not len(conversation.messages) — add_message() above
        # flushes bare Message rows without appending to the already-loaded
        # relationship collection, so that collection is stale here.
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
