"""Relief valve sizing engine — API 520/521/526."""
import math
import logging

logger = logging.getLogger(__name__)

# API 526 standard orifice sizes (letter → area in mm²)
_ORIFICE_TABLE = [
    ("D", 71.0),
    ("E", 126.0),
    ("F", 198.0),
    ("G", 325.0),
    ("H", 506.0),
    ("J", 830.0),
    ("K", 1186.0),
    ("L", 1841.0),
    ("M", 2323.0),
    ("N", 2800.0),
    ("P", 4116.0),
    ("Q", 7126.0),
    ("R", 10323.0),
    ("T", 16774.0),
]


def size_relief_valve(
    phase: str = "gas",
    scenario: str = "blocked_outlet",
    set_pressure: float = 1000.0,
    backpressure: float = 101.325,
    overpressure_pct: float = 10.0,
    mass_flow_rate: float = 0.0,
    molecular_weight: float = 28.97,
    temperature: float = 25.0,
    compressibility: float = 1.0,
    k_ratio: float = 1.4,
    volumetric_flow: float = 0.0,
    specific_gravity: float = 1.0,
    viscosity: float = 1.0,
    wetted_area: float = 0.0,
    insulation_factor: float = 1.0,
    latent_heat: float = 200.0,
    kd: float = 0.975,
    kb: float = 1.0,
    kc: float = 1.0,
) -> dict:
    """Size a relief valve per API 520/521.

    Returns required area, selected orifice, and related info.
    """
    # Relieving pressure = set pressure * (1 + overpressure%)
    p1_kpa = set_pressure * (1.0 + overpressure_pct / 100.0)
    p1_pa = p1_kpa * 1000.0  # Pa
    pb_pa = backpressure * 1000.0

    required_area_m2 = 0.0
    flow_kg_hr = mass_flow_rate

    if scenario == "fire":
        # API 521 fire case: Q = 21000 * F * A_w^0.82 (BTU/hr), convert to kW
        # F = insulation_factor, A_w = wetted area (ft²)
        a_w_ft2 = wetted_area * 10.7639  # m² → ft²
        q_btu_hr = 21000.0 * insulation_factor * (a_w_ft2 ** 0.82)
        q_kw = q_btu_hr * 0.000293071  # BTU/hr → kW
        # Mass flow from latent heat
        flow_kg_hr = (q_kw * 3600.0) / max(latent_heat, 1.0)  # kg/hr
        mass_flow_rate = flow_kg_hr

    if phase == "gas":
        required_area_m2 = _size_gas(
            W=mass_flow_rate, T_C=temperature, Z=compressibility,
            M=molecular_weight, k=k_ratio, P1=p1_pa,
            Kd=kd, Kb=kb, Kc=kc,
        )
    elif phase == "liquid":
        dp_pa = p1_pa - pb_pa
        required_area_m2 = _size_liquid(
            Q_m3hr=volumetric_flow, G=specific_gravity,
            dP=dp_pa, Kd=kd, Kc=kc, mu=viscosity,
        )
    else:
        # Two-phase: use gas sizing with combined flow
        required_area_m2 = _size_gas(
            W=mass_flow_rate, T_C=temperature, Z=compressibility,
            M=molecular_weight, k=k_ratio, P1=p1_pa,
            Kd=kd, Kb=kb, Kc=kc,
        )

    required_area_mm2 = required_area_m2 * 1e6
    required_area_in2 = required_area_mm2 / 645.16

    # Select orifice from API 526
    selected_orifice = ""
    orifice_area = 0.0
    for letter, area_mm2 in _ORIFICE_TABLE:
        if area_mm2 >= required_area_mm2:
            selected_orifice = letter
            orifice_area = area_mm2
            break
    if not selected_orifice and _ORIFICE_TABLE:
        selected_orifice = _ORIFICE_TABLE[-1][0]
        orifice_area = _ORIFICE_TABLE[-1][1]

    return {
        "required_area_mm2": round(required_area_mm2, 2),
        "required_area_in2": round(required_area_in2, 4),
        "selected_orifice": selected_orifice,
        "orifice_area_mm2": orifice_area,
        "relieving_pressure_kpa": round(p1_kpa, 2),
        "mass_flow_kg_hr": round(flow_kg_hr, 2),
        "status": "success",
        "disclaimer": "For preliminary estimation only. Final design must be verified by a qualified engineer per API 520/521.",
    }


def _size_gas(W: float, T_C: float, Z: float, M: float, k: float,
              P1: float, Kd: float, Kb: float, Kc: float) -> float:
    """API 520 gas sizing: A = W*sqrt(T*Z) / (C*Kd*P1*Kb*Kc*sqrt(M))

    W in kg/hr, T in K, P1 in Pa, returns m².
    """
    T_K = T_C + 273.15
    if W <= 0 or P1 <= 0 or M <= 0:
        return 0.0

    # C coefficient from k
    # C = 0.03948 * sqrt(k * (2/(k+1))^((k+1)/(k-1)))  [metric, kg/hr, Pa, K]
    exp = (k + 1.0) / (k - 1.0)
    C = 0.03948 * math.sqrt(k * ((2.0 / (k + 1.0)) ** exp))

    numerator = W * math.sqrt(T_K * Z)
    denominator = C * Kd * P1 * Kb * Kc * math.sqrt(M)
    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _size_liquid(Q_m3hr: float, G: float, dP: float,
                 Kd: float, Kc: float, mu: float) -> float:
    """API 520 liquid sizing: A = Q / (38*Kd*Kw*Kc*sqrt(dP/G))

    Q in m³/hr, dP in Pa, returns m².
    """
    if Q_m3hr <= 0 or dP <= 0:
        return 0.0

    # Kw (viscosity correction, simplified)
    # For Re > 100000, Kw ≈ 1.0
    Kw = 1.0
    if mu > 10:
        Kw = 0.9  # rough correction for viscous fluids
    elif mu > 100:
        Kw = 0.8

    dP_kpa = dP / 1000.0
    denominator = 38.0 * Kd * Kw * Kc * math.sqrt(max(dP_kpa / G, 1e-10))
    if denominator <= 0:
        return 0.0

    # Convert result to m² (formula gives mm² with kPa inputs → convert)
    area_mm2 = Q_m3hr / denominator
    return area_mm2 / 1e6
