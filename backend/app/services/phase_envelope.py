"""Phase envelope computation for PT diagrams.

Computes bubble point and dew point curves by sweeping temperature,
finding the corresponding bubble pressure (VF=0) and dew pressure (VF=1)
at each temperature point. Also provides cricondentherm and cricondenbar.
"""

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

_thermo_available = False
try:
    from thermo import (  # type: ignore[import-untyped]
        ChemicalConstantsPackage,
        CEOSGas,
        CEOSLiquid,
        PRMIX,
        FlashVL,
        FlashPureVLS,
    )
    from thermo.interaction_parameters import IPDB  # type: ignore[import-untyped]

    try:
        from thermo import SRKMIX  # type: ignore[import-untyped]
    except ImportError:
        SRKMIX = None  # type: ignore[assignment]

    _thermo_available = True
except Exception:
    pass


def _build_flasher(
    comp_names: list[str],
    zs: list[float],
    property_package: str = "PengRobinson",
) -> tuple[Any, Any, Any] | None:
    """Build a flasher object for the given composition and property package.

    Returns (flasher, constants, properties) or None.
    """
    if not _thermo_available or not comp_names or not zs:
        return None

    try:
        total = sum(zs)
        if total <= 0:
            return None
        zs_norm = [z / total for z in zs]
        constants, properties = ChemicalConstantsPackage.from_IDs(comp_names)

        bip_source = "ChemSep SRK" if property_package == "SRK" else "ChemSep PR"
        try:
            kijs = IPDB.get_ip_asymmetric_matrix(bip_source, constants.CASs, "kij")
        except Exception:
            kijs = [[0.0] * len(comp_names) for _ in comp_names]

        eos_kwargs = {
            "Pcs": constants.Pcs,
            "Tcs": constants.Tcs,
            "omegas": constants.omegas,
            "kijs": kijs,
        }

        EOS_class = PRMIX
        if property_package == "SRK" and SRKMIX is not None:
            EOS_class = SRKMIX

        T_ref, P_ref = 300.0, 101325.0
        gas = CEOSGas(
            EOS_class, eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
            T=T_ref, P=P_ref, zs=zs_norm,
        )
        liq = CEOSLiquid(
            EOS_class, eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
            T=T_ref, P=P_ref, zs=zs_norm,
        )

        if len(comp_names) == 1:
            flasher = FlashPureVLS(constants, properties, liquids=[liq], gas=gas, solids=[])
        else:
            flasher = FlashVL(constants, properties, liquid=liq, gas=gas)

        return flasher, constants, properties
    except Exception as exc:
        logger.warning("Failed to build flasher: %s", exc)
        return None


