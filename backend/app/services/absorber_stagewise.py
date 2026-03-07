"""Stage-by-stage equilibrium model for absorbers and strippers.

Replaces the Kremser shortcut with a rigorous countercurrent equilibrium-stage
calculation that accounts for temperature-dependent K-values across the column.

Motivation
----------
The Kremser equation assumes constant K-values on every stage, which is valid
for nearly-isothermal physical absorption but breaks down when:

  * Temperature varies 20-40 C across the column (amine systems).
  * Heat of absorption shifts equilibrium on lower stages.
  * Reactive systems (CO2/H2S in MEA/DEA) have strongly T-dependent
    effective K-values (Kent-Eisenberg / eCPA behaviour).

This module provides ``solve_absorber_stagewise``, which solves the full MESH
(Material balance, Equilibrium, Summation, enthalpy/Heat balance) equations
stage by stage with successive substitution on stage temperatures.

The Kremser solution is retained as a fast initialisation for flow profiles
and as an automatic fallback when the rigorous solver does not converge.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.services.flash_helpers import wilson_k_values, normalize_compound_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Physical constants & reference data
# ---------------------------------------------------------------------------
_R = 8.314462  # J/(mol K)

# Heat of absorption (kJ/mol, exothermic) for acid-gas / amine systems.
# Positive value = heat released when gas is absorbed into liquid.
_HEAT_OF_ABSORPTION: dict[str, float] = {
    "carbon dioxide": 84.0,
    "hydrogen sulfide": 60.0,
    "sulfur dioxide": 50.0,
    "ammonia": 35.0,
}

# Default effective K-values for reactive (chemical) absorption.
# Format: compound -> (K_eff_ref, T_ref_K, dH_abs_kJ_mol)
_REACTIVE_K_EFF_DEFAULT: dict[str, tuple[float, float, float]] = {
    "carbon dioxide": (0.02, 313.15, 84.0),
    "hydrogen sulfide": (0.008, 313.15, 60.0),
    "sulfur dioxide": (0.03, 313.15, 50.0),
    "ammonia": (0.05, 298.15, 35.0),
}

# Built-in molecular weights (g/mol) for compounds that appear frequently.
# Used when the thermo library is not available.
_MW_BUILTIN: dict[str, float] = {
    "water": 18.015,
    "carbon dioxide": 44.010,
    "hydrogen sulfide": 34.081,
    "methane": 16.043,
    "ethane": 30.069,
    "propane": 44.096,
    "nitrogen": 28.014,
    "oxygen": 31.998,
    "hydrogen": 2.016,
    "sulfur dioxide": 64.066,
    "ammonia": 17.031,
    "monoethanolamine": 61.084,
    "diethanolamine": 105.137,
    "methyldiethanolamine": 119.163,
    "n-butane": 58.123,
    "i-butane": 58.123,
    "n-pentane": 72.150,
    "n-hexane": 86.177,
    "argon": 39.948,
    "carbon monoxide": 28.010,
}

# Rough ideal-gas Cp at 300 K (J/(mol K)).  Used only when thermo is
# unavailable; accurate enough for energy-balance initialisation.
_CP_IG_APPROX: dict[str, float] = {
    "water": 33.6,
    "carbon dioxide": 37.1,
    "hydrogen sulfide": 34.2,
    "methane": 35.7,
    "ethane": 52.5,
    "propane": 73.6,
    "nitrogen": 29.1,
    "oxygen": 29.4,
    "hydrogen": 28.8,
    "sulfur dioxide": 39.9,
    "ammonia": 35.1,
    "monoethanolamine": 135.0,
    "diethanolamine": 210.0,
    "methyldiethanolamine": 240.0,
    "n-butane": 97.5,
    "n-pentane": 120.0,
    "n-hexane": 143.0,
    "argon": 20.8,
    "carbon monoxide": 29.1,
}

# Approximate liquid-phase Cp (J/(mol K)) -- very rough, for energy
# balance when thermo is missing.
_CP_LIQ_APPROX: dict[str, float] = {
    "water": 75.3,
    "monoethanolamine": 170.0,
    "diethanolamine": 280.0,
    "methyldiethanolamine": 320.0,
    "carbon dioxide": 80.0,
    "hydrogen sulfide": 76.0,
    "methane": 55.0,
    "ethane": 70.0,
    "propane": 100.0,
    "nitrogen": 58.0,
}

# Critical properties for Wilson K-value fallback.
# Format: (Tc_K, Pc_Pa, omega)
_CRITICAL_PROPS: dict[str, tuple[float, float, float]] = {
    "water": (647.1, 22064000.0, 0.3449),
    "carbon dioxide": (304.2, 7382500.0, 0.2236),
    "hydrogen sulfide": (373.5, 8963000.0, 0.0942),
    "methane": (190.6, 4599200.0, 0.0115),
    "ethane": (305.3, 4872200.0, 0.0995),
    "propane": (369.8, 4248000.0, 0.1523),
    "nitrogen": (126.2, 3394400.0, 0.0377),
    "oxygen": (154.6, 5043000.0, 0.0222),
    "hydrogen": (33.2, 1296400.0, -0.216),
    "sulfur dioxide": (430.8, 7884000.0, 0.2454),
    "ammonia": (405.4, 11333000.0, 0.2526),
    "n-butane": (425.1, 3796000.0, 0.2002),
    "n-pentane": (469.7, 3370000.0, 0.2515),
    "n-hexane": (507.6, 3025000.0, 0.3013),
    "monoethanolamine": (678.0, 4460000.0, 0.6050),
    "diethanolamine": (736.6, 3270000.0, 0.9530),
    "methyldiethanolamine": (741.9, 3880000.0, 0.6320),
    "argon": (150.9, 4898000.0, -0.0022),
    "carbon monoxide": (132.9, 3499000.0, 0.0482),
}


# ---------------------------------------------------------------------------
# Thermo library availability (optional)
# ---------------------------------------------------------------------------
_thermo_available = False
try:
    from thermo import (  # type: ignore[import-untyped]
        ChemicalConstantsPackage,
        CEOSGas,
        CEOSLiquid,
        PRMIX,
        FlashVL,
    )

    _thermo_available = True
except Exception:
    pass

try:
    from thermo import SRKMIX  # type: ignore[import-untyped]
except Exception:
    SRKMIX = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_mw(name: str) -> float:
    """Return molecular weight in g/mol, falling back to built-in table."""
    clean = normalize_compound_name(name)
    if _thermo_available:
        try:
            consts = ChemicalConstantsPackage.constants_from_IDs([clean])
            if consts and consts.MWs and consts.MWs[0] is not None:
                return consts.MWs[0]
        except Exception:
            pass
    return _MW_BUILTIN.get(clean, 100.0)


def _get_cp_gas(name: str) -> float:
    """Return approximate ideal-gas Cp in J/(mol K)."""
    clean = normalize_compound_name(name)
    return _CP_IG_APPROX.get(clean, 35.0)


def _get_cp_liq(name: str) -> float:
    """Return approximate liquid Cp in J/(mol K)."""
    clean = normalize_compound_name(name)
    return _CP_LIQ_APPROX.get(clean, 75.0)


def _reactive_k_eff_at_T(
    compound: str,
    T: float,
    reactive_k_eff: dict[str, tuple[float, float, float]] | None,
) -> float | None:
    """Compute effective K for a reactive compound at temperature *T* (K).

    K_eff(T) = K_ref * exp(dH / (R * (1/T - 1/T_ref)))

    where dH is the heat of absorption in J/mol (converted from kJ/mol
    stored in the reference table).

    Returns ``None`` if the compound is not in the reactive table.
    """
    table = reactive_k_eff if reactive_k_eff is not None else _REACTIVE_K_EFF_DEFAULT
    entry = table.get(compound)
    if entry is None:
        return None
    k_ref, t_ref, dh_kj = entry

    # --- Root-cause fix: guard against invalid reference temperature --------
    # Callers may pass t_ref=0.0 (e.g. (k_ref, 0.0, 0.0)) when the reference
    # temperature is unknown or not applicable.  T_ref=0 K is physically
    # impossible and causes ZeroDivisionError in 1/t_ref below.  Fall back to
    # the built-in default T_ref for the compound, or 313.15 K (40 C, typical
    # amine absorber reference temperature).
    if t_ref <= 0.0:
        default_entry = _REACTIVE_K_EFF_DEFAULT.get(compound)
        t_ref = default_entry[1] if default_entry is not None else 313.15
        logger.debug(
            "_reactive_k_eff_at_T: t_ref <= 0 for %s, using default T_ref=%.2f K",
            compound, t_ref,
        )

    # Defense-in-depth: stage temperature T must also be positive.
    # T=0 K is thermodynamically impossible; clamp to a safe minimum.
    if T <= 0.0:
        logger.warning(
            "_reactive_k_eff_at_T: stage T=%.4f K for %s is non-physical, "
            "clamping to 200 K", T, compound,
        )
        T = 200.0

    dh_j = dh_kj * 1000.0  # kJ -> J
    try:
        # van't Hoff: d(ln K)/d(1/T) = -dH_abs/R for exothermic absorption (dH > 0)
        k_eff = k_ref * math.exp(-dh_j / _R * (1.0 / T - 1.0 / t_ref))
    except (OverflowError, ValueError):
        k_eff = k_ref
    return max(k_eff, 1e-12)


def _wilson_k_for_compound(name: str, T: float, P: float) -> float:
    """Wilson K-value for a single compound (fallback when thermo unavailable)."""
    clean = normalize_compound_name(name)
    props = _CRITICAL_PROPS.get(clean)
    if props is None:
        return 1.0
    Tc, Pc, omega = props
    ks = wilson_k_values([Tc], [Pc], [omega], T, P)
    return ks[0]


def _get_critical_props_from_chemicals(name: str) -> tuple[float, float, float] | None:
    """Look up Tc, Pc, omega from the chemicals library for ANY compound.

    Falls back to the built-in _CRITICAL_PROPS table if chemicals is unavailable.
    """
    clean = normalize_compound_name(name)

    # Try chemicals library first (covers thousands of compounds)
    try:
        from chemicals import Tc as _Tc, Pc as _Pc, omega as _omega  # type: ignore[import-untyped]
        from chemicals.identifiers import search_chemical  # type: ignore[import-untyped]
        chem = search_chemical(clean)
        if chem and chem.CASs:
            tc = _Tc(chem.CASs)
            pc = _Pc(chem.CASs)
            om = _omega(chem.CASs)
            if tc and pc and om is not None:
                return (tc, pc, om)
    except Exception:
        pass

    # Fallback to built-in table
    return _CRITICAL_PROPS.get(clean)


def _flash_k_values(
    comp_names: list[str],
    zs: list[float],
    T: float,
    P: float,
    property_package: str,
) -> dict[str, float] | None:
    """Obtain K-values from a thermo T-P flash.  Returns None on failure.

    ROOT CAUSE FIX (Phase 17.8):
    When the T,P flash returns single-phase (common at high pressure in
    absorber conditions), the old code tried a bubble-point flash that often
    failed, returning None and leaving the caller with Wilson K-values from
    a limited 18-entry table.

    The fix:
    1. If the T,P flash yields two phases → use y_i/x_i directly (unchanged).
    2. If single-phase → use Wilson K-values from chemicals library Tc/Pc/omega
       (covers ANY compound, not just the hardcoded 18).
    3. Never return K_i = 1.0 for all components (the root cause of the absorber
       failing to separate).
    """
    if not _thermo_available:
        return None
    if not comp_names or not zs:
        return None

    try:
        consts, props = ChemicalConstantsPackage.from_IDs(comp_names)
    except Exception:
        return None

    try:
        EOS_class = PRMIX
        if property_package.upper() in ("SRK", "SRKMIX") and SRKMIX is not None:
            EOS_class = SRKMIX

        eos_kwargs = dict(
            Tcs=consts.Tcs,
            Pcs=consts.Pcs,
            omegas=consts.omegas,
        )
        gas = CEOSGas(EOS_class, eos_kwargs, HeatCapacityGases=props.HeatCapacityGases, T=T, P=P, zs=zs)
        liquid = CEOSLiquid(EOS_class, eos_kwargs, HeatCapacityGases=props.HeatCapacityGases, T=T, P=P, zs=zs)
        flasher = FlashVL(consts, props, liquid=liquid, gas=gas)
        state = flasher.flash(T=T, P=P, zs=zs)

        vf = getattr(state, "VF", None)
        if vf is None:
            return None

        gas_phase = getattr(state, "gas", None)
        liq_phase = getattr(state, "liquid0", None)

        if gas_phase is not None and liq_phase is not None:
            result: dict[str, float] = {}
            all_unity = True
            for i, c in enumerate(comp_names):
                x_i = liq_phase.zs[i] if liq_phase.zs[i] > 1e-15 else 1e-15
                y_i = gas_phase.zs[i] if gas_phase.zs[i] > 1e-15 else 1e-15
                k_i = y_i / x_i
                result[c] = k_i
                if abs(k_i - 1.0) > 0.01:
                    all_unity = False

            # Guard: if all K ≈ 1.0, the flash didn't really separate —
            # fall through to Wilson fallback below.
            if not all_unity:
                return result

        # --- ROOT CAUSE FIX ---
        # Single-phase or degenerate two-phase (all K≈1): use Wilson K-values
        # from the chemicals library, which covers thousands of compounds.
        logger.debug(
            "_flash_k_values: single-phase at T=%.1f P=%.0f — using Wilson K fallback",
            T, P,
        )
        result_wilson: dict[str, float] = {}
        for i, c in enumerate(comp_names):
            props_c = _get_critical_props_from_chemicals(c)
            if props_c is not None:
                Tc, Pc, omega = props_c
                ks = wilson_k_values([Tc], [Pc], [omega], T, P)
                result_wilson[c] = ks[0]
            else:
                result_wilson[c] = 1.0
        return result_wilson

    except Exception as exc:
        logger.debug("_flash_k_values failed for %s at T=%.1f P=%.0f: %s",
                     comp_names, T, P, exc)

    return None


def _get_k_values(
    comp_names: list[str],
    zs: list[float],
    T: float,
    P: float,
    property_package: str,
    solutes: list[str],
    reactive_k_eff: dict[str, tuple[float, float, float]] | None,
) -> dict[str, float]:
    """Get K-values for all components, using flash when possible.

    For reactive solutes, the effective K-values override the flash result.
    Non-solute components use flash K-values or Wilson correlation as fallback.
    """
    # Start with flash-based K-values
    k_vals = _flash_k_values(comp_names, zs, T, P, property_package)

    # Fallback: Wilson K-values for everything
    if k_vals is None:
        k_vals = {}
        for c in comp_names:
            k_vals[c] = _wilson_k_for_compound(c, T, P)

    # Override solutes with reactive K_eff where applicable
    for c in solutes:
        k_eff = _reactive_k_eff_at_T(c, T, reactive_k_eff)
        if k_eff is not None:
            k_vals[c] = k_eff

    return k_vals


def _kremser_init(
    comp_names: list[str],
    gas_flows_in: dict[str, float],
    liquid_flows_in: dict[str, float],
    K_avg: dict[str, float],
    n_stages: int,
    G_total: float,
    L_total: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Kremser-based initial estimate for outlet molar flows.

    Returns (gas_out_moles, liquid_out_moles) dicts keyed by component name.
    """
    gas_out: dict[str, float] = {}
    liq_out: dict[str, float] = {}

    for c in comp_names:
        K = K_avg.get(c, 1.0)
        m = K
        n_g_in = gas_flows_in.get(c, 0.0)
        n_l_in = liquid_flows_in.get(c, 0.0)
        A = L_total / (m * G_total) if (m * G_total) > 1e-12 else 10.0

        if A > 1.001 and n_stages > 0 and n_g_in > 1e-15:
            frac_absorbed = (A ** (n_stages + 1) - A) / (A ** (n_stages + 1) - 1)
            frac_absorbed = max(0.0, min(1.0, frac_absorbed))
        elif A > 0.999:
            frac_absorbed = n_stages / (n_stages + 1)
        else:
            frac_absorbed = 0.0

        gas_out[c] = n_g_in * (1.0 - frac_absorbed)
        liq_out[c] = n_l_in + n_g_in * frac_absorbed

    return gas_out, liq_out


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_absorber_stagewise(
    gas_comp_names: list[str],
    gas_zs: list[float],
    gas_T: float,
    gas_P: float,
    gas_flow: float,           # kg/s
    liquid_comp_names: list[str],
    liquid_zs: list[float],
    liquid_T: float,
    liquid_P: float,
    liquid_flow: float,        # kg/s
    n_stages: int,
    solutes: list[str],        # components to absorb (e.g., ["carbon dioxide", "hydrogen sulfide"])
    property_package: str = "PengRobinson",
    reactive_k_eff: dict | None = None,  # override K-values for reactive systems
    pressure_drop_per_stage: float = 0.0,  # Pa per stage
) -> dict:
    """Solve an absorber or stripper using stage-by-stage equilibrium.

    Gas enters the bottom (stage N) and flows upward.
    Liquid enters the top (stage 1) and flows downward.
    Stage numbering: 1 = top, N = bottom.

    Parameters
    ----------
    gas_comp_names : list[str]
        Component names for the gas feed.
    gas_zs : list[float]
        Mole fractions of the gas feed (sum to 1).
    gas_T : float
        Gas feed temperature (K).
    gas_P : float
        Gas feed pressure (Pa).
    gas_flow : float
        Gas feed mass flow rate (kg/s).
    liquid_comp_names : list[str]
        Component names for the liquid feed (solvent).
    liquid_zs : list[float]
        Mole fractions of the liquid feed (sum to 1).
    liquid_T : float
        Liquid feed temperature (K).
    liquid_P : float
        Liquid feed pressure (Pa).
    liquid_flow : float
        Liquid feed mass flow rate (kg/s).
    n_stages : int
        Number of equilibrium stages.
    solutes : list[str]
        Components being absorbed (e.g., ``["carbon dioxide"]``).
    property_package : str
        Thermodynamic model for flash calculations (``"PengRobinson"`` or
        ``"SRK"``).
    reactive_k_eff : dict or None
        Override reactive K-value parameters.  Keys are component names,
        values are ``(K_ref, T_ref_K, dH_kJ_mol)`` tuples.  When ``None``
        the built-in amine/acid-gas defaults are used.
    pressure_drop_per_stage : float
        Pressure drop per stage (Pa).  Applied linearly from top to bottom.

    Returns
    -------
    dict
        converged : bool
        iterations : int
        gas_out_comp : dict   -- cleaned-gas mole fractions
        liquid_out_comp : dict -- rich-solvent mole fractions
        gas_out_T : float (K)
        liquid_out_T : float (K)
        removal_efficiency : dict  -- per-solute removal %
        stage_temperatures : list[float]
        stage_profiles : list[dict]  -- per-stage detail
    """
    # ------------------------------------------------------------------
    # 0. Input validation & normalisation
    # ------------------------------------------------------------------
    gas_comp_names = [normalize_compound_name(c) for c in gas_comp_names]
    liquid_comp_names = [normalize_compound_name(c) for c in liquid_comp_names]
    solutes = [normalize_compound_name(s) for s in solutes]

    if n_stages < 1:
        n_stages = 1
    if gas_flow <= 0 or liquid_flow <= 0:
        logger.error("solve_absorber_stagewise: non-positive flow rate "
                     "(gas=%.4g, liquid=%.4g)", gas_flow, liquid_flow)
        return _error_result("Non-positive flow rate supplied")

    # Unified component list (preserving order: gas first, then liquid-only)
    comp_set: dict[str, None] = {}
    for c in gas_comp_names:
        comp_set[c] = None
    for c in liquid_comp_names:
        comp_set[c] = None
    all_comps: list[str] = list(comp_set.keys())
    n_comp = len(all_comps)

    if n_comp == 0:
        return _error_result("No components specified")

    # Map input compositions onto the unified component list
    gas_z_map: dict[str, float] = {}
    for i, c in enumerate(gas_comp_names):
        gas_z_map[c] = gas_z_map.get(c, 0.0) + gas_zs[i]
    liq_z_map: dict[str, float] = {}
    for i, c in enumerate(liquid_comp_names):
        liq_z_map[c] = liq_z_map.get(c, 0.0) + liquid_zs[i]

    # Convert mass flows to molar flows (mol/s)
    mw_gas_mix = sum(gas_z_map.get(c, 0.0) * _get_mw(c) for c in all_comps)
    mw_liq_mix = sum(liq_z_map.get(c, 0.0) * _get_mw(c) for c in all_comps)
    if mw_gas_mix < 1e-6:
        mw_gas_mix = 28.0  # fallback ~ air
    if mw_liq_mix < 1e-6:
        mw_liq_mix = 18.0  # fallback ~ water

    G_total = gas_flow / (mw_gas_mix / 1000.0)       # mol/s
    L_total = liquid_flow / (mw_liq_mix / 1000.0)     # mol/s

    # Component molar flows in the feeds
    gas_feed_n: dict[str, float] = {c: gas_z_map.get(c, 0.0) * G_total for c in all_comps}
    liq_feed_n: dict[str, float] = {c: liq_z_map.get(c, 0.0) * L_total for c in all_comps}

    # Pressure profile (top to bottom)
    stage_P = [gas_P - pressure_drop_per_stage * (n_stages - 1 - j) for j in range(n_stages)]
    # Ensure no negative pressures
    stage_P = [max(p, 1e3) for p in stage_P]

    # ------------------------------------------------------------------
    # 1. Kremser initialisation
    # ------------------------------------------------------------------
    T_avg_init = (gas_T + liquid_T) / 2.0
    combined_zs_init: dict[str, float] = {}
    total_n_init = G_total + L_total
    for c in all_comps:
        combined_zs_init[c] = (gas_feed_n[c] + liq_feed_n[c]) / total_n_init if total_n_init > 0 else 0.0
    zs_init_list = [combined_zs_init[c] for c in all_comps]

    K_avg_init = _get_k_values(
        all_comps, zs_init_list, T_avg_init, gas_P, property_package,
        solutes, reactive_k_eff,
    )

    kremser_gas_out, kremser_liq_out = _kremser_init(
        all_comps, gas_feed_n, liq_feed_n, K_avg_init, n_stages, G_total, L_total,
    )

    logger.info(
        "Absorber stagewise: %d stages, %d components, G=%.2f mol/s, L=%.2f mol/s",
        n_stages, n_comp, G_total, L_total,
    )

    # ------------------------------------------------------------------
    # 2. Initialise stage temperatures & flow profiles
    # ------------------------------------------------------------------
    # Linear temperature profile from liquid_T (top) to gas_T (bottom)
    stage_T = [
        liquid_T + (gas_T - liquid_T) * j / max(n_stages - 1, 1)
        for j in range(n_stages)
    ]

    # Stage liquid and vapour molar flows per component
    # L[j][c] = liquid flow leaving stage j (flowing to j+1)
    # V[j][c] = vapour flow leaving stage j (flowing to j-1)
    # Initialise with linear interpolation between feed and Kremser outlet.
    # Gas flow profile accounts for absorption: V decreases from bottom to top.
    L_stage: list[dict[str, float]] = []
    V_stage: list[dict[str, float]] = []

    # Estimate overall removal for gas-flow profile initialisation
    total_solute_in = sum(gas_feed_n.get(s, 0.0) for s in solutes)
    total_solute_out = sum(kremser_gas_out.get(s, 0.0) for s in solutes)
    removal_frac = (
        (total_solute_in - total_solute_out) / total_solute_in
        if total_solute_in > 1e-15 else 0.0
    )

    for j in range(n_stages):
        frac = (j + 1) / n_stages  # 0 at top feed, 1 at bottom
        l_j: dict[str, float] = {}
        v_j: dict[str, float] = {}
        for c in all_comps:
            # Liquid profile: from liq_feed (enters top) to kremser_liq_out (leaves bottom)
            l_j[c] = liq_feed_n[c] + frac * (kremser_liq_out[c] - liq_feed_n[c])
            if c in solutes:
                # Gas flow for solutes decreases linearly from bottom to top
                absorbed_j = gas_feed_n.get(c, 0.0) * removal_frac * frac
                v_j[c] = max(gas_feed_n.get(c, 0.0) - absorbed_j, 0.0) * (1.0 - frac) + kremser_gas_out.get(c, 0.0) * frac
            else:
                # Non-solute gas: nearly constant
                v_j[c] = kremser_gas_out.get(c, 0.0) + (1.0 - frac) * (gas_feed_n.get(c, 0.0) - kremser_gas_out.get(c, 0.0))
        L_stage.append(l_j)
        V_stage.append(v_j)

    # ------------------------------------------------------------------
    # 3. Stage-by-stage MESH iteration
    # ------------------------------------------------------------------
    MAX_ITER = 200
    TOL = 1e-4
    # Adaptive damping: start conservative (0.3), increase to 0.7 as residuals decrease
    DAMP_MIN = 0.3
    DAMP_MAX = 0.7
    prev_max_dT = float("inf")

    converged = False
    iteration = 0

    for iteration in range(1, MAX_ITER + 1):
        T_old = list(stage_T)
        # Adaptive damping: increase damping as convergence improves
        if prev_max_dT < 1.0:
            DAMPING = DAMP_MAX
        elif prev_max_dT < 5.0:
            DAMPING = (DAMP_MIN + DAMP_MAX) / 2.0
        else:
            DAMPING = DAMP_MIN

        # --- Forward sweep: stage 1 (top) to stage N (bottom) ---
        for j in range(n_stages):
            P_j = stage_P[j]
            T_j = stage_T[j]

            # Flows entering stage j:
            #   Liquid in: L_feed (if j==0) or L_stage[j-1]
            #   Vapour in: V_feed (if j==N-1) or V_stage[j+1]
            L_in: dict[str, float] = liq_feed_n if j == 0 else L_stage[j - 1]
            V_in: dict[str, float] = gas_feed_n if j == n_stages - 1 else V_stage[j + 1]

            # Total moles entering stage
            L_in_total = sum(L_in.values())
            V_in_total = sum(V_in.values())

            # Mixed-feed composition for K-value evaluation
            total_in_j = L_in_total + V_in_total
            if total_in_j < 1e-15:
                continue
            mixed_z: list[float] = [
                (L_in.get(c, 0.0) + V_in.get(c, 0.0)) / total_in_j
                for c in all_comps
            ]

            # K-values at stage conditions
            K_j = _get_k_values(
                all_comps, mixed_z, T_j, P_j, property_package,
                solutes, reactive_k_eff,
            )

            # --- Material balance + equilibrium ---
            # For each component: total moles on stage = L_in_c + V_in_c
            # Equilibrium: y_c = K_c * x_c
            # Summation:   sum(x_c) = 1, sum(y_c) = 1
            # We solve for L_out and V_out compositions.
            #
            # Defining F_c = L_in_c + V_in_c (total component feed to stage),
            # L_out_total and V_out_total are constrained by overall balances.
            # We approximate total flows: L_out ~ L_in_total (nearly constant
            # molar overflow for dilute systems), then correct.

            F_c: dict[str, float] = {}
            for c in all_comps:
                F_c[c] = L_in.get(c, 0.0) + V_in.get(c, 0.0)
            F_total = sum(F_c.values())

            # Split F_c into L and V using equilibrium: y = K*x
            # x_c = F_c / (L_ratio + K_c * V_ratio)  where L_ratio + V_ratio = 1
            # This is essentially a Rachford-Rice solve on the stage.
            # V_ratio = fraction of total moles leaving as vapour.

            # Estimate V_ratio from overall flow balance
            V_ratio_est = V_in_total / total_in_j if total_in_j > 1e-15 else 0.5
            V_ratio = max(0.01, min(0.99, V_ratio_est))

            # Rachford-Rice on the stage
            K_list = [K_j.get(c, 1.0) for c in all_comps]
            z_stage = [F_c[c] / F_total if F_total > 0 else 0.0 for c in all_comps]

            V_ratio = _solve_rr_bisection(z_stage, K_list)

            # Compute x, y from converged V_ratio
            x_j: list[float] = []
            y_j: list[float] = []
            for i, c in enumerate(all_comps):
                denom = 1.0 + V_ratio * (K_list[i] - 1.0)
                x_i = z_stage[i] / max(denom, 1e-15)
                x_j.append(x_i)
                y_j.append(K_list[i] * x_i)

            # Normalise
            sx = sum(x_j) or 1.0
            sy = sum(y_j) or 1.0
            x_j = [v / sx for v in x_j]
            y_j = [v / sy for v in y_j]

            # Compute total outgoing flows
            V_out_total = V_ratio * F_total
            L_out_total = (1.0 - V_ratio) * F_total

            # Update stage flow arrays
            for i, c in enumerate(all_comps):
                L_stage[j][c] = x_j[i] * L_out_total
                V_stage[j][c] = y_j[i] * V_out_total

            # --- Energy balance: update stage temperature ---
            # Q_stage = 0 (adiabatic)
            # L_in * Cp_L * T_L_in + V_in * Cp_V * T_V_in
            #   = L_out * Cp_L * T_j + V_out * Cp_V * T_j + Q_abs
            #
            # Q_abs = sum over solutes of (moles_absorbed_on_stage * dH_abs)

            T_L_in = liquid_T if j == 0 else stage_T[j - 1]
            T_V_in = gas_T if j == n_stages - 1 else stage_T[j + 1]

            # Moles absorbed on this stage (transferred from V to L)
            Q_abs_j = 0.0  # J/s
            for c in solutes:
                # Moles of solute entering in vapour minus leaving in vapour
                v_in_c = V_in.get(c, 0.0)
                v_out_c = V_stage[j].get(c, 0.0)
                moles_absorbed = max(v_in_c - v_out_c, 0.0)
                dh = _HEAT_OF_ABSORPTION.get(c, 0.0) * 1000.0  # kJ -> J per mol
                Q_abs_j += moles_absorbed * dh

            # Weighted Cp for the stage
            Cp_L_mix = sum(
                (L_in.get(c, 0.0) / max(L_in_total, 1e-15)) * _get_cp_liq(c)
                for c in all_comps
            ) if L_in_total > 1e-15 else 75.0
            Cp_V_mix = sum(
                (V_in.get(c, 0.0) / max(V_in_total, 1e-15)) * _get_cp_gas(c)
                for c in all_comps
            ) if V_in_total > 1e-15 else 35.0

            # Latent heat of non-solute phase changes between stages
            Q_latent_j = 0.0
            for c in all_comps:
                if c in solutes:
                    continue  # solute latent heat already in Q_abs_j
                v_in_c = V_in.get(c, 0.0)
                v_out_c = V_stage[j].get(c, 0.0)
                delta_vap = v_out_c - v_in_c  # positive = vaporised
                if abs(delta_vap) > 1e-12:
                    # Clausius-Clapeyron Hvap(T) via Watson correlation
                    props = _CRITICAL_PROPS.get(c)
                    if props is not None:
                        Tc_c, _, _ = props
                        # Trouton: Hvap_nb ~ 88 * Tb; approximate Tb ~ 0.6 * Tc
                        Tb_c = 0.6 * Tc_c
                        hvap_nb = 88.0 * Tb_c
                        tr = min(T_j / Tc_c, 0.99)
                        tbr = min(Tb_c / Tc_c, 0.99)
                        ratio = (1.0 - tr) / (1.0 - tbr) if (1.0 - tbr) > 0.01 else 1.0
                        hvap_T = hvap_nb * max(ratio, 0.0) ** 0.38
                    else:
                        hvap_T = 30000.0  # fallback J/mol
                    Q_latent_j -= delta_vap * hvap_T  # vaporisation absorbs heat

            H_in = L_in_total * Cp_L_mix * T_L_in + V_in_total * Cp_V_mix * T_V_in
            denom_T = L_out_total * Cp_L_mix + V_out_total * Cp_V_mix
            if denom_T > 1e-10:
                T_new = (H_in + Q_abs_j + Q_latent_j) / denom_T
            else:
                T_new = T_j

            # Clamp to physically reasonable range
            T_min = min(liquid_T, gas_T) - 10.0
            T_max = max(liquid_T, gas_T) + 80.0  # absorption can raise T significantly
            T_new = max(T_min, min(T_max, T_new))

            # Damped update
            stage_T[j] = T_j + DAMPING * (T_new - T_j)

        # --- Check convergence on temperature AND material balance ---
        max_dT = max(abs(stage_T[j] - T_old[j]) for j in range(n_stages))

        # Material balance check: total moles in ≈ total moles out per stage
        max_mb_err = 0.0
        for j in range(n_stages):
            moles_in = sum(L_stage[j - 1].values()) if j > 0 else sum(liq_feed_n.values())
            moles_in += sum(V_stage[j + 1].values()) if j < n_stages - 1 else sum(gas_feed_n.values())
            moles_out = sum(L_stage[j].values()) + sum(V_stage[j].values())
            if moles_in > 1e-15:
                mb_err = abs(moles_out - moles_in) / moles_in
                max_mb_err = max(max_mb_err, mb_err)

        prev_max_dT = max_dT

        if max_dT < TOL and max_mb_err < 0.01:  # 1% material balance closure
            converged = True
            logger.info(
                "Absorber stagewise converged in %d iterations (max dT=%.2e K, max MB err=%.2e)",
                iteration, max_dT, max_mb_err,
            )
            break

        if iteration % 50 == 0:
            logger.debug(
                "Absorber stagewise iteration %d: max dT=%.4f K",
                iteration, max_dT,
            )

    # ------------------------------------------------------------------
    # 4. If not converged, fall back to Kremser
    # ------------------------------------------------------------------
    used_kremser_fallback = False
    if not converged:
        logger.warning(
            "Absorber stagewise did NOT converge after %d iterations "
            "(max dT=%.4f K). Falling back to Kremser initialisation.",
            MAX_ITER, max_dT if iteration > 0 else float("inf"),
        )
        used_kremser_fallback = True
        # Use Kremser results directly
        for i, c in enumerate(all_comps):
            V_stage[0][c] = kremser_gas_out[c]
            L_stage[n_stages - 1][c] = kremser_liq_out[c]
        # Linear temperature fallback
        stage_T = [
            liquid_T + (gas_T - liquid_T) * j / max(n_stages - 1, 1)
            for j in range(n_stages)
        ]

    # ------------------------------------------------------------------
    # 5. Extract results
    # ------------------------------------------------------------------
    # Gas out = vapour leaving stage 1 (top)
    gas_out_n = {c: V_stage[0].get(c, 0.0) for c in all_comps}
    # Liquid out = liquid leaving stage N (bottom)
    liq_out_n = {c: L_stage[n_stages - 1].get(c, 0.0) for c in all_comps}

    # Normalise to mole fractions
    gas_out_total = sum(gas_out_n.values()) or 1e-15
    liq_out_total = sum(liq_out_n.values()) or 1e-15
    gas_out_comp = {c: gas_out_n[c] / gas_out_total for c in all_comps}
    liquid_out_comp = {c: liq_out_n[c] / liq_out_total for c in all_comps}

    # Remove near-zero components for cleanliness
    gas_out_comp = {c: z for c, z in gas_out_comp.items() if z > 1e-10}
    liquid_out_comp = {c: z for c, z in liquid_out_comp.items() if z > 1e-10}

    # Re-normalise after pruning
    s_g = sum(gas_out_comp.values()) or 1.0
    s_l = sum(liquid_out_comp.values()) or 1.0
    gas_out_comp = {c: z / s_g for c, z in gas_out_comp.items()}
    liquid_out_comp = {c: z / s_l for c, z in liquid_out_comp.items()}

    # Temperatures
    gas_out_T = stage_T[0]       # vapour exits at top
    liquid_out_T = stage_T[-1]   # liquid exits at bottom

    # Per-solute removal efficiency
    removal_efficiency: dict[str, float] = {}
    for s in solutes:
        n_in = gas_feed_n.get(s, 0.0)
        n_out = gas_out_n.get(s, 0.0)
        if n_in > 1e-15:
            removal_efficiency[s] = round((1.0 - n_out / n_in) * 100.0, 4)
        else:
            removal_efficiency[s] = 0.0

    # Per-stage profiles
    stage_profiles: list[dict[str, Any]] = []
    for j in range(n_stages):
        L_j_total = sum(L_stage[j].values()) or 1e-15
        V_j_total = sum(V_stage[j].values()) or 1e-15
        x_prof = {c: L_stage[j].get(c, 0.0) / L_j_total for c in all_comps}
        y_prof = {c: V_stage[j].get(c, 0.0) / V_j_total for c in all_comps}
        stage_profiles.append({
            "stage": j + 1,
            "temperature": round(stage_T[j], 4),
            "pressure": round(stage_P[j], 2),
            "liquid_flow_mol_s": round(L_j_total, 6),
            "vapor_flow_mol_s": round(V_j_total, 6),
            "liquid_comp": {c: round(z, 8) for c, z in x_prof.items() if z > 1e-12},
            "vapor_comp": {c: round(z, 8) for c, z in y_prof.items() if z > 1e-12},
        })

    result: dict[str, Any] = {
        "converged": converged,
        "iterations": iteration,
        "gas_out_comp": gas_out_comp,
        "liquid_out_comp": liquid_out_comp,
        "gas_out_T": round(gas_out_T, 4),
        "liquid_out_T": round(liquid_out_T, 4),
        "removal_efficiency": removal_efficiency,
        "stage_temperatures": [round(t, 4) for t in stage_T],
        "stage_profiles": stage_profiles,
    }

    if used_kremser_fallback:
        result["fallback"] = "kremser"
        result["warning"] = (
            "Stagewise solver did not converge; results are from Kremser "
            "shortcut (constant-K assumption). Temperature profile may be "
            "inaccurate for reactive / high-heat-of-absorption systems."
        )

    logger.info(
        "Absorber stagewise result: converged=%s, iterations=%d, "
        "removal=%s",
        converged, iteration,
        {s: f"{v:.1f}%" for s, v in removal_efficiency.items()},
    )

    return result


