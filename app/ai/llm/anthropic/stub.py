import json
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.tools.catalog import scope_grants
from app.integrations.warehouse import WarehouseClient

_CANNED_ANSWERS = {
    "berapa total warehouse partnership saat ini": (
        "Saat ini terdapat total 32 warehouse partnership."
    ),
}
_REVENUE_WINDOWS = {
    "berapa revenue client greenfields bulan lalu": (
        date(2026, 6, 1),
        date(2026, 6, 30),
    ),
    "berapa revenue client greenfields 3 bulan terakhir": (
        date(2026, 4, 1),
        date(2026, 6, 30),
    ),
}
GREENFIELDS_PARTNER_IDS = (1334, 1336)
RENAME_PATTERN = re.compile(
    r"(?:rename (?:this (?:thread|conversation|chat) )?to|"
    r'(?:ganti|ubah) judul(?:nya)? (?:jadi|ke))\s+["\']?([^"\'.!]+?)["\']?[.!]*$',
    re.IGNORECASE,
)


class StubBlock:
    def __init__(self, data: dict[str, Any]):
        self._data = data
        self.type = data["type"]
        self.id = data.get("id")
        self.name = data.get("name")
        self.input = data.get("input")

    def model_dump(self) -> dict[str, Any]:
        return self._data


# Stub meniru bentuk respons provider agar orchestration memakai kontrak yang sama.
class StubMessage:
    def __init__(self, content: list[dict[str, Any]], stop_reason: str):
        self.content = [StubBlock(block) for block in content]
        self.stop_reason = stop_reason


def _text_message(text: str) -> StubMessage:
    return StubMessage([{"type": "text", "text": text}], "end_turn")


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _format_rupiah(amount: Any) -> str:
    integer, _, decimal = f"{amount:,.2f}".partition(".")
    return f"Rp {integer.replace(',', '.')},{decimal}"


async def create_stub_message(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    allowed_scopes: list[str],
) -> StubMessage:
    last = messages[-1] if messages else {}
    if isinstance(last.get("content"), list):
        result_block = next(
            (
                block
                for block in last["content"]
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ),
            None,
        )
        if result_block:
            try:
                result = json.loads(result_block["content"])
            except (KeyError, TypeError, json.JSONDecodeError):
                result = {}
            if result.get("status") == "renamed":
                return _text_message(
                    f'Baik, saya ubah judul percakapan ini jadi "{result.get("title", "")}".'
                )
            envelope_status = result.get("status")
            if envelope_status == "NO_DATA":
                return _text_message("No inbound shipments found for that date/status.")
            if envelope_status == "UPSTREAM_ERROR":
                return _text_message("Couldn't retrieve that data right now.")
            data = result.get("data") or {}
            return _text_message(
                "[STUBBED RESPONSE] Based on stubbed WMS data, there are "
                f"{data.get('count', 'an unknown number of')} inbound shipments "
                f"with status '{data.get('status', '?')}' on "
                f"{data.get('date', '?')}."
            )

    text = _last_user_text(messages)
    normalized = text.strip().rstrip("?").strip().lower()
    visible_names = {tool["name"] for tool in tools}

    if "rename_conversation" in visible_names:
        match = RENAME_PATTERN.search(text.strip())
        if match:
            return StubMessage(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_stub_rename",
                        "name": "rename_conversation",
                        "input": {"title": match.group(1).strip()},
                    }
                ],
                "tool_use",
            )

    if normalized in _CANNED_ANSWERS:
        return _text_message(_CANNED_ANSWERS[normalized])

    if normalized in _REVENUE_WINDOWS:
        if not scope_grants(allowed_scopes, "odoo"):
            return _text_message("Kami belum punya jawaban untuk pertanyaan itu.")
        total = await WarehouseClient().get_partner_revenue(
            GREENFIELDS_PARTNER_IDS,
            *_REVENUE_WINDOWS[normalized],
        )
        return _text_message(_format_rupiah(total))

    if "get_inbound_count" not in visible_names or not any(
        keyword in text.lower() for keyword in ("pengiriman", "inbound", "shipment")
    ):
        return _text_message("Kami belum punya jawaban untuk pertanyaan itu.")

    return StubMessage(
        [
            {"type": "text", "text": "Let me check the inbound shipment data for you."},
            {
                "type": "tool_use",
                "id": "toolu_stub_inbound",
                "name": "get_inbound_count",
                "input": {
                    "date": datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d"),
                    "status": "pending",
                },
            },
        ],
        "tool_use",
    )
