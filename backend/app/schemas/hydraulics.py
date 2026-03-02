"""Pipe hydraulics schemas."""
from pydantic import BaseModel, Field


class HydraulicsRequest(BaseModel):
    # Fluid properties
    mass_flow_rate: float = Field(..., gt=0, description="kg/s")
    density: float = Field(..., gt=0, description="kg/m³")
    viscosity: float = Field(default=0.001, gt=0, description="Pa·s")
    phase: str = Field(default="liquid", pattern="^(liquid|gas|two_phase)$")
    # Gas-only (for two-phase Lockhart-Martinelli)
    gas_density: float = Field(default=1.2, gt=0, description="kg/m³")
    gas_viscosity: float = Field(default=1.8e-5, gt=0, description="Pa·s")
    gas_mass_fraction: float = Field(default=0.0, ge=0, le=1)
    # Pipe geometry
    length: float = Field(default=100.0, gt=0, description="m")
    diameter: float = Field(default=0.1, gt=0, description="m (inner)")
    roughness: float = Field(default=0.000045, ge=0, description="m (absolute)")
    elevation: float = Field(default=0.0, description="m (positive = uphill)")
    # Fittings (equivalent lengths)
    elbows_90: int = Field(default=0, ge=0)
    elbows_45: int = Field(default=0, ge=0)
    tees: int = Field(default=0, ge=0)
    gate_valves: int = Field(default=0, ge=0)
    globe_valves: int = Field(default=0, ge=0)
    check_valves: int = Field(default=0, ge=0)


class HydraulicsResult(BaseModel):
    pressure_drop_kpa: float = 0.0
    pressure_drop_friction_kpa: float = 0.0
    pressure_drop_elevation_kpa: float = 0.0
    pressure_drop_fittings_kpa: float = 0.0
    velocity_m_s: float = 0.0
    reynolds_number: float = 0.0
    friction_factor: float = 0.0
    flow_regime: str = ""
    erosional_velocity_m_s: float = 0.0
    erosional_ratio: float = 0.0
    erosional_ok: bool = True
    equivalent_length_m: float = 0.0
    status: str = "success"
    error: str | None = None
