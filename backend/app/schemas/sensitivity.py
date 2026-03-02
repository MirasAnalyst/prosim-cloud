from typing import Any
from pydantic import BaseModel, field_validator


class SensitivityVariable(BaseModel):
    node_id: str
    parameter_key: str
    min_value: float
    max_value: float
    steps: int = 10

    @field_validator("steps")
    @classmethod
    def validate_steps(cls, v: int) -> int:
        if v < 2 or v > 100:
            raise ValueError("steps must be between 2 and 100")
        return v


class SensitivityOutput(BaseModel):
    node_id: str
    result_key: str  # e.g. "duty", "outlet_temperature", "vapor_fraction"


class SensitivityRequest(BaseModel):
    base_nodes: list[dict[str, Any]] = []
    base_edges: list[dict[str, Any]] = []
    property_package: str = "PengRobinson"
    simulation_basis: dict[str, Any] | None = None
    variable: SensitivityVariable
    outputs: list[SensitivityOutput] = []


class SensitivityResult(BaseModel):
    variable_values: list[float]
    output_values: dict[str, list[float | None]]
    variable_label: str
    status: str = "success"
    error: str | None = None
