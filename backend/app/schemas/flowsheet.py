import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str
    label: str = ""
    position: dict[str, float] = {}
    data: dict[str, Any] = {}


class EdgeData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    target: str
    source_handle: str | None = Field(None, alias="sourceHandle")
    target_handle: str | None = Field(None, alias="targetHandle")


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
