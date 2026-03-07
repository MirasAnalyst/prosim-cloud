"""Integrated cost estimation — CAPEX/OPEX with CEPCI adjustment and project economics.

Extends equipment-level costing to full plant cost estimation using
factorial (Lang factor) and detailed module methods.  Includes NPV/IRR
project economics for investment appraisal.

References:
  - Turton et al., "Analysis, Synthesis and Design of Chemical Processes" (5th ed)
  - Seider et al., "Product and Process Design Principles" (4th ed)
  - CEPCI (Chemical Engineering Plant Cost Index) for year adjustment
"""

import logging
import math
from typing import Any

try:
    from scipy.optimize import brentq as _brentq  # type: ignore[import-untyped]
    _scipy_available = True
except ImportError:
    _brentq = None  # type: ignore[assignment]
    _scipy_available = False

logger = logging.getLogger(__name__)

# CEPCI values for cost scaling (base year 2019 = 607.5)
CEPCI_VALUES: dict[int, float] = {
    2000: 394.1,
    2005: 468.2,
    2010: 550.8,
    2015: 556.8,
    2018: 603.1,
    2019: 607.5,
    2020: 596.2,
    2021: 708.0,
    2022: 816.0,
    2023: 797.9,
    2024: 810.0,
    2025: 825.0,
}

# Material factors (relative to carbon steel = 1.0)
MATERIAL_FACTORS: dict[str, float] = {
    "carbon_steel": 1.0,
    "stainless_304": 1.7,
    "stainless_316": 2.1,
    "monel": 3.2,
    "inconel": 3.8,
    "nickel": 3.5,
    "titanium": 4.5,
    "hastelloy": 4.0,
    "copper": 1.3,
    "aluminum": 1.2,
}

# Pressure factors (simplified — actual uses chart from Turton)
def _pressure_factor(P_barg: float) -> float:
    """Bare module pressure factor (Turton Table A.2)."""
    if P_barg <= 5:
        return 1.0
    if P_barg <= 10:
        return 1.1
    if P_barg <= 20:
        return 1.3
    if P_barg <= 50:
        return 1.5
    if P_barg <= 100:
        return 1.9
    return 2.5


