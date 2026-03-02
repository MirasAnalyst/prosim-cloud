"""Utility system modeling engine."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default utility costs
DEFAULT_COSTS = {
    "steam": 15.0,        # $/GJ
    "cooling_water": 3.0, # $/GJ
    "electricity": 0.08,  # $/kWh
    "fuel_gas": 8.0,      # $/GJ
}


def compute_utilities(
    simulation_results: dict[str, Any],
    costs: dict[str, float] | None = None,
    hours_per_year: float = 8000.0,
) -> dict[str, Any]:
    """Extract duties/power from simulation results, categorize, and cost."""
    cost_cfg = {**DEFAULT_COSTS, **(costs or {})}

    eq_results = simulation_results.get("equipment_results",
                  simulation_results.get("results", {}).get("equipment_results", {}))

    equipment_utilities = []
    total_heating = 0.0
    total_cooling = 0.0
    total_power = 0.0

    for eq_id, eq_data in eq_results.items():
        if isinstance(eq_data, str):
            continue

        eq_type = eq_data.get("type", eq_data.get("equipmentType", ""))
        eq_name = eq_data.get("name", eq_id[:8])
        duty = eq_data.get("duty")
        work = eq_data.get("work")

        if duty is not None:
            duty_val = float(duty)
            if abs(duty_val) < 0.001:
                continue

            if duty_val > 0:
                # Heating duty → steam
                util_type = "Steam"
                consumption_kw = duty_val
                gj_per_hr = consumption_kw * 3.6 / 1000.0  # kW → GJ/hr
                hourly_cost = gj_per_hr * cost_cfg.get("steam", 15.0)
                total_heating += consumption_kw
            else:
                # Cooling duty → cooling water
                util_type = "Cooling Water"
                consumption_kw = abs(duty_val)
                gj_per_hr = consumption_kw * 3.6 / 1000.0
                hourly_cost = gj_per_hr * cost_cfg.get("cooling_water", 3.0)
                total_cooling += consumption_kw

            equipment_utilities.append({
                "equipment_id": eq_id,
                "equipment_name": eq_name,
                "equipment_type": eq_type,
                "utility_type": util_type,
                "consumption_kw": round(consumption_kw, 2),
                "consumption_gj_per_hr": round(gj_per_hr, 4),
                "hourly_cost": round(hourly_cost, 2),
                "annual_cost": round(hourly_cost * hours_per_year, 2),
            })

        if work is not None:
            work_val = float(work)
            if abs(work_val) < 0.001:
                continue

            util_type = "Electricity"
            consumption_kw = abs(work_val)
            hourly_cost = consumption_kw * cost_cfg.get("electricity", 0.08)
            total_power += consumption_kw

            equipment_utilities.append({
                "equipment_id": eq_id,
                "equipment_name": eq_name,
                "equipment_type": eq_type,
                "utility_type": util_type,
                "consumption_kw": round(consumption_kw, 2),
                "consumption_gj_per_hr": round(consumption_kw * 3.6 / 1000.0, 4),
                "hourly_cost": round(hourly_cost, 2),
                "annual_cost": round(hourly_cost * hours_per_year, 2),
            })

    # Summary by type
    summary: dict[str, float] = {}
    for eu in equipment_utilities:
        t = eu["utility_type"]
        summary[t] = summary.get(t, 0) + eu["annual_cost"]

    total_hourly = sum(eu["hourly_cost"] for eu in equipment_utilities)
    total_annual = sum(eu["annual_cost"] for eu in equipment_utilities)

    return {
        "equipment_utilities": equipment_utilities,
        "total_heating_kw": round(total_heating, 2),
        "total_cooling_kw": round(total_cooling, 2),
        "total_power_kw": round(total_power, 2),
        "total_hourly_cost": round(total_hourly, 2),
        "total_annual_cost": round(total_annual, 2),
        "summary_by_type": {k: round(v, 2) for k, v in summary.items()},
        "status": "success",
    }
