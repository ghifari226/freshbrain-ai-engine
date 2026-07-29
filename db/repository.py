import json
from uuid import UUID

from db.connection import get_pool


async def create_conversation(user_id: UUID) -> UUID:
    pool = get_pool()
    row = await pool.fetchrow(
        "INSERT INTO conversations (user_id) VALUES ($1) RETURNING id", user_id
    )
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


async def update_conversation_title(conversation_id: UUID, title: str) -> None:
    """Persists an ai-engine-detected mid-conversation rename (see
    orchestration/loop.py's rename_conversation tool) — not ownership
    checked, since it's only ever called from within an already-
    authenticated /chat turn for that same conversation."""
    pool = get_pool()
    await pool.execute(
        "UPDATE conversations SET title = $1 WHERE id = $2", title, conversation_id
    )


async def list_conversations(user_id: UUID) -> list[dict]:
    """Returns this user's conversations, most recently active first, each
    with its full message history attached (see auth-contract.md's
    GET /conversations — no separate paginated message-fetch endpoint)."""
    pool = get_pool()
    conversation_rows = await pool.fetch(
        "SELECT id, title, last_active_at FROM conversations "
        "WHERE user_id = $1 ORDER BY last_active_at DESC",
        user_id,
    )
    conversations = []
    for row in conversation_rows:
        messages = await pool.fetch(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = $1 ORDER BY created_at ASC",
            row["id"],
        )
        conversations.append(
            {
                "id": row["id"],
                "title": row["title"],
                "last_active_at": row["last_active_at"],
                "messages": [
                    {
                        "id": m["id"],
                        "role": m["role"],
                        "content": json.loads(m["content"]),
                        "created_at": m["created_at"],
                    }
                    for m in messages
                ],
            }
        )
    return conversations


async def rename_conversation(conversation_id: UUID, user_id: UUID, title: str) -> bool:
    """Ownership-scoped: returns False when conversation_id doesn't exist or
    doesn't belong to user_id — caller raises 404 for both cases alike."""
    pool = get_pool()
    row = await pool.fetchrow(
        "UPDATE conversations SET title = $1 WHERE id = $2 AND user_id = $3 RETURNING id",
        title,
        conversation_id,
        user_id,
    )
    return row is not None


async def delete_conversation(conversation_id: UUID, user_id: UUID) -> bool:
    """Ownership-scoped, same convention as rename_conversation. Cascades to
    that conversation's messages and feedback rows via the FKs in
    schema.sql."""
    pool = get_pool()
    row = await pool.fetchrow(
        "DELETE FROM conversations WHERE id = $1 AND user_id = $2 RETURNING id",
        conversation_id,
        user_id,
    )
    return row is not None


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
