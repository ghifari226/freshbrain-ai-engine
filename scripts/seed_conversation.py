"""Seed one conversation with N turns of chat history, for pagination testing.

Usage:
    .venv/bin/python scripts/seed_conversation.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.conversations.models import Conversation, Message
from app.core.database import SessionFactory
import app.feedback.models  # noqa: F401 — registers Feedback for the Conversation/Message relationship() lookups

TITLE = "FreshBrain Q&A marathon"
TURN_COUNT = 100
USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")

QUESTION = "Can you explain how FreshBrain helps my business make sense of its data?"
ANSWER = (
    "FreshBrain pulls together data from across your business and explains it in plain "
    "language, so you don't need to be a data analyst to understand what's going on. "
    "It connects with the FreshFactory, FreshCommerce, and Frex family of tools to give "
    "you one unified view. Just ask a question, and it answers with clear, actionable "
    "insight grounded in your real data."
)


async def main() -> None:
    start = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)

    async with SessionFactory() as session:
        conversation = Conversation(
            user_id=USER_ID,
            title=TITLE,
            created_at=start,
            last_active_at=start + timedelta(minutes=TURN_COUNT),
        )
        session.add(conversation)
        await session.flush()

        messages = []
        for i in range(TURN_COUNT):
            turn_number = i + 1
            question_time = start + timedelta(minutes=i)
            answer_time = question_time + timedelta(seconds=30)

            messages.append(
                Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=f"{QUESTION} (turn {turn_number})",
                    created_at=question_time,
                )
            )
            messages.append(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=[{"type": "text", "text": f"{ANSWER} (turn {turn_number})"}],
                    created_at=answer_time,
                )
            )

        session.add_all(messages)
        await session.commit()

        print(f"Seeded conversation {conversation.id} for user_id={USER_ID}")
        print(f"{len(messages)} messages inserted across {TURN_COUNT} turns")


if __name__ == "__main__":
    asyncio.run(main())
