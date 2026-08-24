import json
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any

import structlog

from app.ai.llm.anthropic.client import AnthropicClient
from app.ai.prompts.builder import build_datetime_block, build_system_prompt
from app.ai.prompts.chat import CHAT_PROMPT
from app.ai.prompts.title import TITLE_PROMPT
from app.ai.tools.catalog import RENAME_TOOL, tools_for_scopes
from app.ai.tools.executor import execute_tool

logger = structlog.get_logger(__name__)
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5


# Status berasal dari aplikasi agar UI tidak bergantung pada kalimat bebas dari model.
class ChatStatus(StrEnum):
    UNDERSTANDING = "understanding"
    FETCHING_DATA = "fetching_data"
    ANALYZING = "analyzing"


StatusCallback = Callable[[ChatStatus], Awaitable[None]]
ToolCallCallback = Callable[[str, dict[str, Any], str, float], Awaitable[None]]


async def run_chat_loop(
    messages: list[dict[str, Any]],
    allowed_scopes: list[str],
    allow_rename: bool = False,
    client: AnthropicClient | None = None,
    on_status: StatusCallback | None = None,
    on_tool_call: ToolCallCallback | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    # Agent loop meminta keputusan model, menjalankan tool, lalu mengirim hasilnya kembali.
    async def emit(status: ChatStatus) -> None:
        if on_status is not None:
            await on_status(status)

    model_client = client or AnthropicClient()
    working_messages = list(messages)
    new_messages: list[dict[str, Any]] = []
    renamed_title: str | None = None
    tools = tools_for_scopes(allowed_scopes)
    if allow_rename:
        tools.append(RENAME_TOOL)
    # Dibangun sekali di luar loop — datetime-nya tidak perlu segar per iterasi tool-use.
    system = [*build_system_prompt(CHAT_PROMPT), build_datetime_block()]

    for iteration in range(MAX_TOOL_ITERATIONS):
        await emit(ChatStatus.UNDERSTANDING if iteration == 0 else ChatStatus.ANALYZING)
        response = await model_client.create_message(
            system=system,
            tools=tools,
            messages=working_messages,
            max_tokens=MAX_TOKENS,
            allowed_scopes=allowed_scopes,
        )
        assistant_message = {
            "role": "assistant",
            "content": [block.model_dump() for block in response.content],
        }
        working_messages.append(assistant_message)
        new_messages.append(assistant_message)

        if response.stop_reason != "tool_use":
            return new_messages, renamed_title

        await emit(ChatStatus.FETCHING_DATA)
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "rename_conversation":
                renamed_title = block.input.get("title")
                result = {"status": "renamed", "title": renamed_title}
            else:
                tool_start = time.perf_counter()
                result = await execute_tool(block.name, block.input, allowed_scopes)
                duration_ms = round((time.perf_counter() - tool_start) * 1000, 2)
                logger.info("tool_completed", tool=block.name, duration_ms=duration_ms)
                if on_tool_call is not None:
                    await on_tool_call(
                        block.name, block.input, result.get("status", "ERROR"), duration_ms
                    )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        tool_result_message = {"role": "user", "content": results}
        working_messages.append(tool_result_message)
        new_messages.append(tool_result_message)

    logger.warning("Reached tool iteration limit without a final response")
    return new_messages, renamed_title


async def generate_title(message: str) -> str:
    system = [*build_system_prompt(TITLE_PROMPT), build_datetime_block()]
    return await AnthropicClient().generate_title(message, system)