def estimate_equipment_cost(
    equipment_type: str,
    capacity_param: float,
    capacity_unit: str = "",
    material: str = "carbon_steel",
    pressure_barg: float = 5.0,
    year: int = 2024,
    base_year: int = 2019,
) -> dict[str, Any]:
    """Estimate purchased equipment cost using Turton/Seider correlations.

    Args:
        equipment_type: pump, compressor, heat_exchanger, column, vessel, reactor
        capacity_param: sizing parameter (area m², power kW, volume m³, etc.)
        capacity_unit: unit description for the parameter
        material: material of construction
        pressure_barg: design pressure (barg)
        year: target cost year
        base_year: correlation base year

    Returns:
        {purchased_cost, bare_module_cost, material_factor, pressure_factor, cepci_ratio}
    """
    if capacity_param <= 0:
        return {"status": "error", "error": "Capacity parameter must be > 0"}

    # Base purchased cost from Turton correlations (log10(Cp0) = K1 + K2*log10(A) + K3*(log10(A))^2)
    correlations: dict[str, tuple[float, float, float, str]] = {
        "pump": (3.3892, 0.0536, 0.1538, "power_kW"),
        "compressor": (2.2891, 1.3604, -0.1027, "power_kW"),
        "heat_exchanger": (4.3247, -0.3030, 0.1634, "area_m2"),
        "column": (3.4974, 0.4485, 0.1074, "volume_m3"),
        "vessel": (3.4974, 0.4485, 0.1074, "volume_m3"),
        "reactor": (4.1052, 0.5320, -0.0005, "volume_m3"),
        "tower": (3.4974, 0.4485, 0.1074, "volume_m3"),
        "drum": (3.5565, 0.3776, 0.0905, "volume_m3"),
        "heater": (4.3247, -0.3030, 0.1634, "area_m2"),
        "cooler": (4.3247, -0.3030, 0.1634, "area_m2"),
        "separator": (3.4974, 0.4485, 0.1074, "volume_m3"),
        "filter": (3.300, 0.400, 0.100, "area_m2"),
        "dryer": (4.000, 0.500, 0.050, "area_m2"),
        "crystallizer": (3.800, 0.450, 0.080, "volume_m3"),
        "cyclone": (3.200, 0.350, 0.120, "flow_m3_s"),
    }

    corr = correlations.get(equipment_type.lower())
    if corr is None:
        # Fallback: use vessel correlation
        corr = correlations["vessel"]

    K1, K2, K3 = corr[0], corr[1], corr[2]

    log_A = math.log10(max(capacity_param, 0.01))
    log_Cp0 = K1 + K2 * log_A + K3 * log_A ** 2
    Cp0 = 10 ** log_Cp0

    # Normalize material name (accept common aliases like SS316, CS, etc.)
    _MATERIAL_ALIASES: dict[str, str] = {
        "ss316": "stainless_316", "ss316l": "stainless_316",
        "ss304": "stainless_304", "ss304l": "stainless_304",
        "cs": "carbon_steel", "carbon steel": "carbon_steel",
        "stainless 316": "stainless_316", "stainless 304": "stainless_304",
        "monel 400": "monel", "inconel 625": "inconel",
        "hastelloy c": "hastelloy", "hastelloy c276": "hastelloy",
        "ti": "titanium", "cu": "copper", "al": "aluminum",
    }
    material_key = _MATERIAL_ALIASES.get(material.lower(), material.lower())

    # Material and pressure factors
    Fm = MATERIAL_FACTORS.get(material_key, 1.0)
    Fp = _pressure_factor(pressure_barg)

    # Bare module factor (Turton Eq. 22.11)
    B1, B2 = 1.89, 1.35  # Default for process vessels
    if equipment_type.lower() in ("pump",):
        B1, B2 = 1.89, 1.35
    elif equipment_type.lower() in ("compressor",):
        B1, B2 = 1.0, 1.8  # Turton Table A.4 — FBM ≈ 2.8 for CS compressor
        Fm = 1.0  # Material already in base cost for compressors
    elif equipment_type.lower() in ("heat_exchanger", "heater", "cooler"):
        B1, B2 = 1.63, 1.66

    Cbm = Cp0 * (B1 + B2 * Fm * Fp)

    # CEPCI adjustment
    cepci_target = CEPCI_VALUES.get(year, 810.0)
    cepci_base = CEPCI_VALUES.get(base_year, 607.5)
    cepci_ratio = cepci_target / cepci_base

    Cp0_adj = Cp0 * cepci_ratio
    Cbm_adj = Cbm * cepci_ratio

    return {
        "status": "success",
        "equipment_type": equipment_type,
        "capacity_param": capacity_param,
        "capacity_unit": capacity_unit or corr[3],
        "purchased_cost_usd": round(Cp0_adj, 0),
        "bare_module_cost_usd": round(Cbm_adj, 0),
        "material": material,
        "material_factor": Fm,
        "pressure_factor": Fp,
        "cepci_ratio": round(cepci_ratio, 4),
        "cost_year": year,
    }


def estimate_plant_cost(
    equipment_costs: list[dict[str, Any]],
    method: str = "lang",
    lang_factor: float = 4.74,
    year: int = 2024,
    working_capital_pct: float = 0.15,
    contingency_pct: float = 0.15,
) -> dict[str, Any]:
    """Estimate total plant cost from equipment costs.

    Args:
        equipment_costs: list of equipment cost dicts from estimate_equipment_cost()
        method: "lang" (quick) or "module" (detailed bare module)
        lang_factor: Lang factor (3.1 solids, 4.74 fluids, 3.63 mixed)
        year: cost year
        working_capital_pct: working capital as fraction of fixed capital
        contingency_pct: contingency as fraction of bare module total

    Returns:
        {total_capital, fixed_capital, working_capital, total_bare_module, ...}
    """
    if not equipment_costs:
        return {"status": "error", "error": "No equipment costs provided"}

    if method == "lang":
        total_purchased = sum(e.get("purchased_cost_usd", 0) for e in equipment_costs)
        fixed_capital = total_purchased * lang_factor
        total_bare_module = fixed_capital  # Lang method approximation
    else:
        # Module method: sum bare module costs
        total_bare_module = sum(e.get("bare_module_cost_usd", 0) for e in equipment_costs)
        total_purchased = sum(e.get("purchased_cost_usd", 0) for e in equipment_costs)
        fixed_capital = total_bare_module * (1 + contingency_pct)

    working_capital = fixed_capital * working_capital_pct
    total_capital = fixed_capital + working_capital

    return {
        "status": "success",
        "method": method,
        "n_equipment": len(equipment_costs),
        "total_purchased_cost_usd": round(total_purchased, 0),
        "total_bare_module_cost_usd": round(total_bare_module, 0),
        "fixed_capital_investment_usd": round(fixed_capital, 0),
        "working_capital_usd": round(working_capital, 0),
        "total_capital_investment_usd": round(total_capital, 0),
        "contingency_pct": contingency_pct * 100,
        "lang_factor": lang_factor if method == "lang" else None,
        "cost_year": year,
    }


