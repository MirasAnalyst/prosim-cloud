"""Optimization schemas."""
from pydantic import BaseModel, Field
from typing import Any


class DecisionVariable(BaseModel):
    node_id: str
    parameter_key: str
    min_value: float
    max_value: float
    initial_value: float | None = None


class OptimizationObjective(BaseModel):
    node_id: str
    result_key: str
    sense: str = Field(default="minimize", pattern="^(minimize|maximize)$")


class OptimizationConstraint(BaseModel):
    node_id: str
    result_key: str
    operator: str = Field(..., pattern="^(<=|>=|==)$")
    value: float


class OptimizationRequest(BaseModel):
    base_nodes: list[dict[str, Any]]
    base_edges: list[dict[str, Any]]
    property_package: str = "PengRobinson"
    simulation_basis: dict[str, Any] | None = None
    objective: OptimizationObjective
    decision_variables: list[DecisionVariable]
    constraints: list[OptimizationConstraint] = Field(default_factory=list)
    solver: str = Field(default="SLSQP", pattern="^(SLSQP|differential_evolution)$")
    max_iterations: int = Field(default=100, ge=1, le=1000)


class OptimizationResult(BaseModel):
    optimal_values: dict[str, float] = Field(default_factory=dict)
    objective_value: float | None = None
    constraint_values: dict[str, float] = Field(default_factory=dict)
    convergence_history: list[float] = Field(default_factory=list)
    iterations: int = 0
    status: str = "success"
    message: str = ""
    error: str | None = None
