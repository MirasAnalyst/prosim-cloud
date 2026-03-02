"""Relief valve sizing schemas (API 520/521/526)."""
from pydantic import BaseModel, Field


class ReliefValveRequest(BaseModel):
    phase: str = Field(default="gas", pattern="^(gas|liquid|two_phase)$")
    scenario: str = Field(default="blocked_outlet", description="blocked_outlet, fire, thermal_expansion")
    # Common inputs
    set_pressure: float = Field(..., gt=0, description="Set pressure kPa")
    backpressure: float = Field(default=101.325, ge=0, description="Backpressure kPa")
    overpressure_pct: float = Field(default=10.0, ge=0, le=21, description="Overpressure %")
    # Gas inputs
    mass_flow_rate: float = Field(default=0.0, ge=0, description="kg/hr")
    molecular_weight: float = Field(default=28.97, gt=0, description="g/mol")
    temperature: float = Field(default=25.0, description="°C")
    compressibility: float = Field(default=1.0, gt=0, le=2)
    k_ratio: float = Field(default=1.4, gt=1, le=2, description="Cp/Cv")
    # Liquid inputs
    volumetric_flow: float = Field(default=0.0, ge=0, description="m³/hr")
    specific_gravity: float = Field(default=1.0, gt=0)
    viscosity: float = Field(default=1.0, gt=0, description="cP")
    # Fire case
    wetted_area: float = Field(default=0.0, ge=0, description="m²")
    insulation_factor: float = Field(default=1.0, ge=0, le=1)
    latent_heat: float = Field(default=200.0, gt=0, description="kJ/kg")
    # Correction factors
    kd: float = Field(default=0.975, gt=0, le=1, description="Discharge coefficient")
    kb: float = Field(default=1.0, gt=0, le=1, description="Backpressure correction")
    kc: float = Field(default=1.0, gt=0, le=1, description="Combination correction")


class ReliefValveResult(BaseModel):
    required_area_mm2: float = 0.0
    required_area_in2: float = 0.0
    selected_orifice: str = ""
    orifice_area_mm2: float = 0.0
    relieving_pressure_kpa: float = 0.0
    mass_flow_kg_hr: float = 0.0
    status: str = "success"
    disclaimer: str = "For preliminary estimation only. Final design must be verified by a qualified engineer per API 520/521."
    error: str | None = None
