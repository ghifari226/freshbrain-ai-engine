from typing import Any

from app.chat.orchestration import ChatStatus, run_chat_loop
from app.chat.stub import StubMessage


class FakeClient:
    def __init__(self, responses: list[StubMessage]):
        self._responses = list(responses)

    async def create_message(self, **kwargs: Any) -> StubMessage:
        return self._responses.pop(0)


def _text_response(text: str) -> StubMessage:
    return StubMessage([{"type": "text", "text": text}], "end_turn")


def _tool_use_response() -> StubMessage:
    return StubMessage(
        [
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "get_inbound_count",
                "input": {"date": "2026-08-08", "status": "pending"},
            }
        ],
        "tool_use",
    )


async def test_status_sequence_for_direct_answer() -> None:
    client = FakeClient([_text_response("hi")])
    statuses: list[ChatStatus] = []

    async def record(status: ChatStatus) -> None:
        statuses.append(status)

    await run_chat_loop(
        [{"role": "user", "content": "hello"}],
        allowed_scopes=[],
        client=client,
        on_status=record,
    )

    assert statuses == [ChatStatus.UNDERSTANDING, ChatStatus.RESPONDING]


async def test_status_sequence_for_tool_call_then_answer() -> None:
    client = FakeClient([_tool_use_response(), _text_response("here you go")])
    statuses: list[ChatStatus] = []

    async def record(status: ChatStatus) -> None:
        statuses.append(status)

    await run_chat_loop(
        [{"role": "user", "content": "how many inbound shipments today?"}],
        allowed_scopes=["*"],
        client=client,
        on_status=record,
    )

    assert statuses == [
        ChatStatus.UNDERSTANDING,
        ChatStatus.FETCHING_DATA,
        ChatStatus.ANALYZING,
        ChatStatus.RESPONDING,
    ]


async def test_on_status_is_optional() -> None:
    client = FakeClient([_text_response("hi")])
    new_messages, _ = await run_chat_loop(
        [{"role": "user", "content": "hello"}],
        allowed_scopes=[],
        client=client,
    )
    assert new_messages
