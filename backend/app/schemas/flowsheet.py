import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NodeData(BaseModel):
    id: str
    type: str
    label: str
    position: dict[str, float]
    data: dict[str, Any] = {}


class EdgeData(BaseModel):
    id: str
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class FlowsheetUpdate(BaseModel):
    nodes: list[NodeData] = []
    edges: list[EdgeData] = []


class FlowsheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    updated_at: datetime
