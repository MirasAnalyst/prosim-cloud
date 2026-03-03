from typing import Any

from pydantic import BaseModel, Field


class EconomicParams(BaseModel):
    steam_cost: float = 15.0          # $/GJ
    cooling_water_cost: float = 3.0   # $/GJ
    electricity_cost: float = 0.08    # $/kWh
    fuel_gas_cost: float = 8.0        # $/GJ
    carbon_price: float = 50.0        # $/tonne CO2e
    hours_per_year: float = 8000.0


class InsightsRequest(BaseModel):
    simulation_results: dict[str, Any]
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    property_package: str = "PengRobinson"
    economic_params: EconomicParams = Field(default_factory=EconomicParams)


class Insight(BaseModel):
    id: str                              # sequential "INS-01", "INS-02"...
    category: str                        # energy | production | emissions | cost
    equipment_id: str | None = None
    equipment_name: str | None = None
    title: str                           # one-line headline
    description: str                     # detailed explanation + engineering reasoning
    current_value: float | None = None
    suggested_value: float | None = None
    parameter: str | None = None
    unit: str | None = None
    annual_savings_usd: float = 0.0
    co2_reduction_tpy: float = 0.0
    capex_estimate_usd: float = 0.0
    payback_years: float | None = None
    priority: str = "medium"             # critical | high | medium | low
    implementation_type: str = "operational_change"
    # "operational_change" | "minor_modification" | "moderate_project" | "major_project"


class InsightsSummary(BaseModel):
    total_annual_savings: float = 0.0
    total_co2_reduction: float = 0.0
    insight_count: int = 0
    top_quick_wins: list[str] = []       # titles of top 3 by shortest payback
    top_high_impact: list[str] = []      # titles of top 3 by largest savings


class InsightsResult(BaseModel):
    insights: list[Insight] = []
    summary: InsightsSummary = Field(default_factory=InsightsSummary)
    status: str = "success"
    error: str | None = None
