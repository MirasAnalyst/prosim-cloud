"""Dynamic simulation schemas."""
from pydantic import BaseModel, Field
from typing import Any


class DynamicDisturbance(BaseModel):
    node_id: str
    parameter_key: str
    step_size: float
    description: str = ""


class DynamicOutput(BaseModel):
    node_id: str
    result_key: str
    label: str = ""


class DynamicRequest(BaseModel):
    base_nodes: list[dict[str, Any]]
    base_edges: list[dict[str, Any]]
    property_package: str = "PengRobinson"
    simulation_basis: dict[str, Any] | None = None
    disturbances: list[DynamicDisturbance]
    tracked_outputs: list[DynamicOutput]
    time_horizon: float = Field(default=3600.0, ge=1, le=86400, description="seconds")
    time_steps: int = Field(default=50, ge=5, le=500)
    equipment_volumes: dict[str, float] = Field(default_factory=dict, description="node_id → volume m³")


class DynamicResult(BaseModel):
    time_values: list[float]
    output_trajectories: dict[str, list[float | None]]
    steady_state_initial: dict[str, float | None] = Field(default_factory=dict)
    steady_state_final: dict[str, float | None] = Field(default_factory=dict)
    status: str = "success"
    error: str | None = None
