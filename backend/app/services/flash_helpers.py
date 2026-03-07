"""Shared flash calculation helpers.

Provides:
  - Compound name normalization (alias resolution)
  - Wilson K-value correlation
  - Rachford-Rice solver
  - BIP matrix validation
"""

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compound name alias table
# Maps common abbreviations / formulas / alternative names to canonical names
# that thermo/chemicals can resolve.
# ---------------------------------------------------------------------------
_COMPOUND_ALIASES: dict[str, str] = {
    # Formulas
    "h2o": "water",
    "co2": "carbon dioxide",
    "co": "carbon monoxide",
    "h2": "hydrogen",
    "n2": "nitrogen",
    "o2": "oxygen",
    "h2s": "hydrogen sulfide",
    "so2": "sulfur dioxide",
    "nh3": "ammonia",
    "cl2": "chlorine",
    "hcl": "hydrogen chloride",
    "ar": "argon",
    "he": "helium",
    "no2": "nitrogen dioxide",
    "no": "nitric oxide",
    "ch4": "methane",
    "c2h6": "ethane",
    "c2h4": "ethylene",
    "c3h8": "propane",
    "c3h6": "propylene",
    # Common abbreviations
    "mea": "monoethanolamine",
    "dea": "diethanolamine",
    "mdea": "methyldiethanolamine",
    "meg": "ethylene glycol",
    "deg": "diethylene glycol",
    "teg": "triethylene glycol",
    "mtbe": "tert-butyl methyl ether",
    "dme": "dimethyl ether",
    "dee": "diethyl ether",
    "thf": "tetrahydrofuran",
    "dmf": "dimethylformamide",
    "dmso": "dimethyl sulfoxide",
    "dcm": "dichloromethane",
    "meoh": "methanol",
    "etoh": "ethanol",
    "acoh": "acetic acid",
    "ipa": "2-propanol",
    "npa": "1-propanol",
    "nmp": "n-methyl-2-pyrrolidone",
    "eo": "ethylene oxide",
    "po": "propylene oxide",
    "vcm": "vinyl chloride",
    "eg": "ethylene glycol",
    # Alternative names
    "steam": "water",
    "brine": "water",
    "isopropanol": "2-propanol",
    "isopropyl alcohol": "2-propanol",
    "n-propanol": "1-propanol",
    "propan-1-ol": "1-propanol",
    "propan-2-ol": "2-propanol",
    "butane": "n-butane",
    "pentane": "n-pentane",
    "hexane": "n-hexane",
    "heptane": "n-heptane",
    "octane": "n-octane",
    "decane": "n-decane",
    "dodecane": "n-dodecane",
    "hexadecane": "n-hexadecane",
    "cetane": "n-hexadecane",
    "methylene chloride": "dichloromethane",
    "carbon tet": "carbon tetrachloride",
    "caustic": "sodium hydroxide",
    "caustic soda": "sodium hydroxide",
    "muriatic acid": "hydrogen chloride",
    "hydrochloric acid": "hydrogen chloride",
    "sulphuric acid": "sulfuric acid",
    "sulphur dioxide": "sulfur dioxide",
    "xylene": "m-xylene",
    "glycol": "ethylene glycol",
}


def normalize_compound_name(name: str) -> str:
    """Normalize a compound name using the alias table.

    Strips whitespace, lowercases, removes 'pseudo:' prefix,
    then checks alias table for canonical name.

    Returns the canonical name if found, otherwise the cleaned input.
    """
    clean = name.strip().lower().replace("pseudo:", "").strip()
    return _COMPOUND_ALIASES.get(clean, clean)


def normalize_compound_names(names: list[str]) -> list[str]:
    """Normalize a list of compound names."""
    return [normalize_compound_name(n) for n in names]


# ---------------------------------------------------------------------------
# Wilson K-value correlation
# ---------------------------------------------------------------------------

def wilson_k_values(
    Tcs: list[float],
    Pcs: list[float],
    omegas: list[float],
    T: float,
    P: float,
) -> list[float]:
    """Compute Wilson K-values for initial VLE estimates.

    Ki = (Pc_i / P) * exp(5.37 * (1 + omega_i) * (1 - Tc_i / T))

    Args:
        Tcs: critical temperatures (K)
        Pcs: critical pressures (Pa)
        omegas: acentric factors
        T: temperature (K)
        P: pressure (Pa)

    Returns:
        List of K-values (one per component)
    """
    n = len(Tcs)
    K = []
    for i in range(n):
        if T > 0 and Tcs[i] > 0 and P > 0:
            K_i = (Pcs[i] / P) * math.exp(
                5.37 * (1.0 + omegas[i]) * (1.0 - Tcs[i] / T)
            )
            K.append(max(K_i, 1e-10))
        else:
            K.append(1.0)
    return K


