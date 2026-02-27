from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    flowsheet_context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    message: ChatMessage
    usage: dict[str, int] | None = None
