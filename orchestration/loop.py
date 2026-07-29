import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from db.warehouse import get_partner_revenue
from tools.functions.inbound import get_inbound_count

logger = logging.getLogger(__name__)

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5

TOOLS_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "tools" / "schemas"

with open(TOOLS_SCHEMA_DIR / "inbound.json") as f:
    INBOUND_TOOL_SCHEMA = json.load(f)

with open(TOOLS_SCHEMA_DIR / "rename_conversation.json") as f:
    RENAME_TOOL_SCHEMA = json.load(f)

# Every tool schema that exists, unfiltered — see tools_for_scopes() for the
# per-request view actually sent to Claude.
ALL_TOOLS = [INBOUND_TOOL_SCHEMA]

# Maps tool name -> async Python function that implements it.
TOOL_FUNCTIONS = {
    "get_inbound_count": get_inbound_count,
}

# Maps tool name -> the scope tag required to see/use it, per
# freshbrain-agreement/scope-catalog.md. Kept separate from the Claude-
# facing schema files (tools/schemas/*.json) since scope is authorization
# metadata, not part of what the schema shows the model.
TOOL_SCOPES = {
    "get_inbound_count": "wms.inbound",
}


def scope_grants(allowed_scopes: list[str], required_scope: str) -> bool:
    """Implements scope-catalog.md's matching rules: "*" matches every
    scope now and in the future; a system-level tag (e.g. "wms") matches
    itself and any "wms.*" sub-scope; a sub-scope tag (e.g. "wms.inbound")
    matches only itself, exactly. A broader grant doesn't imply the
    narrower sub-scopes were individually requested, and a narrower grant
    does NOT imply the parent system-level tag is also granted."""
    for granted in allowed_scopes:
        if granted == "*" or granted == required_scope:
            return True
        if required_scope.startswith(f"{granted}."):
            return True
    return False


def tools_for_scopes(allowed_scopes: list[str]) -> list[dict]:
    """The subset of ALL_TOOLS this caller's allowed_scopes actually grants
    — this, not ALL_TOOLS, is what gets sent to Claude, so a scope-less
    caller never even sees a tool exists, let alone gets to invoke it."""
    return [tool for tool in ALL_TOOLS if scope_grants(allowed_scopes, TOOL_SCOPES[tool["name"]])]


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

# Deterministic string-to-string answers for a few known questions that
# don't need a tool round trip — same idea as the tool stub above (fake
# data, real client-facing behavior), just for questions where the "tool"
# would be a single fixed fact. Matched on exact question text, trailing
# "?" optional, since real users often skip it.
_CANNED_ANSWERS = {
    "berapa total warehouse partnership saat ini": "Saat ini terdapat total 32 warehouse partnership.",
}

# Odoo stores "Greenfields" as two separate res.partner records.
GREENFIELDS_PARTNER_IDS = (1334, 1336)

# Same exact-match idea as _CANNED_ANSWERS, but backed by a real query
# against the warehouse's fact_revenue table instead of a fixed string.
_REVENUE_WINDOWS = {
    "berapa revenue client greenfields bulan lalu": (date(2026, 6, 1), date(2026, 6, 30)),
    "berapa revenue client greenfields 3 bulan terakhir": (date(2026, 4, 1), date(2026, 6, 30)),
}


def _normalize_question(text: str) -> str:
    return text.strip().rstrip("?").strip().lower()


def _format_rupiah(amount) -> str:
    integer_part, _, decimal_part = f"{amount:,.2f}".partition(".")
    return f"Rp {integer_part.replace(',', '.')},{decimal_part}"


def _last_user_text(messages: list[dict]) -> str:
    """Finds the most recent plain-text user turn (the real question), as
    opposed to a tool_result turn (also role "user", but content is a list,
    not a string)."""
    for msg in reversed(messages):
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            return msg["content"]
    return ""


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


_RENAME_INTENT_PATTERN = re.compile(
    r'(?:rename (?:this (?:thread|conversation|chat) )?to|'
    r'(?:ganti|ubah) judul(?:nya)? (?:jadi|ke))\s+["\']?([^"\'.!]+?)["\']?[.!]*$',
    re.IGNORECASE,
)


def _match_rename_intent(text: str) -> str | None:
    match = _RENAME_INTENT_PATTERN.search(text.strip())
    return match.group(1).strip() if match else None


