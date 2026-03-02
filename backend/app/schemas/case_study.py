import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CaseCreate(BaseModel):
    name: str
    description: str | None = None
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    simulation_basis: dict[str, Any] = {}
    property_package: str = "PengRobinson"
    results: dict[str, Any] | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    property_package: str
    simulation_basis: dict[str, Any]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    results: dict[str, Any] | None
    created_at: datetime


class CaseCompareRequest(BaseModel):
    case_ids: list[uuid.UUID]


class CaseCompareResponse(BaseModel):
    cases: list[CaseResponse]
    diffs: dict[str, Any]