# ---------------------------------------------------------------------------
# Rachford-Rice solver
# ---------------------------------------------------------------------------

def solve_rachford_rice(
    zs: list[float],
    K: list[float],
    tol: float = 1e-10,
    max_iter: int = 50,
) -> tuple[float, list[float], list[float]]:
    """Solve the Rachford-Rice equation for vapor fraction.

    f(V) = sum(z_i * (K_i - 1) / (1 + V * (K_i - 1))) = 0

    Args:
        zs: feed mole fractions
        K: K-values (yi/xi)
        tol: convergence tolerance
        max_iter: maximum bisection iterations

    Returns:
        (VF, liquid_xs, vapor_ys)
        VF is clamped to [0, 1].
    """
    n = len(zs)
    if n == 0:
        return 0.0, [], []

    def rr_func(V: float) -> float:
        return sum(
            zs[i] * (K[i] - 1.0) / (1.0 + V * (K[i] - 1.0))
            for i in range(n)
        )

    # Check boundary conditions
    f0 = rr_func(0.0)
    f1 = rr_func(1.0)

    if f0 <= 0:
        vf = 0.0
    elif f1 >= 0:
        vf = 1.0
    else:
        # Bisection — safe and robust
        lo, hi = 0.0, 1.0
        for _ in range(max_iter):
            mid = (lo + hi) / 2.0
            if abs(hi - lo) < tol:
                break
            if rr_func(mid) > 0:
                lo = mid
            else:
                hi = mid
        vf = (lo + hi) / 2.0

    # Compute phase compositions
    xs = []
    ys = []
    for i in range(n):
        denom = 1.0 + vf * (K[i] - 1.0)
        x_i = zs[i] / max(denom, 1e-15)
        y_i = K[i] * x_i
        xs.append(x_i)
        ys.append(y_i)

    # Normalize
    sum_x = sum(xs) or 1.0
    sum_y = sum(ys) or 1.0
    xs = [x / sum_x for x in xs]
    ys = [y / sum_y for y in ys]

    return vf, xs, ys


# ---------------------------------------------------------------------------
# UNIFAC-based TP flash (gamma-phi approach)
# ---------------------------------------------------------------------------

def flash_tp_unifac(
    comp_names: list[str],
    zs: list[float],
    T: float,
    P: float,
    max_iter: int = 50,
    tol: float = 1e-8,
) -> dict[str, Any] | None:
    """TP flash using gamma-phi approach with UNIFAC activity coefficients.

    Uses modified Raoult's law: y_i * P = x_i * gamma_i * Psat_i
    So K_i = gamma_i * Psat_i / P

    This is suitable for polar/non-ideal liquid mixtures where EOS methods fail.

    Args:
        comp_names: list of compound names (aliases accepted)
        zs: feed mole fractions
        T: temperature [K]
        P: pressure [Pa]
        max_iter: maximum iterations
        tol: convergence tolerance on liquid compositions

    Returns:
        dict with VF, x, y, K, converged, iterations — or None if UNIFAC
        groups are unavailable for the mixture.
    """
    from app.services.bip_manager import get_unifac_gammas

    # Normalize names
    names = normalize_compound_names(comp_names)
    n = len(names)

    # Get vapor pressures at T using thermo correlation objects
    try:
        from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]

        _, correlations = ChemicalConstantsPackage.from_IDs(names)
        Psats = [correlations.VaporPressures[i](T) for i in range(n)]
    except Exception as exc:
        logger.warning("Failed to compute vapor pressures: %s", exc)
        return None

    if any(p is None or p <= 0 for p in Psats):
        logger.warning("Could not obtain vapor pressures for all components")
        return None

    # Initial guess: assume ideal (gamma=1) K-values
    K = [Psats[i] / P for i in range(n)]
    vf, xs, ys = solve_rachford_rice(zs, K)

    converged = False
    for iteration in range(max_iter):
        x_old = xs[:]

        # Get UNIFAC activity coefficients at current liquid composition
        # Guard against pure-phase edge case (all x_i ~ 0 except one)
        x_safe = [max(xi, 1e-12) for xi in xs]
        sum_x = sum(x_safe)
        x_safe = [xi / sum_x for xi in x_safe]

        gammas = get_unifac_gammas(names, T, x_safe)
        if gammas is None:
            return None

        # Update K-values: K_i = gamma_i * Psat_i / P
        K = [gammas[i] * Psats[i] / P for i in range(n)]

        # Solve Rachford-Rice with updated K
        vf, xs, ys = solve_rachford_rice(zs, K)

        # Check convergence on liquid compositions
        dx_max = max(abs(xs[i] - x_old[i]) for i in range(n))
        if dx_max < tol:
            converged = True
            break

    return {
        "VF": vf,
        "x": xs,
        "y": ys,
        "K": K,
        "gammas": gammas,
        "converged": converged,
        "iterations": iteration + 1,
    }