# ---------------------------------------------------------------------------
# Rachford-Rice bisection (standalone, no external dependency)
# ---------------------------------------------------------------------------

def _solve_rr_bisection(
    zs: list[float],
    K: list[float],
    tol: float = 1e-10,
    max_iter: int = 60,
) -> float:
    """Solve the Rachford-Rice equation for vapour fraction by bisection.

    Returns the vapour fraction V in [0, 1].
    """
    n = len(zs)
    if n == 0:
        return 0.5

    def rr(V: float) -> float:
        return sum(
            zs[i] * (K[i] - 1.0) / (1.0 + V * (K[i] - 1.0))
            for i in range(n)
        )

    f0 = rr(0.0)
    f1 = rr(1.0)

    if f0 <= 0.0:
        return 0.0
    if f1 >= 0.0:
        return 1.0

    lo, hi = 0.0, 1.0
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if (hi - lo) < tol:
            break
        if rr(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Error / fallback result builder
# ---------------------------------------------------------------------------

def _error_result(message: str) -> dict:
    """Build a non-converged result dict with an error message."""
    logger.error("solve_absorber_stagewise: %s", message)
    return {
        "converged": False,
        "iterations": 0,
        "gas_out_comp": {},
        "liquid_out_comp": {},
        "gas_out_T": 0.0,
        "liquid_out_T": 0.0,
        "removal_efficiency": {},
        "stage_temperatures": [],
        "stage_profiles": [],
        "error": message,
    }
