import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class VersionCreate(BaseModel):
    label: str | None = None


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flowsheet_id: uuid.UUID
    version_number: int
    label: str | None = None
    property_package: str | None = None
    created_at: datetime


class VersionDetailResponse(VersionResponse):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class VersionDiffResponse(BaseModel):
    added_nodes: list[dict[str, Any]] = []
    removed_nodes: list[dict[str, Any]] = []
    modified_nodes: list[dict[str, Any]] = []
    added_edges: list[dict[str, Any]] = []
    removed_edges: list[dict[str, Any]] = []
    modified_edges: list[dict[str, Any]] = []