def estimate_operating_cost(
    utilities: dict[str, Any],
    raw_materials: list[dict[str, Any]] | None = None,
    n_operators: int = 4,
    operator_salary_usd: float = 75000,
    maintenance_pct: float = 0.06,
    fixed_capital_usd: float = 0,
    operating_hours: float = 8000,
) -> dict[str, Any]:
    """Estimate annual operating cost.

    Args:
        utilities: {electricity_kW, steam_kg_s, cooling_water_m3_s, fuel_gas_MW}
        raw_materials: [{name, flow_kg_s, cost_usd_per_kg}]
        n_operators: number of operators per shift
        operator_salary_usd: annual salary per operator
        maintenance_pct: maintenance as fraction of fixed capital
        fixed_capital_usd: for maintenance calculation
        operating_hours: hours per year

    Returns:
        {total_opex, utility_cost, raw_material_cost, labor_cost, maintenance_cost}
    """
    # Utility costs (typical US Gulf Coast 2024 prices)
    utility_prices = {
        "electricity_kW": 0.07,       # $/kWh
        "steam_kg_s": 0.015,          # $/kg (MP steam)
        "cooling_water_m3_s": 0.02,   # $/m³
        "fuel_gas_MW": 4.0,           # $/GJ (rate in MW × 3.6 GJ/MWh = GJ/hr)
        "refrigeration_kW": 0.12,     # $/kWh (mechanical refrigeration)
    }

    # Unit conversion factors: rate units → per-hour basis
    # electricity_kW: kW * $/kWh * hours = $
    # steam_kg_s: kg/s * 3600 s/hr * $/kg * hours = $
    # cooling_water_m3_s: m3/s * 3600 s/hr * $/m3 * hours = $
    # fuel_gas_MW: MW * 3.6 GJ/MWh * $/GJ * hours = $
    # refrigeration_kW: kW * $/kWh * hours = $
    rate_to_hourly = {
        "electricity_kW": 1.0,          # already per hour (kWh)
        "steam_kg_s": 3600.0,           # kg/s → kg/hr
        "cooling_water_m3_s": 3600.0,   # m3/s → m3/hr
        "fuel_gas_MW": 3.6,             # MW → GJ/hr
        "refrigeration_kW": 1.0,        # already per hour (kWh)
    }

    utility_cost = 0.0
    utility_breakdown = {}
    for util_type, rate in utilities.items():
        if rate and rate > 0 and util_type in utility_prices:
            hourly_factor = rate_to_hourly.get(util_type, 1.0)
            annual = rate * hourly_factor * utility_prices[util_type] * operating_hours
            utility_cost += annual
            utility_breakdown[util_type] = round(annual, 0)

    # Raw materials
    raw_material_cost = 0.0
    if raw_materials:
        for rm in raw_materials:
            flow = rm.get("flow_kg_s", 0)
            price = rm.get("cost_usd_per_kg", 0)
            annual = flow * price * 3600 * operating_hours
            raw_material_cost += annual

    # Labor (Turton: 4.5 shifts per position × n_operators)
    labor_cost = n_operators * 4.5 * operator_salary_usd

    # Maintenance
    maintenance_cost = fixed_capital_usd * maintenance_pct

    # Overhead and general (simplified)
    overhead = 0.6 * labor_cost + 0.01 * fixed_capital_usd

    total_opex = utility_cost + raw_material_cost + labor_cost + maintenance_cost + overhead

    return {
        "status": "success",
        "total_opex_usd_yr": round(total_opex, 0),
        "utility_cost_usd_yr": round(utility_cost, 0),
        "utility_breakdown": utility_breakdown,
        "raw_material_cost_usd_yr": round(raw_material_cost, 0),
        "labor_cost_usd_yr": round(labor_cost, 0),
        "maintenance_cost_usd_yr": round(maintenance_cost, 0),
        "overhead_usd_yr": round(overhead, 0),
        "operating_hours": operating_hours,
        "n_operators": n_operators,
    }


