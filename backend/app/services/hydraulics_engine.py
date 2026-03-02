"""Pipe hydraulics engine — Churchill friction factor, Darcy-Weisbach,
Lockhart-Martinelli two-phase, API RP 14E erosional velocity.
"""
import math
import logging

logger = logging.getLogger(__name__)

# Equivalent lengths (L/D) for fittings
_FITTING_LD = {
    "elbows_90": 30,
    "elbows_45": 16,
    "tees": 20,
    "gate_valves": 8,
    "globe_valves": 340,
    "check_valves": 100,
}


def compute_hydraulics(
    mass_flow_rate: float,
    density: float,
    viscosity: float = 0.001,
    phase: str = "liquid",
    gas_density: float = 1.2,
    gas_viscosity: float = 1.8e-5,
    gas_mass_fraction: float = 0.0,
    length: float = 100.0,
    diameter: float = 0.1,
    roughness: float = 0.000045,
    elevation: float = 0.0,
    elbows_90: int = 0,
    elbows_45: int = 0,
    tees: int = 0,
    gate_valves: int = 0,
    globe_valves: int = 0,
    check_valves: int = 0,
) -> dict:
    """Compute pipe pressure drop and flow parameters."""
    if mass_flow_rate <= 0 or density <= 0 or diameter <= 0:
        return {"status": "error", "error": "Invalid input: flow, density, and diameter must be > 0"}

    area = math.pi * (diameter / 2.0) ** 2
    velocity = mass_flow_rate / (density * area)
    reynolds = density * velocity * diameter / max(viscosity, 1e-12)

    # Flow regime
    if reynolds < 2100:
        flow_regime = "Laminar"
    elif reynolds < 4000:
        flow_regime = "Transitional"
    else:
        flow_regime = "Turbulent"

    # Churchill friction factor (full range: laminar through turbulent)
    f_churchill = _churchill_friction(reynolds, roughness, diameter)

    # Equivalent length for fittings
    fittings = {
        "elbows_90": elbows_90, "elbows_45": elbows_45,
        "tees": tees, "gate_valves": gate_valves,
        "globe_valves": globe_valves, "check_valves": check_valves,
    }
    eq_length = 0.0
    for fit_type, count in fittings.items():
        if count > 0:
            ld = _FITTING_LD.get(fit_type, 0)
            eq_length += count * ld * diameter

    total_length = length + eq_length

    if phase == "two_phase" and gas_mass_fraction > 0:
        # Lockhart-Martinelli correlation
        dp_friction = _lockhart_martinelli(
            mass_flow_rate, density, viscosity,
            gas_density, gas_viscosity, gas_mass_fraction,
            total_length, diameter, roughness,
        )
    else:
        # Darcy-Weisbach: ΔP = f * (L/D) * (ρ*V²/2)
        dp_friction = f_churchill * (total_length / diameter) * (density * velocity ** 2 / 2.0)

    dp_fittings = f_churchill * (eq_length / diameter) * (density * velocity ** 2 / 2.0) if eq_length > 0 else 0.0
    dp_elevation = density * 9.81 * elevation
    dp_total = dp_friction + dp_elevation

    # API RP 14E erosional velocity: V_e = C / sqrt(ρ_mix)
    c_factor = 100.0  # conservative, can be 100-250
    mix_density = density
    if phase == "two_phase" and gas_mass_fraction > 0:
        mix_density = 1.0 / (gas_mass_fraction / gas_density + (1 - gas_mass_fraction) / density)
    erosional_velocity = c_factor / math.sqrt(max(mix_density, 0.01))
    erosional_ratio = velocity / erosional_velocity if erosional_velocity > 0 else 0

    return {
        "pressure_drop_kpa": round(dp_total / 1000.0, 4),
        "pressure_drop_friction_kpa": round((dp_friction - dp_fittings) / 1000.0, 4) if dp_fittings > 0 else round(dp_friction / 1000.0, 4),
        "pressure_drop_elevation_kpa": round(dp_elevation / 1000.0, 4),
        "pressure_drop_fittings_kpa": round(dp_fittings / 1000.0, 4),
        "velocity_m_s": round(velocity, 4),
        "reynolds_number": round(reynolds, 0),
        "friction_factor": round(f_churchill, 6),
        "flow_regime": flow_regime,
        "erosional_velocity_m_s": round(erosional_velocity, 2),
        "erosional_ratio": round(erosional_ratio, 4),
        "erosional_ok": erosional_ratio < 1.0,
        "equivalent_length_m": round(eq_length, 2),
        "status": "success",
    }


def _churchill_friction(Re: float, roughness: float, diameter: float) -> float:
    """Churchill (1977) friction factor — valid for all Reynolds numbers."""
    if Re <= 0:
        return 0.0

    e_d = roughness / diameter if diameter > 0 else 0

    A = (-2.457 * math.log(max((7.0 / Re) ** 0.9 + 0.27 * e_d, 1e-30))) ** 16
    B = (37530.0 / max(Re, 1e-10)) ** 16

    f = 8.0 * ((8.0 / max(Re, 1e-10)) ** 12 + 1.0 / (A + B) ** 1.5) ** (1.0 / 12.0)
    return f


def _lockhart_martinelli(
    mf_total: float, rho_l: float, mu_l: float,
    rho_g: float, mu_g: float, x: float,
    length: float, diameter: float, roughness: float,
) -> float:
    """Lockhart-Martinelli two-phase pressure drop correlation."""
    area = math.pi * (diameter / 2.0) ** 2

    # Liquid-only flow
    mf_l = mf_total * (1 - x)
    v_l = mf_l / (rho_l * area) if rho_l > 0 else 0
    re_l = rho_l * v_l * diameter / max(mu_l, 1e-12)
    f_l = _churchill_friction(re_l, roughness, diameter)
    dp_l = f_l * (length / diameter) * (rho_l * v_l ** 2 / 2.0)

    # Gas-only flow
    mf_g = mf_total * x
    v_g = mf_g / (rho_g * area) if rho_g > 0 else 0
    re_g = rho_g * v_g * diameter / max(mu_g, 1e-12)
    f_g = _churchill_friction(re_g, roughness, diameter)
    dp_g = f_g * (length / diameter) * (rho_g * v_g ** 2 / 2.0)

    # Martinelli parameter
    if dp_g > 0:
        X2 = dp_l / dp_g
        X = math.sqrt(X2) if X2 > 0 else 0
    else:
        return dp_l

    # Chisholm C parameter (turbulent-turbulent)
    C = 20.0
    phi_l2 = 1.0 + C / max(X, 1e-6) + 1.0 / max(X2, 1e-12)

    return dp_l * phi_l2
