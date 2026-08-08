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

    async def summarize(self, previous_summary: str | None, new_message_texts: list[str]) -> str:
        if self.settings.stub_claude_api:
            prefix = f"{previous_summary} " if previous_summary else ""
            return f"{prefix}[+{len(new_message_texts)} turns]"
        assert self.client is not None
        prompt = (
            f"Previous summary:\n{previous_summary or '(none)'}\n\n"
            "New messages to fold in:\n" + "\n".join(new_message_texts)
        )
        response = await self.client.messages.create(
            model=self.settings.claude_model,
            max_tokens=512,
            system=(
                "Produce an updated rolling summary of this conversation, "
                "incorporating the new messages into the previous summary concisely."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return previous_summary or ""
