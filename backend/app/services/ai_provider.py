"""Multi-model AI provider abstraction."""
import os
from abc import ABC, abstractmethod
from typing import AsyncIterator


class AIProvider(ABC):
    """Base class for AI chat providers."""

    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        pass

    @abstractmethod
    async def chat_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        pass


class OpenAIProvider(AIProvider):
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")

    async def chat(self, messages, tools=None):
        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.model_dump(exclude_none=True)

    async def chat_stream(self, messages):
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class ClaudeProvider(AIProvider):
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    async def chat(self, messages, tools=None):
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            system_msg = ""
            conv_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_msg = m["content"]
                else:
                    conv_messages.append({"role": m["role"], "content": m["content"]})
            kwargs: dict = {"model": self.model, "max_tokens": 4096, "messages": conv_messages}
            if system_msg:
                kwargs["system"] = system_msg
            response = await client.messages.create(**kwargs)
            return {"role": "assistant", "content": response.content[0].text}
        except ImportError:
            return {"role": "assistant", "content": "Anthropic SDK not installed. Install with: pip install anthropic"}

    async def chat_stream(self, messages):
        yield "Claude streaming not configured. Set ANTHROPIC_API_KEY."


class OllamaProvider(AIProvider):
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3")

    async def chat(self, messages, tools=None):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                )
                data = response.json()
                return {"role": "assistant", "content": data.get("message", {}).get("content", "")}
        except Exception as e:
            return {"role": "assistant", "content": f"Ollama not available: {e}"}

    async def chat_stream(self, messages):
        yield "Ollama streaming not configured."


def get_ai_provider(provider_name: str | None = None) -> AIProvider:
    """Factory function for AI providers."""
    name = provider_name or os.getenv("AI_PROVIDER", "openai")
    if name in ("claude", "anthropic"):
        return ClaudeProvider()
    elif name == "ollama":
        return OllamaProvider()
    return OpenAIProvider()
