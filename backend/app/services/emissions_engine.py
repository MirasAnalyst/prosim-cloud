"""Environmental / emissions calculation engine.

Uses EPA AP-42 emission factors and IPCC AR5 GWP factors.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# EPA AP-42 emission factors per GJ of fuel burned
# {fuel_type: {pollutant: kg/GJ}}
_EMISSION_FACTORS = {
    "natural_gas": {
        "CO2": 56.1,    # kg/GJ
        "NOx": 0.040,
        "SOx": 0.0003,
        "CO": 0.018,
        "PM": 0.0012,
    },
    "fuel_oil": {
        "CO2": 77.4,
        "NOx": 0.140,
        "SOx": 0.540,
        "CO": 0.015,
        "PM": 0.010,
    },
    "coal": {
        "CO2": 94.6,
        "NOx": 0.200,
        "SOx": 0.600,
        "CO": 0.090,
        "PM": 0.050,
    },
    "lpg": {
        "CO2": 63.1,
        "NOx": 0.050,
        "SOx": 0.001,
        "CO": 0.020,
        "PM": 0.002,
    },
}

# EPA LDAR fugitive emission factors (kg/hr per component)
_FUGITIVE_FACTORS = {
    "valves": {"voc": 0.00597, "methane": 0.00178},
    "pumps": {"voc": 0.02470, "methane": 0.00885},
    "compressors": {"voc": 0.15040, "methane": 0.05384},
    "flanges": {"voc": 0.00083, "methane": 0.00017},
    "connectors": {"voc": 0.00183, "methane": 0.00044},
    "open_ended_lines": {"voc": 0.00220, "methane": 0.00066},
}

# IPCC AR5 GWP (100-year)
_GWP = {
    "CO2": 1,
    "CH4": 28,
    "N2O": 265,
}


def compute_emissions(
    fuel_type: str = "natural_gas",
    fuel_consumption_gj_hr: float = 0.0,
    equipment_counts: dict[str, int] | None = None,
    carbon_price: float = 50.0,
    hours_per_year: float = 8000.0,
    simulation_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute combustion and fugitive emissions."""

    counts = equipment_counts or {}

    # Auto-detect fuel consumption from simulation if not provided
    if fuel_consumption_gj_hr <= 0 and simulation_results:
        total_heating_kw = _sum_heating_duty(simulation_results)
        fuel_consumption_gj_hr = total_heating_kw * 3.6 / 1000.0  # kW → GJ/hr

    # Auto-count equipment from simulation if counts empty
    if not counts and simulation_results:
        counts = _count_equipment(simulation_results)

    # --- Combustion emissions ---
    factors = _EMISSION_FACTORS.get(fuel_type, _EMISSION_FACTORS["natural_gas"])
    combustion = {}
    for pollutant, factor in factors.items():
        kg_per_hr = fuel_consumption_gj_hr * factor
        tpy = kg_per_hr * hours_per_year / 1000.0  # tonnes per year
        combustion[pollutant] = round(tpy, 4)

    # --- Fugitive emissions ---
    fugitive_voc = 0.0
    fugitive_methane = 0.0
    for comp_type, count in counts.items():
        if count <= 0:
            continue
        ff = _FUGITIVE_FACTORS.get(comp_type, {})
        voc_rate = ff.get("voc", 0)
        ch4_rate = ff.get("methane", 0)
        fugitive_voc += count * voc_rate * hours_per_year / 1000.0
        fugitive_methane += count * ch4_rate * hours_per_year / 1000.0

    # --- CO2e calculation ---
    co2e = combustion.get("CO2", 0)
    co2e += fugitive_methane * _GWP["CH4"]
    carbon_cost = co2e * carbon_price

    # Breakdown
    breakdown = [
        {"source": "Combustion CO2", "tonnes_per_year": combustion.get("CO2", 0)},
        {"source": "Combustion NOx", "tonnes_per_year": combustion.get("NOx", 0)},
        {"source": "Combustion SOx", "tonnes_per_year": combustion.get("SOx", 0)},
        {"source": "Combustion CO", "tonnes_per_year": combustion.get("CO", 0)},
        {"source": "Combustion PM", "tonnes_per_year": combustion.get("PM", 0)},
        {"source": "Fugitive VOC", "tonnes_per_year": round(fugitive_voc, 4)},
        {"source": "Fugitive CH4", "tonnes_per_year": round(fugitive_methane, 4)},
    ]

    return {
        "combustion_co2_tpy": combustion.get("CO2", 0),
        "combustion_nox_tpy": combustion.get("NOx", 0),
        "combustion_sox_tpy": combustion.get("SOx", 0),
        "combustion_co_tpy": combustion.get("CO", 0),
        "combustion_pm_tpy": combustion.get("PM", 0),
        "fugitive_voc_tpy": round(fugitive_voc, 4),
        "fugitive_methane_tpy": round(fugitive_methane, 4),
        "total_co2e_tpy": round(co2e, 2),
        "carbon_cost_annual": round(carbon_cost, 2),
        "breakdown": breakdown,
        "status": "success",
    }


def _sum_heating_duty(sim_results: dict) -> float:
    """Sum positive duties from simulation."""
    eq = sim_results.get("equipment_results", sim_results.get("results", {}).get("equipment_results", {}))
    total = 0.0
    for data in eq.values():
        if isinstance(data, str):
            continue
        d = data.get("duty")
        if d is not None and float(d) > 0:
            total += float(d)
    return total


def _count_equipment(sim_results: dict) -> dict[str, int]:
    """Auto-count equipment types for fugitive estimate."""
    eq = sim_results.get("equipment_results", sim_results.get("results", {}).get("equipment_results", {}))
    counts: dict[str, int] = {"valves": 0, "pumps": 0, "compressors": 0, "flanges": 0}
    for data in eq.values():
        if isinstance(data, str):
            continue
        t = str(data.get("type", "")).lower()
        if "valve" in t:
            counts["valves"] += 1
        elif "pump" in t:
            counts["pumps"] += 1
        elif "compressor" in t:
            counts["compressors"] += 1
        # Estimate flanges: 4 per equipment
        counts["flanges"] += 4
    return counts
