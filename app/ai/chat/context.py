from typing import Any

from app.conversations.models import Message


def build_chat_context(
    messages: list[Message],
    rolling_summary: str | None,
    window: int,
) -> list[dict[str, Any]]:
    # Context window membatasi riwayat mentah agar prompt tetap muat dan terkontrol biayanya.
    if not rolling_summary or len(messages) <= window:
        return [{"role": m.role, "content": m.content} for m in messages]
    recent = messages[-window:]
    return [
        {"role": "user", "content": f"[Earlier conversation summary]\n{rolling_summary}"},
        *({"role": m.role, "content": m.content} for m in recent),
    ]
