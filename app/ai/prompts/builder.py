from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.prompts.base import BASE_SYSTEM_PROMPT


def build_system_prompt(task_prompt: str) -> list[dict[str, Any]]:
    # Deterministik dengan sengaja — tidak ada datetime/interpolasi di sini, supaya prefix
    # ini stabil dan bisa kena cache. Bagian dinamis ada di build_datetime_block().
    text = BASE_SYSTEM_PROMPT if not task_prompt else f"{BASE_SYSTEM_PROMPT}\n\n{task_prompt}"
    return [
        {
            "type": "text",
            "text": text,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def build_datetime_block() -> dict[str, Any]:
    # Ekor dinamis: TIDAK diberi cache_control, supaya tidak membatalkan cache blok di atasnya.
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    return {
        "type": "text",
        "text": f"Current datetime: {now:%Y-%m-%d %H:%M:%S} WIB (Asia/Jakarta).",
    }
