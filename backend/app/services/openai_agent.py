import json
import logging
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.agent import ChatMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ProSim AI, an expert process engineering assistant integrated into ProSim Cloud, \
a chemical process simulation platform.

You have deep knowledge of:
- Chemical engineering unit operations (heat exchangers, reactors, distillation columns, pumps, compressors, etc.)
- Thermodynamic property packages (Peng-Robinson, SRK, NRTL, UNIQUAC, etc.)
- Process simulation using DWSIM and similar tools
- Material and energy balances
- Process optimization and troubleshooting

When the user provides flowsheet context, analyze it carefully and give specific, actionable advice.
Reference specific equipment IDs, stream conditions, and parameters from the flowsheet.
If simulation results are included, interpret them and suggest improvements.

Keep responses focused and technical. Use proper engineering terminology and units.
When suggesting changes, be specific about which parameters to modify and what values to use."""


class AgentService:
    """OpenAI-powered process engineering chat agent."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    async def chat(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> tuple[ChatMessage, dict[str, int] | None]:
        """Send messages to OpenAI and return the assistant response."""
        formatted = self._build_messages(messages, flowsheet_context)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=0.7,
            max_tokens=2048,
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return ChatMessage(role="assistant", content=content), usage

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as Server-Sent Events data chunks."""
        formatted = self._build_messages(messages, flowsheet_context)

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=0.7,
            max_tokens=2048,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield f"data: {json.dumps({'content': delta.content})}\n\n"

        yield "data: [DONE]\n\n"

    def _build_messages(
        self,
        messages: list[ChatMessage],
        flowsheet_context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Build the message list for the OpenAI API."""
        system_content = SYSTEM_PROMPT
        if flowsheet_context:
            ctx_str = json.dumps(flowsheet_context, indent=2, default=str)
            system_content += f"\n\nCurrent flowsheet context:\n```json\n{ctx_str}\n```"

        formatted: list[dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]

        for msg in messages:
            formatted.append({"role": msg.role, "content": msg.content})

        return formatted
