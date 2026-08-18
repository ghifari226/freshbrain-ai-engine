from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.anthropic.client import AnthropicClient
from app.conversations.repository import ConversationRepository
from app.core.config import get_settings


async def summarize_conversation(payload: dict[str, Any], session: AsyncSession) -> None:
    settings = get_settings()
    conversations = ConversationRepository(session)
    conversation = await conversations.get_by_id(UUID(payload["conversation_id"]))
    if conversation is None:
        return

    window = settings.context_window_messages
    already = conversation.summarized_through_count
    messages = conversation.messages
    to_fold = messages[already : max(len(messages) - window, already)]
    if not to_fold:
        return

    client = AnthropicClient()
    new_summary = await client.summarize(
        conversation.rolling_summary,
        [str(m.content) for m in to_fold],
    )
    conversation.rolling_summary = new_summary
    conversation.summarized_through_count = already + len(to_fold)
    await session.commit()


JOB_HANDLERS: dict[str, Callable[[dict[str, Any], AsyncSession], Awaitable[None]]] = {
    "summarize_conversation": summarize_conversation,
}
