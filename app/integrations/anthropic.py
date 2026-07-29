from typing import Any

import anthropic

from app.chat.stub import create_stub_message
from app.core.config import get_settings


class AnthropicClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = (
            None
            if settings.stub_claude_api
            else anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        )

    async def create_message(
        self,
        *,
        system: str,
        tools: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        max_tokens: int,
        allowed_scopes: list[str],
    ) -> Any:
        if self.settings.stub_claude_api:
            return await create_stub_message(messages, tools, allowed_scopes)
        assert self.client is not None
        return await self.client.messages.create(
            model=self.settings.claude_model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

    async def generate_title(self, message: str, system: str) -> str:
        if self.settings.stub_claude_api:
            words = message.strip().split()
            summary = " ".join(words[:6])
            title = summary[:1].upper() + summary[1:] if summary else "New chat"
            return f"{title}…" if len(words) > 6 else title
        assert self.client is not None
        response = await self.client.messages.create(
            model=self.settings.claude_model,
            max_tokens=32,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return "New chat"
