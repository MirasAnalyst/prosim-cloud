import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StreamConditions(BaseModel):
    temperature: float | None = None  # °C (frontend units)
    pressure: float | None = None  # kPa (frontend units)
    flowRate: float | None = None  # kg/s
    composition: dict[str, float] = {}  # component_name -> mole fraction
    vapor_fraction: float | None = None


class EquipmentResults(BaseModel):
    equipment_id: str
    equipment_type: str
    duty: float | None = None  # W
    work: float | None = None  # W
    efficiency: float | None = None
    pressure_drop: float | None = None  # Pa
    inlet_streams: dict[str, StreamConditions] = {}
    outlet_streams: dict[str, StreamConditions] = {}
    extra: dict[str, Any] = {}


class SimulationRequest(BaseModel):
    flowsheet_id: uuid.UUID | None = None
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    property_package: str = "PengRobinson"


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flowsheet_id: uuid.UUID | None = None
    status: str
    results: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
