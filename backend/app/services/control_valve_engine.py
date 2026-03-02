"""Control valve sizing engine — ISA 60534."""
import math
import logging

logger = logging.getLogger(__name__)

# Valve coefficients by type: FL (liquid pressure recovery), xT (terminal pressure drop ratio)
_VALVE_COEFF = {
    "globe": {"FL": 0.90, "xT": 0.70},
    "butterfly": {"FL": 0.55, "xT": 0.42},
    "ball": {"FL": 0.60, "xT": 0.55},
}

# Standard Cv sizes
_STANDARD_CV = [
    0.1, 0.2, 0.4, 0.8, 1.0, 1.6, 2.5, 4.0, 6.3, 10.0,
    16.0, 25.0, 40.0, 63.0, 100.0, 160.0, 250.0, 400.0,
    630.0, 1000.0, 1600.0, 2500.0, 4000.0,
]


def size_control_valve(
    phase: str = "liquid",
    valve_type: str = "globe",
    inlet_pressure: float = 500.0,
    outlet_pressure: float = 300.0,
    temperature: float = 25.0,
    volumetric_flow: float = 10.0,
    specific_gravity: float = 1.0,
    vapor_pressure: float = 0.0,
    critical_pressure: float = 22064.0,
    mass_flow_rate: float = 0.0,
    molecular_weight: float = 28.97,
    compressibility: float = 1.0,
    k_ratio: float = 1.4,
    pipe_diameter: float = 0.1,
) -> dict:
    """Size a control valve per ISA 60534."""
    coeffs = _VALVE_COEFF.get(valve_type, _VALVE_COEFF["globe"])
    FL = coeffs["FL"]
    xT = coeffs["xT"]

    dp_kpa = inlet_pressure - outlet_pressure
    if dp_kpa <= 0:
        return {"status": "error", "error": "Inlet pressure must be greater than outlet pressure"}

    # Piping geometry factor Fp (simplified: assume valve = pipe size)
    Fp = 1.0

    choked = False
    choked_dp = 0.0
    calculated_cv = 0.0

    if phase == "liquid":
        calculated_cv, choked, choked_dp = _size_liquid(
            Q=volumetric_flow, Gf=specific_gravity,
            P1=inlet_pressure, P2=outlet_pressure,
            Pv=vapor_pressure, Pc=critical_pressure,
            FL=FL, Fp=Fp,
        )
    else:
        calculated_cv, choked, choked_dp = _size_gas(
            W=mass_flow_rate, M=molecular_weight,
            T1=temperature, Z=compressibility,
            k=k_ratio, P1=inlet_pressure, P2=outlet_pressure,
            xT=xT, Fp=Fp,
        )

    # Select standard Cv
    selected_cv = 0.0
    for cv in _STANDARD_CV:
        if cv >= calculated_cv:
            selected_cv = cv
            break
    if selected_cv == 0 and _STANDARD_CV:
        selected_cv = _STANDARD_CV[-1]

    # Percent open (inherent equal-percentage characteristic)
    percent_open = 0.0
    if selected_cv > 0 and calculated_cv > 0:
        ratio = calculated_cv / selected_cv
        # Equal percentage: Cv/Cv_max = R^(x-1), x = travel fraction
        # Solve for x: x = 1 + ln(ratio)/ln(R), R ≈ 50
        R = 50.0
        if ratio > 0:
            x = 1.0 + math.log(max(ratio, 1e-6)) / math.log(R)
            percent_open = max(0, min(100, x * 100))

    flow_regime = "Choked" if choked else "Normal"

    return {
        "calculated_cv": round(calculated_cv, 4),
        "selected_cv": selected_cv,
        "percent_open": round(percent_open, 1),
        "choked": choked,
        "choked_dp_kpa": round(choked_dp, 2),
        "fl": FL,
        "xt": xT,
        "fp": Fp,
        "flow_regime": flow_regime,
        "status": "success",
    }


def _size_liquid(Q: float, Gf: float, P1: float, P2: float,
                 Pv: float, Pc: float, FL: float, Fp: float) -> tuple[float, bool, float]:
    """ISA 60534 liquid Cv: Cv = Q / (N1*Fp*sqrt(ΔP/Gf))

    Q in m³/hr, pressures in kPa.
    Returns (Cv, choked, choked_dp_kpa).
    """
    N1 = 0.0865  # ISA constant for m³/hr, kPa

    # Choked flow check: ΔP_choked = FL² * (P1 - FF*Pv)
    FF = 0.96 - 0.28 * math.sqrt(max(Pv / max(Pc, 1), 0))
    dp_choked = FL ** 2 * (P1 - FF * Pv)
    dp_actual = P1 - P2

    choked = dp_actual >= dp_choked and dp_choked > 0
    dp_eff = min(dp_actual, dp_choked) if dp_choked > 0 else dp_actual

    if dp_eff <= 0 or Gf <= 0:
        return (0.0, choked, dp_choked)

    Cv = Q / (N1 * Fp * math.sqrt(dp_eff / Gf))
    return (Cv, choked, dp_choked)


def _size_gas(W: float, M: float, T1: float, Z: float, k: float,
              P1: float, P2: float, xT: float, Fp: float) -> tuple[float, bool, float]:
    """ISA 60534 gas Cv: Cv = W / (N8*Fp*Y*sqrt(x*Gg*T1*Z))

    W in kg/hr, T1 in °C, pressures in kPa.
    Returns (Cv, choked, choked_dp_kpa).
    """
    N8 = 94.8  # ISA constant for kg/hr, kPa, K

    T1_K = T1 + 273.15
    Gg = M / 28.97  # Gas specific gravity (relative to air)

    # Specific heat ratio factor
    Fk = k / 1.4

    # Pressure drop ratio
    x = (P1 - P2) / max(P1, 1e-6)
    x_choked = Fk * xT
    dp_choked = P1 * x_choked

    choked = x >= x_choked
    x_eff = min(x, x_choked)

    # Expansion factor
    Y = 1.0 - x_eff / (3.0 * Fk * xT) if Fk * xT > 0 else 1.0
    Y = max(Y, 2.0 / 3.0)

    if W <= 0 or x_eff <= 0 or Gg <= 0 or T1_K <= 0:
        return (0.0, choked, dp_choked)

    Cv = W / (N8 * Fp * Y * math.sqrt(x_eff * Gg * T1_K * Z))
    return (Cv, choked, dp_choked)
