"""Control valve sizing schemas (ISA 60534)."""
from pydantic import BaseModel, Field


class ControlValveRequest(BaseModel):
    phase: str = Field(default="liquid", pattern="^(liquid|gas)$")
    valve_type: str = Field(default="globe", pattern="^(globe|butterfly|ball)$")
    # Common inputs
    inlet_pressure: float = Field(..., gt=0, description="kPa")
    outlet_pressure: float = Field(..., gt=0, description="kPa")
    temperature: float = Field(default=25.0, description="°C")
    # Liquid inputs
    volumetric_flow: float = Field(default=0.0, ge=0, description="m³/hr")
    specific_gravity: float = Field(default=1.0, gt=0)
    vapor_pressure: float = Field(default=0.0, ge=0, description="kPa")
    critical_pressure: float = Field(default=22064.0, gt=0, description="kPa")
    # Gas inputs
    mass_flow_rate: float = Field(default=0.0, ge=0, description="kg/hr")
    molecular_weight: float = Field(default=28.97, gt=0, description="g/mol")
    compressibility: float = Field(default=1.0, gt=0)
    k_ratio: float = Field(default=1.4, gt=1, le=2.0, description="Cp/Cv")
    # Pipe
    pipe_diameter: float = Field(default=0.1, gt=0, description="m")


class ControlValveResult(BaseModel):
    calculated_cv: float = 0.0
    selected_cv: float = 0.0
    percent_open: float = 0.0
    choked: bool = False
    choked_dp_kpa: float = 0.0
    fl: float = 0.0
    xt: float = 0.0
    fp: float = 1.0
    flow_regime: str = ""
    status: str = "success"
    error: str | None = None