# ---------------------------------------------------------------------------
# MACRS depreciation schedules (IRS Publication 946)
# ---------------------------------------------------------------------------

_MACRS_SCHEDULES: dict[int, list[float]] = {
    3: [0.3333, 0.4445, 0.1481, 0.0741],
    5: [0.2000, 0.3200, 0.1920, 0.1152, 0.1152, 0.0576],
    7: [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.0446],
    10: [0.1000, 0.1800, 0.1440, 0.1152, 0.0922, 0.0737, 0.0655, 0.0655, 0.0656, 0.0655, 0.0328],
    15: [0.0500, 0.0950, 0.0855, 0.0770, 0.0693, 0.0623, 0.0590, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0295],
}


def _depreciation_schedule(
    capex: float,
    project_life: int,
    method: str = "MACRS",
    macrs_class: int = 7,
) -> list[float]:
    """Generate annual depreciation amounts.

    Args:
        capex: Total depreciable capital ($)
        project_life: Project life (years)
        method: "MACRS" or "straight_line"
        macrs_class: MACRS property class (3, 5, 7, 10, or 15 years)

    Returns:
        List of annual depreciation amounts (length = project_life)
    """
    if method.upper() == "MACRS":
        schedule = _MACRS_SCHEDULES.get(macrs_class, _MACRS_SCHEDULES[7])
        deps = [capex * rate for rate in schedule]
        # Pad or truncate to project_life
        if len(deps) < project_life:
            deps.extend([0.0] * (project_life - len(deps)))
        return deps[:project_life]
    else:
        # Straight-line
        annual = capex / project_life if project_life > 0 else 0.0
        return [annual] * project_life


