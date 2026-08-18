from app.ai.chat.context import build_chat_context
from app.conversations.models import Message


def make_messages(n: int) -> list[Message]:
    return [
        Message(role="user" if i % 2 == 0 else "assistant", content=f"msg {i}") for i in range(n)
    ]


def test_no_summary_returns_full_history() -> None:
    messages = make_messages(5)
    context = build_chat_context(messages, None, window=20)
    assert context == [{"role": m.role, "content": m.content} for m in messages]


def test_short_history_ignores_window_even_with_summary() -> None:
    messages = make_messages(3)
    context = build_chat_context(messages, "an old summary", window=20)
    assert context == [{"role": m.role, "content": m.content} for m in messages]


def test_summary_plus_window_trims_to_recent_messages() -> None:
    messages = make_messages(10)
    context = build_chat_context(messages, "an old summary", window=4)
    assert context[0] == {
        "role": "user",
        "content": "[Earlier conversation summary]\nan old summary",
    }
    assert context[1:] == [{"role": m.role, "content": m.content} for m in messages[-4:]]
    assert len(context) == 5
