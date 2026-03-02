"""Utility system schemas."""
from pydantic import BaseModel, Field
from typing import Any


class UtilityCost(BaseModel):
    steam_cost: float = Field(default=15.0, description="$/GJ")
    cooling_water_cost: float = Field(default=3.0, description="$/GJ")
    electricity_cost: float = Field(default=0.08, description="$/kWh")
    fuel_gas_cost: float = Field(default=8.0, description="$/GJ")


class UtilityRequest(BaseModel):
    simulation_results: dict[str, Any]
    costs: UtilityCost = Field(default_factory=UtilityCost)
    hours_per_year: float = Field(default=8000.0, ge=1, le=8760)


class EquipmentUtility(BaseModel):
    equipment_id: str
    equipment_name: str
    equipment_type: str
    utility_type: str
    consumption_kw: float = 0.0
    consumption_gj_per_hr: float = 0.0
    hourly_cost: float = 0.0
    annual_cost: float = 0.0


class UtilityResult(BaseModel):
    equipment_utilities: list[EquipmentUtility] = Field(default_factory=list)
    total_heating_kw: float = 0.0
    total_cooling_kw: float = 0.0
    total_power_kw: float = 0.0
    total_hourly_cost: float = 0.0
    total_annual_cost: float = 0.0
    summary_by_type: dict[str, float] = Field(default_factory=dict)
    status: str = "success"
    error: str | None = None
