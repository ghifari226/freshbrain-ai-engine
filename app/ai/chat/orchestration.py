import json
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

import structlog

from app.ai.llm.anthropic.client import AnthropicClient
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
TITLE_SYSTEM_PROMPT = (
    "Summarize the user's message into a short conversation title (at most "
    "6 words, no surrounding quotes or trailing punctuation). Respond with "
    "only the title."
)


def build_system_prompt() -> str:
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    return (
        "You are FreshBrain, an internal AI assistant for Fresh Factory "
        "(cold chain, warehouse, and logistics operations).\n\n"
        f"Current datetime: {now:%Y-%m-%d %H:%M:%S} WIB (Asia/Jakarta).\n\n"
        "Use the available tools to answer operational questions accurately. "
        "If a question requires data you don't have a tool for, say so rather "
        "than guessing.\n\n"
        "Tool results carry a `status` field: SUCCESS, NO_DATA, or "
        "UPSTREAM_ERROR. On NO_DATA, the query was valid and authorized but "
        "genuinely found nothing — tell the user no matching data was found; "
        "don't guess a reason, and don't treat it the same as a SUCCESS "
        "result with a zero/empty value unless that's literally what the "
        "tool's data says. On UPSTREAM_ERROR, the data could not be "
        "retrieved — tell the user it couldn't be retrieved right now; "
        "don't present it as a real answer or invent an explanation for "
        "why.\n\n"
        "If the user pastes a password, API key, token, or other credential "
        "into the conversation, don't repeat it back verbatim — warn them "
        "that it may have been exposed and suggest they rotate it."
    )


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

    for iteration in range(MAX_TOOL_ITERATIONS):
        await emit(ChatStatus.UNDERSTANDING if iteration == 0 else ChatStatus.ANALYZING)
        response = await model_client.create_message(
            system=build_system_prompt(),
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
    return await AnthropicClient().generate_title(message, TITLE_SYSTEM_PROMPT)