def compute_phase_envelope(
    comp_names: list[str],
    zs: list[float],
    property_package: str = "PengRobinson",
    n_points: int = 50,
) -> dict[str, Any]:
    """Compute PT phase envelope (bubble + dew curves).

    Args:
        comp_names: list of compound names
        zs: mole fractions (will be normalized)
        property_package: PengRobinson, SRK, etc.
        n_points: number of temperature points to sweep

    Returns dict with:
        bubble_curve: [{T_K, T_C, P_Pa, P_kPa}, ...]
        dew_curve: [{T_K, T_C, P_Pa, P_kPa}, ...]
        cricondentherm: {T_K, T_C, P_Pa, P_kPa} - max T on envelope
        cricondenbar: {T_K, T_C, P_Pa, P_kPa} - max P on envelope
        critical_point: {T_K, T_C, P_Pa, P_kPa} - mixture critical (approx)
    """
    if not _thermo_available:
        return {"error": "thermo library not available"}

    result = _build_flasher(comp_names, zs, property_package)
    if result is None:
        return {"error": "Failed to build flasher"}

    flasher, constants, properties = result
    total = sum(zs)
    zs_norm = [z / total for z in zs]

    # Estimate temperature range from pure component critical temperatures
    Tcs = list(constants.Tcs)
    T_min = min(Tcs) * 0.4  # Start well below lowest Tc
    T_max = max(Tcs) * 1.05  # Go slightly above highest Tc

    # For single component, use different approach
    if len(comp_names) == 1:
        return _compute_pure_component_envelope(
            flasher, constants, zs_norm, T_min, T_max, n_points
        )

    bubble_curve: list[dict[str, float]] = []
    dew_curve: list[dict[str, float]] = []

    temps = [T_min + i * (T_max - T_min) / (n_points - 1) for i in range(n_points)]

    for T in temps:
        # Bubble point: VF = 0
        try:
            state = flasher.flash(T=T, VF=0.0, zs=zs_norm)
            if state.P > 0 and math.isfinite(state.P):
                bubble_curve.append({
                    "T_K": round(T, 2),
                    "T_C": round(T - 273.15, 2),
                    "P_Pa": round(state.P, 1),
                    "P_kPa": round(state.P / 1000.0, 3),
                })
        except Exception:
            pass

        # Dew point: VF = 1
        try:
            state = flasher.flash(T=T, VF=1.0, zs=zs_norm)
            if state.P > 0 and math.isfinite(state.P):
                dew_curve.append({
                    "T_K": round(T, 2),
                    "T_C": round(T - 273.15, 2),
                    "P_Pa": round(state.P, 1),
                    "P_kPa": round(state.P / 1000.0, 3),
                })
        except Exception:
            pass

    # Find cricondentherm (max T on envelope)
    all_points = bubble_curve + dew_curve
    cricondentherm = max(all_points, key=lambda p: p["T_K"]) if all_points else None
    cricondenbar = max(all_points, key=lambda p: p["P_Pa"]) if all_points else None

    # Approximate mixture critical point (Kay's rule)
    Tc_mix = sum(z * Tc for z, Tc in zip(zs_norm, Tcs))
    Pcs = list(constants.Pcs)
    Pc_mix = sum(z * Pc for z, Pc in zip(zs_norm, Pcs))

    return {
        "bubble_curve": bubble_curve,
        "dew_curve": dew_curve,
        "cricondentherm": cricondentherm,
        "cricondenbar": cricondenbar,
        "critical_point": {
            "T_K": round(Tc_mix, 2),
            "T_C": round(Tc_mix - 273.15, 2),
            "P_Pa": round(Pc_mix, 1),
            "P_kPa": round(Pc_mix / 1000.0, 3),
        },
        "compounds": comp_names,
        "composition": dict(zip(comp_names, zs_norm)),
        "property_package": property_package,
    }


def _compute_pure_component_envelope(
    flasher: Any,
    constants: Any,
    zs: list[float],
    T_min: float,
    T_max: float,
    n_points: int,
) -> dict[str, Any]:
    """Compute vapor pressure curve for a single component."""
    curve: list[dict[str, float]] = []
    Tc = constants.Tcs[0]
    Pc = constants.Pcs[0]

    # For pure components, bubble = dew = vapor pressure
    T_start = max(T_min, constants.Tms[0] if constants.Tms and constants.Tms[0] else T_min)
    T_end = min(T_max, Tc * 0.999)
    temps = [T_start + i * (T_end - T_start) / (n_points - 1) for i in range(n_points)]

    for T in temps:
        try:
            state = flasher.flash(T=T, VF=0.0, zs=zs)
            if state.P > 0 and math.isfinite(state.P):
                curve.append({
                    "T_K": round(T, 2),
                    "T_C": round(T - 273.15, 2),
                    "P_Pa": round(state.P, 1),
                    "P_kPa": round(state.P / 1000.0, 3),
                })
        except Exception:
            pass

    return {
        "bubble_curve": curve,
        "dew_curve": curve,  # Same as bubble for pure component
        "cricondentherm": None,
        "cricondenbar": None,
        "critical_point": {
            "T_K": round(Tc, 2),
            "T_C": round(Tc - 273.15, 2),
            "P_Pa": round(Pc, 1),
            "P_kPa": round(Pc / 1000.0, 3),
        },
        "compounds": list(constants.names),
        "composition": {constants.names[0]: 1.0},
        "property_package": "PengRobinson",
    }
