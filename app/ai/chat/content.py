from typing import Any


def extract_final_text(assistant_content: list[dict[str, Any]]) -> str:
    # Respons provider dinormalisasi sebelum dipakai oleh lapisan bisnis.
    for block in assistant_content:
        if block.get("type") == "text":
            return str(block["text"])
    return ""
