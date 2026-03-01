from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    flowsheet_context: dict[str, Any] | None = None


class FlowsheetEquipment(BaseModel):
    id: str  # temp ID like "equip-1"
    type: str  # must match EquipmentType: "Heater", "Separator", etc.
    name: str  # display label
    parameters: dict[str, Any] = {}


class FlowsheetConnection(BaseModel):
    source_id: str
    source_port: str  # "out-1", "out-2", etc.
    target_id: str
    target_port: str  # "in-1", "in-2", etc.


class FlowsheetAction(BaseModel):
    equipment: list[FlowsheetEquipment]
    connections: list[FlowsheetConnection]
    mode: str = "replace"  # "replace" or "add"


class ChatResponse(BaseModel):
    message: ChatMessage
    usage: dict[str, int] | None = None
    flowsheet_action: FlowsheetAction | None = None
