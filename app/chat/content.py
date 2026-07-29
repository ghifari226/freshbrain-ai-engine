from typing import Any


def extract_final_text(assistant_content: list[dict[str, Any]]) -> str:
    for block in assistant_content:
        if block.get("type") == "text":
            return str(block["text"])
    return ""
