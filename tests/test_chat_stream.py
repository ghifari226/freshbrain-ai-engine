import json
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.chat.schemas import ChatRequest
from app.chat.service import ChatService


def _parse(chunk: str) -> tuple[str, dict]:
    lines = chunk.strip().splitlines()
    event = lines[0].removeprefix("event: ")
    data = json.loads(lines[1].removeprefix("data: "))
    return event, data


async def _collect(events: AsyncIterator[str]) -> list[tuple[str, dict]]:
    return [_parse(chunk) async for chunk in events]


async def test_stream_direct_answer_emits_status_then_done(db_session) -> None:
    service = ChatService(db_session)
    request = ChatRequest(message="berapa total warehouse partnership saat ini")

    events = await service.chat_stream(request, str(uuid4()), [])
    chunks = await _collect(events)

    assert [event for event, _ in chunks] == ["status", "status", "done"]
    assert [data["status"] for _, data in chunks[:2]] == ["understanding", "responding"]
    done_event, done_data = chunks[-1]
    assert done_event == "done"
    assert "32 warehouse partnership" in done_data["answer"]
    assert done_data["conversation_id"]


async def test_stream_tool_use_emits_full_status_sequence(db_session) -> None:
    service = ChatService(db_session)
    request = ChatRequest(message="ada berapa pengiriman inbound hari ini")

    events = await service.chat_stream(request, str(uuid4()), ["wms"])
    chunks = await _collect(events)

    statuses = [data["status"] for event, data in chunks if event == "status"]
    assert statuses == ["understanding", "fetching_data", "analyzing", "responding"]
    assert chunks[-1][0] == "done"


async def test_stream_raises_before_streaming_starts_for_bad_conversation(db_session) -> None:
    service = ChatService(db_session)
    request = ChatRequest(message="hi", conversation_id=str(uuid4()))

    with pytest.raises(HTTPException) as error:
        await service.chat_stream(request, str(uuid4()), [])
    assert error.value.status_code == 404
