import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


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


_VALID_PROPERTY_PACKAGES = {"PengRobinson", "SRK", "NRTL", "UNIQUAC"}


class ConvergenceSettings(BaseModel):
    max_iter: int = 50
    tolerance: float = 1e-4
    damping: float = 0.5

    @field_validator("max_iter")
    @classmethod
    def validate_max_iter(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError("max_iter must be between 1 and 500")
        return v

    @field_validator("tolerance")
    @classmethod
    def validate_tolerance(cls, v: float) -> float:
        if v < 1e-10 or v > 1.0:
            raise ValueError("tolerance must be between 1e-10 and 1.0")
        return v

    @field_validator("damping")
    @classmethod
    def validate_damping(cls, v: float) -> float:
        if v < 0.01 or v > 1.0:
            raise ValueError("damping must be between 0.01 and 1.0")
        return v


class SimulationRequest(BaseModel):
    flowsheet_id: uuid.UUID | None = None
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    property_package: str = "PengRobinson"
    convergence_settings: ConvergenceSettings | None = None
    simulation_basis: dict[str, Any] | None = None

    @field_validator("property_package")
    @classmethod
    def validate_property_package(cls, v: str) -> str:
        if v not in _VALID_PROPERTY_PACKAGES:
            raise ValueError(
                f"Invalid property_package '{v}'. Must be one of: {', '.join(sorted(_VALID_PROPERTY_PACKAGES))}"
            )
        return v

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(v) > 200:
            raise ValueError(f"Too many nodes ({len(v)}). Maximum is 200.")
        for i, node in enumerate(v):
            if "id" not in node:
                raise ValueError(f"Node at index {i} is missing required 'id' field.")
        return v

    @field_validator("edges")
    @classmethod
    def validate_edges(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(v) > 500:
            raise ValueError(f"Too many edges ({len(v)}). Maximum is 500.")
        for i, edge in enumerate(v):
            if "source" not in edge:
                raise ValueError(f"Edge at index {i} is missing required 'source' field.")
            if "target" not in edge:
                raise ValueError(f"Edge at index {i} is missing required 'target' field.")
        return v


class ParameterVariation(BaseModel):
    node_id: str
    parameter_key: str
    values: list[float]


class BatchSimulationRequest(BaseModel):
    base_nodes: list[dict[str, Any]] = []
    base_edges: list[dict[str, Any]] = []
    property_package: str = "PengRobinson"
    convergence_settings: ConvergenceSettings | None = None
    variations: list[ParameterVariation] = []

    @field_validator("property_package")
    @classmethod
    def validate_property_package(cls, v: str) -> str:
        if v not in _VALID_PROPERTY_PACKAGES:
            raise ValueError(f"Invalid property_package '{v}'. Must be one of: {', '.join(sorted(_VALID_PROPERTY_PACKAGES))}")
        return v


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    flowsheet_id: uuid.UUID | None = None
    status: str
    results: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
