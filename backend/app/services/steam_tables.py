"""Steam tables using IAPWS-IF97 via CoolProp.

Provides high-accuracy thermodynamic properties for water/steam
across all phases (compressed liquid, saturated, superheated, supercritical).

Reference: IAPWS-IF97 (International Association for the Properties of Water and Steam)
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import CoolProp.CoolProp as CP
    _coolprop_available = True
except ImportError:
    _coolprop_available = False
    logger.warning("CoolProp not installed — steam_tables will be unavailable")


def steam_properties(
    T: float | None = None,
    P: float | None = None,
    x: float | None = None,
    h: float | None = None,
    s: float | None = None,
) -> dict[str, Any]:
    """Calculate steam/water properties from any two independent inputs.

    Provide exactly two of the five parameters.

    Args:
        T: Temperature (K)
        P: Pressure (Pa)
        x: Quality (0 = saturated liquid, 1 = saturated vapor)
        h: Specific enthalpy (J/kg)
        s: Specific entropy (J/(kg·K))

    Returns:
        Dict with T, P, h, s, v, x, phase, cp, cv, rho, mu, k, sigma
    """
    if not _coolprop_available:
        return {"status": "error", "error": "CoolProp not installed"}

    # Count provided inputs
    inputs = {"T": T, "P": P, "x": x, "h": h, "s": s}
    provided = {k: v for k, v in inputs.items() if v is not None}
    if len(provided) != 2:
        return {"status": "error", "error": f"Provide exactly 2 inputs, got {len(provided)}: {list(provided.keys())}"}

    # Map to CoolProp input pairs (CoolProp uses "Q" for quality, not "x")
    cp_map = {
        "T": (CP.iT, "T"),
        "P": (CP.iP, "P"),
        "x": (CP.iQ, "Q"),
        "h": (CP.iHmass, "Hmass"),
        "s": (CP.iSmass, "Smass"),
    }

    keys = list(provided.keys())
    try:
        cp_input1, _ = cp_map[keys[0]]
        cp_input2, _ = cp_map[keys[1]]
        val1 = provided[keys[0]]
        val2 = provided[keys[1]]

        # CoolProp PropsSI calls
        fluid = "Water"

        def _get(prop: str) -> float | None:
            try:
                return CP.PropsSI(prop, cp_map[keys[0]][1], val1, cp_map[keys[1]][1], val2, fluid)
            except Exception:
                return None

        T_out = _get("T")
        P_out = _get("P")
        h_out = _get("Hmass")
        s_out = _get("Smass")
        v_out = _get("Dmass")  # density first, then invert
        rho = v_out
        if v_out is not None and v_out > 0:
            v_out = 1.0 / v_out  # specific volume m³/kg
        else:
            v_out = None

        quality = _get("Q")
        cp_out = _get("Cpmass")
        cv_out = _get("Cvmass")
        mu_out = _get("viscosity")
        k_out = _get("conductivity")
        sigma_out = _get("surface_tension")

        # Determine phase
        phase_idx = _get("Phase")
        phase_names = {
            0: "liquid",
            # CoolProp phase indices
            6: "supercritical",
            5: "supercritical_gas",
            3: "supercritical_liquid",
        }
        if quality is not None and 0 < quality < 1:
            phase = "two-phase"
        elif quality is not None and quality <= 0:
            phase = "compressed_liquid"
        elif quality is not None and quality >= 1:
            phase = "superheated_vapor"
        else:
            phase = "unknown"

        # More robust phase detection using CoolProp phase string
        try:
            phase_str = CP.PhaseSI(cp_map[keys[0]][1], val1, cp_map[keys[1]][1], val2, fluid)
            phase = phase_str.lower().replace(" ", "_")
        except Exception:
            pass

        result = {
            "status": "success",
            "T_K": round(T_out, 4) if T_out is not None else None,
            "T_C": round(T_out - 273.15, 4) if T_out is not None else None,
            "P_Pa": round(P_out, 2) if P_out is not None else None,
            "P_bar": round(P_out / 1e5, 6) if P_out is not None else None,
            "h_J_per_kg": round(h_out, 2) if h_out is not None else None,
            "h_kJ_per_kg": round(h_out / 1000, 4) if h_out is not None else None,
            "s_J_per_kgK": round(s_out, 4) if s_out is not None else None,
            "v_m3_per_kg": round(v_out, 8) if v_out is not None else None,
            "rho_kg_per_m3": round(rho, 4) if rho is not None else None,
            "quality": round(quality, 6) if quality is not None else None,
            "phase": phase,
            "cp_J_per_kgK": round(cp_out, 4) if cp_out is not None else None,
            "cv_J_per_kgK": round(cv_out, 4) if cv_out is not None else None,
            "mu_Pa_s": round(mu_out, 8) if mu_out is not None else None,
            "k_W_per_mK": round(k_out, 6) if k_out is not None else None,
            "sigma_N_per_m": round(sigma_out, 8) if sigma_out is not None else None,
        }
        return result

    except Exception as exc:
        return {"status": "error", "error": f"CoolProp calculation failed: {exc}"}


def saturated_properties(
    T: float | None = None,
    P: float | None = None,
) -> dict[str, Any]:
    """Calculate saturated steam/water properties at given T or P.

    Provide exactly one of T or P.

    Args:
        T: Saturation temperature (K)
        P: Saturation pressure (Pa)

    Returns:
        Dict with liquid and vapor properties at saturation.
    """
    if not _coolprop_available:
        return {"status": "error", "error": "CoolProp not installed"}

    if (T is None) == (P is None):
        return {"status": "error", "error": "Provide exactly one of T or P"}

    try:
        if T is not None:
            # Get saturation pressure at T
            P_sat = CP.PropsSI("P", "T", T, "Q", 0, "Water")
            input_key, input_val = "T", T
        else:
            T_sat = CP.PropsSI("T", "P", P, "Q", 0, "Water")
            P_sat = P
            T = T_sat
            input_key, input_val = "P", P

        # Saturated liquid (Q=0) and vapor (Q=1)
        liquid = steam_properties(T=T, x=0.0)
        vapor = steam_properties(T=T, x=1.0)

        return {
            "status": "success",
            "T_sat_K": round(T, 4),
            "T_sat_C": round(T - 273.15, 4),
            "P_sat_Pa": round(P_sat, 2),
            "P_sat_bar": round(P_sat / 1e5, 6),
            "liquid": liquid,
            "vapor": vapor,
            "h_fg_kJ_per_kg": round(
                (vapor.get("h_kJ_per_kg", 0) or 0) - (liquid.get("h_kJ_per_kg", 0) or 0), 4
            ),
            "s_fg_J_per_kgK": round(
                (vapor.get("s_J_per_kgK", 0) or 0) - (liquid.get("s_J_per_kgK", 0) or 0), 4
            ),
        }

    except Exception as exc:
        return {"status": "error", "error": f"Saturation calculation failed: {exc}"}


def superheated_steam(T: float, P: float) -> dict[str, Any]:
    """Properties of superheated steam at T (K) and P (Pa).

    Verifies the state is actually superheated.
    """
    result = steam_properties(T=T, P=P)
    if result.get("status") != "success":
        return result

    phase = result.get("phase", "")
    if "liquid" in phase and "supercritical" not in phase:
        result["warning"] = f"State is {phase}, not superheated vapor"

    return result


def compressed_liquid(T: float, P: float) -> dict[str, Any]:
    """Properties of compressed (subcooled) liquid water at T (K) and P (Pa).

    Verifies the state is actually compressed liquid.
    """
    result = steam_properties(T=T, P=P)
    if result.get("status") != "success":
        return result

    phase = result.get("phase", "")
    if "gas" in phase or "vapor" in phase:
        result["warning"] = f"State is {phase}, not compressed liquid"

    return result
