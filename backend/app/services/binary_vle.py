"""Binary VLE diagram computation — Txy and Pxy.

Computes bubble/dew curves for binary mixtures by sweeping composition
at constant pressure (Txy) or constant temperature (Pxy).
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
    )
    from thermo.interaction_parameters import IPDB  # type: ignore[import-untyped]

    try:
        from thermo import SRKMIX  # type: ignore[import-untyped]
    except ImportError:
        SRKMIX = None  # type: ignore[assignment]

    _thermo_available = True
except Exception:
    pass


def _build_binary_flasher(
    comp_a: str,
    comp_b: str,
    property_package: str = "PengRobinson",
) -> tuple[Any, Any, Any] | None:
    """Build a flasher for a binary pair."""
    if not _thermo_available:
        return None
    try:
        comp_names = [comp_a, comp_b]
        constants, properties = ChemicalConstantsPackage.from_IDs(comp_names)

        bip_source = "ChemSep SRK" if property_package == "SRK" else "ChemSep PR"
        try:
            kijs = IPDB.get_ip_asymmetric_matrix(bip_source, constants.CASs, "kij")
        except Exception:
            kijs = [[0.0, 0.0], [0.0, 0.0]]

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
        zs_ref = [0.5, 0.5]
        gas = CEOSGas(
            EOS_class, eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
            T=T_ref, P=P_ref, zs=zs_ref,
        )
        liq = CEOSLiquid(
            EOS_class, eos_kwargs,
            HeatCapacityGases=properties.HeatCapacityGases,
            T=T_ref, P=P_ref, zs=zs_ref,
        )
        flasher = FlashVL(constants, properties, liquid=liq, gas=gas)
        return flasher, constants, properties
    except Exception as exc:
        logger.warning("Failed to build binary flasher: %s", exc)
        return None


def compute_txy(
    comp_a: str,
    comp_b: str,
    P: float,
    property_package: str = "PengRobinson",
    n_points: int = 51,
) -> dict[str, Any]:
    """Compute Txy diagram at constant pressure.

    Args:
        comp_a, comp_b: compound names
        P: pressure in Pa
        property_package: thermodynamic model
        n_points: number of composition points (0 to 1)

    Returns:
        {bubble_curve, dew_curve, xy_curve, compounds, P_Pa, P_kPa}
    """
    if not _thermo_available:
        return {"error": "thermo library not available"}

    result = _build_binary_flasher(comp_a, comp_b, property_package)
    if result is None:
        return {"error": f"Failed to build flasher for {comp_a}/{comp_b}"}

    flasher, constants, properties = result

    bubble_curve: list[dict[str, float]] = []
    dew_curve: list[dict[str, float]] = []
    xy_curve: list[dict[str, float]] = []

    for i in range(n_points):
        x_a = i / (n_points - 1)
        x_b = 1.0 - x_a
        zs = [x_a, x_b]

        # Skip pure endpoints to avoid numerical issues
        if x_a < 1e-8 or x_a > 1.0 - 1e-8:
            # Pure component: bubble = dew
            try:
                state = flasher.flash(T=300.0, VF=0.0, zs=zs if x_a > 0.5 else [1e-8, 1.0 - 1e-8])
            except Exception:
                continue

        # Bubble point (VF=0)
        try:
            state = flasher.flash(P=P, VF=0.0, zs=zs)
            if state.T and math.isfinite(state.T):
                T_C = state.T - 273.15
                bubble_curve.append({
                    "x_a": round(x_a, 6),
                    "T_C": round(T_C, 4),
                    "T_K": round(state.T, 4),
                })
                # Get vapor composition from bubble point
                gas_phase = getattr(state, 'gas', None)
                if gas_phase and hasattr(gas_phase, 'zs') and gas_phase.zs:
                    y_a = gas_phase.zs[0]
                    xy_curve.append({
                        "x_a": round(x_a, 6),
                        "y_a": round(y_a, 6),
                    })
        except Exception:
            pass

        # Dew point (VF=1)
        try:
            state = flasher.flash(P=P, VF=1.0, zs=zs)
            if state.T and math.isfinite(state.T):
                T_C = state.T - 273.15
                dew_curve.append({
                    "x_a": round(x_a, 6),
                    "T_C": round(T_C, 4),
                    "T_K": round(state.T, 4),
                })
        except Exception:
            pass

    return {
        "bubble_curve": bubble_curve,
        "dew_curve": dew_curve,
        "xy_curve": xy_curve,
        "compounds": [comp_a, comp_b],
        "P_Pa": P,
        "P_kPa": round(P / 1000.0, 3),
        "property_package": property_package,
        "diagram_type": "Txy",
    }


def compute_pxy(
    comp_a: str,
    comp_b: str,
    T: float,
    property_package: str = "PengRobinson",
    n_points: int = 51,
) -> dict[str, Any]:
    """Compute Pxy diagram at constant temperature.

    Args:
        comp_a, comp_b: compound names
        T: temperature in K
        property_package: thermodynamic model
        n_points: number of composition points (0 to 1)

    Returns:
        {bubble_curve, dew_curve, xy_curve, compounds, T_K, T_C}
    """
    if not _thermo_available:
        return {"error": "thermo library not available"}

    result = _build_binary_flasher(comp_a, comp_b, property_package)
    if result is None:
        return {"error": f"Failed to build flasher for {comp_a}/{comp_b}"}

    flasher, constants, properties = result

    bubble_curve: list[dict[str, float]] = []
    dew_curve: list[dict[str, float]] = []
    xy_curve: list[dict[str, float]] = []

    for i in range(n_points):
        x_a = i / (n_points - 1)
        x_b = 1.0 - x_a
        zs = [x_a, x_b]

        # Bubble point (VF=0) → gives bubble pressure
        try:
            state = flasher.flash(T=T, VF=0.0, zs=zs)
            if state.P and math.isfinite(state.P) and state.P > 0:
                P_kPa = state.P / 1000.0
                bubble_curve.append({
                    "x_a": round(x_a, 6),
                    "P_kPa": round(P_kPa, 4),
                    "P_Pa": round(state.P, 1),
                })
                gas_phase = getattr(state, 'gas', None)
                if gas_phase and hasattr(gas_phase, 'zs') and gas_phase.zs:
                    y_a = gas_phase.zs[0]
                    xy_curve.append({
                        "x_a": round(x_a, 6),
                        "y_a": round(y_a, 6),
                    })
        except Exception:
            pass

        # Dew point (VF=1) → gives dew pressure
        try:
            state = flasher.flash(T=T, VF=1.0, zs=zs)
            if state.P and math.isfinite(state.P) and state.P > 0:
                P_kPa = state.P / 1000.0
                dew_curve.append({
                    "x_a": round(x_a, 6),
                    "P_kPa": round(P_kPa, 4),
                    "P_Pa": round(state.P, 1),
                })
        except Exception:
            pass

    return {
        "bubble_curve": bubble_curve,
        "dew_curve": dew_curve,
        "xy_curve": xy_curve,
        "compounds": [comp_a, comp_b],
        "T_K": T,
        "T_C": round(T - 273.15, 2),
        "property_package": property_package,
        "diagram_type": "Pxy",
    }
