import json
from uuid import UUID

from db.connection import get_pool


async def create_conversation() -> UUID:
    pool = get_pool()
    row = await pool.fetchrow("INSERT INTO conversations DEFAULT VALUES RETURNING id")
    return row["id"]


async def conversation_exists(conversation_id: UUID) -> bool:
    pool = get_pool()
    row = await pool.fetchrow("SELECT 1 FROM conversations WHERE id = $1", conversation_id)
    return row is not None


async def touch_conversation(conversation_id: UUID) -> None:
    pool = get_pool()
    await pool.execute(
        "UPDATE conversations SET last_active_at = now() WHERE id = $1",
        conversation_id,
    )


async def get_messages(conversation_id: UUID) -> list[dict]:
    """Returns prior turns in Claude message-param format, oldest first."""
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT role, content FROM messages WHERE conversation_id = $1 ORDER BY created_at ASC",
        conversation_id,
    )
    return [{"role": row["role"], "content": json.loads(row["content"])} for row in rows]


async def add_message(conversation_id: UUID, role: str, content) -> UUID:
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO messages (conversation_id, role, content) VALUES ($1, $2, $3::jsonb) RETURNING id",
        conversation_id,
        role,
        json.dumps(content),
    )
    return row["id"]


async def add_feedback(
    message_id: UUID,
    conversation_id: UUID,
    user_id: UUID,
    role: str,
    rating: str,
    reason: str | None,
    comment: str | None,
) -> UUID:
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO feedback (message_id, conversation_id, user_id, role, rating, reason, comment) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        message_id,
        conversation_id,
        user_id,
        role,
        rating,
        reason,
        comment,
    )
    return row["id"]