async def _stub_messages_create(*, model, max_tokens, system, tools, messages, allowed_scopes):
    """Fake substitute for client.messages.create() — see STUB block above.

    Unlike the real API, this doesn't naturally "just not know about" a tool
    it wasn't shown — it has to be told explicitly (via `tools`/
    `allowed_scopes`) which shortcuts are actually reachable, so the stub
    behaves the way real gating would: a scope-less caller gets the same
    "no answer" response a real Claude call would give when it was never
    shown the relevant tool, not a fake successful answer anyway."""
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
        text = _last_user_text(messages)
        normalized = _normalize_question(text)

        rename_tool_visible = any(tool["name"] == "rename_conversation" for tool in tools)
        if rename_tool_visible:
            new_title = _match_rename_intent(text)
            if new_title:
                return _StubMessage(
                    content=[{
                        "type": "tool_use",
                        "id": "toolu_stub_rename_0000000000",
                        "name": "rename_conversation",
                        "input": {"title": new_title},
                    }],
                    stop_reason="tool_use",
                )

        canned = _CANNED_ANSWERS.get(normalized)
        if canned is not None:
            return _StubMessage(
                content=[{"type": "text", "text": canned}],
                stop_reason="end_turn",
            )

        revenue_window = _REVENUE_WINDOWS.get(normalized)
        if revenue_window is not None:
            # This shortcut bypasses the tool-use loop entirely (it never
            # goes through tools_for_scopes/execute_tool), so it needs its own scope
            # check — revenue data is gated by "odoo" per scope-catalog.md.
            if scope_grants(allowed_scopes, "odoo"):
                total = await get_partner_revenue(GREENFIELDS_PARTNER_IDS, *revenue_window)
                return _StubMessage(
                    content=[{"type": "text", "text": _format_rupiah(total)}],
                    stop_reason="end_turn",
                )
            return _StubMessage(
                content=[{"type": "text", "text": "Kami belum punya jawaban untuk pertanyaan itu."}],
                stop_reason="end_turn",
            )

        lowered = text.lower()
        inbound_tool_visible = any(tool["name"] == "get_inbound_count" for tool in tools)
        if not inbound_tool_visible or not any(
            kw in lowered for kw in ("pengiriman", "inbound", "shipment")
        ):
            return _StubMessage(
                content=[{"type": "text", "text": "Kami belum punya jawaban untuk pertanyaan itu."}],
                stop_reason="end_turn",
            )

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

    if result.get("status") == "renamed":
        return _StubMessage(
            content=[{
                "type": "text",
                "text": f'Baik, saya ubah judul percakapan ini jadi "{result.get("title", "")}".',
            }],
            stop_reason="end_turn",
        )

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


async def execute_tool(name: str, tool_input: dict, allowed_scopes: list[str]) -> dict:
    # Defense in depth, not the primary gate — Claude (real or stubbed)
    # should never request a tool outside tools_for_scopes(allowed_scopes)
    # in the first place, since it's never shown one. This catches it
    # anyway rather than trusting that invariant blindly.
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    required_scope = TOOL_SCOPES.get(name)
    if required_scope is None or not scope_grants(allowed_scopes, required_scope):
        return {"error": f"Not authorized to use tool: {name}"}
    return await func(**tool_input)


async def run_chat_loop(
    messages: list[dict], allowed_scopes: list[str], allow_rename: bool = False
) -> tuple[list[dict], str | None]:
    """
    Runs the Claude tool-use loop given prior conversation history plus the
    new user turn (Claude message-param format). Sends the system prompt +
    only the tools allowed_scopes grants, executes any tool_use requests,
    and resends results until Claude produces a final text answer.

    `allow_rename` offers the (unscoped — not a data-access tool)
    rename_conversation tool. Only meaningful mid-conversation — per
    auth-contract.md, a brand-new conversation's title comes from the
    separate POST /chat/title call instead, never from this path.

    Returns (new NEW message dicts produced this turn, in order — the final
    entry is always the assistant's end_turn response; the new title, if
    the model called rename_conversation this turn, else None).
    """
    system_prompt = build_system_prompt()
    working_messages = list(messages)
    new_messages: list[dict] = []
    renamed_title: str | None = None
    tools = tools_for_scopes(allowed_scopes) + ([RENAME_TOOL_SCHEMA] if allow_rename else [])

    for _ in range(MAX_TOOL_ITERATIONS):
        if STUB_CLAUDE_API:
            response = await _stub_messages_create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=working_messages,
                allowed_scopes=allowed_scopes,
            )
        else:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=working_messages,
            )

        assistant_content = [block.model_dump() for block in response.content]
        assistant_message = {"role": "assistant", "content": assistant_content}
        working_messages.append(assistant_message)
        new_messages.append(assistant_message)

        if response.stop_reason != "tool_use":
            return new_messages, renamed_title

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "rename_conversation":
                # Handled here, not via execute_tool/TOOL_FUNCTIONS: this
                # isn't a data-access tool with a real backing function, and
                # its "result" (the title) needs to surface out of the loop
                # to the caller, not just get fed back to Claude.
                renamed_title = block.input.get("title")
                result = {"status": "renamed", "title": renamed_title}
            else:
                result = await execute_tool(block.name, block.input, allowed_scopes)
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
    return new_messages, renamed_title


TITLE_SYSTEM_PROMPT = (
    "Summarize the user's message into a short conversation title (at most "
    "6 words, no surrounding quotes or trailing punctuation). Respond with "
    "only the title."
)


async def generate_title(message: str) -> str:
    """Backs POST /chat/title — a short, stateless summary of a single
    message, decoupled from run_chat_loop so title generation never blocks
    on (or is blocked by) the actual chat answer."""
    if STUB_CLAUDE_API:
        logger.warning(
            "STUB Claude API call in orchestration/loop.py's generate_title "
            "— returning a FAKE title, not calling the real API."
        )
        words = message.strip().split()
        summary = " ".join(words[:6])
        title = summary[:1].upper() + summary[1:] if summary else "New chat"
        return f"{title}…" if len(words) > 6 else title

    response = client.messages.create(
        model=MODEL,
        max_tokens=32,
        system=TITLE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
    )
    return extract_final_text([block.model_dump() for block in response.content]) or "New chat"


def extract_final_text(assistant_content: list[dict]) -> str:
    for block in assistant_content:
        if block.get("type") == "text":
            return block["text"]
    return ""
