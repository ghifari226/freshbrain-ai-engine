import json
from typing import Any

from structlog.testing import capture_logs

from app.chat import orchestration
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

    assert statuses == [ChatStatus.UNDERSTANDING]


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
    ]


async def test_on_status_is_optional() -> None:
    client = FakeClient([_text_response("hi")])
    new_messages, _ = await run_chat_loop(
        [{"role": "user", "content": "hello"}],
        allowed_scopes=[],
        client=client,
    )
    assert new_messages


async def test_tool_execution_logs_completion_with_duration() -> None:
    client = FakeClient([_tool_use_response(), _text_response("here you go")])

    with capture_logs() as logs:
        await run_chat_loop(
            [{"role": "user", "content": "how many inbound shipments today?"}],
            allowed_scopes=["*"],
            client=client,
        )

    completed = [entry for entry in logs if entry["event"] == "tool_completed"]
    assert len(completed) == 1
    assert completed[0]["tool"] == "get_inbound_count"
    assert completed[0]["duration_ms"] >= 0


async def test_no_data_tool_result_is_not_misrepresented_as_success(
    monkeypatch: Any,
) -> None:
    # A NO_DATA envelope must survive execute_tool() -> tool_result content
    # unchanged — it must not get flattened into a bare count/zero anywhere
    # in the plumbing, since that would let a real "found nothing" look
    # identical to a real "found zero of something" SUCCESS response.
    async def fake_execute_tool(name: str, tool_input: dict, allowed_scopes: list[str]) -> dict:
        return {"status": "NO_DATA", "data": None}

    monkeypatch.setattr(orchestration, "execute_tool", fake_execute_tool)

    client = FakeClient([_tool_use_response(), _text_response("here you go")])
    new_messages, _ = await run_chat_loop(
        [{"role": "user", "content": "how many inbound shipments today?"}],
        allowed_scopes=["*"],
        client=client,
    )

    tool_result_message = new_messages[1]
    tool_result_content = json.loads(tool_result_message["content"][0]["content"])
    assert tool_result_content == {"status": "NO_DATA", "data": None}