# ---------------------------------------------------------------------------
# BIP matrix validation
# ---------------------------------------------------------------------------

def validate_bip_matrix(
    matrix: list[list[float]],
    n: int,
) -> tuple[bool, int, int]:
    """Check if a BIP matrix has meaningful (non-zero) off-diagonal entries.

    Args:
        matrix: NxN BIP matrix
        n: number of components

    Returns:
        (has_data, nonzero_count, total_pairs)
        has_data: True if at least one off-diagonal pair is non-zero
        nonzero_count: count of non-zero off-diagonal pairs
        total_pairs: total number of off-diagonal pairs
    """
    nonzero = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1
            if abs(matrix[i][j]) > 1e-15 or abs(matrix[j][i]) > 1e-15:
                nonzero += 1
    return nonzero > 0, nonzero, total


def count_bip_coverage(
    matrix: list[list[float]],
    n: int,
) -> float:
    """Return fraction of off-diagonal pairs that have non-zero BIPs.

    0.0 = no BIPs at all (all zeros)
    1.0 = complete BIP coverage
    """
    if n < 2:
        return 1.0
    _, nonzero, total = validate_bip_matrix(matrix, n)
    return nonzero / total if total > 0 else 1.0


# ---------------------------------------------------------------------------
# Actionable error message helpers
# ---------------------------------------------------------------------------

_ERROR_GUIDANCE: dict[str, str] = {
    "singular": (
        "The equation system became singular — this often indicates "
        "a specification conflict (e.g., reflux ratio below minimum). "
        "Try increasing reflux ratio or adjusting feed stage."
    ),
    "convergence": (
        "The solver did not converge within the iteration limit. "
        "Try relaxing the tolerance, increasing max iterations, "
        "or adjusting operating conditions closer to expected values."
    ),
    "negative_flow": (
        "Negative flow rate detected — check that outlet pressure "
        "is lower than inlet pressure for valves, or that compression "
        "ratio is > 1 for compressors."
    ),
    "temperature_cross": (
        "Temperature cross detected in heat exchanger — the cold outlet "
        "would exceed the hot inlet temperature. Reduce the duty or "
        "increase the hot-side flow rate."
    ),
    "no_bips": (
        "No binary interaction parameters found for this system. "
        "Activity coefficient models (NRTL/UNIQUAC) require BIPs for "
        "accurate VLE — auto-downgrading to Peng-Robinson EOS."
    ),
    "flash_failed": (
        "Flash calculation failed to converge. This may occur near "
        "the critical point or with highly non-ideal mixtures. "
        "The engine will attempt Wilson K-value estimation as fallback."
    ),
    "reflux_below_min": (
        "Specified reflux ratio {R} is below the estimated minimum {R_min:.3f}. "
        "Column cannot achieve the desired separation — try increasing "
        "reflux ratio to at least {R_suggest:.1f} (1.2 × R_min)."
    ),
}




# ---------------------------------------------------------------------------
# Wilson activity coefficient model (GE model, NOT the K-value correlation)
# ---------------------------------------------------------------------------

