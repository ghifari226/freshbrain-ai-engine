import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from tools.functions.inbound import get_inbound_count

logger = logging.getLogger(__name__)

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5

TOOLS_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "tools" / "schemas"

with open(TOOLS_SCHEMA_DIR / "inbound.json") as f:
    INBOUND_TOOL_SCHEMA = json.load(f)

TOOLS = [INBOUND_TOOL_SCHEMA]

# Maps tool name -> async Python function that implements it.
TOOL_FUNCTIONS = {
    "get_inbound_count": get_inbound_count,
}

client = anthropic.Anthropic()

##############################################################################
# STUB — THE CLAUDE API CALL IS FAKED BELOW, NOT REAL.
#
# Payment blocker (bank/OTP issue) is preventing Anthropic API credits from
# being topped up today — out of our control, not a design choice. This
# stub fakes ONE realistic tool-use round trip so the rest of the system
# (endpoint, Postgres persistence, tool registry, execute_tool() dispatch)
# can still be exercised and demoed end-to-end without a real API key.
#
# It does NOT call the real Claude API. It scripts an assistant turn that
# requests the get_inbound_count tool, lets execute_tool() actually run the
# (already-stubbed) tool function in tools/functions/inbound.py, then
# scripts a final assistant text turn built from that tool's result — so
# persistence, the tool registry, and the loop's control flow are all
# genuinely exercised.
#
# TO REVERT once Anthropic credits are available:
#   Set STUB_CLAUDE_API = False (or env var STUB_CLAUDE_API=false). The
#   real client.messages.create() call below is untouched — nothing else
#   needs to change. Then delete this block and the _Stub*/_stub_* helpers.
##############################################################################
STUB_CLAUDE_API = os.getenv("STUB_CLAUDE_API", "true").lower() != "false"


class _StubContentBlock:
    def __init__(self, data: dict):
        self._data = data
        self.type = data["type"]
        if self.type == "tool_use":
            self.id = data["id"]
            self.name = data["name"]
            self.input = data["input"]

    def model_dump(self) -> dict:
        return self._data


class _StubMessage:
    def __init__(self, content: list[dict], stop_reason: str):
        self.content = [_StubContentBlock(b) for b in content]
        self.stop_reason = stop_reason


def _stub_messages_create(*, model, max_tokens, system, tools, messages):
    """Fake substitute for client.messages.create() — see STUB block above."""
    logger.warning(
        "STUB Claude API call in orchestration/loop.py — returning a FAKE "
        "Claude response, not calling the real API. See STUB block above "
        "run_chat_loop() for why and how to revert."
    )

    last = messages[-1] if messages else None
    tool_result = None
    if last and last.get("role") == "user" and isinstance(last.get("content"), list):
        tool_result = next(
            (b for b in last["content"] if isinstance(b, dict) and b.get("type") == "tool_result"),
            None,
        )

    if tool_result is None:
        today = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d")
        return _StubMessage(
            content=[
                {"type": "text", "text": "Let me check the inbound shipment data for you."},
                {
                    "type": "tool_use",
                    "id": "toolu_stub_0000000000000000",
                    "name": "get_inbound_count",
                    "input": {"date": today, "status": "pending"},
                },
            ],
            stop_reason="tool_use",
        )

    try:
        result = json.loads(tool_result["content"])
    except (KeyError, TypeError, json.JSONDecodeError):
        result = {}

    return _StubMessage(
        content=[{
            "type": "text",
            "text": (
                f"[STUBBED RESPONSE] Based on stubbed WMS data, there are "
                f"{result.get('count', 'an unknown number of')} inbound "
                f"shipments with status '{result.get('status', '?')}' on "
                f"{result.get('date', '?')}. This is a fake Claude response — "
                f"see STUB block in orchestration/loop.py."
            ),
        }],
        stop_reason="end_turn",
    )


def build_system_prompt() -> str:
    now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
    return (
        "You are FreshBrain, an internal AI assistant for Fresh Factory "
        "(cold chain, warehouse, and logistics operations).\n\n"
        f"Current datetime: {now_wib.strftime('%Y-%m-%d %H:%M:%S')} WIB (Asia/Jakarta).\n\n"
        "Use the available tools to answer operational questions accurately. "
        "If a question requires data you don't have a tool for, say so rather "
        "than guessing."
    )


async def execute_tool(name: str, tool_input: dict) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    return await func(**tool_input)


async def run_chat_loop(messages: list[dict]) -> list[dict]:
    """
    Runs the Claude tool-use loop given prior conversation history plus the
    new user turn (Claude message-param format). Sends the system prompt +
    the one available tool, executes any tool_use requests, and resends
    results until Claude produces a final text answer.

    Returns the list of NEW message dicts produced this turn (to be
    persisted) in order — the final entry is always the assistant's
    end_turn response.
    """
    system_prompt = build_system_prompt()
    working_messages = list(messages)
    new_messages: list[dict] = []

    for _ in range(MAX_TOOL_ITERATIONS):
        if STUB_CLAUDE_API:
            response = _stub_messages_create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=TOOLS,
                messages=working_messages,
            )
        else:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=TOOLS,
                messages=working_messages,
            )

        assistant_content = [block.model_dump() for block in response.content]
        assistant_message = {"role": "assistant", "content": assistant_content}
        working_messages.append(assistant_message)
        new_messages.append(assistant_message)

        if response.stop_reason != "tool_use":
            return new_messages

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )

        tool_result_message = {"role": "user", "content": tool_results}
        working_messages.append(tool_result_message)
        new_messages.append(tool_result_message)

    logger.warning("Hit MAX_TOOL_ITERATIONS (%s) without reaching end_turn", MAX_TOOL_ITERATIONS)
    return new_messages


def extract_final_text(assistant_content: list[dict]) -> str:
    for block in assistant_content:
        if block.get("type") == "text":
            return block["text"]
    return ""