def compute_project_economics(
    capex: float,
    annual_revenue: float,
    annual_opex: float,
    project_life: int = 20,
    discount_rate: float = 0.10,
    tax_rate: float = 0.25,
    depreciation_method: str = "MACRS",
    macrs_class: int = 7,
    salvage_value: float = 0.0,
    working_capital: float = 0.0,
) -> dict[str, Any]:
    """Compute project economics: NPV, IRR, payback period, profitability index.

    Cash flow model (per year t):
        EBITDA = Revenue - OPEX
        Taxable_income = EBITDA - Depreciation
        Tax = max(0, Taxable_income * tax_rate)
        Net_cash_flow = EBITDA - Tax

    Year 0: -CAPEX - Working_capital
    Year N (last): +Salvage + Working_capital recovery

    Args:
        capex: Total capital expenditure ($)
        annual_revenue: Annual revenue ($)
        annual_opex: Annual operating expenditure ($)
        project_life: Project duration (years)
        discount_rate: Discount rate for NPV (e.g. 0.10 for 10%)
        tax_rate: Corporate tax rate (e.g. 0.25 for 25%)
        depreciation_method: "MACRS" or "straight_line"
        macrs_class: MACRS property class (3, 5, 7, 10, 15)
        salvage_value: End-of-life salvage value ($)
        working_capital: Working capital invested at year 0, recovered at end ($)

    Returns:
        Dict with NPV, IRR, payback_period, discounted_payback, profitability_index,
        annual_cash_flows, cumulative_cash_flows.
    """
    if project_life < 1:
        return {"status": "error", "error": "Project life must be >= 1 year"}
    if capex <= 0:
        return {"status": "error", "error": "CAPEX must be > 0"}

    # Depreciation schedule
    dep_schedule = _depreciation_schedule(capex, project_life, depreciation_method, macrs_class)

    # Build cash flows
    cash_flows: list[float] = []
    # Year 0: investment
    cf_0 = -capex - working_capital
    cash_flows.append(cf_0)

    ebitda = annual_revenue - annual_opex

    for t in range(1, project_life + 1):
        depreciation_t = dep_schedule[t - 1]
        taxable_income = ebitda - depreciation_t
        tax = max(0.0, taxable_income * tax_rate)
        ncf = ebitda - tax

        # Last year: add salvage and working capital recovery
        if t == project_life:
            ncf += salvage_value + working_capital

        cash_flows.append(ncf)

    # NPV calculation
    npv = sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cash_flows))

    # IRR calculation using scipy.optimize.brentq
    irr = None
    if _scipy_available and _brentq is not None:
        def npv_at_rate(r: float) -> float:
            if r <= -1.0:
                return 1e15
            return sum(cf / (1.0 + r) ** t for t, cf in enumerate(cash_flows))

        try:
            irr = _brentq(npv_at_rate, -0.5, 10.0, xtol=1e-8, maxiter=200)
        except (ValueError, RuntimeError):
            # Try narrower range
            try:
                irr = _brentq(npv_at_rate, -0.3, 5.0, xtol=1e-8, maxiter=200)
            except Exception:
                irr = None
    else:
        # Manual bisection fallback
        def npv_at_rate(r: float) -> float:
            if r <= -1.0:
                return 1e15
            return sum(cf / (1.0 + r) ** t for t, cf in enumerate(cash_flows))

        lo, hi = -0.5, 10.0
        try:
            if npv_at_rate(lo) * npv_at_rate(hi) < 0:
                for _ in range(100):
                    mid = (lo + hi) / 2.0
                    if npv_at_rate(mid) > 0:
                        lo = mid
                    else:
                        hi = mid
                irr = (lo + hi) / 2.0
        except Exception:
            pass

    # Payback period (simple — undiscounted)
    cumulative = [cash_flows[0]]
    for i in range(1, len(cash_flows)):
        cumulative.append(cumulative[-1] + cash_flows[i])

    payback = None
    for t in range(1, len(cumulative)):
        if cumulative[t] >= 0 and cumulative[t - 1] < 0:
            # Linear interpolation within the year
            frac = -cumulative[t - 1] / (cumulative[t] - cumulative[t - 1]) if cumulative[t] != cumulative[t - 1] else 0
            payback = (t - 1) + frac
            break

    # Discounted payback
    disc_cumulative = [cash_flows[0]]
    for t in range(1, len(cash_flows)):
        disc_cf = cash_flows[t] / (1.0 + discount_rate) ** t
        disc_cumulative.append(disc_cumulative[-1] + disc_cf)

    disc_payback = None
    for t in range(1, len(disc_cumulative)):
        if disc_cumulative[t] >= 0 and disc_cumulative[t - 1] < 0:
            frac = -disc_cumulative[t - 1] / (disc_cumulative[t] - disc_cumulative[t - 1]) if disc_cumulative[t] != disc_cumulative[t - 1] else 0
            disc_payback = (t - 1) + frac
            break

    # Profitability index: PI = (NPV + CAPEX) / CAPEX = PV of future CFs / CAPEX
    pv_future = sum(cf / (1.0 + discount_rate) ** t for t, cf in enumerate(cash_flows) if t > 0)
    pi = pv_future / capex if capex > 0 else 0.0

    return {
        "status": "success",
        "NPV_usd": round(npv, 2),
        "IRR": round(irr, 6) if irr is not None else None,
        "IRR_pct": round(irr * 100, 2) if irr is not None else None,
        "payback_years": round(payback, 2) if payback is not None else None,
        "discounted_payback_years": round(disc_payback, 2) if disc_payback is not None else None,
        "profitability_index": round(pi, 4),
        "annual_cash_flows": [round(cf, 2) for cf in cash_flows],
        "cumulative_cash_flows": [round(c, 2) for c in cumulative],
        "depreciation_schedule": [round(d, 2) for d in dep_schedule],
        "depreciation_method": depreciation_method,
        "discount_rate": discount_rate,
        "tax_rate": tax_rate,
        "project_life_years": project_life,
    }