def wilson_activity_coefficients(
    T: float,
    x: list[float],
    compounds: list[str],
) -> dict[str, Any] | None:
    """Compute Wilson activity coefficients using the thermo library.

    This is the Wilson GE (excess Gibbs energy) model — distinct from the
    Wilson K-value *correlation* above.  It requires fitted binary interaction
    parameters (Lambda_ij) from the thermo database.

    Args:
        T: Temperature (K)
        x: Liquid mole fractions
        compounds: Compound names (aliases accepted)

    Returns:
        {"gammas": [...], "GE": float, "converged": True} or None if Wilson
        parameters are unavailable.
    """
    names = normalize_compound_names(compounds)
    n = len(names)
    if n < 2:
        return {"gammas": [1.0] * n, "GE": 0.0, "converged": True}

    try:
        from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]
        from thermo.wilson import Wilson  # type: ignore[import-untyped]
        from thermo.unifac import UNIFAC  # type: ignore[import-untyped]

        consts, corr = ChemicalConstantsPackage.from_IDs(names)

        # Try to get Wilson parameters from thermo database
        try:
            GE = Wilson(T=T, xs=x, CASRNS=consts.CASs)
            gammas = GE.gammas()
            ge_val = GE.GE()
            return {
                "gammas": [round(g, 6) for g in gammas],
                "GE": round(ge_val, 4) if ge_val is not None else 0.0,
                "converged": True,
                "model": "Wilson",
            }
        except Exception:
            pass

        # Fallback: use UNIFAC for activity coefficients
        # Note: UNIFAC_groups is on consts (ChemicalConstantsPackage), not corr
        try:
            GE = UNIFAC.from_subgroups(T=T, xs=x, chemgroups=consts.UNIFAC_groups)
            gammas = GE.gammas()
            ge_val = GE.GE()
            return {
                "gammas": [round(g, 6) for g in gammas],
                "GE": round(ge_val, 4) if ge_val is not None else 0.0,
                "converged": True,
                "model": "UNIFAC_fallback",
            }
        except Exception:
            pass

    except ImportError:
        pass
    except Exception as exc:
        logger.debug("wilson_activity_coefficients failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# VLLE three-phase flash
# ---------------------------------------------------------------------------

def flash_vlle(
    compounds: list[str],
    T: float,
    P: float,
    z: list[float],
) -> dict[str, Any] | None:
    """VLLE (vapor-liquid-liquid equilibrium) three-phase flash.

    Uses thermo.FlashVLN for rigorous three-phase calculation.
    Returns vapor, light liquid (organic), and heavy liquid (aqueous) phases.

    Args:
        compounds: Compound names (aliases accepted)
        T: Temperature (K)
        P: Pressure (Pa)
        z: Feed mole fractions

    Returns:
        Dict with VF, liquid1_comp, liquid2_comp, vapor_comp, phase_fractions,
        n_liquid_phases — or None on failure.
    """
    names = normalize_compound_names(compounds)
    n = len(names)

    try:
        from thermo import (  # type: ignore[import-untyped]
            ChemicalConstantsPackage,
            CEOSGas,
            CEOSLiquid,
            PRMIX,
            FlashVL,
            FlashVLN,
        )

        consts, corr = ChemicalConstantsPackage.from_IDs(names)

        eos_kwargs = dict(
            Tcs=consts.Tcs,
            Pcs=consts.Pcs,
            omegas=consts.omegas,
        )

        gas = CEOSGas(PRMIX, eos_kwargs, HeatCapacityGases=corr.HeatCapacityGases, T=T, P=P, zs=z)
        liquid1 = CEOSLiquid(PRMIX, eos_kwargs, HeatCapacityGases=corr.HeatCapacityGases, T=T, P=P, zs=z)
        liquid2 = CEOSLiquid(PRMIX, eos_kwargs, HeatCapacityGases=corr.HeatCapacityGases, T=T, P=P, zs=z)

        flasher = FlashVLN(consts, corr, liquids=[liquid1, liquid2], gas=gas)
        state = flasher.flash(T=T, P=P, zs=z)

        # Extract phases
        VF = getattr(state, "VF", 0.0)
        gas_phase = getattr(state, "gas", None)
        liquids = getattr(state, "liquids", [])

        vapor_comp = {}
        if gas_phase is not None:
            vapor_comp = {names[i]: round(gas_phase.zs[i], 8) for i in range(n)}

        liquid_phases = []
        liquid_betas = []
        for liq in liquids:
            comp = {names[i]: round(liq.zs[i], 8) for i in range(n)}
            liquid_phases.append(comp)
            beta = getattr(liq, "beta", None)
            if beta is not None:
                liquid_betas.append(beta)

        # Get phase fractions from state
        betas = getattr(state, "betas", None)
        if betas is None:
            betas = []

        result: dict[str, Any] = {
            "status": "success",
            "VF": round(VF, 6) if VF is not None else 0.0,
            "n_liquid_phases": len(liquid_phases),
            "vapor_comp": vapor_comp,
            "phase_fractions": [round(b, 6) for b in betas] if betas else [],
        }

        if len(liquid_phases) >= 1:
            result["liquid1_comp"] = liquid_phases[0]
        if len(liquid_phases) >= 2:
            result["liquid2_comp"] = liquid_phases[1]

        return result

    except ImportError:
        logger.warning("thermo library not available for VLLE flash")
        return None
    except Exception as exc:
        logger.debug("flash_vlle failed for %s at T=%.1f P=%.0f: %s", names, T, P, exc)
        return None


def get_actionable_message(key: str, **kwargs) -> str:
    """Return an actionable engineering guidance message.

    Args:
        key: error category key
        **kwargs: format parameters for the message template

    Returns:
        Formatted guidance string, or generic message if key unknown.
    """
    template = _ERROR_GUIDANCE.get(key, f"Engineering calculation error: {key}")
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
