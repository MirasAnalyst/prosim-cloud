"""Environmental / emissions schemas."""
from pydantic import BaseModel, Field
from typing import Any


class FuelInput(BaseModel):
    fuel_type: str = Field(default="natural_gas", description="natural_gas, fuel_oil, coal, lpg")
    consumption: float = Field(default=0.0, ge=0, description="GJ/hr or auto from simulation")


class EquipmentCounts(BaseModel):
    valves: int = Field(default=0, ge=0)
    pumps: int = Field(default=0, ge=0)
    compressors: int = Field(default=0, ge=0)
    flanges: int = Field(default=0, ge=0)
    connectors: int = Field(default=0, ge=0)
    open_ended_lines: int = Field(default=0, ge=0)


class EmissionsRequest(BaseModel):
    simulation_results: dict[str, Any] | None = None
    fuel: FuelInput = Field(default_factory=FuelInput)
    equipment_counts: EquipmentCounts = Field(default_factory=EquipmentCounts)
    carbon_price: float = Field(default=50.0, ge=0, description="$/tonne CO2e")
    hours_per_year: float = Field(default=8000.0, ge=1, le=8760)


class EmissionsResult(BaseModel):
    combustion_co2_tpy: float = 0.0
    combustion_nox_tpy: float = 0.0
    combustion_sox_tpy: float = 0.0
    combustion_co_tpy: float = 0.0
    combustion_pm_tpy: float = 0.0
    fugitive_voc_tpy: float = 0.0
    fugitive_methane_tpy: float = 0.0
    total_co2e_tpy: float = 0.0
    carbon_cost_annual: float = 0.0
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "success"
    error: str | None = None
