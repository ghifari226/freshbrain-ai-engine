import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.chat.tools import RENAME_TOOL, execute_tool, tools_for_scopes
from app.integrations.anthropic import AnthropicClient

logger = logging.getLogger(__name__)
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5
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
        "than guessing."
    )


async def run_chat_loop(
    messages: list[dict[str, Any]],
    allowed_scopes: list[str],
    allow_rename: bool = False,
    client: AnthropicClient | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    model_client = client or AnthropicClient()
    working_messages = list(messages)
    new_messages: list[dict[str, Any]] = []
    renamed_title: str | None = None
    tools = tools_for_scopes(allowed_scopes)
    if allow_rename:
        tools.append(RENAME_TOOL)

    for _ in range(MAX_TOOL_ITERATIONS):
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

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "rename_conversation":
                renamed_title = block.input.get("title")
                result = {"status": "renamed", "title": renamed_title}
            else:
                result = await execute_tool(block.name, block.input, allowed_scopes)
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
