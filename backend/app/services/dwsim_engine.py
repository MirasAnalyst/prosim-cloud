import copy
import functools
import json
import logging
import math
from typing import Any

from app.core.config import settings
from app.services.distillation_rigorous import solve_rigorous_distillation
from app.services.flash_helpers import (
    normalize_compound_name,
    normalize_compound_names,
    wilson_k_values,
    solve_rachford_rice,
    validate_bip_matrix,
    get_actionable_message,
    flash_vlle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine availability flags
# ---------------------------------------------------------------------------

# Try DWSIM via pythonnet
_dwsim_available = False
try:
    import clr  # type: ignore[import-untyped]

    clr.AddReference("System")
    dwsim_path = settings.DWSIM_PATH
    import os

    for dll in [
        "DWSIM.Thermodynamics",
        "DWSIM.UnitOperations",
        "DWSIM.FlowsheetSolver",
        "DWSIM.Interfaces",
        "DWSIM.GlobalSettings",
        "DWSIM.SharedClasses",
        "DWSIM.Thermodynamics.CoolPropInterface",
    ]:
        dll_path = os.path.join(dwsim_path, f"{dll}.dll")
        if os.path.exists(dll_path):
            clr.AddReference(dll_path)

    from DWSIM.Thermodynamics import PropertyPackages  # type: ignore[import-untyped]
    from DWSIM.UnitOperations import UnitOperations  # type: ignore[import-untyped]
    from DWSIM.FlowsheetSolver import FlowsheetSolver  # type: ignore[import-untyped]
    from DWSIM.Interfaces import IFlowsheet  # type: ignore[import-untyped]
    from DWSIM.SharedClasses import Flowsheet as DWSIMFlowsheet  # type: ignore[import-untyped]

    _dwsim_available = True
    logger.info("DWSIM engine loaded successfully via pythonnet")
except Exception as exc:
    logger.warning("DWSIM not available (%s), using fallback", exc)

# Try thermo (separate from CoolProp so each can work independently)
_thermo_available = False
try:
    from thermo import ChemicalConstantsPackage, CEOSGas, CEOSLiquid, PRMIX, FlashVL, FlashPureVLS  # type: ignore[import-untyped]
    from thermo import GibbsExcessLiquid  # type: ignore[import-untyped]
    from thermo.nrtl import NRTL as NRTLModel  # type: ignore[import-untyped]
    from thermo.uniquac import UNIQUAC as UNIQUACModel  # type: ignore[import-untyped]
    from thermo.interaction_parameters import IPDB  # type: ignore[import-untyped]

    _thermo_available = True
    logger.info("thermo library available")

    # Try importing SRK for property package support
    try:
        from thermo import SRKMIX  # type: ignore[import-untyped]
    except ImportError:
        SRKMIX = None  # type: ignore[assignment]
except Exception as exc:
    logger.warning("thermo not available: %s", exc)

# Try CoolProp (optional, independent of thermo)
_coolprop_available = False
try:
    import CoolProp.CoolProp as CP  # type: ignore[import-untyped]

    _coolprop_available = True
    logger.info("CoolProp available")
except Exception as exc:
    logger.warning("CoolProp not available: %s", exc)


# ---------------------------------------------------------------------------
# Unit conversion helpers
# Frontend uses: °C, kPa, kW, %
# Internal / CoolProp / thermo use: K, Pa, W, fraction
# ---------------------------------------------------------------------------

def _c_to_k(t_c: float) -> float:
    """Celsius → Kelvin."""
    return t_c + 273.15


def _k_to_c(t_k: float) -> float:
    """Kelvin → Celsius."""
    return t_k - 273.15


def _kpa_to_pa(p_kpa: float) -> float:
    return p_kpa * 1000.0


def _pa_to_kpa(p_pa: float) -> float:
    return p_pa / 1000.0


def _kw_to_w(power_kw: float) -> float:
    return power_kw * 1000.0


def _w_to_kw(power_w: float) -> float:
    return power_w / 1000.0


def _lmtd_correction_factor(R: float, P: float, n_shell_passes: int = 1) -> float:
    """LMTD correction factor (Ft) for shell-and-tube exchangers.

    Bowman (1940) analytical formula for 1-2N exchangers.
    R = (T1in - T1out) / (T2out - T2in)  (capacity ratio)
    P = (T2out - T2in) / (T1in - T2in)   (effectiveness)
    n_shell_passes: number of shell passes (1, 2, etc.)
    """
    if P < 1e-10:
        return 1.0
    if P * R > 1.0 - 1e-10:
        return 0.5  # thermodynamically infeasible

    # For multi-shell passes, convert to per-shell P
    if n_shell_passes > 1:
        # Seider et al.: P_1 from overall P for N shells
        PR = P * R
        if abs(PR - 1.0) < 1e-6:
            P1 = P / n_shell_passes
        else:
            E = ((1 - PR) / (1 - P)) ** (1.0 / n_shell_passes)
            P1 = (E - 1) / (E - R) if abs(E - R) > 1e-10 else P / n_shell_passes
        P = max(P1, 1e-10)

    if abs(R - 1.0) < 1e-6:
        # Special case R=1: F = (P*sqrt(2)) / ((1-P) * ln((2-P*(2-sqrt(2)))/(2-P*(2+sqrt(2)))))
        s2 = math.sqrt(2.0)
        a = 2.0 - P * (2.0 - s2)
        b = 2.0 - P * (2.0 + s2)
        if b <= 0 or a <= 0:
            return 0.75
        F = P * s2 / ((1.0 - P) * math.log(a / b))
        return max(min(F, 1.0), 0.5)

    S = math.sqrt(R * R + 1.0)
    # Bowman formula: F = S*ln(W) / ((R-1)*ln((2-P*(R+1-S))/(2-P*(R+1+S))))
    # where W = (1-PR)/(1-P)
    W = (1.0 - P * R) / (1.0 - P)
    if W <= 0:
        return 0.5
    a = 2.0 - P * (R + 1.0 - S)
    b = 2.0 - P * (R + 1.0 + S)
    if a <= 0 or b <= 0 or abs(b) < 1e-15:
        return 0.75
    ratio = a / b
    if ratio <= 0:
        return 0.75
    num = S * math.log(1.0 / W)  # = -S*ln(W); positive since W < 1
    den = (R - 1.0) * math.log(ratio)
    if abs(den) < 1e-10:
        return 0.75
    F = num / den
    return max(min(F, 1.0), 0.5)


# ---------------------------------------------------------------------------
# Equipment type map: frontend PascalCase → DWSIM class name
# Must match the EquipmentType enum in frontend/src/types/index.ts
# ---------------------------------------------------------------------------
EQUIPMENT_TYPE_MAP: dict[str, str] = {
    "Mixer": "Mixer",
    "Splitter": "Splitter",
    "Heater": "Heater",
    "Cooler": "Cooler",
    "Separator": "FlashDrum",
    "Pump": "Pump",
    "Compressor": "Compressor",
    "Valve": "Valve",
    "HeatExchanger": "HeatExchanger",
    "DistillationColumn": "DistillationColumn",
    "CSTRReactor": "CSTR",
    "PFRReactor": "PFR",
    "ConversionReactor": "ConversionReactor",
    "Absorber": "Absorber",
    "Stripper": "Stripper",
    "Cyclone": "Cyclone",
    "ThreePhaseSeparator": "ThreePhaseSeparator",
    "Crystallizer": "Crystallizer",
    "Dryer": "Dryer",
    "Filter": "Filter",
    "PipeSegment": "PipeSegment",
    "EquilibriumReactor": "EquilibriumReactor",
    "GibbsReactor": "GibbsReactor",
}

# Default feed conditions (SI units) when no upstream data and no user params
_DEFAULT_FEED = {
    "temperature": 298.15,   # K
    "pressure": 101325.0,    # Pa
    "mass_flow": 1.0,        # kg/s
    "vapor_fraction": 0.0,
    "enthalpy": 0.0,         # J/kg relative to T_ref=298.15 K (h=0 at 25 °C)
    "composition": {"water": 1.0},
}

# Reference temperature for enthalpy calculations (K)
_T_REF = 298.15
# Default Cp for water (J/(kg·K))
_CP_WATER = 4186.0
# Default Cp for air/gas (J/(kg·K))
_CP_AIR = 1005.0

# ---------------------------------------------------------------------------
# Pseudo-component support
# ---------------------------------------------------------------------------
# Global registry: maps pseudo-component name -> {mw, tb_k, tc, pc, omega, cp_ig}
# Populated at simulation start from flowsheet_data["pseudo_components"]
_PSEUDO_PROPS: dict[str, dict[str, float]] = {}


def _estimate_critical_props(mw: float, tb_k: float) -> dict[str, float]:
    """Estimate Tc, Pc, omega from MW and Tb for pseudo-components.

    Uses:
    - Tc: fitted Tb/(a + b*Tb) correlation (±5% for C5-C16 hydrocarbons)
    - Pc: corresponding-states Zc*R*Tc/Vc with Vc ~ MW correlation
    - omega: Edmister correlation
    """
    import math

    # Critical temperature: Tc = Tb / (0.567 + 0.0003 * Tb)
    # Fitted to n-alkane data C5-C16; gives Tc/Tb ≈ 1.29-1.52
    tc = tb_k / (0.567 + 0.0003 * tb_k)
    tc = max(tc, tb_k + 10.0)  # Tc must be > Tb

    # Critical pressure from corresponding states:
    # Zc ≈ 0.27, Vc ≈ 4.3e-6 * MW (m³/mol, fitted to n-alkanes)
    # Pc = Zc * R * Tc / Vc = 0.27 * 8.314 * Tc / (4.3e-6 * MW)
    # ≈ 522000 * Tc / MW (Pa)
    pc = 522000.0 * tc / max(mw, 1.0)  # Pa
    pc = max(pc, 500000.0)    # floor 500 kPa
    pc = min(pc, 10000000.0)  # cap 10 MPa

    # Edmister acentric factor: omega = (3/7) * log10(Pc/1atm) / (Tc/Tb - 1) - 1
    pc_atm = pc / 101325.0
    tc_over_tb = tc / max(tb_k, 1.0)
    if tc_over_tb > 1.01 and pc_atm > 1.0:
        omega = (3.0 / 7.0) * math.log10(pc_atm) / (tc_over_tb - 1.0) - 1.0
    else:
        omega = 0.3  # fallback
    omega = max(0.0, min(omega, 1.5))

    return {"tc": tc, "pc": pc, "omega": omega}


def _register_pseudo_components(pseudo_comps: list[dict]) -> list[str]:
    """Register pseudo-components in the global registry.
    Returns list of registered pseudo-component names (with pseudo: prefix stripped).
    """
    registered = []
    for pc in pseudo_comps:
        raw_name = pc.get("name", "").strip()
        if not raw_name:
            continue
        # Strip "pseudo:" prefix if present (frontend adds it to compounds list)
        pc_name = raw_name.lower().replace("pseudo:", "").strip()
        if not pc_name:
            continue

        pc_mw = float(pc.get("mw", 100))
        pc_tb_c = float(pc.get("tb", 100))
        pc_tb_k = pc_tb_c + 273.15

        # User-supplied or auto-estimated critical properties
        user_tc = pc.get("tc")
        user_pc = pc.get("pc")
        user_omega = pc.get("omega")

        est = _estimate_critical_props(pc_mw, pc_tb_k)
        tc_k = (float(user_tc) + 273.15) if user_tc is not None else est["tc"]
        pc_pa = (float(user_pc) * 1000.0) if user_pc is not None else est["pc"]
        omega = float(user_omega) if user_omega is not None else est["omega"]

        # Estimate ideal gas Cp (J/mol/K) — count ~3R per heavy atom (C,O,N,S)
        # For hydrocarbons: ~3 atoms per CH2 (14 g/mol), so n_atoms ~ MW/14*3
        # Cp_ig ~ n_atoms * R ~ (MW/14*3) * 8.314 = MW * 1.78
        n_heavy_atoms = pc_mw / 14.0 * 3.0  # approximate atom count
        cp_ig = max(n_heavy_atoms * 8.314, 33.0)  # J/(mol·K), floor at 4R

        _PSEUDO_PROPS[pc_name] = {
            "mw": pc_mw,
            "tb_k": pc_tb_k,
            "tc": tc_k,
            "pc": pc_pa,
            "omega": omega,
            "cp_ig": cp_ig,
        }
        # Also register in MW table
        _MW_BUILTIN[pc_name] = pc_mw

        registered.append(pc_name)
        logger.info("Registered pseudo-component '%s': MW=%.1f, Tb=%.1fK, Tc=%.1fK, Pc=%.0fPa, omega=%.3f",
                     pc_name, pc_mw, pc_tb_k, tc_k, pc_pa, omega)
    return registered


# ---------------------------------------------------------------------------
# Molecular weight cache and helpers
# ---------------------------------------------------------------------------
# Built-in MW fallback for common compounds (g/mol)
_MW_BUILTIN: dict[str, float] = {
    "water": 18.015, "methane": 16.043, "ethane": 30.069, "propane": 44.096,
    "n-butane": 58.122, "isobutane": 58.122, "n-pentane": 72.149,
    "isopentane": 72.149, "n-hexane": 86.175, "n-heptane": 100.202,
    "n-octane": 114.229, "n-decane": 142.282, "ethylene": 28.053,
    "propylene": 42.080, "benzene": 78.112, "toluene": 92.138,
    "o-xylene": 106.165, "methanol": 32.042, "ethanol": 46.068,
    "acetone": 58.079, "acetic acid": 60.052, "hydrogen": 2.016,
    "nitrogen": 28.014, "oxygen": 31.998, "carbon dioxide": 44.009,
    "carbon monoxide": 28.010, "hydrogen sulfide": 34.081,
    "sulfur dioxide": 64.064, "ammonia": 17.031, "chlorine": 70.906,
    "argon": 39.948, "helium": 4.003, "cyclohexane": 84.159,
    "styrene": 104.149, "1-propanol": 60.095, "2-propanol": 60.095,
    "diethyl ether": 74.121, "dimethyl ether": 46.068,
    "formic acid": 46.025, "formaldehyde": 30.026,
    "diethanolamine": 105.136, "monoethanolamine": 61.083,
    "sulfur": 32.065, "triethylene glycol": 150.173,
    "n-dodecane": 170.334, "n-hexadecane": 226.441,
}

# Heat capacity ratio (Cp/Cv) for compressor calculations
_GAMMA_TABLE: dict[str, float] = {
    "hydrogen": 1.41, "helium": 1.66, "nitrogen": 1.40, "oxygen": 1.40,
    "argon": 1.67, "carbon dioxide": 1.29, "carbon monoxide": 1.40,
    "water": 1.33, "ammonia": 1.31, "hydrogen sulfide": 1.32,
    "sulfur dioxide": 1.26, "chlorine": 1.36,
    "methane": 1.31, "ethane": 1.19, "propane": 1.13,
    "n-butane": 1.09, "isobutane": 1.10, "n-pentane": 1.07,
    "isopentane": 1.08, "n-hexane": 1.06, "n-heptane": 1.05,
    "n-octane": 1.04, "n-decane": 1.03,
    "ethylene": 1.24, "propylene": 1.15,
    "benzene": 1.10, "toluene": 1.09,
    "methanol": 1.20, "ethanol": 1.13, "acetone": 1.11,
    "dimethyl ether": 1.11, "diethyl ether": 1.08,
    "formaldehyde": 1.27,
}

# Heat of absorption (kJ/mol, exothermic) for acid gas absorption in amine solvents
_HEAT_OF_ABSORPTION: dict[str, float] = {
    "carbon dioxide": 84.0,
    "hydrogen sulfide": 60.0,
    "sulfur dioxide": 50.0,
    "ammonia": 35.0,
}

# Effective K-values for reactive (chemical) absorption systems.
# PR/SRK EOS gives physical VLE K-values that ignore chemical reactions
# (e.g., CO2 + 2 DEA → DEAH⁺ + DEACOO⁻). These effective K-values
# approximate Kent-Eisenberg / eCPA results at typical absorber conditions.
# Format: acid_gas -> (K_eff_ref, T_ref_K, dH_abs_kJ_mol for temperature correction)
_REACTIVE_K_EFF: dict[str, tuple[float, float, float]] = {
    "carbon dioxide": (0.02, 313.15, 84.0),   # Keff≈0.02 at 40°C in DEA/MEA
    "hydrogen sulfide": (0.008, 313.15, 60.0),  # Keff≈0.008 at 40°C in DEA/MEA
    "sulfur dioxide": (0.03, 313.15, 50.0),     # Keff≈0.03 at 40°C in aqueous
    "ammonia": (0.05, 298.15, 35.0),            # Keff≈0.05 at 25°C in water
}
# Amine solvents that enable reactive absorption for CO2/H2S
_AMINE_SOLVENTS: set[str] = {
    "monoethanolamine", "diethanolamine",
    "methyldiethanolamine", "diglycolamine",
    "diisopropanolamine", "piperazine",
}
# Aqueous solvents for SO2/NH3 physical+reactive absorption (no amine needed)
_AQUEOUS_REACTIVE: set[str] = {"sulfur dioxide", "ammonia"}

# C4: Solubility data for crystallizer (g solute / 100g water at various temperatures)
# Format: compound -> list of (T_celsius, solubility_g_per_100g_water)
_SOLUBILITY_TABLE: dict[str, list[tuple[float, float]]] = {
    "sodium chloride": [(0, 35.7), (20, 36.0), (40, 36.6), (60, 37.3), (80, 38.4), (100, 39.8)],
    "potassium chloride": [(0, 27.6), (20, 34.0), (40, 40.0), (60, 45.5), (80, 51.1), (100, 56.7)],
    "potassium nitrate": [(0, 13.3), (20, 31.6), (40, 63.9), (60, 110.0), (80, 169.0), (100, 246.0)],
    "urea": [(0, 67.0), (20, 108.0), (40, 167.0), (60, 251.0), (80, 400.0), (100, 733.0)],
    "sucrose": [(0, 179.2), (20, 203.9), (40, 238.1), (60, 287.3), (80, 362.1), (100, 487.2)],
    "ammonium sulfate": [(0, 70.6), (20, 75.4), (40, 81.0), (60, 88.0), (80, 95.3), (100, 103.8)],
    "sodium sulfate": [(0, 5.0), (20, 19.5), (40, 48.8), (60, 45.3), (80, 43.7), (100, 42.5)],
    "copper sulfate": [(0, 14.3), (20, 20.7), (40, 28.5), (60, 40.0), (80, 55.0), (100, 75.4)],
}


def _get_solubility(compound: str, T_celsius: float) -> float | None:
    """Interpolate solubility (g/100g water) at given T from table. Returns None if unknown."""
    data = _SOLUBILITY_TABLE.get(compound.lower())
    if not data:
        return None
    if T_celsius <= data[0][0]:
        return data[0][1]
    if T_celsius >= data[-1][0]:
        return data[-1][1]
    # Linear interpolation
    for i in range(len(data) - 1):
        t0, s0 = data[i]
        t1, s1 = data[i + 1]
        if t0 <= T_celsius <= t1:
            frac = (T_celsius - t0) / (t1 - t0) if t1 > t0 else 0
            return s0 + frac * (s1 - s0)
    return data[-1][1]


@functools.lru_cache(maxsize=256)
def _get_mw(comp_name: str) -> float:
    """Get molecular weight (g/mol) for a compound, with caching."""
    # Strip pseudo: prefix and normalize alias
    clean = normalize_compound_name(comp_name)

    # Check pseudo-component registry first
    pc = _PSEUDO_PROPS.get(clean.lower())
    if pc:
        return pc["mw"]

    # Try thermo/chemicals library (20,000+ compounds)
    if _thermo_available:
        try:
            c, _ = ChemicalConstantsPackage.from_IDs([clean])
            return c.MWs[0]
        except Exception:
            pass

    # Try chemicals library directly for broader coverage
    try:
        from chemicals import MW as chemicals_MW  # type: ignore[import-untyped]
        from chemicals import CAS_from_any  # type: ignore[import-untyped]
        cas = CAS_from_any(clean)
        if cas:
            mw = chemicals_MW(cas)
            if mw and mw > 0:
                return mw
    except Exception:
        pass

    # Fallback to builtin table
    return _MW_BUILTIN.get(clean.lower(), _MW_BUILTIN.get(clean, 18.015))


# Heat of vaporization (J/kg) for separator fallback
_HVAP_TABLE: dict[str, float] = {
    "water": 2260e3, "methane": 510e3, "ethane": 489e3, "propane": 426e3,
    "n-butane": 386e3, "isobutane": 366e3, "n-pentane": 358e3,
    "isopentane": 342e3, "n-hexane": 335e3, "n-heptane": 318e3,
    "n-octane": 302e3, "n-decane": 276e3,
    "hydrogen": 449e3, "nitrogen": 199e3, "oxygen": 213e3,
    "carbon dioxide": 234e3, "carbon monoxide": 216e3,
    "hydrogen sulfide": 548e3, "ammonia": 1371e3,
    "ethylene": 482e3, "propylene": 439e3,
    "benzene": 394e3, "toluene": 363e3, "methanol": 1100e3,
    "ethanol": 841e3, "acetone": 518e3,
}


def _estimate_hvap(composition: dict[str, float]) -> float:
    """Estimate composition-weighted heat of vaporization (J/kg) for fallback."""
    if not composition:
        return 2260e3  # water default
    total_mass_basis = sum(z * _get_mw(name) for name, z in composition.items())
    if total_mass_basis <= 0:
        return 2260e3
    total_hvap = 0.0
    for name, z in composition.items():
        mw = _get_mw(name)
        w_i = (z * mw) / total_mass_basis
        hvap_c = _HVAP_TABLE.get(name.lower(), _HVAP_TABLE.get(name, 300e3))
        total_hvap += w_i * hvap_c
    return total_hvap if total_hvap > 0 else 2260e3


def _clean_composition(comp: dict[str, float]) -> dict[str, float]:
    """Remove pseudo-components (like 'products') and renormalize."""
    _PSEUDO = {"products"}
    cleaned = {k: v for k, v in comp.items() if k not in _PSEUDO and v > 0}
    if not cleaned:
        return comp  # don't lose everything
    total = sum(cleaned.values())
    if total > 0 and abs(total - 1.0) > 1e-9:
        cleaned = {k: v / total for k, v in cleaned.items()}
    return cleaned


def _compute_component_properties(composition: dict[str, float], mass_flow: float) -> dict:
    """Compute per-component properties (HYSYS/DWSIM convention).

    Args:
        composition: mole fractions {name: z_i}
        mass_flow: total mass flow in kg/s

    Returns dict with molecular_weight, molar_flow, mass_fractions,
    component_molar_flows, component_mass_flows. Empty dict if invalid input.
    """
    if not composition or mass_flow <= 0:
        return {}
    mw_mix = sum(z * _get_mw(name) for name, z in composition.items())
    if mw_mix <= 0:
        return {}
    molar_flow = mass_flow / (mw_mix / 1000.0)  # mol/s
    mass_fracs = {name: z * _get_mw(name) / mw_mix for name, z in composition.items()}
    comp_molar = {name: z * molar_flow for name, z in composition.items()}
    comp_mass = {name: w * mass_flow for name, w in mass_fracs.items()}
    return {
        "molecular_weight": round(mw_mix, 4),
        "molar_flow": round(molar_flow, 6),
        "mass_fractions": {k: round(v, 6) for k, v in mass_fracs.items()},
        "component_molar_flows": {k: round(v, 6) for k, v in comp_molar.items()},
        "component_mass_flows": {k: round(v, 6) for k, v in comp_mass.items()},
    }


def _estimate_cp(composition: dict[str, float]) -> float:
    """Estimate mass-weighted Cp (J/kg/K) from composition for fallback.

    Light hydrocarbons (C1-C4) ~2200, gases (H2, N2, CO2) ~1000,
    water ~4186, heavier organics ~1800.
    """
    _CP_TABLE: dict[str, float] = {
        "water": 4186.0, "methane": 2226.0, "ethane": 1746.0,
        "propane": 1669.0, "n-butane": 1658.0, "isobutane": 1640.0,
        "n-pentane": 2310.0, "n-hexane": 2260.0, "n-heptane": 2240.0,
        "n-octane": 2220.0, "n-decane": 2210.0,
        "hydrogen": 14300.0, "nitrogen": 1040.0, "oxygen": 918.0,
        "carbon dioxide": 844.0, "carbon monoxide": 1040.0,
        "hydrogen sulfide": 1003.0, "ammonia": 2060.0,
        "ethylene": 1530.0, "propylene": 1520.0,
        "benzene": 1740.0, "toluene": 1690.0,
        "methanol": 2530.0, "ethanol": 2440.0, "acetone": 2160.0,
    }
    if not composition:
        return _CP_WATER

    # Convert mole fractions to mass fractions via MW, then mass-weight Cp
    total_mass_basis = 0.0
    for name, z in composition.items():
        mw = _get_mw(name)
        total_mass_basis += z * mw

    if total_mass_basis <= 0:
        return _CP_WATER

    total_cp = 0.0
    for name, z in composition.items():
        mw = _get_mw(name)
        w_i = (z * mw) / total_mass_basis  # mass fraction
        cp_c = _CP_TABLE.get(name.lower(), _CP_TABLE.get(name, 1800.0))
        total_cp += w_i * cp_c

    return total_cp if total_cp > 0 else _CP_WATER


class DWSIMEngine:
    """Process simulation engine.

    Priority:
      1. DWSIM via pythonnet (full-fidelity)
      2. thermo + optional CoolProp (flash calculations)
      3. Basic energy/mass balance (always available)
    """

    def __init__(self) -> None:
        self.use_dwsim = _dwsim_available
        self.use_thermo = _thermo_available
        self.use_coolprop = _coolprop_available

    @staticmethod
    def _normalize_nodes(nodes: list[dict]) -> list[dict]:
        """Normalize React Flow node format to engine's flat format.

        React Flow sends: {id, type: "equipment", data: {equipmentType, label, parameters}}
        Engine expects:   {id, type: "Heater", name: "...", parameters: {...}}
        """
        normalized = []
        for node in nodes:
            data = node.get("data", {})
            # If node has data.equipmentType, it's React Flow format
            eq_type = data.get("equipmentType")
            if eq_type:
                normalized.append({
                    "id": node.get("id", ""),
                    "type": eq_type,
                    "name": data.get("name", data.get("label", node.get("id", ""))),
                    "parameters": data.get("parameters", {}),
                    "position": node.get("position", {}),
                })
            else:
                # Already flat format or unknown — pass through
                normalized.append(node)
        return normalized

    @staticmethod
    def _find_nearest_feed(tear_edge_target: str, nodes: list[dict], edges: list[dict], feed_conditions: dict[str, dict]) -> dict | None:
        """BFS backward from tear edge target to find nearest FeedStream."""
        visited: set[str] = set()
        queue = [tear_edge_target]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            # Check if this is a FeedStream with known conditions
            node = next((n for n in nodes if n.get("id") == current), None)
            if node and node.get("type") == "FeedStream":
                feed_cond = feed_conditions.get(current)
                if feed_cond:
                    return dict(feed_cond)
            # Add upstream nodes (edges where target == current)
            for e in edges:
                if e.get("target") == current and e.get("type") != "energy-stream":
                    queue.append(e["source"])
        return None

    async def simulate(self, flowsheet_data: dict[str, Any]) -> dict[str, Any]:
        """Run simulation on flowsheet_data = {nodes, edges, property_package}."""
        nodes = self._normalize_nodes(flowsheet_data.get("nodes", []))
        edges = flowsheet_data.get("edges", [])
        property_package = flowsheet_data.get("property_package", "PengRobinson")
        simulation_basis = flowsheet_data.get("simulation_basis") or {}

        # Clear and register pseudo-components (prevents cross-session leakage)
        _PSEUDO_PROPS.clear()
        pseudo_comps = flowsheet_data.get("pseudo_components") or []
        if pseudo_comps:
            _register_pseudo_components(pseudo_comps)

        if not nodes:
            return {"status": "error", "error": "No equipment nodes in flowsheet"}

        if self.use_dwsim:
            try:
                return await self._simulate_dwsim(nodes, edges)
            except Exception as exc:
                logger.exception("DWSIM simulation failed, trying fallback")

        # Fallback: basic calculations (works with or without thermo/CoolProp)
        convergence_settings = flowsheet_data.get("convergence_settings") or {}
        progress_callback = flowsheet_data.get("progress_callback")
        return await self._simulate_basic(
            nodes, edges, property_package, convergence_settings,
            progress_callback, simulation_basis,
        )

    # ------------------------------------------------------------------
    # Public flash API
    # ------------------------------------------------------------------
    @staticmethod
    def flash_tp(
        comp_names: list[str],
        zs: list[float],
        T: float,
        P: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """Public API for TP flash.

        Delegates to the internal ``_flash_tp`` implementation.
        """
        return DWSIMEngine._flash_tp(comp_names, zs, T, P, property_package)

    # ------------------------------------------------------------------
    # Shared flash helper (reusable across equipment types)
    # ------------------------------------------------------------------
    @staticmethod
    def _flash_tp(
        comp_names: list[str],
        zs: list[float],
        T: float,
        P: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """Flash at T,P using thermo library.

        Returns dict with: T, P, H (J/mol), S (J/mol/K), VF, Cp (J/mol/K),
        gas_zs, liquid_zs, MW_mix, rho_liquid, flasher, constants, properties,
        or None if flash fails.
        """
        if not comp_names or not zs:
            return None

        try:
            # Normalize mole fractions
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            # Normalize compound names (alias resolution + pseudo: prefix strip)
            clean_names = normalize_compound_names(comp_names)

            # Check if any component is a pseudo-component
            has_pseudo = any(n.lower() in _PSEUDO_PROPS for n in clean_names)

            if has_pseudo:
                # Simplified flash for mixtures containing pseudo-components.
                # Cannot use thermo library (no CAS/properties for custom compounds).
                return DWSIMEngine._flash_tp_pseudo(clean_names, zs_norm, T, P)

            if not _thermo_available:
                return None

            # Phase 15 §4.4: CoolProp pure-component flash for reference-grade properties
            # ~110 fluids with Helmholtz EOS — superior accuracy for single-component streams
            if _coolprop_available and len(clean_names) == 1:
                try:
                    cp_result = DWSIMEngine._flash_tp_coolprop(clean_names[0], T, P)
                    if cp_result is not None:
                        return cp_result
                except Exception:
                    pass  # Fall through to thermo

            constants, properties = ChemicalConstantsPackage.from_IDs(clean_names)

            # Build gas + liquid phase objects based on property package
            if property_package in ("NRTL", "UNIQUAC") and len(comp_names) >= 2:
                # Activity coefficient models for non-ideal liquid mixtures
                # Gas phase: always use PR EOS
                pr_kijs = [[0.0] * len(comp_names) for _ in comp_names]
                try:
                    pr_kijs = IPDB.get_ip_asymmetric_matrix("ChemSep PR", constants.CASs, "kij")
                except Exception:
                    pass
                eos_kwargs_gas = {
                    "Pcs": constants.Pcs, "Tcs": constants.Tcs,
                    "omegas": constants.omegas, "kijs": pr_kijs,
                }
                gas = CEOSGas(
                    PRMIX, eos_kwargs_gas,
                    HeatCapacityGases=properties.HeatCapacityGases,
                    T=T, P=P, zs=zs_norm,
                )

                # Liquid phase: GibbsExcessLiquid with NRTL or UNIQUAC
                if property_package == "NRTL":
                    try:
                        taus = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "bij")
                        alphas = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "alphaij")
                    except Exception:
                        n = len(comp_names)
                        taus = [[0.0] * n for _ in range(n)]
                        alphas = [[0.3] * n for _ in range(n)]
                        logger.warning("NRTL BIPs not found for %s, using zero-interaction matrix", comp_names)

                    # Phase 15 §1.1: BIP Validation Gate — detect all-zero BIP matrix
                    has_bips, nz_count, total_pairs = validate_bip_matrix(taus, len(comp_names))
                    if not has_bips and len(comp_names) >= 2:
                        logger.warning(
                            "NRTL BIP matrix is all zeros for %s — activity coefficients will "
                            "be γ=1.0 (ideal solution). Auto-downgrading to Peng-Robinson EOS.",
                            comp_names,
                        )
                        # Recurse with PR to avoid silent ideal-solution results
                        result = DWSIMEngine._flash_tp(comp_names, zs, T, P, "PengRobinson")
                        if result:
                            result["_bip_warning"] = get_actionable_message("no_bips")
                            result["_original_pp"] = "NRTL"
                        return result

                    # M7: Also fetch aij parameters for full NRTL tau = aij + bij/T
                    tau_as = None
                    try:
                        tau_as = IPDB.get_ip_asymmetric_matrix("ChemSep NRTL", constants.CASs, "aij")
                    except Exception:
                        pass
                    nrtl_kwargs: dict[str, Any] = {"T": T, "xs": zs_norm, "tau_bs": taus, "alpha_cs": alphas}
                    if tau_as is not None:
                        nrtl_kwargs["tau_as"] = tau_as
                    ge_model = NRTLModel(**nrtl_kwargs)
                else:  # UNIQUAC
                    try:
                        taus = IPDB.get_ip_asymmetric_matrix("ChemSep UNIQUAC", constants.CASs, "bij")
                    except Exception:
                        n = len(comp_names)
                        taus = [[0.0] * n for _ in range(n)]
                        logger.warning("UNIQUAC BIPs not found for %s, using zero-interaction matrix", comp_names)

                    # Phase 15 §1.1: BIP Validation Gate — detect all-zero UNIQUAC BIPs
                    has_bips, nz_count, total_pairs = validate_bip_matrix(taus, len(comp_names))
                    if not has_bips and len(comp_names) >= 2:
                        logger.warning(
                            "UNIQUAC BIP matrix is all zeros for %s — auto-downgrading to PR.",
                            comp_names,
                        )
                        result = DWSIMEngine._flash_tp(comp_names, zs, T, P, "PengRobinson")
                        if result:
                            result["_bip_warning"] = get_actionable_message("no_bips")
                            result["_original_pp"] = "UNIQUAC"
                        return result
                    # UNIQUAC r/q: use UNIFAC dimensionless parameters, NOT Van der Waals volumes/areas
                    rs = constants.UNIFAC_Rs if constants.UNIFAC_Rs is not None else [2.0] * len(comp_names)
                    qs = constants.UNIFAC_Qs if constants.UNIFAC_Qs is not None else [1.8] * len(comp_names)
                    # Individual None entries: fallback per-component
                    rs = [r if r is not None else 2.0 for r in rs]
                    qs = [q if q is not None else 1.8 for q in qs]
                    ge_model = UNIQUACModel(
                        T=T, xs=zs_norm, tau_bs=taus,
                        rs=rs, qs=qs,
                    )

                liq = GibbsExcessLiquid(
                    VaporPressures=properties.VaporPressures,
                    HeatCapacityGases=properties.HeatCapacityGases,
                    VolumeLiquids=properties.VolumeLiquids,
                    GibbsExcessModel=ge_model,
                    T=T, P=P, zs=zs_norm,
                )
            else:
                # Cubic EOS (PR or SRK) for both phases
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

                EOS_class = PRMIX  # default
                if property_package == "SRK" and SRKMIX is not None:
                    EOS_class = SRKMIX

                gas = CEOSGas(
                    EOS_class, eos_kwargs,
                    HeatCapacityGases=properties.HeatCapacityGases,
                    T=T, P=P, zs=zs_norm,
                )
                liq = CEOSLiquid(
                    EOS_class, eos_kwargs,
                    HeatCapacityGases=properties.HeatCapacityGases,
                    T=T, P=P, zs=zs_norm,
                )
            # Use FlashPureVLS for single-component (FlashVL fails with div/0)
            if len(comp_names) == 1:
                flasher = FlashPureVLS(constants, properties, liquids=[liq], gas=gas, solids=[])
            else:
                flasher = FlashVL(constants, properties, liquid=liq, gas=gas)
            state = flasher.flash(T=T, P=P, zs=zs_norm)

            vf = state.VF if state.VF is not None else 0.0

            # Phase 15 §1.5: Supercritical phase classification
            # Use compressibility factor Z to decide phase behavior instead of
            # simple Tr/Pr thresholds. Z > 0.3 → gas-like, Z < 0.3 → liquid-like.
            _is_supercritical = False
            if hasattr(constants, 'Tcs') and len(constants.Tcs) > 0:
                Tc_mix = sum(zs_norm[i] * constants.Tcs[i] for i in range(len(zs_norm)))
                Pc_mix = sum(zs_norm[i] * constants.Pcs[i] for i in range(len(zs_norm)))
                Tr = T / Tc_mix if Tc_mix > 0 else 0
                Pr = P / Pc_mix if Pc_mix > 0 else 0
                if Tr > 1.0 and Pr > 0:
                    _is_supercritical = True
                    # Use actual Z from flash if available, else estimate
                    Z_actual = None
                    try:
                        Z_actual = state.Z()
                    except Exception:
                        pass
                    if Z_actual is None:
                        # Estimate from ideal gas: Z = PV/(nRT) ≈ P*MW/(ρ*R*T)
                        Z_actual = P * (MW_mix / 1000.0) / (8.314 * T) if T > 0 else 0.5
                    if vf < 0.5 and Z_actual > 0.3:
                        # Gas-like supercritical — force VF=1.0
                        vf = 1.0
                    elif vf > 0.5 and Z_actual < 0.2:
                        # Dense supercritical — keep as liquid-like
                        vf = 0.0

            # Compute mixture molecular weight
            MW_mix = sum(z * mw for z, mw in zip(zs_norm, constants.MWs))

            # Get enthalpy (J/mol), entropy (J/mol/K), and Cp (J/mol/K)
            H = state.H() if callable(getattr(state, 'H', None)) else 0.0
            try:
                S = state.S() if callable(getattr(state, 'S', None)) else 0.0
            except Exception:
                S = 0.0
            try:
                Cp = state.Cp() if callable(getattr(state, 'Cp', None)) else None
            except Exception:
                Cp = None

            gas_phase = getattr(state, 'gas', None)
            liquid_phase = getattr(state, 'liquid0', None)
            gas_zs = list(gas_phase.zs) if gas_phase else zs_norm
            liquid_zs = list(liquid_phase.zs) if liquid_phase else zs_norm

            # --- Per-phase property extraction (HYSYS/DWSIM-style) ---
            def _safe(obj: Any, method: str) -> float | None:
                """Safely call a phase property method, return None on failure."""
                fn = getattr(obj, method, None)
                if fn is None:
                    return None
                try:
                    val = fn()
                    if val is not None and math.isfinite(val):
                        return val
                except Exception:
                    pass
                return None

            # Liquid properties
            rho_liquid = _safe(liquid_phase, 'rho_mass') if liquid_phase else None
            mu_liquid = _safe(liquid_phase, 'mu') if liquid_phase else None
            k_liquid = _safe(liquid_phase, 'k') if liquid_phase else None  # W/(m·K)
            sigma = _safe(liquid_phase, 'sigma') if liquid_phase else None  # N/m
            Cp_liquid = _safe(liquid_phase, 'Cp_mass') if liquid_phase else None  # J/(kg·K)
            Cv_liquid = _safe(liquid_phase, 'Cv_mass') if liquid_phase else None  # J/(kg·K)
            H_liquid = _safe(liquid_phase, 'H') if liquid_phase else None  # J/mol
            S_liquid = _safe(liquid_phase, 'S') if liquid_phase else None  # J/(mol·K)
            Z_liquid = _safe(liquid_phase, 'Z') if liquid_phase else None

            # Gas properties
            rho_gas = _safe(gas_phase, 'rho_mass') if gas_phase else None
            mu_gas = _safe(gas_phase, 'mu') if gas_phase else None
            k_gas = _safe(gas_phase, 'k') if gas_phase else None  # W/(m·K)
            Cp_gas = _safe(gas_phase, 'Cp_mass') if gas_phase else None  # J/(kg·K)
            Cv_gas = _safe(gas_phase, 'Cv_mass') if gas_phase else None  # J/(kg·K)
            H_gas = _safe(gas_phase, 'H') if gas_phase else None  # J/mol
            S_gas = _safe(gas_phase, 'S') if gas_phase else None  # J/(mol·K)
            Z_gas = _safe(gas_phase, 'Z') if gas_phase else None

            # Fugacity coefficients (ln(phi)) for high-pressure corrections
            lnphis_gas = None
            if gas_phase:
                try:
                    lnphis_gas = list(gas_phase.lnphis())
                except Exception:
                    pass

            # Supercritical fallbacks: when VF forced to 1.0 but flash only has liquid phase,
            # use mixture-level properties as gas-phase substitutes
            if _is_supercritical and vf >= 0.999 and gas_phase is None:
                H_gas = H_gas if H_gas is not None else H  # Use mixture enthalpy
                S_gas = S_gas if S_gas is not None else S
                # Ideal gas density: P*MW/(R*T)
                if rho_gas is None and MW_mix > 0 and T > 0:
                    rho_gas = P * (MW_mix / 1000.0) / (8.314 * T)
                # Use liquid-phase properties as fallbacks for transport
                if mu_gas is None and mu_liquid is not None:
                    mu_gas = mu_liquid
                if Cp_gas is None and Cp_liquid is not None:
                    Cp_gas = Cp_liquid
            # Dense supercritical (VF kept at 0): ensure liquid properties available
            if _is_supercritical and vf <= 0.001 and liquid_phase is None:
                H_liquid = H_liquid if H_liquid is not None else H
                S_liquid = S_liquid if S_liquid is not None else S
                if rho_liquid is None and MW_mix > 0 and T > 0:
                    rho_liquid = P * (MW_mix / 1000.0) / (8.314 * T)  # Rough estimate

            # Mixture-level Cv and Z
            Cv_mix = None
            try:
                Cv_mix = state.Cv() if callable(getattr(state, 'Cv', None)) else None
            except Exception:
                pass

            Z_mix = None
            try:
                Z_mix = state.Z() if callable(getattr(state, 'Z', None)) else None
            except Exception:
                pass

            # Mixture density (kg/m³) — phase-fraction weighted
            rho_mix = None
            if vf >= 0.999 and rho_gas is not None:
                rho_mix = rho_gas
            elif vf <= 0.001 and rho_liquid is not None:
                rho_mix = rho_liquid
            elif rho_gas is not None and rho_liquid is not None and rho_liquid > 0 and rho_gas > 0:
                # Two-phase: 1/rho = VF/rho_gas + (1-VF)/rho_liquid
                rho_mix = 1.0 / (vf / rho_gas + (1.0 - vf) / rho_liquid)
            elif rho_liquid is not None:
                rho_mix = rho_liquid

            # Mixture Cp in mass basis J/(kg·K)
            Cp_mass_mix = None
            if Cp is not None and MW_mix > 0:
                Cp_mass_mix = Cp * 1000.0 / MW_mix  # J/mol/K * 1000 g/kg / (g/mol) = J/(kg·K)

            return {
                "T": T,
                "P": P,
                "H": H,             # J/mol
                "S": S,             # J/(mol·K)
                "VF": vf,
                "Cp": Cp,           # J/mol/K (may be None)
                "Cv": Cv_mix,       # J/mol/K (may be None)
                "Z": Z_mix,         # compressibility factor (dimensionless)
                "MW_mix": MW_mix,    # g/mol
                "MWs": list(constants.MWs),
                "rho_liquid": rho_liquid,  # kg/m³ or None
                "rho_gas": rho_gas,        # kg/m³ or None
                "rho_mix": rho_mix,        # kg/m³ or None
                "mu_liquid": mu_liquid,    # Pa·s or None
                "mu_gas": mu_gas,          # Pa·s or None
                "k_liquid": k_liquid,      # W/(m·K) or None
                "k_gas": k_gas,            # W/(m·K) or None
                "sigma": sigma,            # N/m (surface tension) or None
                "Cp_mass_mix": Cp_mass_mix,  # J/(kg·K) or None
                "Cp_liquid": Cp_liquid,    # J/(kg·K) or None
                "Cp_gas": Cp_gas,          # J/(kg·K) or None
                "Cv_liquid": Cv_liquid,    # J/(kg·K) or None
                "Cv_gas": Cv_gas,          # J/(kg·K) or None
                "H_liquid": H_liquid,      # J/mol or None
                "H_gas": H_gas,            # J/mol or None
                "S_liquid": S_liquid,      # J/(mol·K) or None
                "S_gas": S_gas,            # J/(mol·K) or None
                "Z_liquid": Z_liquid,      # dimensionless or None
                "Z_gas": Z_gas,            # dimensionless or None
                "gas_zs": gas_zs,
                "liquid_zs": liquid_zs,
                "lnphis_gas": lnphis_gas,
                "comp_names": comp_names,
                "zs": zs_norm,
                "flasher": flasher,
                "state": state,
                "constants": constants,
                "properties": properties,
            }
        except (ValueError, ArithmeticError, RuntimeError, ZeroDivisionError) as exc:
            # Phase 15 §1.2/1.6: Multi-solver retry with Wilson+RR intermediate
            # Attempt 1 already failed (EOS flash above)

            # Attempt 2: Retry with PR if using activity model
            if property_package in ("NRTL", "UNIQUAC"):
                logger.warning("_flash_tp %s failed for %s, retrying with PengRobinson: %s",
                               property_package, comp_names, exc)
                try:
                    result = DWSIMEngine._flash_tp(comp_names, zs, T, P, "PengRobinson")
                    if result:
                        result["_flash_warning"] = (
                            f"{property_package} flash failed — fell back to Peng-Robinson. "
                            "Results may be less accurate for polar/non-ideal mixtures."
                        )
                        return result
                except Exception:
                    pass

            # Attempt 3: Wilson K-values + Rachford-Rice (intermediate — better than ideal gas)
            logger.warning("_flash_tp EOS failed for %s at T=%.1f P=%.0f: %s — trying Wilson+RR",
                           comp_names, T, P, exc)
            try:
                constants_fb, properties_fb = ChemicalConstantsPackage.from_IDs(comp_names)
                total_fb = sum(zs)
                zs_fb = [z / total_fb for z in zs] if total_fb > 0 else zs
                MW_mix_fb = sum(z * mw for z, mw in zip(zs_fb, constants_fb.MWs))

                # Wilson K-values using actual critical properties
                K_wilson = wilson_k_values(
                    list(constants_fb.Tcs), list(constants_fb.Pcs),
                    list(constants_fb.omegas), T, P,
                )

                # Rachford-Rice for VF and phase compositions
                vf_fb, liq_xs, vap_ys = solve_rachford_rice(zs_fb, K_wilson)

                # Estimate Cp from HeatCapacityGases
                Cp_fb = None
                try:
                    Cp_fb = sum(zs_fb[i] * properties_fb.HeatCapacityGases[i].T_dependent_property(T)
                                for i in range(len(zs_fb)))
                except Exception:
                    pass

                # Enthalpy from Cp integration
                T_ref = 298.15
                H_fb = Cp_fb * (T - T_ref) if Cp_fb else 0.0

                # Density estimates
                rho_gas_fb = P * (MW_mix_fb / 1000.0) / (8.314 * T) if T > 0 else 1.0
                rho_liq_fb = 800.0  # rough default

                # Entropy estimate
                S_fb = 0.0
                if Cp_fb and T > 0:
                    S_fb = Cp_fb * math.log(T / T_ref) - 8.314 * math.log(max(P, 1.0) / 101325.0)

                return {
                    "T": T, "P": P, "H": H_fb, "S": S_fb, "Cp": Cp_fb,
                    "VF": vf_fb, "MW_mix": MW_mix_fb, "MWs": list(constants_fb.MWs),
                    "rho_liquid": rho_liq_fb, "rho_gas": rho_gas_fb,
                    "rho_mix": rho_gas_fb if vf_fb > 0.5 else rho_liq_fb,
                    "mu_liquid": None, "mu_gas": None,
                    "k_liquid": None, "k_gas": None, "sigma": None,
                    "Cp_mass_mix": Cp_fb * 1000.0 / MW_mix_fb if Cp_fb and MW_mix_fb > 0 else None,
                    "Cp_liquid": None, "Cp_gas": None,
                    "Cv_liquid": None, "Cv_gas": None,
                    "H_liquid": H_fb if vf_fb < 0.5 else None,
                    "H_gas": H_fb if vf_fb >= 0.5 else None,
                    "S_liquid": S_fb if vf_fb < 0.5 else None,
                    "S_gas": S_fb if vf_fb >= 0.5 else None,
                    "Z_liquid": None, "Z_gas": None,
                    "gas_zs": vap_ys, "liquid_zs": liq_xs,
                    "lnphis_gas": None,
                    "comp_names": comp_names, "zs": zs_fb,
                    "flasher": None, "state": None,
                    "constants": constants_fb, "properties": properties_fb,
                    "flash_degraded": True,
                    "_flash_warning": get_actionable_message("flash_failed"),
                }
            except Exception as exc2:
                logger.warning("Wilson+RR fallback also failed: %s — last resort ideal gas", exc2)

            # Attempt 4: Ideal gas fallback (last resort)
            try:
                constants_fb, properties_fb = ChemicalConstantsPackage.from_IDs(comp_names)
                total_fb = sum(zs)
                zs_fb = [z / total_fb for z in zs] if total_fb > 0 else zs
                MW_mix_fb = sum(z * mw for z, mw in zip(zs_fb, constants_fb.MWs))
                Cp_fb = None
                try:
                    Cp_fb = sum(zs_fb[i] * properties_fb.HeatCapacityGases[i].T_dependent_property(T)
                                for i in range(len(zs_fb)))
                except Exception:
                    pass
                T_ref = 298.15
                H_fb = Cp_fb * (T - T_ref) if Cp_fb else 0.0
                rho_gas_fb = P * (MW_mix_fb / 1000.0) / (8.314 * T) if T > 0 else 1.0
                vf_fb = 1.0 if all(T > 0.95 * Tc for Tc in constants_fb.Tcs) else 0.0
                return {
                    "T": T, "P": P, "H": H_fb, "S": 0.0, "Cp": Cp_fb,
                    "VF": vf_fb, "MW_mix": MW_mix_fb,
                    "rho_liquid": 800.0, "rho_gas": rho_gas_fb,
                    "mu_liquid": None, "mu_gas": None,
                    "H_liquid": H_fb if vf_fb < 0.5 else None,
                    "H_gas": H_fb if vf_fb >= 0.5 else None,
                    "S_liquid": None, "S_gas": None,
                    "Z_liquid": None, "Z_gas": None,
                    "gas_zs": zs_fb, "liquid_zs": zs_fb,
                    "comp_names": comp_names, "zs": zs_fb,
                    "flasher": None, "state": None,
                    "constants": constants_fb, "properties": properties_fb,
                    "flash_degraded": True,
                    "_flash_warning": "All flash methods failed — using ideal gas approximation. Results may be inaccurate.",
                }
            except Exception:
                pass
            return None
        except Exception as exc:
            logger.error("_flash_tp unexpected error for %s at T=%.1f P=%.0f: %s (%s)",
                         comp_names, T, P, exc, type(exc).__name__)
            return None

    # ------------------------------------------------------------------
    # CoolProp pure-component flash (Helmholtz EOS, ~110 fluids)
    # ------------------------------------------------------------------

    @staticmethod
    def _flash_tp_coolprop(
        compound: str,
        T: float,
        P: float,
    ) -> dict[str, Any] | None:
        """TP flash for a single component using CoolProp Helmholtz EOS.

        Returns reference-grade thermodynamic properties for ~110 supported
        fluids. Returns None if CoolProp doesn't support the compound.
        """
        if not _coolprop_available:
            return None

        # Map common names to CoolProp fluid names
        _CP_NAME_MAP: dict[str, str] = {
            "water": "Water", "methane": "Methane", "ethane": "Ethane",
            "propane": "Propane", "n-butane": "n-Butane", "isobutane": "IsoButane",
            "n-pentane": "n-Pentane", "isopentane": "Isopentane",
            "n-hexane": "n-Hexane", "n-heptane": "n-Heptane", "n-octane": "n-Octane",
            "n-nonane": "n-Nonane", "n-decane": "n-Decane",
            "n-dodecane": "n-Dodecane", "hydrogen": "Hydrogen",
            "nitrogen": "Nitrogen", "oxygen": "Oxygen",
            "carbon dioxide": "CarbonDioxide", "carbon monoxide": "CarbonMonoxide",
            "hydrogen sulfide": "HydrogenSulfide", "sulfur dioxide": "SulfurDioxide",
            "ammonia": "Ammonia", "argon": "Argon", "helium": "Helium",
            "ethylene": "Ethylene", "propylene": "Propylene",
            "methanol": "Methanol", "ethanol": "Ethanol",
            "benzene": "Benzene", "toluene": "Toluene",
            "cyclohexane": "CycloHexane", "acetone": "Acetone",
            "dimethyl ether": "DimethylEther",
            "diethyl ether": "DiethylEther",
            "dichloromethane": "DichloroMethane",
        }

        cp_name = _CP_NAME_MAP.get(compound.lower())
        if cp_name is None:
            # Try CoolProp's own name resolution
            try:
                CP.PropsSI("T", "T", 300, "P", 101325, compound)
                cp_name = compound
            except Exception:
                return None

        try:
            # Core flash properties
            H = CP.PropsSI("Hmolar", "T", T, "P", P, cp_name)  # J/mol
            S = CP.PropsSI("Smolar", "T", T, "P", P, cp_name)  # J/(mol·K)
            Cp_mol = CP.PropsSI("Cpmolar", "T", T, "P", P, cp_name)  # J/(mol·K)
            Cv_mol = CP.PropsSI("Cvmolar", "T", T, "P", P, cp_name)  # J/(mol·K)
            rho = CP.PropsSI("Dmass", "T", T, "P", P, cp_name)  # kg/m³
            MW = CP.PropsSI("M", "T", T, "P", P, cp_name) * 1000.0  # g/mol
            phase_idx = CP.PropsSI("Phase", "T", T, "P", P, cp_name)

            # Phase determination using CoolProp phase constants when available,
            # falling back to integer indices for compatibility
            _is_two_phase = False
            try:
                _phase_liquid = CP.iphase_liquid
                _phase_gas = CP.iphase_gas
                _phase_twophase = CP.iphase_twophase
                _phase_supercritical = CP.iphase_supercritical
                _phase_supercrit_gas = CP.iphase_supercritical_gas
                _phase_supercrit_liq = CP.iphase_supercritical_liquid
            except AttributeError:
                _phase_liquid, _phase_gas, _phase_twophase = 0, 5, 6
                _phase_supercritical, _phase_supercrit_gas, _phase_supercrit_liq = 1, 2, 3

            if phase_idx == _phase_twophase:
                vf = CP.PropsSI("Q", "T", T, "P", P, cp_name)
                vf = max(0.0, min(1.0, vf))
                _is_two_phase = True
            elif phase_idx in (_phase_liquid, _phase_supercrit_liq):
                vf = 0.0
            else:
                vf = 1.0

            # Transport & phase-specific properties
            rho_liquid = None
            rho_gas = None
            mu_liquid = None
            mu_gas = None
            k_liquid = None
            k_gas = None
            Cp_liquid = None
            Cp_gas = None
            sigma_val = None
            H_liquid = None
            H_gas = None
            S_liquid = None
            S_gas = None

            if _is_two_phase:
                # Query saturated phase properties individually for two-phase
                try:
                    rho_liquid = CP.PropsSI("Dmass", "Q", 0, "P", P, cp_name)
                    rho_gas = CP.PropsSI("Dmass", "Q", 1, "P", P, cp_name)
                except Exception:
                    pass
                try:
                    mu_liquid = CP.PropsSI("viscosity", "Q", 0, "P", P, cp_name)
                    mu_gas = CP.PropsSI("viscosity", "Q", 1, "P", P, cp_name)
                except Exception:
                    pass
                try:
                    k_liquid = CP.PropsSI("conductivity", "Q", 0, "P", P, cp_name)
                    k_gas = CP.PropsSI("conductivity", "Q", 1, "P", P, cp_name)
                except Exception:
                    pass
                try:
                    sigma_val = CP.PropsSI("surface_tension", "Q", 0, "P", P, cp_name)
                except Exception:
                    pass
                try:
                    Cp_liq_mol = CP.PropsSI("Cpmolar", "Q", 0, "P", P, cp_name)
                    Cp_gas_mol = CP.PropsSI("Cpmolar", "Q", 1, "P", P, cp_name)
                    Cp_liquid = Cp_liq_mol * 1000.0 / MW if MW > 0 else None
                    Cp_gas = Cp_gas_mol * 1000.0 / MW if MW > 0 else None
                except Exception:
                    pass
                try:
                    H_liquid = CP.PropsSI("Hmolar", "Q", 0, "P", P, cp_name)
                    H_gas = CP.PropsSI("Hmolar", "Q", 1, "P", P, cp_name)
                except Exception:
                    pass
                try:
                    S_liquid = CP.PropsSI("Smolar", "Q", 0, "P", P, cp_name)
                    S_gas = CP.PropsSI("Smolar", "Q", 1, "P", P, cp_name)
                except Exception:
                    pass
            else:
                # Single-phase: assign to the appropriate bucket
                try:
                    mu_val = CP.PropsSI("viscosity", "T", T, "P", P, cp_name)
                    if vf < 0.5:
                        mu_liquid = mu_val
                    else:
                        mu_gas = mu_val
                except Exception:
                    pass
                try:
                    k_val = CP.PropsSI("conductivity", "T", T, "P", P, cp_name)
                    if vf < 0.5:
                        k_liquid = k_val
                    else:
                        k_gas = k_val
                except Exception:
                    pass
                try:
                    sigma_val = CP.PropsSI("surface_tension", "T", T, "P", P, cp_name)
                except Exception:
                    pass

                if vf < 0.5:
                    rho_liquid = rho
                    H_liquid = H
                    S_liquid = S
                    Cp_liquid = Cp_mol * 1000.0 / MW if MW > 0 else None
                else:
                    rho_gas = rho
                    H_gas = H
                    S_gas = S
                    Cp_gas = Cp_mol * 1000.0 / MW if MW > 0 else None

            Z = P * (MW / 1000.0) / (rho * 8.314 * T) if rho > 0 and T > 0 else None
            Cp_mass = Cp_mol * 1000.0 / MW if MW > 0 else None
            Z_liquid = Z if vf < 0.5 else None
            Z_gas = Z if vf >= 0.5 else None
            if _is_two_phase:
                # Both phases present — compute Z for each
                if rho_liquid and rho_liquid > 0:
                    Z_liquid = P * (MW / 1000.0) / (rho_liquid * 8.314 * T)
                if rho_gas and rho_gas > 0:
                    Z_gas = P * (MW / 1000.0) / (rho_gas * 8.314 * T)

            return {
                "T": T,
                "P": P,
                "H": H,
                "S": S,
                "VF": vf,
                "Cp": Cp_mol,
                "Cv": Cv_mol,
                "Z": Z,
                "MW_mix": MW,
                "MWs": [MW],
                "rho_liquid": rho_liquid,
                "rho_gas": rho_gas,
                "rho_mix": rho,
                "mu_liquid": mu_liquid,
                "mu_gas": mu_gas,
                "k_liquid": k_liquid,
                "k_gas": k_gas,
                "sigma": sigma_val,
                "Cp_mass_mix": Cp_mass,
                "Cp_liquid": Cp_liquid,
                "Cp_gas": Cp_gas,
                "Cv_liquid": None,
                "Cv_gas": None,
                "H_liquid": H_liquid,
                "H_gas": H_gas,
                "S_liquid": S_liquid,
                "S_gas": S_gas,
                "Z_liquid": Z_liquid,
                "Z_gas": Z_gas,
                "gas_zs": [1.0],
                "liquid_zs": [1.0],
                "lnphis_gas": None,
                "comp_names": [compound],
                "zs": [1.0],
                "flasher": None,
                "state": None,
                "constants": None,
                "properties": None,
                "_source": "CoolProp Helmholtz EOS",
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Simplified flash for pseudo-component mixtures
    # ------------------------------------------------------------------

    @staticmethod
    def _flash_tp_pseudo(
        comp_names: list[str],
        zs: list[float],
        T: float,
        P: float,
    ) -> dict[str, Any] | None:
        """TP flash for mixtures containing pseudo-components.

        Phase 15 §1.3: Try PR EOS first by constructing ChemicalConstantsPackage
        from pseudo-component properties. Falls back to Wilson K-values if PR fails.
        """
        n = len(comp_names)
        if n == 0:
            return None

        # Gather per-component properties
        mws = []
        tbs = []
        tcs = []
        pcs = []
        omegas = []
        cps = []  # J/(mol·K)

        for name in comp_names:
            pc_props = _PSEUDO_PROPS.get(name.lower())
            if pc_props:
                mws.append(pc_props["mw"])
                tbs.append(pc_props["tb_k"])
                tcs.append(pc_props["tc"])
                pcs.append(pc_props["pc"])
                omegas.append(pc_props["omega"])
                cps.append(pc_props["cp_ig"])
            else:
                # Real component — look up from thermo if available, else use rough estimates
                mw = _MW_BUILTIN.get(name.lower(), 100.0)
                mws.append(mw)
                tb_est = 200.0 + mw * 1.5
                tbs.append(tb_est)
                tc_est = tb_est * 1.5
                tcs.append(tc_est)
                pcs.append(3000000.0)
                omegas.append(0.3)
                cps.append(max((mw / 14.0 * 3.0) * 8.314, 33.0))

                if _thermo_available:
                    try:
                        c, p = ChemicalConstantsPackage.from_IDs([name])
                        mws[-1] = c.MWs[0]
                        if c.Tbs and c.Tbs[0]:
                            tbs[-1] = c.Tbs[0]
                        if c.Tcs and c.Tcs[0]:
                            tcs[-1] = c.Tcs[0]
                        if c.Pcs and c.Pcs[0]:
                            pcs[-1] = c.Pcs[0]
                        if c.omegas and c.omegas[0] is not None:
                            omegas[-1] = c.omegas[0]
                        try:
                            cp_val = p.HeatCapacityGases[0].T_dependent_property(T)
                            if cp_val and cp_val > 0:
                                cps[-1] = cp_val
                        except Exception:
                            pass
                    except Exception:
                        pass

        MW_mix = sum(z * mw for z, mw in zip(zs, mws))

        # Phase 15 §1.3: Try PR EOS flash with manually constructed constants
        pr_flash_ok = False
        if _thermo_available and n >= 1:
            try:
                from thermo import PropertyCorrelationsPackage  # type: ignore[import-untyped]
                # Build a ChemicalConstantsPackage from our gathered properties
                constants_manual = ChemicalConstantsPackage(
                    MWs=mws, Tcs=tcs, Pcs=pcs, omegas=omegas, Tbs=tbs,
                    CASs=[f"pseudo-{i}" for i in range(n)],
                    names=comp_names,
                )
                # Zero kijs for pseudo-components
                kijs = [[0.0] * n for _ in range(n)]
                eos_kwargs = {
                    "Pcs": pcs, "Tcs": tcs, "omegas": omegas, "kijs": kijs,
                }
                # Need HeatCapacityGases — use constant Cp approximation
                from thermo import HeatCapacityGas  # type: ignore[import-untyped]
                HCGs = []
                for i in range(n):
                    # Create a simple constant Cp model
                    hcg = HeatCapacityGas(CASRN=f"pseudo-{i}", MW=mws[i])
                    HCGs.append(hcg)

                gas = CEOSGas(PRMIX, eos_kwargs, HeatCapacityGases=HCGs, T=T, P=P, zs=zs)
                liq = CEOSLiquid(PRMIX, eos_kwargs, HeatCapacityGases=HCGs, T=T, P=P, zs=zs)

                if n == 1:
                    # Can't easily build FlashPureVLS without full properties
                    raise ValueError("Single pseudo-component — use Wilson fallback")
                flasher = FlashVL(constants_manual, None, liquid=liq, gas=gas)
                state = flasher.flash(T=T, P=P, zs=zs)

                vf = state.VF if state.VF is not None else 0.0
                gas_phase = getattr(state, 'gas', None)
                liquid_phase = getattr(state, 'liquid0', None)
                gas_zs_pr = list(gas_phase.zs) if gas_phase else zs
                liq_zs_pr = list(liquid_phase.zs) if liquid_phase else zs
                H_pr = state.H() if callable(getattr(state, 'H', None)) else 0.0
                S_pr = 0.0
                try:
                    S_pr = state.S() if callable(getattr(state, 'S', None)) else 0.0
                except Exception:
                    pass

                Cp_mol = sum(z * cp for z, cp in zip(zs, cps))
                rho_gas_pr = P * (MW_mix / 1000.0) / (8.314 * max(T, 1.0))
                rho_liq_pr = 700.0 + MW_mix * 0.5
                Cp_mass = Cp_mol * 1000.0 / max(MW_mix, 1.0)

                pr_flash_ok = True
                return {
                    "T": T, "P": P, "H": H_pr, "S": S_pr,
                    "VF": vf, "Cp": Cp_mol, "Cv": None, "Z": None,
                    "MW_mix": MW_mix, "MWs": mws,
                    "rho_liquid": rho_liq_pr, "rho_gas": rho_gas_pr,
                    "rho_mix": rho_gas_pr if vf > 0.5 else rho_liq_pr,
                    "mu_liquid": None, "mu_gas": None,
                    "k_liquid": None, "k_gas": None, "sigma": None,
                    "Cp_mass_mix": Cp_mass,
                    "Cp_liquid": Cp_mass if vf < 0.5 else None,
                    "Cp_gas": Cp_mass if vf >= 0.5 else None,
                    "Cv_liquid": None, "Cv_gas": None,
                    "H_liquid": H_pr if vf < 0.5 else None,
                    "H_gas": H_pr if vf >= 0.5 else None,
                    "S_liquid": S_pr if vf < 0.5 else None,
                    "S_gas": S_pr if vf >= 0.5 else None,
                    "Z_liquid": None, "Z_gas": None,
                    "gas_zs": gas_zs_pr, "liquid_zs": liq_zs_pr,
                    "lnphis_gas": None,
                    "comp_names": comp_names, "zs": zs,
                    "flasher": flasher, "state": state,
                    "constants": constants_manual, "properties": None,
                    "pseudo_flash": True, "pseudo_method": "PR_EOS",
                }
            except Exception as exc:
                logger.debug("PR EOS flash for pseudo-components failed: %s — using Wilson", exc)

        # Wilson K-values fallback (original method)
        Cp = sum(z * cp for z, cp in zip(zs, cps))
        K_vals = wilson_k_values(tcs, pcs, omegas, T, P)
        vf, liquid_zs, gas_zs = solve_rachford_rice(zs, K_vals)

        # Enthalpy: ideal gas H = Cp * (T - T_ref), J/mol
        T_ref = 298.15
        H = Cp * (T - T_ref)

        # Entropy: ideal gas S = Cp * ln(T/T_ref) - R * ln(P/P_ref), J/(mol·K)
        P_ref = 101325.0
        S = Cp * math.log(max(T, 1.0) / T_ref) - 8.314 * math.log(max(P, 1.0) / P_ref)

        # Density estimates
        rho_gas = P * (MW_mix / 1000.0) / (8.314 * max(T, 1.0))  # ideal gas
        rho_liquid = 700.0 + MW_mix * 0.5  # crude liquid density estimate

        Cp_mass = Cp * 1000.0 / max(MW_mix, 1.0)  # J/(kg·K)

        return {
            "T": T,
            "P": P,
            "H": H,
            "S": S,
            "VF": vf,
            "Cp": Cp,
            "Cv": None,
            "Z": None,
            "MW_mix": MW_mix,
            "MWs": mws,
            "rho_liquid": rho_liquid,
            "rho_gas": rho_gas,
            "rho_mix": rho_gas if vf > 0.5 else rho_liquid,
            "mu_liquid": None,
            "mu_gas": None,
            "k_liquid": None,
            "k_gas": None,
            "sigma": None,
            "Cp_mass_mix": Cp_mass,
            "Cp_liquid": Cp_mass if vf < 0.5 else None,
            "Cp_gas": Cp_mass if vf >= 0.5 else None,
            "Cv_liquid": None,
            "Cv_gas": None,
            "H_liquid": H if vf < 0.5 else None,
            "H_gas": H if vf >= 0.5 else None,
            "S_liquid": S if vf < 0.5 else None,
            "S_gas": S if vf >= 0.5 else None,
            "Z_liquid": None,
            "Z_gas": None,
            "gas_zs": gas_zs,
            "liquid_zs": liquid_zs,
            "lnphis_gas": None,
            "comp_names": comp_names,
            "zs": zs,
            "flasher": None,
            "state": None,
            "constants": None,
            "properties": None,
            "pseudo_flash": True,
        }

    # ------------------------------------------------------------------
    # Additional flash helpers (T1-5: Flash Type Expansion)
    # ------------------------------------------------------------------

    @staticmethod
    def _flash_ph(
        comp_names: list[str],
        zs: list[float],
        P: float,
        H: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """PH flash (isenthalpic) — given pressure and molar enthalpy (J/mol).

        Used for: valves (isenthalpic expansion), adiabatic mixing.
        Returns same dict format as _flash_tp with resolved T and VF.
        """
        if not _thermo_available or not comp_names or not zs:
            return None
        try:
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            # Build flasher using a dummy TP flash first for infrastructure
            tp_flash = DWSIMEngine._flash_tp(comp_names, zs_norm, 300.0, P, property_package)
            if not tp_flash or not tp_flash.get("flasher"):
                return None

            flasher = tp_flash["flasher"]
            state = flasher.flash(P=P, H=H, zs=zs_norm)
            T_result = state.T
            # Now do a full TP flash at the resolved T to get all properties
            return DWSIMEngine._flash_tp(comp_names, zs_norm, T_result, P, property_package)
        except Exception as exc:
            logger.warning("_flash_ph failed for %s: %s", comp_names, exc)
            return None

    @staticmethod
    def _flash_ps(
        comp_names: list[str],
        zs: list[float],
        P: float,
        S: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """PS flash (isentropic) — given pressure and molar entropy (J/mol/K).

        Used for: isentropic compressor/turbine outlet calculation.
        Returns same dict format as _flash_tp with resolved T and VF.
        """
        if not _thermo_available or not comp_names or not zs:
            return None
        try:
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            tp_flash = DWSIMEngine._flash_tp(comp_names, zs_norm, 300.0, P, property_package)
            if not tp_flash or not tp_flash.get("flasher"):
                return None

            flasher = tp_flash["flasher"]
            state = flasher.flash(P=P, S=S, zs=zs_norm)
            T_result = state.T
            return DWSIMEngine._flash_tp(comp_names, zs_norm, T_result, P, property_package)
        except Exception as exc:
            logger.warning("_flash_ps failed for %s: %s", comp_names, exc)
            return None

    @staticmethod
    def _flash_pvf(
        comp_names: list[str],
        zs: list[float],
        P: float,
        VF: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """PVF flash — given pressure and vapor fraction (0=bubble, 1=dew).

        Used for: bubble/dew point calculations, condenser/reboiler specs.
        Returns same dict format as _flash_tp with resolved T.
        """
        if not _thermo_available or not comp_names or not zs:
            return None
        try:
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            tp_flash = DWSIMEngine._flash_tp(comp_names, zs_norm, 300.0, P, property_package)
            if not tp_flash or not tp_flash.get("flasher"):
                return None

            flasher = tp_flash["flasher"]
            state = flasher.flash(P=P, VF=VF, zs=zs_norm)
            T_result = state.T
            return DWSIMEngine._flash_tp(comp_names, zs_norm, T_result, P, property_package)
        except Exception as exc:
            logger.warning("_flash_pvf failed for %s: %s", comp_names, exc)
            return None

    @staticmethod
    def _flash_tvf(
        comp_names: list[str],
        zs: list[float],
        T: float,
        VF: float,
        property_package: str = "PengRobinson",
    ) -> dict[str, Any] | None:
        """TVF flash — given temperature and vapor fraction.

        Used for: bubble/dew pressure at given T.
        Returns same dict format as _flash_tp with resolved P.
        """
        if not _thermo_available or not comp_names or not zs:
            return None
        try:
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            tp_flash = DWSIMEngine._flash_tp(comp_names, zs_norm, T, 101325.0, property_package)
            if not tp_flash or not tp_flash.get("flasher"):
                return None

            flasher = tp_flash["flasher"]
            state = flasher.flash(T=T, VF=VF, zs=zs_norm)
            P_result = state.P
            return DWSIMEngine._flash_tp(comp_names, zs_norm, T, P_result, property_package)
        except Exception as exc:
            logger.warning("_flash_tvf failed for %s: %s", comp_names, exc)
            return None

    # ------------------------------------------------------------------
    # Density helper
    # ------------------------------------------------------------------
    def _get_density(
        self, comp_names: list[str], zs: list[float],
        T: float, P: float, property_package: str = "PengRobinson",
    ) -> float:
        """Get mixture density (kg/m³) via flash. Gas-aware (ideal gas fallback)."""
        flash = self._flash_tp(comp_names, zs, T, P, property_package)
        if flash:
            vf = flash.get("VF", 0.0)
            if vf > 0.5:
                # Primarily gas — try gas phase density
                gas_phase = None
                flasher = flash.get("flasher")
                if flasher:
                    try:
                        state = flasher.flash(T=T, P=P, zs=flash["zs"])
                        gas_phase = getattr(state, 'gas', None)
                    except Exception:
                        pass
                if gas_phase is not None:
                    try:
                        return gas_phase.rho_mass()
                    except Exception:
                        pass
                # Ideal gas fallback: rho = P*MW / (R*T)
                MW_mix = flash.get("MW_mix", 28.0)
                R = 8.314
                rho_ideal = P * (MW_mix / 1000.0) / (R * T) if T > 0 else 1000.0
                return max(rho_ideal, 0.01)
            else:
                # Primarily liquid
                rho_liq = flash.get("rho_liquid")
                if rho_liq is not None and rho_liq > 0:
                    return rho_liq
        return 1000.0  # default water density

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------
    @staticmethod
    def _topological_sort(
        nodes: list[dict], edges: list[dict]
    ) -> tuple[list[str], list[str]]:
        """Return (sorted_ids, cycle_node_ids) in topological order."""
        node_ids = {n["id"] for n in nodes}
        incoming: dict[str, set[str]] = {nid: set() for nid in node_ids}
        outgoing: dict[str, set[str]] = {nid: set() for nid in node_ids}
        for e in edges:
            # Skip energy streams — they don't define material flow dependencies
            if e.get("type", "stream") == "energy-stream":
                continue
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in node_ids and tgt in node_ids:
                incoming[tgt].add(src)
                outgoing[src].add(tgt)

        # Kahn's algorithm
        queue = [nid for nid in node_ids if not incoming[nid]]
        result: list[str] = []
        while queue:
            nid = queue.pop(0)
            result.append(nid)
            for tgt in outgoing.get(nid, set()):
                incoming[tgt].discard(nid)
                if not incoming[tgt]:
                    queue.append(tgt)

        # Append any remaining (cycles) so nothing is silently skipped
        cycle_ids: list[str] = []
        for nid in node_ids:
            if nid not in result:
                result.append(nid)
                cycle_ids.append(nid)
        return result, cycle_ids

    # ------------------------------------------------------------------
    # Build feed from node parameters (Feature 1)
    # ------------------------------------------------------------------
    @staticmethod
    def _build_feed_from_params(params: dict[str, Any], property_package: str = "PengRobinson") -> dict[str, Any]:
        """Build SI feed conditions from user-specified node parameters.

        Reads feedTemperature (°C), feedPressure (kPa), feedFlowRate (kg/s),
        feedComposition (JSON string or dict). Falls back to _DEFAULT_FEED
        for any missing values.
        """
        feed = dict(_DEFAULT_FEED)
        feed["composition"] = dict(_DEFAULT_FEED["composition"])

        ft = params.get("feedTemperature")
        if ft is not None:
            feed["temperature"] = _c_to_k(float(ft))

        fp = params.get("feedPressure")
        if fp is not None:
            feed["pressure"] = _kpa_to_pa(float(fp))

        ff = params.get("feedFlowRate")
        if ff is not None:
            feed["mass_flow"] = float(ff)

        fc = params.get("feedComposition")
        if fc:
            comp: dict[str, float] = {}
            if isinstance(fc, str):
                try:
                    comp = json.loads(fc)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(fc, dict):
                comp = {str(k): float(v) for k, v in fc.items()}
            if comp:
                # Normalize
                total = sum(comp.values())
                if total > 0:
                    comp = {k: v / total for k, v in comp.items()}
                feed["composition"] = comp

        # Recompute enthalpy — use thermo flash if composition available, else estimated Cp
        comp = feed["composition"]
        comp_names = list(comp.keys())
        zs = [float(v) for v in comp.values()]
        flash = DWSIMEngine._flash_tp(comp_names, zs, feed["temperature"], feed["pressure"], property_package)
        if flash and flash.get("MW_mix", 0) > 0:
            mw_kg = flash["MW_mix"] / 1000.0  # kg/mol
            feed["enthalpy"] = flash["H"] / mw_kg  # J/kg
            if flash.get("S") is not None:
                feed["entropy"] = flash["S"] / mw_kg  # J/(kg·K)
        else:
            cp_est = _estimate_cp(comp)
            feed["enthalpy"] = cp_est * (feed["temperature"] - _T_REF)
        return feed

    # ------------------------------------------------------------------
    # DWSIM primary engine (kept for when DWSIM is installed)
    # ------------------------------------------------------------------
    async def _simulate_dwsim(
        self, nodes: list[dict], edges: list[dict]
    ) -> dict[str, Any]:
        flowsheet = DWSIMFlowsheet()  # type: ignore[name-defined]
        pp = PropertyPackages.PengRobinsonPropertyPackage()  # type: ignore[name-defined]
        flowsheet.AddPropertyPackage(pp)

        obj_map: dict[str, Any] = {}

        # Create unit operations
        for node in nodes:
            ntype = node.get("type", "")
            nid = node.get("id", "")
            params = node.get("parameters", {})
            dwsim_type = EQUIPMENT_TYPE_MAP.get(ntype)
            if dwsim_type is None:
                continue

            uo = flowsheet.AddObject(dwsim_type, 0, 0, nid)
            unit = uo.GetAsObject()

            # Set parameters (convert from frontend units to SI)
            if ntype in ("Heater", "Cooler"):
                if params.get("outletTemperature") is not None:
                    unit.SetOutletTemperature(_c_to_k(float(params["outletTemperature"])))
            elif ntype == "Pump":
                if params.get("outletPressure") is not None:
                    unit.SetOutletPressure(_kpa_to_pa(float(params["outletPressure"])))
                if params.get("efficiency") is not None:
                    unit.SetEfficiency(float(params["efficiency"]) / 100.0)
            elif ntype == "Compressor":
                if params.get("outletPressure") is not None:
                    unit.SetOutletPressure(_kpa_to_pa(float(params["outletPressure"])))
                if params.get("efficiency") is not None:
                    unit.SetEfficiency(float(params["efficiency"]) / 100.0)
            elif ntype == "Valve":
                if params.get("outletPressure") is not None:
                    unit.SetOutletPressure(_kpa_to_pa(float(params["outletPressure"])))
            elif ntype == "DistillationColumn":
                if params.get("numberOfStages") is not None:
                    unit.SetNumberOfStages(int(params["numberOfStages"]))
                if params.get("refluxRatio") is not None:
                    unit.SetRefluxRatio(float(params["refluxRatio"]))
            elif ntype == "CSTRReactor":
                if params.get("volume") is not None:
                    unit.SetVolume(float(params["volume"]))

            obj_map[nid] = unit

        # Connect via edges
        for edge in edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            sh = edge.get("sourceHandle", "out")
            th = edge.get("targetHandle", "in")
            if src in obj_map and tgt in obj_map:
                flowsheet.ConnectObjects(obj_map[src], obj_map[tgt], sh, th)

        FlowsheetSolver.SolveFlowsheet(flowsheet)  # type: ignore[name-defined]

        # Extract results (convert back to frontend units)
        equipment_results: dict[str, Any] = {}
        stream_results: dict[str, Any] = {}
        for node in nodes:
            nid, ntype = node.get("id", ""), node.get("type", "")
            if nid not in obj_map:
                continue
            obj = obj_map[nid]
            if EQUIPMENT_TYPE_MAP.get(ntype):
                res: dict[str, Any] = {"equipment_type": ntype}
                try:
                    res["duty"] = _w_to_kw(obj.GetDuty())
                except Exception:
                    pass
                try:
                    res["work"] = _w_to_kw(obj.GetWork())
                except Exception:
                    pass
                equipment_results[nid] = res

        return {
            "status": "success",
            "engine": "dwsim",
            "stream_results": stream_results,
            "equipment_results": equipment_results,
            "convergence_info": {"iterations": 1, "converged": True, "error": 0.0},
            "logs": ["DWSIM simulation completed"],
        }

    # ------------------------------------------------------------------
    # Basic simulation (works without any external thermo library)
    # Uses simple energy/mass balance formulas.
    # When thermo/CoolProp are available they augment the calculations.
    # ------------------------------------------------------------------
    async def _simulate_basic(
        self, nodes: list[dict], edges: list[dict],
        property_package: str = "PengRobinson",
        convergence_settings: dict[str, Any] | None = None,
        progress_callback: Any = None,
        simulation_basis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            logs: list[str] = []
            equipment_results: dict[str, Any] = {}
            has_errors = False
            stream_results: dict[str, Any] = {}

            # Separate FeedStream/ProductStream/DesignSpec nodes from equipment nodes
            feed_stream_nodes = [n for n in nodes if n.get("type") == "FeedStream"]
            product_stream_nodes = [n for n in nodes if n.get("type") == "ProductStream"]
            design_spec_nodes = [n for n in nodes if n.get("type") == "DesignSpec"]
            equipment_nodes = [n for n in nodes if n.get("type") not in ("FeedStream", "ProductStream", "DesignSpec")]

            # Cache thermo constants from simulation basis for reuse
            _basis_constants = None
            _basis_properties = None
            basis_compounds = (simulation_basis or {}).get("compounds", []) if simulation_basis else []
            if basis_compounds and _thermo_available:
                try:
                    _basis_constants, _basis_properties = ChemicalConstantsPackage.from_IDs(basis_compounds)
                    logs.append(f"Simulation basis: {len(basis_compounds)} compounds loaded ({', '.join(basis_compounds[:5])}{'...' if len(basis_compounds) > 5 else ''})")
                except Exception as exc:
                    logs.append(f"WARNING: Failed to load simulation basis compounds: {exc}")

            # Auto-add feed compounds to simulation basis (Fix D)
            if simulation_basis is None:
                simulation_basis = {}
            if "compounds" not in simulation_basis:
                simulation_basis["compounds"] = []
            basis_lc = set(c.lower() for c in simulation_basis["compounds"])
            for fs_n in feed_stream_nodes:
                fs_p = fs_n.get("parameters", {})
                fc = fs_p.get("feedComposition", {})
                if isinstance(fc, str):
                    try:
                        fc = json.loads(fc)
                    except Exception:
                        fc = {}
                for comp_name in fc:
                    if comp_name.lower() not in basis_lc:
                        simulation_basis["compounds"].append(comp_name)
                        basis_lc.add(comp_name.lower())
                        logs.append(f"INFO: Auto-added '{comp_name}' to simulation basis")
            basis_compounds = simulation_basis.get("compounds", [])

            basis_set = set(basis_compounds) if basis_compounds else None

            # Activity coefficient model info
            if property_package in ("NRTL", "UNIQUAC"):
                logs.append(
                    f"Using {property_package} activity coefficient model for liquid phase, "
                    "Peng-Robinson EOS for gas phase."
                )

            # Build adjacency with target handles for port-aware routing
            # downstream: source_id → [(target_id, srcHandle, tgtHandle)]
            downstream: dict[str, list[tuple[str, str, str]]] = {}
            # upstream: target_id → [(source_id, srcHandle, tgtHandle)]
            upstream: dict[str, list[tuple[str, str, str]]] = {}
            for edge in edges:
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                sh = edge.get("sourceHandle", "")
                th = edge.get("targetHandle", "")
                # Skip energy streams for material flow adjacency
                edge_type = edge.get("type", "stream")
                if edge_type == "energy-stream":
                    continue
                downstream.setdefault(src, []).append((tgt, sh, th))
                upstream.setdefault(tgt, []).append((src, sh, th))

            node_map = {n["id"]: n for n in nodes}
            sorted_ids, cycle_ids = self._topological_sort(nodes, edges)

            # ----------------------------------------------------------
            # T4-4: Unit operation topology validation
            # ----------------------------------------------------------
            _INLET_REQUIREMENTS: dict[str, int] = {
                "Mixer": 2, "HeatExchanger": 2, "Absorber": 2, "Stripper": 2,
            }
            _OUTLET_REQUIREMENTS: dict[str, int] = {
                "Splitter": 2, "Separator": 2, "DistillationColumn": 2,
                "Absorber": 2, "Stripper": 1,  # Stripper can operate with 1 feed (reboiled mode)
            }
            for node in nodes:
                nid = node.get("id", "")
                ntype = node.get("type", "")
                nname = node.get("name", nid)
                n_inlets = len(upstream.get(nid, []))
                n_outlets = len(downstream.get(nid, []))
                min_in = _INLET_REQUIREMENTS.get(ntype, 0)
                min_out = _OUTLET_REQUIREMENTS.get(ntype, 0)
                if min_in > 0 and n_inlets < min_in:
                    logs.append(
                        f"WARNING: {nname} ({ntype}) expects at least {min_in} "
                        f"inlet(s) but has {n_inlets} — simulation may use default feed conditions"
                    )
                if min_out > 0 and n_outlets < min_out:
                    logs.append(
                        f"WARNING: {nname} ({ntype}) expects at least {min_out} "
                        f"outlet(s) but has {n_outlets} — some products will not propagate downstream"
                    )

            # ----------------------------------------------------------
            # T4-2: Tear-stream convergence for recycle loops
            # ----------------------------------------------------------
            # Detect tear edges: back-edges where target appears before source in topo order
            sorted_set = set()
            tear_edges: list[dict] = []
            non_tear_edges = list(edges)
            if cycle_ids:
                order_idx = {nid: i for i, nid in enumerate(sorted_ids)}
                tear_edges = []
                non_tear_keep = []
                for edge in edges:
                    src = edge.get("source", "")
                    tgt = edge.get("target", "")
                    if src in order_idx and tgt in order_idx and order_idx[tgt] <= order_idx[src]:
                        tear_edges.append(edge)
                    else:
                        non_tear_keep.append(edge)
                non_tear_edges = non_tear_keep if tear_edges else list(edges)
                if tear_edges:
                    tear_names = []
                    for te in tear_edges:
                        sn = node_map.get(te["source"], {}).get("name", te["source"])
                        tn = node_map.get(te["target"], {}).get("name", te["target"])
                        tear_names.append(f"{sn}→{tn}")
                    logs.append(f"Tear streams identified: {', '.join(tear_names)}")

            conv_settings = convergence_settings or {}
            max_iterations = conv_settings.get("max_iter", 50)
            tolerance = conv_settings.get("tolerance", 1e-4)
            damping = conv_settings.get("damping", 0.5)
            converged_recycle = not bool(tear_edges)  # True if no recycle
            actual_iterations = 1

            # Wegstein acceleration state: stores previous two iterates per tear edge key
            wegstein_prev: dict[str, list[float]] = {}  # key → [x_prev, g_prev]

            # T2-5: Convergence diagnostics — track variable history per iteration
            convergence_history: list[dict[str, Any]] = []

            # Pre-compute feed conditions for tear-stream initialization
            _feed_conditions_cache: dict[str, dict[str, Any]] = {}
            if tear_edges:
                for fs_node in feed_stream_nodes:
                    fs_id = fs_node.get("id", "")
                    fs_params = fs_node.get("parameters", {})
                    try:
                        fc = self._build_feed_from_params(fs_params, property_package)
                        _feed_conditions_cache[fs_id] = fc
                    except Exception:
                        pass  # Feed will be processed normally in the loop

            # Initialize tear stream conditions — prefer nearest upstream feed over default water
            tear_stream_conditions: dict[str, dict[str, Any]] = {}
            for te in tear_edges:
                te_key = f"{te['source']}_{te.get('sourceHandle', 'out-1')}"
                target_id = te.get("target", "")
                nearest_feed = self._find_nearest_feed(target_id, nodes, edges, _feed_conditions_cache)
                if nearest_feed is not None:
                    tear_stream_conditions[te_key] = nearest_feed
                    logs.append(f"INFO: Tear stream {te_key} initialized from upstream feed")
                else:
                    # Fallback: use any available feed
                    any_feed = None
                    for fc_val in _feed_conditions_cache.values():
                        any_feed = dict(fc_val)
                        break
                    if any_feed is not None:
                        tear_stream_conditions[te_key] = any_feed
                        logs.append(f"INFO: Tear stream {te_key} initialized from available feed")
                    else:
                        tear_stream_conditions[te_key] = dict(_DEFAULT_FEED)
                        logs.append(f"WARNING: Tear stream {te_key} initialized with default water — may converge slowly")

            for iteration in range(1, max_iterations + 1):
                actual_iterations = iteration

                # Outlet conditions per (node_id, port_id) – in SI units internally
                port_conditions: dict[tuple[str, str], dict[str, Any]] = {}
                equipment_results = {}
                has_errors = False

                # Inject tear stream conditions so downstream equipment can see them
                for te in tear_edges:
                    src = te.get("source", "")
                    sh = te.get("sourceHandle", "out-1")
                    te_key = f"{src}_{sh}"
                    if te_key in tear_stream_conditions:
                        port_conditions[(src, sh)] = dict(tear_stream_conditions[te_key])

                # Process FeedStream nodes first — they set port_conditions for their outlet
                for fs_node in feed_stream_nodes:
                    fs_id = fs_node.get("id", "")
                    fs_name = fs_node.get("name", fs_id)
                    fs_params = fs_node.get("parameters", {})
                    try:
                        feed_cond = self._build_feed_from_params(fs_params, property_package)
                        port_conditions[(fs_id, "out-1")] = feed_cond

                        # Store feed stream results
                        T_c = _k_to_c(feed_cond["temperature"])
                        P_kpa = _pa_to_kpa(feed_cond["pressure"])
                        mf = feed_cond.get("mass_flow", 1.0)
                        comp = feed_cond.get("composition", {})
                        comp_names = list(comp.keys())
                        zs = [float(v) for v in comp.values()]
                        vf = 0.0
                        # Validate compounds against simulation basis
                        if basis_set and comp_names:
                            unknown = [c for c in comp_names if c not in basis_set]
                            if unknown:
                                logs.append(f"WARNING: Feed '{fs_name}' has compounds not in simulation basis: {unknown}")

                        flash = self._flash_tp(comp_names, zs, feed_cond["temperature"], feed_cond["pressure"], property_package)
                        if flash:
                            vf = flash.get("VF", 0.0) or 0.0
                            # Propagate flash VF back to port_conditions for downstream
                            port_conditions[(fs_id, "out-1")]["vapor_fraction"] = vf

                        _comp_props = _compute_component_properties(comp, mf)
                        _h_kj = round(feed_cond.get("enthalpy", 0.0) / 1000.0, 4)  # J/kg → kJ/kg
                        equipment_results[fs_id] = {
                            "equipment_id": fs_id,
                            "equipment_type": "FeedStream",
                            "name": fs_name,
                            "outletTemperature": T_c,
                            "outletPressure": P_kpa,
                            "massFlow": mf,
                            "vaporFraction": vf,
                            "composition": comp,
                            **_comp_props,
                            "outlet_streams": {
                                "out-1": {
                                    "temperature": T_c,
                                    "pressure": P_kpa,
                                    "flowRate": mf,
                                    "vapor_fraction": vf,
                                    "composition": comp,
                                    "enthalpy": _h_kj,
                                    **_comp_props,
                                },
                            },
                        }

                        # Store stream result for the outgoing edge
                        for tgt_id, sh, _th in downstream.get(fs_id, []):
                            edge_key = f"{fs_id}_{sh}_{tgt_id}"
                            stream_results[edge_key] = {
                                "temperature": T_c,
                                "pressure": P_kpa,
                                "flowRate": mf,
                                "vapor_fraction": vf,
                                "composition": comp,
                                "enthalpy": _h_kj,
                                **_comp_props,
                            }

                        logs.append(f"Feed stream '{fs_name}': T={T_c:.1f}°C, P={P_kpa:.1f} kPa, flow={mf:.3f} kg/s")
                    except Exception as exc:
                        equipment_results[fs_id] = {
                            "equipment_id": fs_id,
                            "equipment_type": "FeedStream",
                            "name": fs_name,
                            "error": str(exc),
                        }
                        has_errors = True
                        logs.append(f"ERROR: Feed stream '{fs_name}' failed: {exc}")

                for nid in sorted_ids:
                    node = node_map.get(nid)
                    if not node:
                        continue

                    try:
                        ntype = node.get("type", "")
                        # Skip FeedStream/ProductStream/DesignSpec — handled separately
                        if ntype in ("FeedStream", "ProductStream", "DesignSpec"):
                            continue
                        if ntype not in EQUIPMENT_TYPE_MAP:
                            logs.append(f"Skipping unknown type '{ntype}' for node {nid}")
                            continue

                        params = node.get("parameters", {})
                        name = node.get("name", nid)

                        # Collect inlet conditions (SI), tagged with targetHandle
                        inlets: list[dict[str, Any]] = []
                        inlet_handles: list[str] = []  # parallel list of target handles
                        for src_id, _sh, tgt_handle in upstream.get(nid, []):
                            # Find the matching source outlet port
                            for tgt_id, sh2, _th2 in downstream.get(src_id, []):
                                if tgt_id == nid:
                                    cond = port_conditions.get((src_id, sh2))
                                    if cond:
                                        inlets.append(cond)
                                        inlet_handles.append(tgt_handle)
                                    break

                        # If no upstream connections, build feed from node parameters
                        _mark_underspecified = False
                        if not inlets:
                            # Check if user specified a feed composition on this node
                            has_user_feed = bool(params.get("feedComposition"))
                            feed_from_params = self._build_feed_from_params(params, property_package)
                            use_basis_fallback = (
                                (feed_from_params is None or feed_from_params.get("mass_flow", 0) <= 0)
                                or (not has_user_feed and simulation_basis and simulation_basis.get("compounds"))
                            )
                            if use_basis_fallback:
                                # Graceful fallback: build feed from simulation basis compounds
                                if simulation_basis and simulation_basis.get("compounds"):
                                    basis_comps = simulation_basis["compounds"]
                                    n_comps_fb = len(basis_comps)
                                    fallback_comp = {c: 1.0 / n_comps_fb for c in basis_comps}
                                    fb_T = _c_to_k(float(params.get("feedTemperature", params.get("temperature", 25))))
                                    fb_P = _kpa_to_pa(float(params.get("feedPressure", params.get("pressure", 101.325))))
                                    fb_mf = float(params.get("feedFlowRate", params.get("massFlow", 1.0)))
                                    feed_from_params = {
                                        "temperature": fb_T, "pressure": fb_P, "mass_flow": fb_mf,
                                        "composition": fallback_comp, "vapor_fraction": 0.0,
                                    }
                                    fb_flash = self._flash_tp(
                                        basis_comps, [1.0 / n_comps_fb] * n_comps_fb,
                                        fb_T, fb_P, property_package,
                                    )
                                    if fb_flash and fb_flash.get("MW_mix", 0) > 0:
                                        feed_from_params["enthalpy"] = fb_flash["H"] / (fb_flash["MW_mix"] / 1000.0)
                                        feed_from_params["vapor_fraction"] = fb_flash.get("VF", 0.0)
                                    else:
                                        feed_from_params["enthalpy"] = _estimate_cp(fallback_comp) * (fb_T - _T_REF)
                                    logs.append(f"INFO: {name} — no upstream, using simulation basis as default feed")
                                    _mark_underspecified = True
                                else:
                                    # No basis either — use _DEFAULT_FEED (water at 25°C) as last resort
                                    feed_from_params = dict(_DEFAULT_FEED)
                                    feed_from_params["composition"] = dict(_DEFAULT_FEED["composition"])
                                    logs.append(f"INFO: {name} — no upstream or basis, using default water feed")
                                    _mark_underspecified = True
                            inlets = [feed_from_params]

                        # ----------------------------------------------------------
                        # Equipment-specific calculations (all SI internally)
                        # ----------------------------------------------------------
                        eq_res: dict[str, Any] = {"equipment_type": ntype, "name": name}
                        if _mark_underspecified:
                            eq_res["underspecified"] = True
                        outlets: dict[str, dict[str, Any]] = {}

                        if ntype in ("Heater", "Cooler"):
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            dp = _kpa_to_pa(float(params.get("pressureDrop", 0)))
                            P_out = P_in - dp

                            # Outlet temp: user-specified or default
                            T_out_c = params.get("outletTemperature")
                            duty_kw = params.get("duty")
                            duty_mode = False

                            # Try thermo flash for real Cp
                            cp = _estimate_cp(comp)  # composition-aware fallback
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                            flash_out = None
                            used_thermo = False

                            if T_out_c is not None:
                                T_out = _c_to_k(float(T_out_c))
                                # Use real enthalpy difference if thermo available
                                flash_out = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                                if flash_in and flash_out and flash_in["MW_mix"] > 0:
                                    # H is J/mol, convert to J/kg: H / (MW/1000)
                                    mw_kg = flash_in["MW_mix"] / 1000.0  # kg/mol
                                    H_in = flash_in["H"] / mw_kg if mw_kg > 0 else 0  # J/kg
                                    H_out = flash_out["H"] / mw_kg if mw_kg > 0 else 0
                                    duty_w = mf * (H_out - H_in)
                                    used_thermo = True
                                else:
                                    duty_w = mf * cp * (T_out - T_in)
                            elif duty_kw is not None and float(duty_kw) != 0:
                                duty_w = _kw_to_w(float(duty_kw))
                                duty_mode = True
                                if ntype == "Cooler":
                                    duty_w = -abs(duty_w)
                                if ntype == "Heater":
                                    duty_w = abs(duty_w)
                                # Cp-based estimate first
                                T_out = T_in + duty_w / (mf * cp) if mf > 0 else T_in
                                # HP flash for real T_out (T2-05)
                                if flash_in and flash_in.get("flasher") and flash_in["MW_mix"] > 0:
                                    try:
                                        mw_kg = flash_in["MW_mix"] / 1000.0
                                        H_in_mol = flash_in["H"]  # J/mol
                                        H_out_mol = H_in_mol + (duty_w / mf) * mw_kg if mf > 0 else H_in_mol
                                        flasher = flash_in["flasher"]
                                        state_out = flasher.flash(H=H_out_mol, P=P_out, zs=flash_in["zs"])
                                        T_out = state_out.T
                                        flash_out = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                                        used_thermo = True
                                    except Exception as exc:
                                        logger.warning("Heater/Cooler HP flash failed: %s", exc)
                            else:
                                T_out = T_in + (50 if ntype == "Heater" else -50)
                                duty_w = mf * cp * (T_out - T_in)

                            # Flash outlet for VF regardless of mode (T2-05)
                            if not flash_out and comp_names:
                                flash_out = self._flash_tp(comp_names, zs, T_out, P_out, property_package)

                            eq_res["duty"] = round(_w_to_kw(duty_w), 3)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                            eq_res["pressureDrop"] = round(_pa_to_kpa(dp), 3)

                            # Get VF from flash at outlet conditions
                            vf_out = 0.0
                            if flash_out:
                                vf_out = flash_out.get("VF", 0.0)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Store enthalpy from first law for energy consistency
                            # (independent re-flash can give different H than upstream,
                            # causing false energy-balance warnings)
                            if mf > 0:
                                outlet["enthalpy"] = inlet["enthalpy"] + duty_w / mf
                            else:
                                outlet["enthalpy"] = inlet.get("enthalpy", 0.0)
                            outlet["vapor_fraction"] = vf_out
                            outlet["composition"] = dict(comp)
                            outlets["out-1"] = outlet
                            engine_note = " (thermo)" if used_thermo else ""
                            logs.append(f"{name}: duty = {eq_res['duty']:.1f} kW, T_out = {eq_res['outletTemperature']:.1f} °C{engine_note}")

                        elif ntype == "Pump":
                            inlet = inlets[0]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            if mf <= 0:
                                logs.append(f"WARNING: {name} mass flow ≤ 0, clamping to 1e-10")
                                mf = 1e-10
                            T_in = inlet["temperature"]
                            comp = inlet.get("composition", {})

                            # Density from _get_density helper (T2-02a, T2-15)
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            rho = self._get_density(comp_names, zs, T_in, P_in, property_package)
                            flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                            if flash_in:
                                vf_in = flash_in.get("VF", 0)
                                if vf_in > 0.5:
                                    logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — pump expects liquid feed")
                                elif vf_in > 0.01:
                                    logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — significant vapor in pump feed")

                            # Guard rho (T2-15)
                            if rho <= 0:
                                logs.append(f"WARNING: {name} density ≤ 0, using 1000 kg/m³ fallback")
                                rho = 1000.0

                            P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in * 2))))
                            if P_out < P_in:
                                logs.append(
                                    f"WARNING: {name} outlet pressure ({_pa_to_kpa(P_out):.0f} kPa) < inlet "
                                    f"({_pa_to_kpa(P_in):.0f} kPa) — pump cannot reduce pressure. "
                                    f"Consider using a Valve instead."
                                )
                            eff = float(params.get("efficiency", 75)) / 100.0
                            if eff <= 0:
                                eff = 0.75

                            # Pump curve mode: use rated flow/head to compute head and efficiency
                            use_pump_curve = bool(params.get("pumpCurve", False))
                            if use_pump_curve:
                                rated_flow_m3h = float(params.get("ratedFlow", 10))
                                rated_head_m = float(params.get("ratedHead", 50))
                                # Actual volumetric flow
                                Q_m3s = mf / rho if rho > 0 else 0
                                Q_m3h = Q_m3s * 3600
                                # Simple quadratic pump curve: H = H_rated * (1 - 0.5*(Q/Q_rated)^2)
                                Q_ratio = Q_m3h / rated_flow_m3h if rated_flow_m3h > 0 else 0
                                head_m = rated_head_m * max(0.0, 1.0 - 0.5 * Q_ratio ** 2)
                                P_out = P_in + head_m * rho * 9.81  # Pa
                                logs.append(f"{name}: pump curve Q={Q_m3h:.1f} m³/h, H={head_m:.1f} m")

                            # NPSH check
                            npsh_a = float(params.get("npshAvailable", 0))
                            if npsh_a > 0:
                                npsh_r = 3.0  # default NPSH_required, m
                                if npsh_a < npsh_r:
                                    logs.append(f"WARNING: {name} NPSH_available ({npsh_a:.1f} m) < NPSH_required ({npsh_r:.1f} m) — cavitation risk")
                                eq_res["npshAvailable"] = round(npsh_a, 1)

                            # M3: Enthalpy-based pump work for near-critical fluids
                            w_actual = 0.0
                            w_ideal = 0.0
                            pump_enthalpy_method = False
                            if flash_in and flash_in.get("S") and flash_in.get("flasher"):
                                # Check if near-critical (VF > 0 or T near Tc)
                                vf_pump = flash_in.get("VF", 0)
                                try:
                                    consts_pump = flash_in.get("constants")
                                    Tc_avg = sum(z * tc for z, tc in zip(flash_in["zs"], consts_pump.Tcs)) if consts_pump else 0
                                    near_critical = vf_pump > 0.01 or (Tc_avg > 0 and T_in > 0.85 * Tc_avg)
                                except Exception:
                                    near_critical = False
                                if near_critical:
                                    try:
                                        S_in_pump = flash_in["S"]
                                        H_in_pump = flash_in["H"]
                                        flasher_pump = flash_in["flasher"]
                                        zs_pump = flash_in["zs"]
                                        mw_pump_kg = flash_in["MW_mix"] / 1000.0
                                        state_isen_pump = flasher_pump.flash(S=S_in_pump, P=P_out, zs=zs_pump)
                                        H_isen_pump = state_isen_pump.H()
                                        w_isen = mf * (H_isen_pump - H_in_pump) / mw_pump_kg if mw_pump_kg > 0 else 0
                                        w_ideal = w_isen
                                        w_actual = w_isen / eff
                                        pump_enthalpy_method = True
                                        logs.append(f"  {name}: using enthalpy-based method (near-critical fluid)")
                                    except Exception:
                                        pump_enthalpy_method = False
                            if not pump_enthalpy_method:
                                # Standard incompressible: W_ideal = V·ΔP = m·ΔP/ρ
                                w_ideal = mf * (P_out - P_in) / rho  # W
                                w_actual = w_ideal / eff  # W

                            # Temperature rise from pump inefficiency — Cp from flash (T2-13)
                            cp = _estimate_cp(comp)
                            if flash_in and flash_in.get("Cp") and flash_in["MW_mix"] > 0:
                                mw_kg = flash_in["MW_mix"] / 1000.0
                                cp = flash_in["Cp"] / mw_kg  # J/(kg·K)
                            dT_friction = (w_actual - w_ideal) / (mf * cp) if mf > 0 else 0
                            T_out = T_in + dT_friction

                            eq_res["work"] = round(_w_to_kw(w_actual), 3)
                            eq_res["efficiency"] = round(eff * 100, 1)
                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)
                            eq_res["temperatureRise"] = round(dT_friction, 3)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Energy-balance-consistent enthalpy (avoids TP re-flash inconsistency)
                            if mf > 0:
                                outlet["enthalpy"] = inlet["enthalpy"] + w_actual / mf
                            else:
                                outlet["enthalpy"] = inlet.get("enthalpy", 0.0)
                            outlet["composition"] = dict(comp)
                            # Flash for VF determination at outlet conditions
                            flash_pump_out = self._flash_tp(list(comp.keys()), [float(v) for v in comp.values()], T_out, P_out, property_package)
                            if flash_pump_out:
                                outlet["vapor_fraction"] = flash_pump_out.get("VF", inlet.get("vapor_fraction", 0.0))
                            outlets["out-1"] = outlet
                            logs.append(f"{name}: work = {eq_res['work']:.1f} kW, ΔT = {dT_friction:.2f} K")

                        elif ntype == "Compressor":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            if mf <= 0:
                                logs.append(f"WARNING: {name} mass flow ≤ 0, clamping to 1e-10")
                                mf = 1e-10
                            comp = inlet.get("composition", {})

                            # Guard P_in (T2-15)
                            if P_in <= 0:
                                logs.append(f"WARNING: {name} inlet pressure ≤ 0, using 101325 Pa")
                                P_in = 101325.0

                            P_out_final = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in * 3))))
                            if P_out_final < P_in:
                                logs.append(f"WARNING: {name} P_out < P_in — this is expansion, not compression")

                            eff = float(params.get("efficiency", 75)) / 100.0
                            if eff <= 0:
                                eff = 0.75

                            # Phase 15 §3.2: Polytropic efficiency mode
                            eff_mode = str(params.get("efficiencyMode", "isentropic")).lower()
                            poly_eff = float(params.get("polytropicEfficiency", 0)) / 100.0
                            if poly_eff <= 0:
                                poly_eff = eff  # default: same as isentropic

                            n_stages = max(1, int(params.get("stages", 1)))
                            intercool_temp = _c_to_k(float(params.get("intercoolTemp", 35)))

                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                            used_thermo = False
                            used_entropy = False

                            if flash_in:
                                vf_in = flash_in.get("VF", 1.0)
                                if vf_in < 0.1:
                                    # M8: Liquid feed — flag as error, not just warning
                                    logs.append(f"ERROR: {name} inlet VF={vf_in:.2f} — liquid feed will damage compressor")
                                    has_errors = True
                                    eq_res["error_liquid_feed"] = True
                                elif vf_in < 0.5:
                                    logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — compressor expects vapor feed")
                                elif vf_in < 0.90:
                                    logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — wet gas in compressor feed")

                            # Multi-stage compression (C1: entropy method per stage)
                            if n_stages > 1:
                                r_stage = (P_out_final / P_in) ** (1.0 / n_stages) if P_in > 0 else 1.0
                                total_work = 0.0
                                T_stage_in = T_in
                                P_stage_in = P_in
                                stage_data = []
                                for stg in range(n_stages):
                                    P_stage_out = P_stage_in * r_stage
                                    if stg == n_stages - 1:
                                        P_stage_out = P_out_final  # ensure exact final pressure

                                    # Preferred: entropy-based isentropic per stage
                                    stg_entropy_ok = False
                                    flash_stg = self._flash_tp(comp_names, zs, T_stage_in, P_stage_in, property_package)
                                    if flash_stg and flash_stg.get("S") and flash_stg.get("flasher"):
                                        try:
                                            S_stg_in = flash_stg["S"]
                                            H_stg_in = flash_stg["H"]
                                            flasher_stg = flash_stg["flasher"]
                                            zs_stg = flash_stg["zs"]
                                            mw_stg_kg = flash_stg["MW_mix"] / 1000.0

                                            state_stg_isen = flasher_stg.flash(S=S_stg_in, P=P_stage_out, zs=zs_stg)
                                            H_stg_isen = state_stg_isen.H()
                                            dH_stg_isen = H_stg_isen - H_stg_in
                                            dH_stg_actual = dH_stg_isen / eff
                                            H_stg_out = H_stg_in + dH_stg_actual

                                            state_stg_actual = flasher_stg.flash(H=H_stg_out, P=P_stage_out, zs=zs_stg)
                                            T_stg_out = state_stg_actual.T
                                            w_stg = mf * dH_stg_actual / mw_stg_kg if mw_stg_kg > 0 else 0
                                            stg_entropy_ok = True
                                        except Exception:
                                            stg_entropy_ok = False

                                    if not stg_entropy_ok:
                                        # Fallback: gamma method
                                        gamma_stg = 1.4
                                        cp_stg = _estimate_cp(comp)
                                        if flash_stg and flash_stg.get("Cp") is not None:
                                            try:
                                                Cp_mol = flash_stg["Cp"]
                                                R_gas = 8.314
                                                Cv_mol = Cp_mol - R_gas
                                                if Cv_mol > 0:
                                                    gamma_stg = Cp_mol / Cv_mol
                                                mw_kg = flash_stg["MW_mix"] / 1000.0
                                                if mw_kg > 0:
                                                    cp_stg = Cp_mol / mw_kg
                                            except Exception:
                                                pass
                                        ratio_stg = P_stage_out / P_stage_in if P_stage_in > 0 else 1.0
                                        T_stg_isen = T_stage_in * (ratio_stg ** ((gamma_stg - 1) / gamma_stg))
                                        T_stg_out = T_stage_in + (T_stg_isen - T_stage_in) / eff
                                        w_stg = mf * cp_stg * (T_stg_out - T_stage_in)

                                    total_work += w_stg

                                    stage_data.append({
                                        "stage": stg + 1,
                                        "T_in": round(_k_to_c(T_stage_in), 1),
                                        "T_out": round(_k_to_c(T_stg_out), 1),
                                        "P_in": round(_pa_to_kpa(P_stage_in), 1),
                                        "P_out": round(_pa_to_kpa(P_stage_out), 1),
                                        "work_kW": round(_w_to_kw(w_stg), 2),
                                        "method": "entropy" if stg_entropy_ok else "gamma",
                                    })

                                    # Intercooling: cool back to intercool_temp before next stage
                                    if stg < n_stages - 1:
                                        T_stage_in = intercool_temp
                                    else:
                                        T_stage_in = T_stg_out
                                    P_stage_in = P_stage_out

                                T_out = T_stage_in
                                work_w = total_work
                                P_out = P_out_final
                                used_thermo = True
                                used_entropy = True  # for outlet enthalpy consistency
                                eq_res["stages"] = n_stages
                                eq_res["stage_data"] = stage_data
                                logs.append(f"{name}: {n_stages}-stage compression, total work = {_w_to_kw(total_work):.1f} kW")
                            else:
                                P_out = P_out_final
                                # Preferred: entropy-based isentropic calculation (Fix 5)
                                if flash_in and flash_in.get("S") and flash_in.get("flasher"):
                                    try:
                                        S_in = flash_in["S"]     # J/(mol·K)
                                        H_in_mol = flash_in["H"]  # J/mol
                                        flasher = flash_in["flasher"]
                                        zs_norm = flash_in["zs"]
                                        mw_kg = flash_in["MW_mix"] / 1000.0  # kg/mol

                                        # Isentropic outlet: flash at (S_in, P_out)
                                        state_isen = flasher.flash(S=S_in, P=P_out, zs=zs_norm)
                                        H_out_isen = state_isen.H()  # J/mol

                                        # Actual work: W = (H_isen - H_in) / eta
                                        dH_isen = H_out_isen - H_in_mol  # J/mol
                                        dH_actual = dH_isen / eff         # J/mol
                                        H_out_actual = H_in_mol + dH_actual

                                        # Actual outlet T: flash at (H_actual, P_out)
                                        state_actual = flasher.flash(H=H_out_actual, P=P_out, zs=zs_norm)
                                        T_out = state_actual.T

                                        work_w = mf * dH_actual / mw_kg if mw_kg > 0 else 0  # W
                                        used_thermo = True
                                        used_entropy = True
                                    except Exception as exc:
                                        logger.warning("Compressor entropy flash failed: %s, falling back to gamma", exc)
                                        used_entropy = False

                                if not used_entropy:
                                    # H6: gamma from flash Cp/Cv first, table fallback only if flash fails
                                    gamma = 1.4
                                    cp = _estimate_cp(comp)
                                    if flash_in and flash_in.get("Cp") is not None:
                                        try:
                                            Cp_mol = flash_in["Cp"]
                                            R = 8.314
                                            Cv_mol = Cp_mol - R
                                            if Cv_mol > 0:
                                                gamma = Cp_mol / Cv_mol
                                            mw_kg = flash_in["MW_mix"] / 1000.0
                                            if mw_kg > 0:
                                                cp = Cp_mol / mw_kg
                                            used_thermo = True
                                        except Exception:
                                            pass
                                    if not used_thermo and comp:
                                        # Last resort: composition-weighted gamma from table
                                        gamma_sum = 0.0
                                        z_sum = 0.0
                                        for c_name, z_frac in comp.items():
                                            g = _GAMMA_TABLE.get(c_name.lower(), _GAMMA_TABLE.get(c_name, 1.4))
                                            gamma_sum += z_frac * g
                                            z_sum += z_frac
                                        if z_sum > 0:
                                            gamma = gamma_sum / z_sum

                                    ratio = P_out / P_in if P_in > 0 else 1.0

                                    if eff_mode == "polytropic" and poly_eff > 0:
                                        # Phase 15 §3.2: Polytropic compression
                                        # T_out = T_in * (P_out/P_in)^((gamma-1)/(gamma*eta_p))
                                        poly_exp = (gamma - 1) / (gamma * poly_eff) if gamma > 1 else 0
                                        T_out = T_in * (ratio ** poly_exp)
                                        work_w = mf * cp * (T_out - T_in)
                                        eq_res["efficiencyMode"] = "polytropic"
                                        eq_res["polytropicEfficiency"] = round(poly_eff * 100, 1)
                                    else:
                                        # Standard isentropic
                                        T_out_isen = T_in * (ratio ** ((gamma - 1) / gamma))
                                        T_out = T_in + (T_out_isen - T_in) / eff
                                        work_w = mf * cp * (T_out - T_in)
                                        eq_res["efficiencyMode"] = "isentropic"

                            eq_res["work"] = round(_w_to_kw(work_w), 3)
                            eq_res["efficiency"] = round(eff * 100, 1)
                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Outlet enthalpy from first law using upstream inlet enthalpy
                            # (avoids inconsistency between re-flash H_in and upstream H_in)
                            outlet["enthalpy"] = inlet["enthalpy"] + (work_w / mf if mf > 0 else 0)
                            outlet["composition"] = dict(comp)
                            # Update VF from flash at outlet conditions
                            flash_comp_vf = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                            if flash_comp_vf:
                                outlet["vapor_fraction"] = flash_comp_vf.get("VF", inlet.get("vapor_fraction", 1.0))
                            outlets["out-1"] = outlet
                            engine_note = " (entropy)" if used_entropy else (" (γ)" if used_thermo else "")
                            logs.append(f"{name}: work = {eq_res['work']:.1f} kW, T_out = {_k_to_c(T_out):.1f} °C{engine_note}")

                        elif ntype == "Valve":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})

                            P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in / 2))))

                            # Isenthalpic expansion – Joule-Thomson effect (Fix 6)
                            T_out = T_in  # default: ideal gas approximation
                            vf_out = inlet.get("vapor_fraction", 0.0)
                            comp_names = list(comp.keys())
                            zs_v = [float(v) for v in comp.values()]

                            flash_in = None
                            # Preferred: thermo HP flash for multi-component JT
                            if comp_names and len(comp_names) >= 1:
                                flash_in = self._flash_tp(comp_names, zs_v, T_in, P_in, property_package)
                                if flash_in and flash_in.get("flasher"):
                                    try:
                                        H_in_mol = flash_in["H"]  # J/mol
                                        flasher = flash_in["flasher"]
                                        zs_norm = flash_in["zs"]
                                        state_out = flasher.flash(H=H_in_mol, P=P_out, zs=zs_norm)
                                        T_out = state_out.T
                                        vf_out = state_out.VF if state_out.VF is not None else 0.0
                                    except Exception as exc:
                                        logger.warning("Valve HP flash failed: %s", exc)
                            elif _coolprop_available and len(comp) == 1:
                                # CoolProp fallback for single component
                                comp_name = list(comp.keys())[0]
                                try:
                                    h_in = CP.PropsSI("H", "T", T_in, "P", P_in, comp_name)
                                    T_out = CP.PropsSI("T", "H", h_in, "P", P_out, comp_name)
                                except Exception:
                                    pass

                            eq_res["pressureDrop"] = round(_pa_to_kpa(P_in - P_out), 3)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            # Cv calculation — M4: use gas formula when VF > 0.5
                            dp_psi = _pa_to_kpa(P_in - P_out) * 0.145038  # kPa to psi
                            rho = self._get_density(comp_names, zs_v, T_in, P_in, property_package) if comp_names else 1000.0
                            sg = rho / 999.0 if rho > 0 else 1.0  # specific gravity relative to water
                            if vf_out > 0.5:
                                # ISA gas Cv formula: Cv = W * sqrt(T*Z / (M*dP*P_avg))
                                MW_gas = sum(z * _get_mw(c) for c, z in comp.items()) if comp else 28.97
                                P_avg = (P_in + P_out) / 2.0
                                dp_pa = P_in - P_out
                                Z = 1.0  # compressibility factor approximation
                                if dp_pa > 0 and P_avg > 0 and MW_gas > 0:
                                    # W in kg/h, P in kPa
                                    W_kgh = mf * 3600
                                    cv_calc = W_kgh * math.sqrt(T_in * Z / (MW_gas * _pa_to_kpa(dp_pa) * _pa_to_kpa(P_avg))) / 94.8
                                    eq_res["cv"] = round(cv_calc, 2)
                                    eq_res["cvMethod"] = "gas"
                            else:
                                Q_gpm = (mf / rho * 15850.3) if rho > 0 else 0  # m³/s to US GPM
                                if dp_psi > 0 and Q_gpm > 0:
                                    cv_calc = Q_gpm * math.sqrt(sg / dp_psi)
                                    eq_res["cv"] = round(cv_calc, 2)
                                    eq_res["cvMethod"] = "liquid"

                            # Choked flow check
                            if bool(params.get("chokedFlowCheck", False)):
                                # Get vapor pressure from flash
                                Pv = P_in * 0.1  # rough default
                                Pc = P_in * 10.0  # rough default
                                if flash_in and flash_in.get("flasher"):
                                    try:
                                        consts = flash_in.get("constants")
                                        if consts and hasattr(consts, "Pcs") and consts.Pcs:
                                            Pc = sum(z * pc for z, pc in zip(zs_v, consts.Pcs)) if len(consts.Pcs) == len(zs_v) else Pc
                                        # Estimate Pv from VF=0 flash
                                        if flash_in.get("VF", 0) < 0.01:
                                            Pv = P_in * 0.3  # subcooled liquid estimate
                                    except Exception:
                                        pass
                                FF = 0.96 - 0.28 * math.sqrt(Pv / Pc) if Pc > 0 else 0.96
                                P_choked = Pv * FF
                                if P_out < P_choked:
                                    logs.append(f"WARNING: {name} choked flow detected — P_out ({_pa_to_kpa(P_out):.1f} kPa) < P_choked ({_pa_to_kpa(P_choked):.1f} kPa)")
                                    eq_res["chokedFlow"] = True
                                else:
                                    eq_res["chokedFlow"] = False

                            # ISA 60534 control valve sizing (when sizingMode enabled)
                            if bool(params.get("sizingMode", False)):
                                try:
                                    from app.services.control_valve_engine import size_control_valve
                                    valve_type = str(params.get("valveType", "globe"))
                                    pipe_dia = float(params.get("pipeDiameter", 0.1))
                                    phase_v = "gas" if vf_out > 0.5 else "liquid"
                                    cv_result = size_control_valve(
                                        phase=phase_v, valve_type=valve_type,
                                        inlet_pressure=_pa_to_kpa(P_in),
                                        outlet_pressure=_pa_to_kpa(P_out),
                                        temperature=_k_to_c(T_in),
                                        volumetric_flow=mf / rho * 3600 if rho > 0 else 0,
                                        specific_gravity=rho / 999.0 if rho > 0 else 1.0,
                                        mass_flow_rate=mf * 3600,
                                        molecular_weight=flash_in.get("MW_mix", 28.97) if flash_in else 28.97,
                                        pipe_diameter=pipe_dia,
                                    )
                                    eq_res["calculatedCv"] = cv_result.get("calculated_cv", 0)
                                    eq_res["selectedCv"] = cv_result.get("selected_cv", 0)
                                    eq_res["percentOpen"] = cv_result.get("percent_open", 0)
                                    eq_res["flowRegime"] = cv_result.get("flow_regime", "")
                                except Exception as exc_cv:
                                    logs.append(f"WARNING: {name} ISA 60534 sizing failed: {exc_cv}")

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Valve is isenthalpic by definition: h_out = h_in
                            outlet["enthalpy"] = inlet["enthalpy"]
                            outlet["vapor_fraction"] = vf_out
                            outlet["composition"] = dict(comp)
                            outlets["out-1"] = outlet
                            logs.append(f"{name}: ΔP = {eq_res['pressureDrop']:.1f} kPa, T_out = {_k_to_c(T_out):.1f} °C")

                        elif ntype == "Mixer":
                            total_mass = 0.0
                            total_enthalpy_rate = 0.0  # W  (mass_flow * specific_enthalpy)
                            mixed_comp_molar: dict[str, float] = {}  # accumulate molar amounts
                            total_molar = 0.0
                            P_min = float("inf")

                            for s in inlets:
                                mf = s.get("mass_flow", 1.0)
                                h = s.get("enthalpy", 0.0)  # J/kg
                                total_mass += mf
                                total_enthalpy_rate += mf * h
                                P_min = min(P_min, s.get("pressure", 101325.0))

                                # Molar weighting for composition (Fix 2)
                                s_comp = s.get("composition", {})
                                if s_comp:
                                    MW_mix_s = sum(z * _get_mw(c) for c, z in s_comp.items())
                                    if MW_mix_s > 0:
                                        n_molar = mf / (MW_mix_s / 1000.0)  # mol/s
                                    else:
                                        n_molar = mf / 0.018  # fallback to water MW
                                    for cname, zfrac in s_comp.items():
                                        mixed_comp_molar[cname] = mixed_comp_molar.get(cname, 0.0) + zfrac * n_molar
                                    total_molar += n_molar

                            # Normalize mole fractions
                            mixed_comp: dict[str, float] = {}
                            if total_molar > 0:
                                for cname in mixed_comp_molar:
                                    mixed_comp[cname] = mixed_comp_molar[cname] / total_molar
                            else:
                                mixed_comp = {}

                            if total_mass > 0:
                                h_mix = total_enthalpy_rate / total_mass  # J/kg
                            else:
                                h_mix = 0.0

                            if P_min == float("inf"):
                                P_min = 101325.0

                            # User-specified outlet pressure or pressure drop
                            p_out_user = params.get("pressure")
                            if p_out_user is not None:
                                P_out = _kpa_to_pa(float(p_out_user))
                            else:
                                dp = _kpa_to_pa(float(params.get("pressureDrop", 0)))
                                P_out = P_min - dp

                            # Use HP flash for correct outlet T (Fix 9)
                            vf_out = 0.0
                            used_thermo = False
                            comp_names = list(mixed_comp.keys())
                            zs = [float(v) for v in mixed_comp.values()]

                            # M1: Estimate T for fallback using mass-weighted average inlet T and h
                            cp_est = _estimate_cp(mixed_comp)
                            T_avg_inlets = sum(s.get("mass_flow", 1.0) * s.get("temperature", _T_REF) for s in inlets) / max(total_mass, 1e-12)
                            h_avg_inlets = sum(s.get("mass_flow", 1.0) * s.get("enthalpy", 0.0) for s in inlets) / max(total_mass, 1e-12)
                            T_out = T_avg_inlets + (h_mix - h_avg_inlets) / cp_est if cp_est > 0 else T_avg_inlets

                            if comp_names and len(comp_names) >= 1:
                                # Try HP flash: given mixed H (molar) and P_out, find T
                                try:
                                    MW_mix_out = sum(z * _get_mw(c) for c, z in mixed_comp.items())
                                    H_molar = h_mix * (MW_mix_out / 1000.0)  # J/kg → J/mol
                                    # Build flasher for HP flash
                                    test_flash = self._flash_tp(comp_names, zs, max(T_out, 200.0), P_out, property_package)
                                    if test_flash and test_flash.get("flasher"):
                                        flasher = test_flash["flasher"]
                                        state_hp = flasher.flash(H=H_molar, P=P_out, zs=test_flash["zs"])
                                        T_out = state_hp.T
                                        vf_out = state_hp.VF if state_hp.VF is not None else 0.0
                                        used_thermo = True
                                except Exception as exc:
                                    logger.warning("Mixer HP flash failed: %s", exc)
                                    # Keep estimated T_out
                                if not used_thermo and comp_names:
                                    tp_fallback = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                                    if tp_fallback:
                                        vf_out = tp_fallback.get("VF", 0.0)

                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)
                            eq_res["totalMassFlow"] = round(total_mass, 4)

                            outlet = {
                                "temperature": T_out,
                                "pressure": P_out,
                                "mass_flow": total_mass,
                                "enthalpy": h_mix,
                                "vapor_fraction": vf_out,
                                "composition": mixed_comp,
                            }
                            outlets["out-1"] = outlet
                            engine_note = " (thermo)" if used_thermo else ""
                            logs.append(f"{name}: mixed flow = {total_mass:.2f} kg/s{engine_note}")

                        elif ntype == "Splitter":
                            inlet = inlets[0]
                            mf = inlet["mass_flow"]
                            ratio = float(params.get("splitRatio", 0.5))
                            ratio = max(0.0, min(1.0, ratio))

                            eq_res["splitRatio"] = ratio

                            out1 = dict(inlet)
                            out1["mass_flow"] = mf * ratio
                            out1["composition"] = dict(inlet.get("composition", {}))
                            out2 = dict(inlet)
                            out2["mass_flow"] = mf * (1.0 - ratio)
                            out2["composition"] = dict(inlet.get("composition", {}))

                            outlets["out-1"] = out1
                            outlets["out-2"] = out2
                            logs.append(f"{name}: split {ratio:.0%} / {1-ratio:.0%}")

                        elif ntype == "HeatExchanger":
                            # Two-stream heat exchanger — match inlets by port handle
                            hot = None
                            cold = None

                            for i, handle in enumerate(inlet_handles):
                                if i < len(inlets):
                                    if handle == "in-hot":
                                        hot = inlets[i]
                                    elif handle == "in-cold":
                                        cold = inlets[i]

                            # If no handles matched (old-style position-based), use index
                            if hot is None and len(inlets) >= 1:
                                hot = inlets[0]
                            if cold is None and len(inlets) >= 2:
                                cold = inlets[1]
                            if hot is None:
                                hot = dict(_DEFAULT_FEED)
                            if cold is None:
                                cold = dict(_DEFAULT_FEED)

                            # Ensure hot is actually hotter (T2-08: track swap for correct outlet mapping)
                            swapped = False
                            if cold["temperature"] > hot["temperature"]:
                                hot, cold = cold, hot
                                swapped = True

                            T_hot_in = hot["temperature"]
                            T_cold_in = cold["temperature"]
                            mf_hot = hot["mass_flow"]
                            mf_cold = cold["mass_flow"]
                            P_hot_in = hot.get("pressure", 101325.0)
                            P_cold_in = cold.get("pressure", 101325.0)

                            # Real Cp from thermo flash (Fix 7)
                            hot_comp = hot.get("composition", {})
                            cold_comp = cold.get("composition", {})
                            cp_hot = _estimate_cp(hot_comp)  # composition-aware fallback
                            cp_cold = _estimate_cp(cold_comp)

                            hot_comp_names = list(hot_comp.keys())
                            hot_zs = [float(v) for v in hot_comp.values()]
                            cold_comp_names = list(cold_comp.keys())
                            cold_zs = [float(v) for v in cold_comp.values()]

                            flash_hot = self._flash_tp(hot_comp_names, hot_zs, T_hot_in, P_hot_in, property_package)
                            flash_cold = self._flash_tp(cold_comp_names, cold_zs, T_cold_in, P_cold_in, property_package)
                            if flash_hot and flash_hot.get("Cp") and flash_hot["MW_mix"] > 0:
                                mw_hot_kg = flash_hot["MW_mix"] / 1000.0
                                cp_hot = flash_hot["Cp"] / mw_hot_kg  # J/(kg·K)
                            if flash_cold and flash_cold.get("Cp") and flash_cold["MW_mix"] > 0:
                                mw_cold_kg = flash_cold["MW_mix"] / 1000.0
                                cp_cold = flash_cold["Cp"] / mw_cold_kg  # J/(kg·K)

                            dp_hot = _kpa_to_pa(float(params.get("pressureDropHot", 10)))
                            dp_cold = _kpa_to_pa(float(params.get("pressureDropCold", 10)))

                            # Use specified outlet temps if provided
                            T_hot_out_c = params.get("hotOutletTemp")
                            T_cold_out_c = params.get("coldOutletTemp")

                            # H2: Use enthalpy-based calculation when thermo available
                            # Compute inlet enthalpies for HP flash approach
                            h_hot_in_kg = None
                            h_cold_in_kg = None
                            if flash_hot and flash_hot.get("MW_mix", 0) > 0:
                                h_hot_in_kg = flash_hot["H"] / (flash_hot["MW_mix"] / 1000.0)  # J/kg
                            if flash_cold and flash_cold.get("MW_mix", 0) > 0:
                                h_cold_in_kg = flash_cold["H"] / (flash_cold["MW_mix"] / 1000.0)

                            if T_hot_out_c is not None and T_cold_out_c is not None:
                                T_hot_out = _c_to_k(float(T_hot_out_c))
                                T_cold_out = _c_to_k(float(T_cold_out_c))
                                # Compute duty from enthalpy if available, else Cp
                                if h_hot_in_kg is not None:
                                    flash_h_out = self._flash_tp(hot_comp_names, hot_zs, T_hot_out, P_hot_in - dp_hot, property_package)
                                    if flash_h_out and flash_h_out.get("MW_mix", 0) > 0:
                                        h_hot_out_kg = flash_h_out["H"] / (flash_h_out["MW_mix"] / 1000.0)
                                        duty = mf_hot * (h_hot_in_kg - h_hot_out_kg)
                                    else:
                                        duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                else:
                                    duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                duty_cold = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                                if max(abs(duty), abs(duty_cold)) > 0:
                                    imbalance = abs(duty - duty_cold) / max(abs(duty), abs(duty_cold))
                                    if imbalance > 0.05:
                                        logs.append(
                                            f"WARNING: {name} specified outlet temps imply {imbalance:.0%} energy imbalance "
                                            f"— adjusting cold outlet to match hot-side duty"
                                        )
                                        # Use HP flash to find cold outlet T from duty
                                        if h_cold_in_kg is not None and flash_cold and flash_cold.get("flasher"):
                                            try:
                                                mw_cold_kg = flash_cold["MW_mix"] / 1000.0
                                                H_cold_out_mol = (h_cold_in_kg + duty / mf_cold) * mw_cold_kg if mf_cold > 0 else flash_cold["H"]
                                                state_cold_hp = flash_cold["flasher"].flash(H=H_cold_out_mol, P=P_cold_in - dp_cold, zs=flash_cold["zs"])
                                                T_cold_out = state_cold_hp.T
                                            except Exception:
                                                T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                                        else:
                                            T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                            elif T_hot_out_c is not None:
                                T_hot_out = _c_to_k(float(T_hot_out_c))
                                # Compute duty from enthalpy
                                if h_hot_in_kg is not None:
                                    flash_h_out = self._flash_tp(hot_comp_names, hot_zs, T_hot_out, P_hot_in - dp_hot, property_package)
                                    if flash_h_out and flash_h_out.get("MW_mix", 0) > 0:
                                        duty = mf_hot * (h_hot_in_kg - flash_h_out["H"] / (flash_h_out["MW_mix"] / 1000.0))
                                    else:
                                        duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                else:
                                    duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                # Find cold outlet T from duty via HP flash
                                if h_cold_in_kg is not None and flash_cold and flash_cold.get("flasher"):
                                    try:
                                        mw_cold_kg = flash_cold["MW_mix"] / 1000.0
                                        H_cold_out_mol = (h_cold_in_kg + duty / mf_cold) * mw_cold_kg if mf_cold > 0 else flash_cold["H"]
                                        state_cold_hp = flash_cold["flasher"].flash(H=H_cold_out_mol, P=P_cold_in - dp_cold, zs=flash_cold["zs"])
                                        T_cold_out = state_cold_hp.T
                                    except Exception:
                                        T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                                else:
                                    T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                            elif T_cold_out_c is not None:
                                T_cold_out = _c_to_k(float(T_cold_out_c))
                                # Compute duty from cold side enthalpy
                                if h_cold_in_kg is not None:
                                    flash_c_out = self._flash_tp(cold_comp_names, cold_zs, T_cold_out, P_cold_in - dp_cold, property_package)
                                    if flash_c_out and flash_c_out.get("MW_mix", 0) > 0:
                                        duty = mf_cold * (flash_c_out["H"] / (flash_c_out["MW_mix"] / 1000.0) - h_cold_in_kg)
                                    else:
                                        duty = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                                else:
                                    duty = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                                # Find hot outlet T from duty via HP flash
                                if h_hot_in_kg is not None and flash_hot and flash_hot.get("flasher"):
                                    try:
                                        mw_hot_kg = flash_hot["MW_mix"] / 1000.0
                                        H_hot_out_mol = (h_hot_in_kg - duty / mf_hot) * mw_hot_kg if mf_hot > 0 else flash_hot["H"]
                                        state_hot_hp = flash_hot["flasher"].flash(H=H_hot_out_mol, P=P_hot_in - dp_hot, zs=flash_hot["zs"])
                                        T_hot_out = state_hot_hp.T
                                    except Exception:
                                        T_hot_out = T_hot_in - duty / (mf_hot * cp_hot) if mf_hot * cp_hot > 0 else T_hot_in
                                else:
                                    T_hot_out = T_hot_in - duty / (mf_hot * cp_hot) if mf_hot * cp_hot > 0 else T_hot_in
                            else:
                                # Default: 30% of driving force as approach (prevents excessive duty with large ΔT)
                                dT_available = T_hot_in - T_cold_in
                                approach_hx = max(1.0, min(0.3 * dT_available, dT_available - 1.0)) if dT_available > 2.0 else max(0.5, dT_available * 0.3)
                                T_hot_out = T_cold_in + approach_hx
                                logs.append(
                                    f"{name}: no outlet temps specified — using {approach_hx:.0f}K approach "
                                    f"(T_hot_out = {_k_to_c(T_hot_out):.0f}°C). Specify hotOutletTemp or "
                                    f"coldOutletTemp for accuracy."
                                )
                                if h_hot_in_kg is not None:
                                    flash_h_out = self._flash_tp(hot_comp_names, hot_zs, T_hot_out, P_hot_in - dp_hot, property_package)
                                    if flash_h_out and flash_h_out.get("MW_mix", 0) > 0:
                                        duty = mf_hot * (h_hot_in_kg - flash_h_out["H"] / (flash_h_out["MW_mix"] / 1000.0))
                                    else:
                                        duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                else:
                                    duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                if h_cold_in_kg is not None and flash_cold and flash_cold.get("flasher"):
                                    try:
                                        mw_cold_kg = flash_cold["MW_mix"] / 1000.0
                                        H_cold_out_mol = (h_cold_in_kg + duty / mf_cold) * mw_cold_kg if mf_cold > 0 else flash_cold["H"]
                                        state_cold_hp = flash_cold["flasher"].flash(H=H_cold_out_mol, P=P_cold_in - dp_cold, zs=flash_cold["zs"])
                                        T_cold_out = state_cold_hp.T
                                    except Exception:
                                        T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                                else:
                                    T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in

                            # Clamp to prevent 2nd-law violations (temperature cross)
                            dT_min_hx = 1.0  # K minimum approach temperature
                            if T_cold_out > T_hot_in - dT_min_hx:
                                T_cold_out_old = T_cold_out
                                T_cold_out = T_hot_in - dT_min_hx
                                logs.append(
                                    f"WARNING: {name} cold outlet {_k_to_c(T_cold_out_old):.1f}°C > hot inlet {_k_to_c(T_hot_in):.1f}°C "
                                    f"— clamped to {_k_to_c(T_cold_out):.1f}°C (2nd law)"
                                )
                                # Recompute duty from clamped cold side
                                duty = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                                # Recompute hot outlet from energy balance
                                T_hot_out = T_hot_in - duty / (mf_hot * cp_hot) if mf_hot * cp_hot > 0 else T_hot_in
                            if T_hot_out < T_cold_in + dT_min_hx:
                                T_hot_out_old = T_hot_out
                                T_hot_out = T_cold_in + dT_min_hx
                                logs.append(
                                    f"WARNING: {name} hot outlet {_k_to_c(T_hot_out_old):.1f}°C < cold inlet {_k_to_c(T_cold_in):.1f}°C "
                                    f"— clamped to {_k_to_c(T_hot_out):.1f}°C (2nd law)"
                                )
                                # Recompute duty from clamped hot side
                                duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                                # Recompute cold outlet from energy balance
                                T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                                # Final safety clamp on cold side
                                if T_cold_out > T_hot_in - dT_min_hx:
                                    T_cold_out = T_hot_in - dT_min_hx
                                    # Recompute duty to stay consistent with clamped temps
                                    duty = mf_cold * cp_cold * (T_cold_out - T_cold_in)

                            hot_out = dict(hot)
                            hot_out["temperature"] = T_hot_out
                            hot_out["pressure"] = P_hot_in - dp_hot
                            # Store thermo-based enthalpy if available
                            flash_hot_out = self._flash_tp(hot_comp_names, hot_zs, T_hot_out, P_hot_in - dp_hot, property_package)
                            if flash_hot_out and flash_hot_out["MW_mix"] > 0:
                                hot_out["enthalpy"] = flash_hot_out["H"] / (flash_hot_out["MW_mix"] / 1000.0)
                                hot_out["vapor_fraction"] = flash_hot_out.get("VF", hot_out.get("vapor_fraction", 0))
                            else:
                                hot_out["enthalpy"] = cp_hot * (T_hot_out - _T_REF)
                            hot_out["composition"] = dict(hot_comp)

                            cold_out = dict(cold)
                            cold_out["temperature"] = T_cold_out
                            cold_out["pressure"] = P_cold_in - dp_cold
                            flash_cold_out = self._flash_tp(cold_comp_names, cold_zs, T_cold_out, P_cold_in - dp_cold, property_package)
                            if flash_cold_out and flash_cold_out["MW_mix"] > 0:
                                cold_out["enthalpy"] = flash_cold_out["H"] / (flash_cold_out["MW_mix"] / 1000.0)
                                cold_out["vapor_fraction"] = flash_cold_out.get("VF", cold_out.get("vapor_fraction", 0))
                            else:
                                cold_out["enthalpy"] = cp_cold * (T_cold_out - _T_REF)

                            # Recompute duty from upstream enthalpies (not re-flash)
                            # to ensure energy balance consistency with upstream equipment
                            h_hot_in_up = hot.get("enthalpy", 0.0)
                            h_hot_out_j = hot_out["enthalpy"]
                            duty = mf_hot * (h_hot_in_up - h_hot_out_j)
                            # Force cold outlet enthalpy from energy balance
                            h_cold_in_up = cold.get("enthalpy", 0.0)
                            if mf_cold > 0:
                                cold_out["enthalpy"] = h_cold_in_up + duty / mf_cold

                            eq_res["duty"] = round(_w_to_kw(duty), 3)
                            eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out), 2)
                            eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out), 2)
                            eq_res["LMTD"] = round(self._calc_lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out), 2)

                            # Determine VF for hot inlet (used below for U estimation)
                            vf_hot_in = flash_hot.get("VF", 0) if flash_hot else 0

                            # Phase 15 §3.1: Multi-pass Ft correction
                            n_shell_passes = int(params.get("shellPasses", 1))
                            n_tube_passes = int(params.get("tubePasses", 2))
                            fouling_hot = float(params.get("foulingHot", 0.0002))
                            fouling_cold = float(params.get("foulingCold", 0.0002))
                            if n_shell_passes >= 1 and n_tube_passes >= 2:
                                R_ht = (T_hot_in - T_hot_out) / max(T_cold_out - T_cold_in, 0.1)
                                P_ht = (T_cold_out - T_cold_in) / max(T_hot_in - T_cold_in, 0.1)
                                Ft = None
                                try:
                                    from ht import F_LMTD_Fagan  # type: ignore[import-untyped]
                                    Ft = F_LMTD_Fagan(R_ht, P_ht, n_shell_passes)
                                except ImportError:
                                    pass
                                except Exception as exc_ht:
                                    logger.debug("ht Ft correction failed: %s", exc_ht)
                                # Analytical fallback when ht is unavailable or failed
                                if Ft is None:
                                    Ft = _lmtd_correction_factor(R_ht, P_ht, n_shell_passes)
                                Ft = max(0.5, min(1.0, Ft))
                                eq_res["Ft_correction"] = round(Ft, 4)
                                eq_res["shellPasses"] = n_shell_passes
                                eq_res["tubePasses"] = n_tube_passes
                                # Corrected LMTD
                                lmtd_corr = eq_res.get("LMTD", 10) * Ft
                                eq_res["LMTD_corrected"] = round(lmtd_corr, 2)
                                logs.append(f"{name}: Ft={Ft:.3f} ({n_shell_passes}S-{n_tube_passes}T), LMTD_corr={lmtd_corr:.1f} K")

                            # Overall U estimation with fouling
                            U_user = float(params.get("overallU", 0))
                            if U_user <= 0:
                                # Estimate U from service type
                                U_user = 500.0  # default W/(m²·K)
                                hx_geometry_type = str(params.get("geometry", "shell-tube"))
                                if hx_geometry_type == "plate":
                                    U_user = 1000.0
                                elif vf_hot_in > 0.5:
                                    U_user = 200.0  # gas cooling
                            # Apply fouling resistance: 1/U_dirty = 1/U_clean + R_f
                            total_fouling = fouling_hot + fouling_cold
                            if total_fouling > 0 and U_user > 0:
                                U_dirty = 1.0 / (1.0 / U_user + total_fouling)
                                eq_res["U_clean"] = round(U_user, 1)
                                eq_res["U_dirty"] = round(U_dirty, 1)
                                eq_res["fouling_total"] = round(total_fouling, 6)

                            # Estimate area from duty and LMTD
                            lmtd_for_area = eq_res.get("LMTD_corrected", eq_res.get("LMTD", 10))
                            U_for_area = eq_res.get("U_dirty", U_user)
                            if lmtd_for_area > 0 and U_for_area > 0:
                                area_est = abs(duty) / (U_for_area * lmtd_for_area)
                                eq_res["area_estimated"] = round(area_est, 2)

                            # Effective UA
                            if lmtd_for_area > 0 and abs(duty) > 0:
                                eq_res["UA_effective"] = round(abs(duty) / lmtd_for_area, 2)

                            # Geometry-based rating via equipment_rating
                            tube_geom = params.get("tubeGeometry") or params.get("tube_geometry")
                            if isinstance(tube_geom, dict) and tube_geom.get("n_tubes"):
                                try:
                                    from app.services.equipment_rating import rate_heat_exchanger
                                    # Build process dict from current stream data
                                    _mu_hot = flash_hot.get("mu", 0.001) if flash_hot else 0.001
                                    _mu_cold = flash_cold.get("mu", 0.001) if flash_cold else 0.001
                                    _k_hot = flash_hot.get("k", 0.6) if flash_hot else 0.6
                                    _k_cold = flash_cold.get("k", 0.6) if flash_cold else 0.6
                                    _rho_hot = flash_hot.get("rho", 1000.0) if flash_hot else 1000.0
                                    _rho_cold = flash_cold.get("rho", 1000.0) if flash_cold else 1000.0
                                    rating_process = {
                                        "hot_flow_kg_s": mf_hot,
                                        "cold_flow_kg_s": mf_cold,
                                        "T_hot_in_K": T_hot_in,
                                        "T_cold_in_K": T_cold_in,
                                        "Cp_hot": cp_hot,
                                        "Cp_cold": cp_cold,
                                        "mu_hot": _mu_hot,
                                        "mu_cold": _mu_cold,
                                        "k_hot": _k_hot,
                                        "k_cold": _k_cold,
                                        "rho_hot": _rho_hot,
                                        "rho_cold": _rho_cold,
                                    }
                                    rating_geom = dict(tube_geom)
                                    rating_geom.setdefault("n_passes", n_tube_passes)
                                    rating_geom.setdefault("fouling_factor", total_fouling)
                                    rating_result = rate_heat_exchanger(rating_geom, rating_process)
                                    eq_res["rating"] = rating_result
                                    # Override outlet temps and duty from geometry rating
                                    T_hot_out_r = rating_result.get("T_hot_out_K", T_hot_out)
                                    T_cold_out_r = rating_result.get("T_cold_out_K", T_cold_out)
                                    duty_r = rating_result.get("duty_W", duty)
                                    hot_out["temperature"] = T_hot_out_r
                                    cold_out["temperature"] = T_cold_out_r
                                    # Re-flash outlets at rated temperatures
                                    flash_hot_r = self._flash_tp(hot_comp_names, hot_zs, T_hot_out_r, P_hot_in - dp_hot, property_package)
                                    if flash_hot_r and flash_hot_r.get("MW_mix", 0) > 0:
                                        hot_out["enthalpy"] = flash_hot_r["H"] / (flash_hot_r["MW_mix"] / 1000.0)
                                        hot_out["vapor_fraction"] = flash_hot_r.get("VF", hot_out.get("vapor_fraction", 0))
                                    flash_cold_r = self._flash_tp(cold_comp_names, cold_zs, T_cold_out_r, P_cold_in - dp_cold, property_package)
                                    if flash_cold_r and flash_cold_r.get("MW_mix", 0) > 0:
                                        cold_out["enthalpy"] = flash_cold_r["H"] / (flash_cold_r["MW_mix"] / 1000.0)
                                        cold_out["vapor_fraction"] = flash_cold_r.get("VF", cold_out.get("vapor_fraction", 0))
                                    # Update eq_res with rated values
                                    eq_res["duty"] = round(_w_to_kw(duty_r), 3)
                                    eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out_r), 2)
                                    eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out_r), 2)
                                    eq_res["LMTD"] = round(rating_result.get("LMTD_K", eq_res.get("LMTD", 0)), 2)
                                    eq_res["U_rated"] = rating_result.get("U_overall_W_m2K")
                                    eq_res["area_rated"] = rating_result.get("area_m2")
                                    eq_res["method"] = "geometry-rating"
                                    logs.append(
                                        f"{name}: geometry rating — U={rating_result.get('U_overall_W_m2K', 0):.0f} W/(m²·K), "
                                        f"A={rating_result.get('area_m2', 0):.1f} m², Q={rating_result.get('duty_kW', 0):.1f} kW"
                                    )
                                except ImportError:
                                    logger.warning("equipment_rating not available for geometry-based HX rating")
                                except Exception as exc_rating:
                                    logger.debug("HX geometry rating failed: %s", exc_rating)

                            # NTU method override
                            hx_method = str(params.get("method", "LMTD"))
                            if hx_method == "NTU":
                                geometry = str(params.get("geometry", "shell-tube"))
                                fouling = float(params.get("foulingFactor", 0.0002))
                                C_hot = mf_hot * cp_hot
                                C_cold = mf_cold * cp_cold
                                C_min = min(C_hot, C_cold)
                                C_max = max(C_hot, C_cold)
                                C_r = C_min / C_max if C_max > 0 else 0
                                Q_max = C_min * abs(T_hot_in - T_cold_in)
                                U = 500.0
                                if fouling > 0:
                                    U = 1.0 / (1.0 / U + fouling)
                                # H9: Accept area as input parameter; fall back to LMTD-derived area
                                user_area = float(params.get("area", 0))
                                if user_area > 0:
                                    A_ntu = user_area
                                else:
                                    lmtd_val = eq_res.get("LMTD", 10)
                                    A_ntu = abs(duty) / (U * max(lmtd_val, 1)) if lmtd_val > 0 else 10.0
                                NTU = U * A_ntu / C_min if C_min > 0 else 0
                                if C_r == 0:
                                    epsilon = 1 - math.exp(-NTU) if NTU > 0 else 0
                                elif geometry == "plate":
                                    denom = 1 - C_r * math.exp(-NTU * (1 - C_r))
                                    epsilon = (1 - math.exp(-NTU * (1 - C_r))) / denom if denom != 0 else 0
                                else:
                                    factor = math.sqrt(1 + C_r ** 2)
                                    exp_val = math.exp(-NTU * factor)
                                    numer = 1 + exp_val
                                    denom_s = 1 - exp_val + 1e-30
                                    epsilon = 2.0 / (1 + C_r + factor * numer / denom_s)
                                epsilon = max(0, min(1, epsilon))
                                Q_ntu = epsilon * Q_max
                                T_hot_out = T_hot_in - Q_ntu / C_hot if C_hot > 0 else T_hot_in
                                T_cold_out = T_cold_in + Q_ntu / C_cold if C_cold > 0 else T_cold_in
                                hot_out["temperature"] = T_hot_out
                                cold_out["temperature"] = T_cold_out
                                # Re-flash outlets at NTU temperatures to update enthalpies and VF
                                flash_hot_ntu = self._flash_tp(hot_comp_names, hot_zs, T_hot_out, P_hot_in - dp_hot, property_package)
                                if flash_hot_ntu and flash_hot_ntu.get("MW_mix", 0) > 0:
                                    hot_out["enthalpy"] = flash_hot_ntu["H"] / (flash_hot_ntu["MW_mix"] / 1000.0)
                                    hot_out["vapor_fraction"] = flash_hot_ntu.get("VF", hot_out.get("vapor_fraction", 0))
                                flash_cold_ntu = self._flash_tp(cold_comp_names, cold_zs, T_cold_out, P_cold_in - dp_cold, property_package)
                                if flash_cold_ntu and flash_cold_ntu.get("MW_mix", 0) > 0:
                                    cold_out["enthalpy"] = flash_cold_ntu["H"] / (flash_cold_ntu["MW_mix"] / 1000.0)
                                    cold_out["vapor_fraction"] = flash_cold_ntu.get("VF", cold_out.get("vapor_fraction", 0))
                                # Recalculate duty using upstream enthalpies for consistency
                                h_hot_out_ntu = hot_out["enthalpy"]
                                Q_ntu = mf_hot * (h_hot_in_up - h_hot_out_ntu)
                                # Force cold-side enthalpy from energy balance
                                if mf_cold > 0:
                                    cold_out["enthalpy"] = h_cold_in_up + Q_ntu / mf_cold
                                eq_res["method"] = "NTU"
                                eq_res["area"] = round(A_ntu, 3)
                                eq_res["ntu"] = round(NTU, 3)
                                eq_res["effectiveness"] = round(epsilon, 4)
                                eq_res["duty"] = round(_w_to_kw(Q_ntu), 3)
                                eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out), 2)
                                eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out), 2)
                                logs.append(f"{name}: NTU={NTU:.2f}, ε={epsilon:.3f}, Q={_w_to_kw(Q_ntu):.1f} kW")

                            cold_out["composition"] = dict(cold_comp)

                            # T2-08: If streams were swapped, reverse outlet assignment
                            if swapped:
                                outlets["out-hot"] = cold_out
                                outlets["out-cold"] = hot_out
                            else:
                                outlets["out-hot"] = hot_out
                                outlets["out-cold"] = cold_out
                            logs.append(f"{name}: duty = {eq_res['duty']:.1f} kW, LMTD = {eq_res['LMTD']:.1f} K")

                        elif ntype == "Separator":
                            inlet = inlets[0]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})

                            # Operating conditions from parameters (user-specified T & P)
                            T_op_c = params.get("temperature")
                            T_op = _c_to_k(float(T_op_c)) if T_op_c is not None else inlet["temperature"]
                            P_op_kpa = params.get("pressure")
                            P_op = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else inlet["pressure"]
                            # M2: Apply pressure drop
                            dp_sep = _kpa_to_pa(float(params.get("pressureDrop", 0)))
                            P_op = max(P_op - dp_sep, 1000.0)

                            vf = 0.0  # molar vapor fraction
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]

                            # Use shared _flash_tp helper (Fix 3: >= 1 allows single-component)
                            if len(comp_names) >= 1:
                                flash_result = self._flash_tp(comp_names, zs, T_op, P_op, property_package)
                                if flash_result:
                                    vf = flash_result["VF"]
                                    # Supercritical override now handled in _flash_tp()
                                    # Mass-based split
                                    MWs = flash_result["MWs"]
                                    gas_zs = flash_result["gas_zs"]
                                    liq_zs = flash_result["liquid_zs"]

                                    MW_vap = sum(z * mw for z, mw in zip(gas_zs, MWs))
                                    MW_liq = sum(z * mw for z, mw in zip(liq_zs, MWs))
                                    denom = vf * MW_vap + (1 - vf) * MW_liq
                                    mass_vap_frac = (vf * MW_vap) / denom if denom > 0 else vf

                                    vapor_comp = {comp_names[i]: gas_zs[i] for i in range(len(comp_names))}
                                    liquid_comp = {comp_names[i]: liq_zs[i] for i in range(len(comp_names))}

                                    # Per-phase enthalpy directly from _flash_tp result (no re-flash needed)
                                    MW_vap_kg = MW_vap / 1000.0 if MW_vap > 0 else 0.028  # g/mol → kg/mol
                                    MW_liq_kg = MW_liq / 1000.0 if MW_liq > 0 else 0.018
                                    H_gas_mol = flash_result.get("H_gas")  # J/mol or None
                                    H_liq_mol = flash_result.get("H_liquid")  # J/mol or None
                                    h_vap = H_gas_mol / MW_vap_kg if H_gas_mol is not None and MW_vap_kg > 0 else 0.0  # J/kg
                                    h_liq = H_liq_mol / MW_liq_kg if H_liq_mol is not None and MW_liq_kg > 0 else 0.0  # J/kg
                                    # Overall mixture enthalpy as fallback (supercritical/single-phase)
                                    h_mix = flash_result.get("H", 0.0)
                                    MW_mix = flash_result.get("MW_mix", 1.0)
                                    h_mix_mass = h_mix / (MW_mix / 1000.0) if MW_mix > 0 else 0.0
                                    # Supercritical/single-phase fallback: if VF≈1 but no gas phase
                                    # (supercritical override), use overall mixture enthalpy
                                    if vf > 0.99 and h_vap == 0.0 and h_mix_mass != 0.0:
                                        h_vap = h_mix_mass
                                    if vf < 0.01 and h_liq == 0.0 and h_mix_mass != 0.0:
                                        h_liq = h_mix_mass

                                    # Enforce energy balance: scale per-phase enthalpies
                                    # so mf_vap*h_vap + mf_liq*h_liq = mf*h_inlet
                                    mf_vap_sep = mf * mass_vap_frac
                                    mf_liq_sep = mf * (1 - mass_vap_frac)
                                    h_in_sep = inlet.get("enthalpy", 0.0)
                                    total_out_h = mf_vap_sep * h_vap + mf_liq_sep * h_liq
                                    total_in_h = mf * h_in_sep
                                    if abs(total_out_h) > 1e-6:
                                        eb_scale = total_in_h / total_out_h
                                        h_vap *= eb_scale
                                        h_liq *= eb_scale

                                    outlets["out-1"] = {
                                        "temperature": T_op,
                                        "pressure": P_op,
                                        "mass_flow": mf_vap_sep,
                                        "vapor_fraction": 1.0,
                                        "enthalpy": h_vap,
                                        "composition": vapor_comp,
                                    }
                                    outlets["out-2"] = {
                                        "temperature": T_op,
                                        "pressure": P_op,
                                        "mass_flow": mf_liq_sep,
                                        "vapor_fraction": 0.0,
                                        "enthalpy": h_liq,
                                        "composition": liquid_comp,
                                    }
                                    # Log zero-flow outlets
                                    mass_flow_liq = mf * (1 - mass_vap_frac)
                                    mass_flow_vap = mf * mass_vap_frac
                                    if mass_flow_liq <= 1e-12:
                                        logs.append(f"{name}: liquid outlet has zero flow (all vapor) — liquid composition is equilibrium estimate")
                                    if mass_flow_vap <= 1e-12:
                                        logs.append(f"{name}: vapor outlet has zero flow (all liquid) — vapor composition is equilibrium estimate")
                                    eq_res["vaporFraction"] = round(vf, 4)
                                    eq_res["massVaporFraction"] = round(mass_vap_frac, 4)
                                    logs.append(f"{name}: VF = {vf:.3f} (molar), mass VF = {mass_vap_frac:.3f}")

                            if not outlets:
                                # Simple fallback: assume 10% vapor (T3-05: differentiate V/L enthalpy)
                                vf_est = 0.1
                                cp_est = _estimate_cp(comp)
                                h_liq_est = cp_est * (T_op - _T_REF)
                                h_vap_est = h_liq_est + _estimate_hvap(comp)
                                outlets["out-1"] = {
                                    "temperature": T_op,
                                    "pressure": P_op,
                                    "mass_flow": mf * vf_est,
                                    "vapor_fraction": 1.0,
                                    "enthalpy": h_vap_est,
                                    "composition": comp,
                                }
                                outlets["out-2"] = {
                                    "temperature": T_op,
                                    "pressure": P_op,
                                    "mass_flow": mf * (1 - vf_est),
                                    "vapor_fraction": 0.0,
                                    "enthalpy": h_liq_est,
                                    "composition": comp,
                                }
                                eq_res["vaporFraction"] = vf_est
                                logs.append(f"WARNING: {name}: flash failed, estimated VF = {vf_est:.1%}")

                        elif ntype == "DistillationColumn":
                            # Collect all material inlets (skip energy handles)
                            material_inlets = [
                                inp for inp in inlets
                                if inp.get("mass_flow", 0) > 0
                            ]
                            inlet = material_inlets[0] if material_inlets else inlets[0]
                            mf = inlet["mass_flow"]
                            T_feed = inlet["temperature"]
                            P_feed = inlet["pressure"]
                            comp = inlet.get("composition", {})

                            n_stages = int(params.get("numberOfStages", 10))
                            reflux_ratio = float(params.get("refluxRatio", 1.5))
                            lk_recovery = max(0.5, min(0.9999, float(params.get("lkRecovery", 99)) / 100.0))
                            hk_recovery = max(0.5, min(0.9999, float(params.get("hkRecovery", 99)) / 100.0))
                            P_cond = _kpa_to_pa(float(params.get("condenserPressure", _pa_to_kpa(P_feed))))

                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            fug_ok = False

                            # Collect all active side draws (up to 3)
                            side_draws_fug: list[dict] = []
                            for sd_idx in range(1, 4):
                                suffix = "" if sd_idx == 1 else str(sd_idx)
                                sd_stage_raw = params.get(f"sideDrawStage{suffix}")
                                if sd_stage_raw is not None and float(sd_stage_raw) > 0:
                                    sd_stage_val = int(float(sd_stage_raw))
                                    sd_type_val = str(params.get(f"sideDrawType{suffix}", "liquid")).lower()
                                    sd_frac_val = float(params.get(f"sideDrawFlowFraction{suffix}", 0.1))
                                    sd_port_id = f"out-{sd_idx + 2}"  # out-3, out-4, out-5
                                    side_draws_fug.append({
                                        "stage": sd_stage_val, "type": sd_type_val,
                                        "fraction": sd_frac_val, "port": sd_port_id, "idx": sd_idx,
                                    })

                            # Collect pump-around circuits (up to 2)
                            pump_arounds_fug: list[dict] = []
                            for pa_idx in range(1, 3):
                                pa_draw = params.get(f"pumpAround{pa_idx}DrawStage")
                                pa_return = params.get(f"pumpAround{pa_idx}ReturnStage")
                                pa_duty = float(params.get(f"pumpAround{pa_idx}Duty", 0))
                                if pa_draw is not None and pa_return is not None and pa_duty > 0:
                                    pump_arounds_fug.append({
                                        "draw": int(float(pa_draw)),
                                        "return": int(float(pa_return)),
                                        "duty": pa_duty * 1000,  # kW to W
                                    })

                            # Multi-feed: merge additional feeds into equivalent single feed for FUG
                            # Use molar basis for composition merge (not mass-weighted mole fractions)
                            if len(material_inlets) > 1:
                                # Convert primary feed to molar flow
                                primary_mw_fug = sum(zs[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))
                                primary_molar = mf / (primary_mw_fug / 1000.0) if primary_mw_fug > 0 else mf / 0.1
                                total_molar_all = primary_molar
                                molar_weighted_zs = [z * primary_molar for z in zs]
                                # Compute enthalpy-weighted T via HP flash later; for now track enthalpy rate
                                total_mf_all = mf
                                h_rate_total = mf * inlet.get("enthalpy", 0.0)
                                for extra_in in material_inlets[1:]:
                                    extra_mf = extra_in.get("mass_flow", 0)
                                    extra_comp = extra_in.get("composition", {})
                                    extra_zs_fug = [float(extra_comp.get(cn, 0.0)) for cn in comp_names]
                                    ezs_sum = sum(extra_zs_fug) or 1.0
                                    extra_zs_fug = [z / ezs_sum for z in extra_zs_fug]
                                    extra_mw_fug = sum(extra_zs_fug[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))
                                    extra_molar_fug = extra_mf / (extra_mw_fug / 1000.0) if extra_mw_fug > 0 else extra_mf / 0.1
                                    total_molar_all += extra_molar_fug
                                    total_mf_all += extra_mf
                                    for ci in range(len(comp_names)):
                                        molar_weighted_zs[ci] += extra_zs_fug[ci] * extra_molar_fug
                                    h_rate_total += extra_mf * extra_in.get("enthalpy", inlet.get("enthalpy", 0.0))
                                if total_molar_all > 0:
                                    mf = total_mf_all
                                    zs_sum = sum(molar_weighted_zs) or 1.0
                                    zs = [z / zs_sum for z in molar_weighted_zs]
                                    # Use column operating pressure for merged feed
                                    P_feed = P_cond
                                    # Estimate T_feed: use enthalpy-weighted average as initial guess
                                    # (HP flash would be better but TP flash at average is reasonable for FUG)
                                    T_feed_sum = mf * T_feed
                                    for extra_in in material_inlets[1:]:
                                        T_feed_sum += extra_in.get("mass_flow", 0) * extra_in.get("temperature", T_feed)
                                    T_feed = T_feed_sum / total_mf_all if total_mf_all > 0 else T_feed

                            # Fenske-Underwood-Gilliland shortcut method (T2-01)
                            if len(comp_names) >= 2 and _thermo_available:
                                try:
                                    # Flash feed for K-values
                                    flash_feed = self._flash_tp(comp_names, zs, T_feed, P_feed, property_package)
                                    if flash_feed and flash_feed.get("VF") is not None:
                                        gas_zs = flash_feed["gas_zs"]
                                        liq_zs = flash_feed["liquid_zs"]
                                        vf_feed = flash_feed["VF"]

                                        # If single-phase, flash at bubble point for K-values
                                        if vf_feed <= 0.0 or vf_feed >= 1.0:
                                            flasher = flash_feed.get("flasher")
                                            if flasher:
                                                try:
                                                    state_bp = flasher.flash(VF=0, P=P_feed, zs=flash_feed["zs"])
                                                    gas_bp = getattr(state_bp, 'gas', None)
                                                    liq_bp = getattr(state_bp, 'liquid0', None)
                                                    if gas_bp and liq_bp:
                                                        gas_zs = list(gas_bp.zs)
                                                        liq_zs = list(liq_bp.zs)
                                                except Exception:
                                                    pass

                                        # K-values: K_i = y_i / x_i
                                        K_vals: list[float] = []
                                        for i in range(len(comp_names)):
                                            x_i = liq_zs[i] if liq_zs[i] > 1e-12 else 1e-12
                                            y_i = gas_zs[i] if gas_zs[i] > 1e-12 else 1e-12
                                            K_vals.append(y_i / x_i)

                                        # Identify light key and heavy key
                                        # User-specified override takes priority
                                        user_lk = params.get("lightKey")
                                        user_hk = params.get("heavyKey")
                                        lk_idx = -1
                                        hk_idx = -1

                                        if user_lk and user_lk in comp_names:
                                            lk_idx = comp_names.index(user_lk)
                                        if user_hk and user_hk in comp_names:
                                            hk_idx = comp_names.index(user_hk)

                                        if lk_idx < 0 or hk_idx < 0:
                                            # Adjacent key selection: sort by K-value, find closest pair
                                            sorted_indices = sorted(range(len(K_vals)), key=lambda i: K_vals[i], reverse=True)
                                            if len(sorted_indices) >= 2:
                                                best_pair = None
                                                best_alpha = float('inf')
                                                for j in range(len(sorted_indices) - 1):
                                                    i1, i2 = sorted_indices[j], sorted_indices[j + 1]
                                                    alpha_pair = K_vals[i1] / K_vals[i2] if K_vals[i2] > 1e-12 else 1e6
                                                    if 1.01 < alpha_pair < best_alpha:
                                                        best_alpha = alpha_pair
                                                        best_pair = (i1, i2)
                                                if best_pair:
                                                    if lk_idx < 0:
                                                        lk_idx = best_pair[0]
                                                    if hk_idx < 0:
                                                        hk_idx = best_pair[1]
                                                else:
                                                    # Fallback to extremes if no valid pair
                                                    if lk_idx < 0:
                                                        lk_idx = sorted_indices[0]
                                                    if hk_idx < 0:
                                                        hk_idx = sorted_indices[-1]
                                            else:
                                                lk_idx = 0
                                                hk_idx = 1 if len(comp_names) > 1 else 0

                                        K_lk = K_vals[lk_idx]
                                        K_hk = K_vals[hk_idx]

                                        # Relative volatilities: alpha_i = K_i / K_hk
                                        alpha_lk_hk = K_lk / K_hk if K_hk > 1e-12 else 10.0
                                        alphas = [K / K_hk if K_hk > 1e-12 else 1.0 for K in K_vals]

                                        if alpha_lk_hk > 1.01:
                                            # Fenske: N_min
                                            N_min = math.log((lk_recovery / (1 - lk_recovery)) * (hk_recovery / (1 - hk_recovery))) / math.log(alpha_lk_hk)

                                            # Preliminary component split using N_min (for Underwood R_min calc)
                                            d_hk_over_b_hk_pre = (1 - hk_recovery) / hk_recovery
                                            d_fracs_pre: list[float] = []
                                            for i in range(len(comp_names)):
                                                alpha_Nmin = alphas[i] ** N_min if N_min < 200 else 1e6
                                                ratio_db_pre = d_hk_over_b_hk_pre * alpha_Nmin
                                                d_i_pre = zs[i] * ratio_db_pre / (1.0 + ratio_db_pre)
                                                d_fracs_pre.append(max(d_i_pre, 0.0))

                                            # Underwood: multicomponent R_min via theta solve
                                            # Solve sum(alpha_i * z_i / (alpha_i - theta)) = 1 - q
                                            q = 1.0 - vf_feed  # feed quality (q=1 for saturated liquid)
                                            R_min = 1.0 / (alpha_lk_hk - 1.0)  # fallback (binary)
                                            try:
                                                # Bisection for theta in (1 + eps, alpha_lk_hk - eps)
                                                lo = 1.0 + 1e-6
                                                hi = alpha_lk_hk - 1e-6
                                                if hi > lo:
                                                    target = 1.0 - q
                                                    def _uw_func(theta: float) -> float:
                                                        return sum(alphas[i] * zs[i] / (alphas[i] - theta)
                                                                   for i in range(len(comp_names))) - target
                                                    fa = _uw_func(lo)
                                                    fb = _uw_func(hi)
                                                    if fa * fb < 0:
                                                        for _ in range(100):
                                                            mid = (lo + hi) / 2.0
                                                            fm = _uw_func(mid)
                                                            if abs(fm) < 1e-10 or (hi - lo) < 1e-12:
                                                                break
                                                            if fa * fm < 0:
                                                                hi = mid
                                                                fb = fm
                                                            else:
                                                                lo = mid
                                                                fa = fm
                                                        theta = (lo + hi) / 2.0
                                                        # R_min + 1 = sum(alpha_i * d_i / (alpha_i - theta))
                                                        d_total_pre = sum(d_fracs_pre) or 1e-12
                                                        R_min_plus_1 = sum(
                                                            alphas[i] * (d_fracs_pre[i] / d_total_pre) / (alphas[i] - theta)
                                                            for i in range(len(comp_names))
                                                        )
                                                        R_min = max(R_min_plus_1 - 1.0, 0.01)
                                            except Exception:
                                                pass  # keep binary fallback

                                            # Gilliland correlation
                                            R = reflux_ratio
                                            if R <= R_min:
                                                R = R_min * 1.2
                                                logs.append(f"WARNING: {name} R={reflux_ratio:.2f} ≤ R_min={R_min:.2f}, adjusting to {R:.2f}")
                                            X = (R - R_min) / (R + 1.0)
                                            Y = 0.75 * (1.0 - X ** 0.5668)
                                            N_eff = (N_min + Y) / (1.0 - Y) if Y < 1.0 else n_stages

                                            # Component recovery: d_i/b_i = (d_hk/b_hk) * alpha_i^N_eff
                                            d_hk_over_b_hk = (1 - hk_recovery) / hk_recovery
                                            d_fracs: list[float] = []
                                            b_fracs: list[float] = []
                                            for i in range(len(comp_names)):
                                                alpha_N = alphas[i] ** N_eff if N_eff < 200 else 1e6
                                                ratio_db = d_hk_over_b_hk * alpha_N
                                                d_i = zs[i] * ratio_db / (1.0 + ratio_db)
                                                b_i = zs[i] - d_i
                                                d_fracs.append(max(d_i, 0.0))
                                                b_fracs.append(max(b_i, 0.0))

                                            # Normalize
                                            d_total = sum(d_fracs) or 1e-12
                                            b_total = sum(b_fracs) or 1e-12
                                            distillate_comp = {comp_names[i]: d_fracs[i] / d_total for i in range(len(comp_names))}
                                            bottoms_comp = {comp_names[i]: b_fracs[i] / b_total for i in range(len(comp_names))}

                                            # Mass splits
                                            MWs = flash_feed["MWs"]
                                            mass_dist = sum(d_fracs[i] * MWs[i] for i in range(len(comp_names)))
                                            mass_bott = sum(b_fracs[i] * MWs[i] for i in range(len(comp_names)))
                                            mass_total = mass_dist + mass_bott
                                            frac_dist = mass_dist / mass_total if mass_total > 0 else 0.5
                                            frac_bott = 1.0 - frac_dist  # default: no side draws
                                            # Adjust distillate/bottoms fractions for side draws
                                            total_sd_frac = sum(sd["fraction"] for sd in side_draws_fug)
                                            if total_sd_frac > 0:
                                                remaining = max(1.0 - total_sd_frac, 0.05)
                                                frac_dist *= remaining
                                                frac_bott = remaining - frac_dist

                                            # Reboiler pressure: user-specified or auto (condenser P + column ΔP)
                                            P_reb_kpa = float(params.get("reboilerPressure", 0))
                                            P_bott = _kpa_to_pa(P_reb_kpa) if P_reb_kpa > 0 else P_cond + n_stages * 700.0  # ~0.7 kPa/tray
                                            d_names = list(distillate_comp.keys())
                                            d_zs = [float(v) for v in distillate_comp.values()]
                                            b_names = list(bottoms_comp.keys())
                                            b_zs = [float(v) for v in bottoms_comp.values()]

                                            # Try bubble point flash for distillate
                                            flash_dist = self._flash_tp(d_names, d_zs, T_feed - 20, P_cond, property_package)
                                            if flash_dist:
                                                T_dist = flash_dist["T"]
                                                # Try proper bubble point
                                                try:
                                                    flasher = flash_dist["flasher"]
                                                    state_bp = flasher.flash(VF=0, P=P_cond, zs=flash_dist["zs"])
                                                    T_dist = state_bp.T
                                                except Exception:
                                                    pass
                                            else:
                                                T_dist = T_feed - 20

                                            flash_bott = self._flash_tp(b_names, b_zs, T_feed + 20, P_bott, property_package)
                                            if flash_bott:
                                                T_bott = flash_bott["T"]
                                                try:
                                                    flasher = flash_bott["flasher"]
                                                    state_bp = flasher.flash(VF=0, P=P_bott, zs=flash_bott["zs"])
                                                    T_bott = state_bp.T
                                                except Exception:
                                                    pass
                                            else:
                                                T_bott = T_feed + 20

                                            # Enthalpies
                                            h_dist = 0.0
                                            h_bott = 0.0
                                            flash_d_out = self._flash_tp(d_names, d_zs, T_dist, P_cond, property_package)
                                            if flash_d_out and flash_d_out.get("MW_mix", 0) > 0:
                                                h_dist = flash_d_out["H"] / (flash_d_out["MW_mix"] / 1000.0)
                                            flash_b_out = self._flash_tp(b_names, b_zs, T_bott, P_bott, property_package)
                                            if flash_b_out and flash_b_out.get("MW_mix", 0) > 0:
                                                h_bott = flash_b_out["H"] / (flash_b_out["MW_mix"] / 1000.0)

                                            # Condenser/reboiler duties (with reflux ratio)
                                            # Re-flash feed at feed T/P for consistent enthalpy reference
                                            h_feed = inlet.get("enthalpy", 0.0)
                                            flash_feed_dist = self._flash_tp(comp_names, zs, T_feed, P_feed, property_package)
                                            if flash_feed_dist and flash_feed_dist.get("MW_mix", 0) > 0:
                                                h_feed = flash_feed_dist["H"] / (flash_feed_dist["MW_mix"] / 1000.0)
                                            D = mf * frac_dist  # distillate mass flow
                                            B = mf * frac_bott  # bottoms mass flow
                                            # C2: Get vapor enthalpy from dew-point flash at column P
                                            h_vap_dist = h_dist + _estimate_hvap(distillate_comp)  # fallback
                                            if flash_d_out and flash_d_out.get("flasher"):
                                                try:
                                                    state_dew = flash_d_out["flasher"].flash(VF=1, P=P_cond, zs=flash_d_out["zs"])
                                                    mw_d_kg = flash_d_out["MW_mix"] / 1000.0
                                                    if mw_d_kg > 0:
                                                        h_vap_dist = state_dew.H() / mw_d_kg
                                                except Exception:
                                                    pass  # keep _estimate_hvap fallback
                                            # M6: Partial condenser support
                                            condenser_type = str(params.get("condenserType", "total")).lower()

                                            # Auto-detect cryogenic/refrigerated distillation:
                                            # -40°C is the practical limit for single-stage propane
                                            # refrigeration.  Below that, partial condenser is standard
                                            # (demethanizers, deethanizers, cold-box columns).
                                            # Between -40°C and 0°C, warn the user — conventional CW
                                            # or air-cooled condensers cannot reach sub-zero temperatures.
                                            if condenser_type == "total" and T_dist < 233.15:  # -40°C in K
                                                condenser_type = "partial"
                                                logs.append(
                                                    f"WARNING: {name} distillate bubble point {_k_to_c(T_dist):.0f}°C — "
                                                    f"auto-switched to partial condenser (total condenser impractical below -40°C)"
                                                )
                                            elif condenser_type == "total" and T_dist < 273.15:  # 0°C in K
                                                logs.append(
                                                    f"WARNING: {name} total condenser produces distillate at "
                                                    f"{_k_to_c(T_dist):.0f}°C — consider condenserType='partial'"
                                                )

                                            dist_vf = 0.0
                                            if condenser_type == "partial":
                                                dist_vf = 1.0  # distillate exits as vapor
                                                # Re-flash at dew point for partial condenser
                                                if flash_d_out and flash_d_out.get("flasher"):
                                                    try:
                                                        state_dew_d = flash_d_out["flasher"].flash(VF=1, P=P_cond, zs=flash_d_out["zs"])
                                                        T_dist = state_dew_d.T
                                                        mw_d_kg = flash_d_out["MW_mix"] / 1000.0
                                                        if mw_d_kg > 0:
                                                            h_dist = state_dew_d.H() / mw_d_kg
                                                    except Exception:
                                                        pass
                                                eq_res["condenserType"] = "partial"
                                            else:
                                                eq_res["condenserType"] = "total"
                                                # Condenser subcooling (total condenser only) — apply before duty calc
                                                subcooling = float(params.get("condenserSubcooling", 0))
                                                if subcooling > 0:
                                                    if subcooling > 30:
                                                        logs.append(
                                                            f"WARNING: {name} subcooling {subcooling:.1f}°C is unusually high "
                                                            f"(typical: 5-15°C)"
                                                        )
                                                    T_dist -= subcooling  # subcooling in °C = ΔK
                                                    eq_res["condenserSubcooling"] = subcooling
                                                    # Re-flash distillate at subcooled temperature
                                                    flash_sc = self._flash_tp(d_names, d_zs, T_dist, P_cond, property_package)
                                                    if flash_sc and flash_sc.get("MW_mix", 0) > 0:
                                                        h_dist = flash_sc["H"] / (flash_sc["MW_mix"] / 1000.0)
                                                    logs.append(f"{name}: condenser subcooling {subcooling:.1f}°C applied")

                                            # Q_cond = V_top * (h_vap - h_dist), V_top = D * (R + 1)
                                            # h_dist now includes subcooling if applied
                                            Q_cond = D * (reflux_ratio + 1) * (h_vap_dist - h_dist) if flash_d_out else 0.0

                                            # Pump-around reduces condenser load (for sizing) but total
                                            # heat removal = Q_cond_effective + Q_PA for energy balance
                                            total_pa_duty = sum(pa["duty"] for pa in pump_arounds_fug)
                                            Q_cond_effective = Q_cond  # original condenser duty
                                            if total_pa_duty > 0:
                                                Q_cond_effective = max(Q_cond - total_pa_duty, 0.0)
                                                logs.append(
                                                    f"{name}: {len(pump_arounds_fug)} pump-around(s) removing "
                                                    f"{_w_to_kw(total_pa_duty):.1f} kW from condenser load"
                                                )

                                            # Condenser duty spec: user-provided non-zero overrides calculation
                                            cond_duty_spec = float(params.get("condenserDuty", 0))
                                            if cond_duty_spec > 0:
                                                Q_cond = cond_duty_spec * 1000.0  # kW → W
                                                Q_cond_effective = Q_cond
                                                logs.append(f"{name}: using specified condenser duty {cond_duty_spec:.1f} kW")

                                            # Pre-compute side draw enthalpies for energy balance
                                            total_sd_enthalpy_rate = 0.0  # W (mass_flow * specific_enthalpy)
                                            for sd in side_draws_fug:
                                                sd_mf_eb = mf * sd["fraction"]
                                                stage_frac_eb = sd["stage"] / max(N_eff, 1)
                                                sd_h_eb = h_dist + stage_frac_eb * (h_bott - h_dist)
                                                # Try flash for better enthalpy
                                                try:
                                                    sd_T_eb = T_dist + stage_frac_eb * (T_bott - T_dist)
                                                    sd_P_eb = P_cond + stage_frac_eb * (P_bott - P_cond)
                                                    sd_comp_eb: dict[str, float] = {}
                                                    for c in comp_names:
                                                        sd_comp_eb[c] = distillate_comp.get(c, 0) * (1 - stage_frac_eb) + bottoms_comp.get(c, 0) * stage_frac_eb
                                                    total_z_eb = sum(sd_comp_eb.values())
                                                    if total_z_eb > 0:
                                                        sd_comp_eb = {c: z / total_z_eb for c, z in sd_comp_eb.items()}
                                                    fl_sd_eb = self._flash_tp(list(sd_comp_eb.keys()), list(sd_comp_eb.values()), sd_T_eb, sd_P_eb, property_package)
                                                    if fl_sd_eb and fl_sd_eb.get("MW_mix", 0) > 0:
                                                        sd_h_eb = fl_sd_eb["H"] / (fl_sd_eb["MW_mix"] / 1000.0)
                                                except Exception:
                                                    pass
                                                total_sd_enthalpy_rate += sd_mf_eb * sd_h_eb

                                            # Q_reb from overall energy balance:
                                            # F*hF + Q_reb = D*hD + B*hB + sum(SD*h_SD) + Q_cond + sum(Q_PA)
                                            # Total heat removal from column = condenser + pump-arounds
                                            Q_total_removal = Q_cond_effective + total_pa_duty
                                            Q_reb = (D * h_dist + B * h_bott + total_sd_enthalpy_rate + Q_total_removal - mf * h_feed) if (flash_d_out or flash_b_out) else 0.0
                                            # Reboiler must add heat — enforce Q_reb >= 0
                                            if Q_reb < 0:
                                                logs.append(
                                                    f"WARNING: {name} computed Q_reb={_w_to_kw(Q_reb):.1f} kW (negative) "
                                                    f"— using hvap-based estimate"
                                                )
                                                Q_reb = B * _estimate_hvap(bottoms_comp)

                                            # Reboiler duty spec: user-provided non-zero overrides energy balance
                                            reb_duty_spec = float(params.get("reboilerDuty", 0))
                                            if reb_duty_spec > 0:
                                                Q_reb = reb_duty_spec * 1000.0  # kW → W
                                                logs.append(f"{name}: using specified reboiler duty {reb_duty_spec:.1f} kW")
                                            if cond_duty_spec > 0 and reb_duty_spec > 0:
                                                logs.append(
                                                    f"WARNING: {name} both condenser and reboiler duties specified — "
                                                    f"column energy balance may not close"
                                                )

                                            # LK purity in distillate
                                            lk_purity = distillate_comp.get(comp_names[lk_idx], 0.0)

                                            eq_res["numberOfStages"] = n_stages
                                            eq_res["refluxRatio"] = reflux_ratio
                                            eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)
                                            eq_res["N_min"] = round(N_min, 1)
                                            eq_res["R_min"] = round(R_min, 3)
                                            eq_res["N_eff"] = round(N_eff, 1)
                                            eq_res["lightKeyPurity"] = round(lk_purity * 100, 1)
                                            eq_res["lkRecovery"] = round(lk_recovery * 100, 2)
                                            eq_res["hkRecovery"] = round(hk_recovery * 100, 2)
                                            eq_res["lightKey"] = comp_names[lk_idx]
                                            eq_res["heavyKey"] = comp_names[hk_idx]
                                            eq_res["condenserDuty"] = round(_w_to_kw(Q_cond_effective), 1)
                                            eq_res["reboilerDuty"] = round(_w_to_kw(Q_reb), 1)
                                            eq_res["distillateTemperature"] = round(_k_to_c(T_dist), 1)
                                            eq_res["bottomsTemperature"] = round(_k_to_c(T_bott), 1)
                                            eq_res["reboilerPressure"] = round(_pa_to_kpa(P_bott), 3)
                                            eq_res["reboilerTemperature"] = round(_k_to_c(T_bott), 1)
                                            eq_res["reboilerType"] = str(params.get("reboilerType", "kettle"))

                                            outlets["out-1"] = {
                                                "temperature": T_dist,
                                                "pressure": P_cond,
                                                "mass_flow": mf * frac_dist,
                                                "vapor_fraction": dist_vf,
                                                "enthalpy": h_dist,
                                                "composition": distillate_comp,
                                            }
                                            outlets["out-2"] = {
                                                "temperature": T_bott,
                                                "pressure": P_bott,
                                                "mass_flow": mf * frac_bott,
                                                "vapor_fraction": 0.0,
                                                "enthalpy": h_bott,
                                                "composition": bottoms_comp,
                                            }

                                            # FUG side draw outlet streams
                                            for sd in side_draws_fug:
                                                stage_frac = sd["stage"] / max(N_eff, 1)  # 0=top, 1=bottom
                                                sd_comp: dict[str, float] = {}
                                                for c in comp_names:
                                                    sd_comp[c] = distillate_comp.get(c, 0) * (1 - stage_frac) + bottoms_comp.get(c, 0) * stage_frac
                                                total_z = sum(sd_comp.values())
                                                if total_z > 0:
                                                    sd_comp = {c: z / total_z for c, z in sd_comp.items()}
                                                sd_mf = mf * sd["fraction"]
                                                sd_T = T_dist + stage_frac * (T_bott - T_dist)
                                                sd_P = P_cond + stage_frac * (P_bott - P_cond)
                                                sd_h = h_dist + stage_frac * (h_bott - h_dist)  # linear enthalpy interpolation
                                                # Try flash for better enthalpy
                                                try:
                                                    sd_names = list(sd_comp.keys())
                                                    sd_zs_l = list(sd_comp.values())
                                                    fl_sd = self._flash_tp(sd_names, sd_zs_l, sd_T, sd_P, property_package)
                                                    if fl_sd and fl_sd.get("MW_mix", 0) > 0:
                                                        sd_h = fl_sd["H"] / (fl_sd["MW_mix"] / 1000.0)
                                                except Exception:
                                                    pass
                                                outlets[sd["port"]] = {
                                                    "temperature": sd_T,
                                                    "pressure": sd_P,
                                                    "mass_flow": sd_mf,
                                                    "vapor_fraction": 0.0 if sd["type"] == "liquid" else 1.0,
                                                    "enthalpy": sd_h,
                                                    "composition": sd_comp,
                                                }
                                                eq_res[f"sideDrawStage_{sd['idx']}"] = sd["stage"]
                                                eq_res[f"sideDrawFlow_{sd['idx']}"] = round(sd_mf, 4)
                                                eq_res[f"sideDrawType_{sd['idx']}"] = sd["type"]
                                                logs.append(f"{name}: Side draw {sd['idx']} at stage {sd['stage']} ({sd['type']}, {sd_mf:.3f} kg/s)")

                                            # Report pump-around results
                                            if pump_arounds_fug:
                                                eq_res["pumpArounds"] = len(pump_arounds_fug)
                                                for i, pa in enumerate(pump_arounds_fug):
                                                    eq_res[f"pumpAround{i+1}Duty"] = round(pa["duty"] / 1000, 1)  # W to kW
                                                    eq_res[f"pumpAround{i+1}DrawStage"] = pa["draw"]
                                                    eq_res[f"pumpAround{i+1}ReturnStage"] = pa["return"]

                                            fug_ok = True
                                            logs.append(
                                                f"{name}: FUG — N_min={N_min:.1f}, R_min={R_min:.3f}, N_eff={N_eff:.1f}, "
                                                f"LK purity={lk_purity:.1%}, T_dist={_k_to_c(T_dist):.1f}°C, T_bott={_k_to_c(T_bott):.1f}°C"
                                            )
                                except Exception as exc:
                                    logger.warning("Distillation FUG failed: %s, using boiling-point fallback", exc)
                                    logs.append(f"WARNING: {name} FUG method failed ({exc}), using boiling-point fallback")

                            # Phase 15 §2.3: Auto-select solver
                            # Default to "Auto" instead of "FUG"
                            # Auto: FUG for binary (exact), rigorous first for 3+ components
                            dist_method = str(params.get("method", "Auto")).upper()
                            if dist_method == "AUTO":
                                if len(comp_names) <= 2:
                                    dist_method = "FUG"  # FUG is exact for binary
                                else:
                                    dist_method = "RIGOROUS"  # Try rigorous first for multicomponent
                                    logs.append(f"{name}: Auto-selected rigorous solver for {len(comp_names)}-component system")

                            if dist_method == "RIGOROUS" and len(comp_names) >= 2 and _thermo_available:
                                try:
                                    # Compute primary feed molar flow from primary feed mass flow
                                    # Use primary inlet (not merged mf) to avoid double-counting with additional_feeds
                                    primary_mf = material_inlets[0].get("mass_flow", mf)
                                    primary_comp = material_inlets[0].get("composition", comp)
                                    primary_zs = [float(primary_comp.get(cn, 0.0)) for cn in comp_names]
                                    pzs_sum = sum(primary_zs) or 1.0
                                    primary_zs = [z / pzs_sum for z in primary_zs]
                                    feed_mw = sum(primary_zs[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))
                                    feed_molar_flow = primary_mf / (feed_mw / 1000.0) if feed_mw > 0 else 10.0
                                    df_ratio = float(params.get("distillateToFeedRatio", 0.5))
                                    # Total molar flow: sum per-feed molar flows using each feed's own MW
                                    total_molar = feed_molar_flow
                                    for extra_inlet in material_inlets[1:]:
                                        extra_mf_r = extra_inlet.get("mass_flow", 0)
                                        extra_comp_r = extra_inlet.get("composition", {})
                                        extra_zs_r = [float(extra_comp_r.get(cn, 0.0)) for cn in comp_names]
                                        ezs_sum_r = sum(extra_zs_r) or 1.0
                                        extra_zs_r = [z / ezs_sum_r for z in extra_zs_r]
                                        extra_mw_r = sum(extra_zs_r[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))
                                        if extra_mw_r > 0:
                                            total_molar += extra_mf_r / (extra_mw_r / 1000.0)
                                    dist_molar_rate = total_molar * df_ratio
                                    condenser_t = str(params.get("condenserType", "total")).lower()

                                    # Build additional feeds for multi-feed columns
                                    add_feeds_rig: list[dict] | None = None
                                    if len(material_inlets) > 1:
                                        add_feeds_rig = []
                                        for fi, extra_in in enumerate(material_inlets[1:], start=2):
                                            extra_comp = extra_in.get("composition", {})
                                            # Merge composition bases: use primary comp_names
                                            extra_zs_l = []
                                            for cn in comp_names:
                                                extra_zs_l.append(float(extra_comp.get(cn, 0.0)))
                                            zs_sum = sum(extra_zs_l) or 1.0
                                            extra_zs_norm = [z / zs_sum for z in extra_zs_l]
                                            extra_mf = extra_in["mass_flow"]
                                            # Use extra feed's own MW for molar flow conversion (not primary feed MW)
                                            extra_mw_rig = sum(extra_zs_norm[i] * _get_mw(comp_names[i]) for i in range(len(comp_names)))
                                            extra_molar = extra_mf / (extra_mw_rig / 1000.0) if extra_mw_rig > 0 else 1.0
                                            extra_stage = int(params.get(f"feed{fi}Stage", n_stages // 3))
                                            # Flash for enthalpy
                                            extra_H = None
                                            try:
                                                fl_extra = self._flash_tp(comp_names, extra_zs_norm, extra_in["temperature"], extra_in["pressure"], property_package)
                                                if fl_extra:
                                                    extra_H = fl_extra["H"]
                                            except Exception:
                                                pass
                                            add_feeds_rig.append({
                                                "stage": extra_stage,
                                                "flow": extra_molar,
                                                "zs": extra_zs_norm,
                                                "enthalpy": extra_H,
                                            })
                                        logs.append(f"{name}: Multi-feed column with {len(material_inlets)} feeds")

                                    # Build side draws (up to 3)
                                    side_draws_rig: list[dict] | None = None
                                    for sd_idx_r in range(1, 4):
                                        suffix_r = "" if sd_idx_r == 1 else str(sd_idx_r)
                                        sd_stage_r = params.get(f"sideDrawStage{suffix_r}")
                                        if sd_stage_r is not None and int(float(sd_stage_r)) > 0:
                                            sd_type_r = str(params.get(f"sideDrawType{suffix_r}", "liquid")).lower()
                                            sd_frac_r = float(params.get(f"sideDrawFlowFraction{suffix_r}", 0.1))
                                            if side_draws_rig is None:
                                                side_draws_rig = []
                                            side_draws_rig.append({
                                                "stage": int(float(sd_stage_r)),
                                                "type": sd_type_r,
                                                "flow_fraction": sd_frac_r,
                                            })
                                            logs.append(f"{name}: Side draw {sd_idx_r} at stage {int(float(sd_stage_r))} ({sd_type_r}, {sd_frac_r:.0%})")

                                    P_reb_kpa_rig = float(params.get("reboilerPressure", 0))
                                    P_bott_rig = _kpa_to_pa(P_reb_kpa_rig) if P_reb_kpa_rig > 0 else None

                                    rig_result = solve_rigorous_distillation(
                                        feed_comp_names=comp_names,
                                        feed_zs=zs,
                                        feed_T=T_feed,
                                        feed_P=P_feed,
                                        n_stages=n_stages,
                                        feed_stage=int(params.get("feedStage", n_stages // 2)),
                                        reflux_ratio=reflux_ratio,
                                        distillate_rate=dist_molar_rate,
                                        feed_flow=feed_molar_flow,
                                        pressure_top=P_cond,
                                        pressure_bottom=P_bott_rig,
                                        property_package=property_package,
                                        condenser_type=condenser_t,
                                        additional_feeds=add_feeds_rig,
                                        side_draws=side_draws_rig,
                                    )

                                    if rig_result.get("converged") or (rig_result.get("iterations", 0) > 0 and not rig_result.get("error")):
                                        # Use rigorous results
                                        rig_dist_comp = rig_result.get("distillate_comp", {})
                                        rig_bott_comp = rig_result.get("bottoms_comp", {})
                                        T_dist_r = rig_result.get("condenser_temperature", T_feed - 20)
                                        T_bott_r = rig_result.get("reboiler_temperature", T_feed + 20)
                                        Q_cond_r = rig_result.get("condenser_duty", 0.0)
                                        Q_reb_r = rig_result.get("reboiler_duty", 0.0)
                                        P_reb_kpa_r = float(params.get("reboilerPressure", 0))
                                        P_bott_r = _kpa_to_pa(P_reb_kpa_r) if P_reb_kpa_r > 0 else P_cond + n_stages * 700.0

                                        # Flash outlets for enthalpies
                                        d_zs_r = [float(v) for v in rig_dist_comp.values()]
                                        b_zs_r = [float(v) for v in rig_bott_comp.values()]
                                        h_dist_r = 0.0
                                        h_bott_r = 0.0
                                        flash_dr = self._flash_tp(comp_names, d_zs_r, T_dist_r, P_cond, property_package)
                                        if flash_dr and flash_dr.get("MW_mix", 0) > 0:
                                            h_dist_r = flash_dr["H"] / (flash_dr["MW_mix"] / 1000.0)
                                        flash_br = self._flash_tp(comp_names, b_zs_r, T_bott_r, P_bott_r, property_package)
                                        if flash_br and flash_br.get("MW_mix", 0) > 0:
                                            h_bott_r = flash_br["H"] / (flash_br["MW_mix"] / 1000.0)

                                        # Mass splits from molar flows × molecular weight
                                        MWs_r = [_get_mw(cn) for cn in comp_names]
                                        MW_d = sum(d_zs_r[i] * MWs_r[i] for i in range(len(comp_names)))
                                        MW_b = sum(b_zs_r[i] * MWs_r[i] for i in range(len(comp_names)))
                                        B_molar = feed_molar_flow - dist_molar_rate
                                        mass_d_raw = dist_molar_rate * (MW_d / 1000.0)  # kg/s
                                        mass_b_raw = B_molar * (MW_b / 1000.0)  # kg/s
                                        # Pre-compute side draw mass to subtract from D+B budget
                                        rig_side_draws_pre = rig_result.get("side_draws", [])
                                        sd_mass_total_r = 0.0
                                        for sd_res_pre in rig_side_draws_pre:
                                            sd_comp_pre = sd_res_pre.get("composition", {})
                                            sd_mol_pre = sd_res_pre.get("molar_flow", 0.0)
                                            sd_zs_pre = [float(sd_comp_pre.get(cn, 0.0)) for cn in comp_names]
                                            sd_mw_pre = sum(sd_zs_pre[i] * MWs_r[i] for i in range(len(comp_names)))
                                            sd_mass_total_r += sd_mol_pre * (sd_mw_pre / 1000.0)
                                        # Normalize: D + B + SD = mf (enforce mass conservation)
                                        mass_db_raw = mass_d_raw + mass_b_raw
                                        mf_available = mf - sd_mass_total_r  # mass available for D + B
                                        if mass_db_raw > 0 and mf_available > 0:
                                            scale = mf_available / mass_db_raw
                                            frac_d = (mass_d_raw * scale) / mf
                                            frac_b = (mass_b_raw * scale) / mf
                                        else:
                                            frac_d = 0.5 * (1.0 - sd_mass_total_r / mf if mf > 0 else 0.5)
                                            frac_b = frac_d

                                        dist_vf_r = 0.0
                                        if condenser_t == "partial":
                                            dist_vf_r = 1.0

                                        outlets["out-1"] = {
                                            "temperature": T_dist_r,
                                            "pressure": P_cond,
                                            "mass_flow": mf * frac_d,
                                            "vapor_fraction": dist_vf_r,
                                            "enthalpy": h_dist_r,
                                            "composition": rig_dist_comp,
                                        }
                                        outlets["out-2"] = {
                                            "temperature": T_bott_r,
                                            "pressure": P_bott_r,
                                            "mass_flow": mf * frac_b,
                                            "vapor_fraction": 0.0,
                                            "enthalpy": h_bott_r,
                                            "composition": rig_bott_comp,
                                        }

                                        eq_res["method"] = "Rigorous"
                                        eq_res["numberOfStages"] = n_stages
                                        eq_res["refluxRatio"] = reflux_ratio
                                        eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)
                                        eq_res["condenserDuty"] = round(_w_to_kw(abs(Q_cond_r)), 1)
                                        eq_res["reboilerDuty"] = round(_w_to_kw(abs(Q_reb_r)), 1)
                                        eq_res["distillateTemperature"] = round(_k_to_c(T_dist_r), 1)
                                        eq_res["bottomsTemperature"] = round(_k_to_c(T_bott_r), 1)
                                        eq_res["reboilerPressure"] = round(_pa_to_kpa(P_bott_r), 3)
                                        eq_res["reboilerTemperature"] = round(_k_to_c(T_bott_r), 1)
                                        eq_res["reboilerType"] = str(params.get("reboilerType", "kettle"))
                                        eq_res["converged"] = rig_result.get("converged", False)
                                        eq_res["iterations"] = rig_result.get("iterations", 0)
                                        eq_res["stage_profiles"] = rig_result.get("stage_profiles", [])
                                        eq_res["condenserType"] = condenser_t

                                        lk_r = comp_names[lk_idx] if lk_idx < len(comp_names) else comp_names[0]
                                        eq_res["lightKeyPurity"] = round(rig_dist_comp.get(lk_r, 0) * 100, 1)

                                        # Create side draw outlet streams
                                        rig_side_draws = rig_result.get("side_draws", [])
                                        for sd_idx, sd_res in enumerate(rig_side_draws):
                                            sd_comp = sd_res.get("composition", {})
                                            sd_molar = sd_res.get("molar_flow", 0.0)
                                            sd_T_k = sd_res.get("temperature", T_feed)
                                            sd_vf = sd_res.get("vapor_fraction", 0.0)
                                            sd_H = sd_res.get("enthalpy", 0.0)
                                            # Convert molar flow to mass flow
                                            sd_zs_l = [float(sd_comp.get(cn, 0.0)) for cn in comp_names]
                                            sd_mw = sum(sd_zs_l[i] * MWs_r[i] for i in range(len(comp_names)))
                                            sd_mass = sd_molar * (sd_mw / 1000.0)
                                            # Use P at the draw stage
                                            sd_stage_idx = sd_res.get("stage", n_stages // 2)
                                            sd_P = P_cond + sd_stage_idx * 1000.0
                                            port_id = f"out-{3 + sd_idx}"
                                            outlets[port_id] = {
                                                "temperature": sd_T_k,
                                                "pressure": sd_P,
                                                "mass_flow": sd_mass,
                                                "vapor_fraction": sd_vf,
                                                "enthalpy": sd_H,
                                                "composition": sd_comp,
                                            }
                                            eq_res[f"sideDrawStage_{sd_idx}"] = sd_res.get("stage")
                                            eq_res[f"sideDrawFlow_{sd_idx}"] = round(sd_mass, 4)
                                            eq_res[f"sideDrawType_{sd_idx}"] = sd_res.get("type")

                                        # Report pump-around results (rigorous path)
                                        if pump_arounds_fug:
                                            eq_res["pumpArounds"] = len(pump_arounds_fug)
                                            for i, pa in enumerate(pump_arounds_fug):
                                                eq_res[f"pumpAround{i+1}Duty"] = round(pa["duty"] / 1000, 1)
                                                eq_res[f"pumpAround{i+1}DrawStage"] = pa["draw"]
                                                eq_res[f"pumpAround{i+1}ReturnStage"] = pa["return"]

                                        if len(material_inlets) > 1:
                                            eq_res["feedCount"] = len(material_inlets)

                                        fug_ok = True
                                        logs.append(
                                            f"{name}: Rigorous MESH — {rig_result.get('iterations', 0)} iter, "
                                            f"converged={rig_result.get('converged')}, "
                                            f"T_dist={_k_to_c(T_dist_r):.1f}°C, T_bott={_k_to_c(T_bott_r):.1f}°C"
                                        )
                                    else:
                                        err_msg = rig_result.get("error", "did not converge")
                                        logs.append(f"WARNING: {name} Wang-Henke solver failed ({err_msg}), trying Naphtali-Sandholm backup")

                                        # Phase 15 §2.2: Naphtali-Sandholm backup solver
                                        try:
                                            from app.services.distillation_newton import solve_naphtali_sandholm
                                            ns_result = solve_naphtali_sandholm(
                                                feed_comp_names=comp_names,
                                                feed_zs=zs,
                                                feed_T=T_feed,
                                                feed_P=P_feed,
                                                n_stages=n_stages,
                                                feed_stage=int(params.get("feedStage", n_stages // 2)),
                                                reflux_ratio=reflux_ratio,
                                                distillate_rate=dist_molar_rate,
                                                feed_flow=feed_molar_flow,
                                                pressure_top=P_cond,
                                                pressure_bottom=P_bott_rig,
                                                property_package=property_package,
                                                condenser_type=condenser_t,
                                                additional_feeds=add_feeds_rig,
                                                side_draws=side_draws_rig,
                                            )
                                            if ns_result.get("converged") or (ns_result.get("iterations", 0) > 0 and not ns_result.get("error")):
                                                rig_result = ns_result
                                                logs.append(f"{name}: Naphtali-Sandholm backup converged in {ns_result.get('iterations', 0)} iterations")
                                                # Re-process results from backup solver
                                                # (handled by the same code path above)
                                            else:
                                                ns_err = ns_result.get("error", "did not converge")
                                                logs.append(f"WARNING: {name} Naphtali-Sandholm also failed ({ns_err}), using FUG results")
                                        except ImportError:
                                            logs.append(f"WARNING: {name} Naphtali-Sandholm solver not available, using FUG results")
                                        except Exception as ns_exc:
                                            logs.append(f"WARNING: {name} Naphtali-Sandholm error ({ns_exc}), using FUG results")
                                except Exception as exc:
                                    logger.warning("Rigorous distillation failed: %s", exc)
                                    logs.append(f"WARNING: {name} Rigorous solver error ({exc}), keeping FUG results")

                            # Boiling-point fallback (original method)
                            if not fug_ok:
                                comp_bp: list[tuple[str, float, float]] = []
                                for cname, cfrac in comp.items():
                                    bp = 373.15
                                    if _thermo_available:
                                        try:
                                            c, _ = ChemicalConstantsPackage.from_IDs([cname])
                                            bp = c.Tbs[0] if c.Tbs[0] else 373.15
                                        except Exception:
                                            pass
                                    elif _coolprop_available:
                                        try:
                                            bp = CP.PropsSI("T", "P", 101325, "Q", 0, cname)
                                        except Exception:
                                            pass
                                    comp_bp.append((cname, cfrac, bp))

                                comp_bp.sort(key=lambda x: x[2])
                                distillate_comp = {}
                                bottoms_comp = {}
                                half = max(1, len(comp_bp) // 2)
                                for i, (cname, cfrac, _bp) in enumerate(comp_bp):
                                    if i < half:
                                        distillate_comp[cname] = cfrac
                                    else:
                                        bottoms_comp[cname] = cfrac

                                dist_total = sum(distillate_comp.values()) or 1.0
                                bott_total = sum(bottoms_comp.values()) or 1.0
                                distillate_comp = {k: v / dist_total for k, v in distillate_comp.items()}
                                bottoms_comp = {k: v / bott_total for k, v in bottoms_comp.items()}

                                T_dist = T_feed - 20
                                T_bott = T_feed + 20

                                # Reboiler pressure for fallback path
                                P_reb_kpa_fb = float(params.get("reboilerPressure", 0))
                                P_bott_fb = _kpa_to_pa(P_reb_kpa_fb) if P_reb_kpa_fb > 0 else P_cond + n_stages * 700.0

                                # Flash outlets for real enthalpies (was enthalpy=0.0, cascading downstream)
                                h_dist_fb = 0.0
                                h_bott_fb = 0.0
                                d_names_fb = list(distillate_comp.keys())
                                d_zs_fb = list(distillate_comp.values())
                                b_names_fb = list(bottoms_comp.keys())
                                b_zs_fb = list(bottoms_comp.values())
                                flash_d_fb = self._flash_tp(d_names_fb, d_zs_fb, T_dist, P_cond, property_package)
                                if flash_d_fb and flash_d_fb.get("MW_mix", 0) > 0:
                                    h_dist_fb = flash_d_fb["H"] / (flash_d_fb["MW_mix"] / 1000.0)
                                flash_b_fb = self._flash_tp(b_names_fb, b_zs_fb, T_bott, P_bott_fb, property_package)
                                if flash_b_fb and flash_b_fb.get("MW_mix", 0) > 0:
                                    h_bott_fb = flash_b_fb["H"] / (flash_b_fb["MW_mix"] / 1000.0)

                                eq_res["numberOfStages"] = n_stages
                                eq_res["refluxRatio"] = reflux_ratio
                                eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)
                                eq_res["reboilerPressure"] = round(_pa_to_kpa(P_bott_fb), 3)
                                eq_res["reboilerType"] = str(params.get("reboilerType", "kettle"))

                                outlets["out-1"] = {
                                    "temperature": T_dist,
                                    "pressure": P_cond,
                                    "mass_flow": mf * 0.5,
                                    "vapor_fraction": 0.0,
                                    "enthalpy": h_dist_fb,
                                    "composition": distillate_comp,
                                }
                                outlets["out-2"] = {
                                    "temperature": T_bott,
                                    "pressure": P_bott_fb,
                                    "mass_flow": mf * 0.5,
                                    "vapor_fraction": 0.0,
                                    "enthalpy": h_bott_fb,
                                    "composition": bottoms_comp,
                                }
                                logs.append(f"{name}: {n_stages} stages, RR = {reflux_ratio:.1f} (boiling-point fallback)")

                        elif ntype == "CSTRReactor":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})

                            volume = float(params.get("volume", 10.0))
                            T_op_c = params.get("temperature")
                            P_op_kpa = params.get("pressure")
                            duty_kw = params.get("duty", 0)

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            # Residence time with real density (T2-02a)
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            rho = self._get_density(comp_names, zs, T_out, P_out, property_package)
                            vol_flow = mf / rho if rho > 0 else 0
                            tau = volume / vol_flow if vol_flow > 0 else float("inf")

                            eq_res["volume"] = volume
                            eq_res["residenceTime"] = round(tau, 1) if tau < 1e6 else "∞"
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            # Store inlet enthalpy for energy balance
                            h_in = inlet.get("enthalpy", 0.0)

                            # Arrhenius kinetics (applied before flash for correct outlet composition)
                            out_comp = dict(comp)
                            Ea_kj = float(params.get("activationEnergy", 0))
                            A_pre = float(params.get("preExpFactor", 0))
                            if Ea_kj > 0 and A_pre > 0:
                                R_gas = 8.314e-3  # kJ/(mol·K)
                                k_rate = A_pre * math.exp(-Ea_kj / (R_gas * T_out))
                                X_arr = tau * k_rate / (1 + tau * k_rate) if tau < 1e6 else 0.999
                                conversion_val = min(X_arr, 0.999)
                                eq_res["rateConstant"] = round(k_rate, 4)
                                eq_res["conversion"] = round(conversion_val * 100, 1)
                                logs.append(f"  CSTR Arrhenius: k={k_rate:.4g} 1/s, X={conversion_val:.4f}")

                                # H1: Apply conversion to outlet composition
                                key_reactant_param = params.get("keyReactant", "")
                                if key_reactant_param and key_reactant_param in out_comp:
                                    key_r = key_reactant_param
                                else:
                                    key_r = comp_names[0] if comp_names else ""
                                if key_r and key_r in out_comp:
                                    z_before = out_comp[key_r]
                                    consumed = z_before * conversion_val
                                    out_comp[key_r] = z_before - consumed
                                    out_comp["products"] = out_comp.get("products", 0.0) + consumed
                                    total_z = sum(out_comp.values())
                                    if total_z > 0:
                                        out_comp = {k: v / total_z for k, v in out_comp.items()}
                                    logs.append(f"  CSTR: {key_r} z={z_before:.4f} → {out_comp.get(key_r, 0):.4f}")

                            # Clean composition (remove pseudo-components) and flash for enthalpy/VF
                            clean_comp = _clean_composition(out_comp)
                            clean_names = list(clean_comp.keys())
                            clean_zs = [float(v) for v in clean_comp.values()]
                            flash_out = self._flash_tp(clean_names, clean_zs, T_out, P_out, property_package)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            outlet["composition"] = out_comp
                            # Flash for VF and duty estimation, then first-law enthalpy
                            outlet["vapor_fraction"] = flash_out.get("VF", 0.0) if flash_out else inlet.get("vapor_fraction", 0.0)
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg = flash_out["MW_mix"] / 1000.0
                                h_out_flash = flash_out["H"] / mw_kg
                                actual_duty_w = mf * (h_out_flash - h_in) if mf > 0 else 0.0
                            else:
                                actual_duty_w = mf * _estimate_cp(clean_comp) * (T_out - T_in) if mf > 0 else 0.0
                            # First-law enthalpy: guarantees energy balance
                            outlet["enthalpy"] = h_in + actual_duty_w / mf if mf > 0 else h_in
                            eq_res["duty"] = round(_w_to_kw(actual_duty_w), 3)

                            # Jacket heat transfer
                            jacket_UA = float(params.get("jacketUA", 0))
                            jacket_T_c = params.get("jacketTemp")
                            if jacket_UA > 0 and jacket_T_c is not None:
                                jacket_T = _c_to_k(float(jacket_T_c))
                                Q_jacket = jacket_UA * 1000 * (jacket_T - T_out)
                                eq_res["jacketDuty"] = round(Q_jacket / 1000, 2)
                                logs.append(f"  CSTR jacket: Q={Q_jacket / 1000:.1f} kW")

                            outlets["out-1"] = outlet
                            logs.append(f"{name}: V = {volume} m³, τ = {tau:.0f} s")

                        elif ntype == "PFRReactor":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})

                            length = float(params.get("length", 5.0))
                            diameter = float(params.get("diameter", 0.5))
                            T_op_c = params.get("temperature")
                            P_op_kpa = params.get("pressure")

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            volume = math.pi * (diameter / 2) ** 2 * length
                            # Real density from flash (T2-02a)
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            rho = self._get_density(comp_names, zs, T_out, P_out, property_package)
                            vol_flow = mf / rho if rho > 0 else 0
                            tau = volume / vol_flow if vol_flow > 0 else float("inf")

                            eq_res["volume"] = round(volume, 3)
                            eq_res["length"] = length
                            eq_res["diameter"] = diameter
                            eq_res["residenceTime"] = round(tau, 1) if tau < 1e6 else "∞"
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            # Store inlet enthalpy for energy balance
                            h_in = inlet.get("enthalpy", 0.0)

                            # Flash at inlet composition for viscosity (used by Ergun)
                            flash_pfr = self._flash_tp(comp_names, zs, T_out, P_out, property_package)

                            # PFR Ergun pressure drop
                            Ea_kj = float(params.get("activationEnergy", 0))
                            A_pre = float(params.get("preExpFactor", 0))
                            eps = float(params.get("voidFraction", params.get("bedVoidFraction", 0.4)))
                            d_p = float(params.get("particleDiameter", 0.003))
                            # Sanity check: d_p > 0.1 m likely means user passed mm instead of m
                            if d_p > 0.1:
                                logs.append(f"WARNING: {name} particleDiameter={d_p*1000:.0f} mm seems very large — did you mean {d_p/1000:.4f} m ({d_p:.1f} mm)?")
                                d_p = d_p / 1000.0  # Auto-correct: assume user passed mm

                            P_out_final = P_out  # Track final outlet pressure after Ergun
                            if d_p > 0 and eps > 0:
                                mu = 1e-5  # default gas viscosity Pa·s
                                if flash_pfr:
                                    if inlet.get("vapor_fraction", 0) > 0.5 and flash_pfr.get("mu_gas"):
                                        mu = flash_pfr["mu_gas"]
                                    elif flash_pfr.get("mu_liquid"):
                                        mu = flash_pfr["mu_liquid"]
                                A_cross = math.pi * (diameter / 2) ** 2
                                u_sup = mf / (rho * A_cross) if rho > 0 and A_cross > 0 else 1.0
                                term1 = 150 * mu * (1 - eps) ** 2 / (d_p ** 2 * eps ** 3)
                                term2 = 1.75 * rho * abs(u_sup) * (1 - eps) / (d_p * eps ** 3)
                                dPdz = (term1 + term2) * abs(u_sup)
                                dp_total = dPdz * length
                                # Cap at 80% of operating pressure to prevent vacuum blowthrough
                                dp_max = 0.8 * P_out
                                if dp_total > dp_max:
                                    logs.append(
                                        f"WARNING: {name} Ergun ΔP ({_pa_to_kpa(dp_total):.0f} kPa) exceeds 80% of "
                                        f"operating pressure ({_pa_to_kpa(P_out):.0f} kPa) — capped at "
                                        f"{_pa_to_kpa(dp_max):.0f} kPa. Check particle diameter "
                                        f"({d_p*1000:.1f} mm) and void fraction ({eps:.2f})."
                                    )
                                    dp_total = dp_max
                                P_out_final = max(P_out - dp_total, 10000.0)  # Floor: 10 kPa
                                eq_res["pressureDrop"] = round(_pa_to_kpa(dp_total), 2)
                                logs.append(f"  PFR Ergun ΔP = {_pa_to_kpa(dp_total):.1f} kPa")

                            # Arrhenius kinetics
                            out_comp = dict(comp)
                            reaction_order = float(params.get("reactionOrder", 1))
                            if Ea_kj > 0 and A_pre > 0:
                                R_gas = 8.314e-3
                                k_rate = A_pre * math.exp(-Ea_kj / (R_gas * T_out))
                                # Compute conversion based on reaction order
                                # C_A0 = initial concentration of key reactant (mol/m³)
                                key_r_tmp = params.get("keyReactant", "")
                                z_A0 = comp.get(key_r_tmp, 0) if key_r_tmp and key_r_tmp in comp else max(comp.values()) if comp else 0.5
                                C_A0 = (z_A0 * rho / (sum(comp.get(c, 0) * _get_mw(c) for c in comp) / 1000.0)) if rho > 0 and comp else 1.0
                                if reaction_order == 0:
                                    X_pfr = min(k_rate * tau / C_A0, 1.0) if C_A0 > 0 else 0.0
                                elif reaction_order == 1 or abs(reaction_order - 1.0) < 0.01:
                                    X_pfr = 1.0 - math.exp(-k_rate * tau) if tau < 1e6 else 0.999
                                elif reaction_order == 2 or abs(reaction_order - 2.0) < 0.01:
                                    X_pfr = k_rate * tau * C_A0 / (1 + k_rate * tau * C_A0)
                                else:
                                    # General nth-order PFR: X = 1 - (1 + (n-1)*k*tau*C_A0^(n-1))^(-1/(n-1))
                                    n_ord = reaction_order
                                    base = 1 + (n_ord - 1) * k_rate * tau * C_A0 ** (n_ord - 1)
                                    X_pfr = 1.0 - base ** (-1.0 / (n_ord - 1)) if base > 0 else 0.999
                                conversion_val = min(X_pfr, 0.999)
                                eq_res["conversion"] = round(conversion_val * 100, 1)
                                eq_res["rateConstant"] = round(k_rate, 4)
                                logs.append(f"  PFR Arrhenius: k={k_rate:.4g} 1/s, X={X_pfr:.4f}")

                                # H1: Apply conversion to outlet composition
                                key_reactant_param = params.get("keyReactant", "")
                                if key_reactant_param and key_reactant_param in out_comp:
                                    key_r = key_reactant_param
                                else:
                                    key_r = comp_names[0] if comp_names else ""
                                if key_r and key_r in out_comp:
                                    z_before = out_comp[key_r]
                                    consumed = z_before * conversion_val
                                    out_comp[key_r] = z_before - consumed
                                    out_comp["products"] = out_comp.get("products", 0.0) + consumed
                                    total_z = sum(out_comp.values())
                                    if total_z > 0:
                                        out_comp = {k: v / total_z for k, v in out_comp.items()}
                                    logs.append(f"  PFR: {key_r} z={z_before:.4f} → {out_comp.get(key_r, 0):.4f}")

                            # Clean composition (remove pseudo-components) and flash at final T/P for enthalpy/VF
                            clean_comp = _clean_composition(out_comp)
                            clean_names = list(clean_comp.keys())
                            clean_zs = [float(v) for v in clean_comp.values()]
                            flash_final = self._flash_tp(clean_names, clean_zs, T_out, P_out_final, property_package)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out_final
                            outlet["composition"] = out_comp
                            # Flash for VF and duty estimation, then first-law enthalpy
                            outlet["vapor_fraction"] = flash_final.get("VF", 0.0) if flash_final else inlet.get("vapor_fraction", 0.0)
                            if flash_final and flash_final.get("MW_mix", 0) > 0:
                                mw_kg = flash_final["MW_mix"] / 1000.0
                                h_out_flash = flash_final["H"] / mw_kg
                                actual_duty_w = mf * (h_out_flash - h_in) if mf > 0 else 0.0
                            else:
                                actual_duty_w = mf * _estimate_cp(clean_comp) * (T_out - T_in) if mf > 0 else 0.0
                            # First-law enthalpy: guarantees energy balance
                            outlet["enthalpy"] = h_in + actual_duty_w / mf if mf > 0 else h_in
                            eq_res["duty"] = round(_w_to_kw(actual_duty_w), 3)

                            outlets["out-1"] = outlet
                            logs.append(f"{name}: L = {length} m, D = {diameter} m, V = {volume:.2f} m³")

                        elif ntype == "ConversionReactor":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            in_comp = inlet.get("composition", {})
                            h_in = inlet.get("enthalpy", 0.0)

                            conversion = float(params.get("conversion", 80)) / 100.0
                            conversion = max(0.0, min(1.0, conversion))
                            T_op_c = params.get("temperature")
                            P_op_kpa = params.get("pressure")
                            duty_kw = params.get("duty", 0)

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            # Parse reactions array (T2-1: stoichiometric conversion)
                            reactions_json = params.get("reactions", "[]")
                            reactions: list[dict] = []
                            if reactions_json and reactions_json != "[]":
                                try:
                                    reactions = json.loads(reactions_json) if isinstance(reactions_json, str) else reactions_json
                                except Exception:
                                    pass

                            out_comp = dict(in_comp)
                            heat_of_reaction_w = 0.0  # Total heat of reaction in W

                            if reactions:
                                # Stoichiometric conversion with proper product formation
                                for rxn_idx, rxn in enumerate(reactions[:10]):
                                    reactant = rxn.get("reactant", "")
                                    conv_r = float(rxn.get("conversion", conversion))
                                    stoich_products = rxn.get("products", {})
                                    stoich_reactants = rxn.get("reactants", {})
                                    dH_rxn = float(rxn.get("heatOfReaction", 0))  # kJ/mol of key reactant

                                    if reactant not in out_comp or out_comp[reactant] <= 0:
                                        continue

                                    # Moles of key reactant consumed
                                    z_before = out_comp[reactant]
                                    consumed = z_before * conv_r
                                    out_comp[reactant] = max(0, z_before - consumed)

                                    # Consume other reactants per stoichiometry (with limiting reagent check)
                                    for r_name, r_coeff in stoich_reactants.items():
                                        if r_name != reactant and r_name in out_comp:
                                            max_consume = out_comp[r_name]
                                            actual_consume = min(consumed * float(r_coeff), max_consume)
                                            out_comp[r_name] = max(0, out_comp[r_name] - actual_consume)
                                            if actual_consume < consumed * float(r_coeff) - 1e-10:
                                                logs.append(f"WARNING: {name} reaction {rxn_idx+1}: insufficient {r_name} (limiting reagent)")

                                    # Produce products per stoichiometry
                                    for p_name, p_coeff in stoich_products.items():
                                        out_comp[p_name] = out_comp.get(p_name, 0) + consumed * float(p_coeff)

                                    # Heat of reaction (if specified): Q = n_consumed × ΔH_rxn
                                    if abs(dH_rxn) > 0 and mf > 0:
                                        mw_key = _get_mw(reactant)
                                        # consumed is in mole fraction; convert to mol/s
                                        mw_mix = sum(z * _get_mw(c) for c, z in in_comp.items())
                                        if mw_mix > 0:
                                            total_moles = mf / (mw_mix / 1000.0)  # mol/s
                                            n_consumed = consumed * total_moles  # mol/s of key reactant
                                            heat_of_reaction_w += n_consumed * dH_rxn * 1000.0  # W (kJ/mol → J/mol)

                                    logs.append(
                                        f"  Reaction {rxn_idx + 1}: {reactant} z={z_before:.4f}→{out_comp.get(reactant, 0):.4f}, "
                                        f"X={conv_r:.0%}, products: {list(stoich_products.keys())}"
                                    )

                                eq_res["reactionCount"] = len(reactions)
                            else:
                                # Legacy single-reaction mode (fallback to pseudo-component if no products defined)
                                if out_comp:
                                    key_reactant_param = params.get("keyReactant", "")
                                    if key_reactant_param and key_reactant_param in out_comp:
                                        key_reactant = key_reactant_param
                                    else:
                                        key_reactant = list(out_comp.keys())[0]
                                    z_before = out_comp[key_reactant]
                                    consumed = z_before * conversion
                                    out_comp[key_reactant] = z_before - consumed
                                    out_comp["products"] = out_comp.get("products", 0.0) + consumed
                                    logs.append(f"{name}: key reactant '{key_reactant}' z={z_before:.4f} → {out_comp.get(key_reactant, 0):.4f}")
                                    if consumed > 1e-6:
                                        logs.append(
                                            f"WARNING: {name} uses 'products' pseudo-component — define reactions with products "
                                            f"for stoichiometric conversion and heat of reaction."
                                        )

                            # Renormalize composition
                            total_z = sum(out_comp.values())
                            if total_z > 0:
                                out_comp = {k: v / total_z for k, v in out_comp.items()}

                            # Flash outlet for enthalpy (filter pseudo-components)
                            clean_comp = _clean_composition(out_comp)
                            out_comp_names = list(clean_comp.keys())
                            out_zs = [float(v) for v in clean_comp.values()]
                            flash_out = self._flash_tp(out_comp_names, out_zs, T_out, P_out, property_package)

                            eq_res["conversion"] = round(conversion * 100, 1)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            outlet["composition"] = out_comp
                            # Flash for VF and duty estimation, then first-law enthalpy
                            outlet["vapor_fraction"] = flash_out.get("VF", 0.0) if flash_out else inlet.get("vapor_fraction", 0.0)
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg = flash_out["MW_mix"] / 1000.0
                                h_out_flash = flash_out["H"] / mw_kg
                                actual_duty_w = mf * (h_out_flash - h_in) + heat_of_reaction_w + float(duty_kw) * 1000.0
                            else:
                                actual_duty_w = mf * _estimate_cp(clean_comp) * (T_out - T_in) + heat_of_reaction_w + float(duty_kw) * 1000.0
                            # First-law enthalpy: guarantees energy balance
                            outlet["enthalpy"] = h_in + actual_duty_w / mf if mf > 0 else h_in
                            eq_res["duty"] = round(_w_to_kw(actual_duty_w), 3)
                            if abs(heat_of_reaction_w) > 0:
                                eq_res["heatOfReaction_kW"] = round(_w_to_kw(heat_of_reaction_w), 3)

                            outlets["out-1"] = outlet
                            logs.append(f"{name}: X = {conversion:.0%}")

                        elif ntype == "EquilibriumReactor":
                            # Equilibrium reactor — solves for reaction extent xi
                            # where the reaction quotient Q equals Keq.
                            # Keq = exp(keqA - keqB / T)  (van't Hoff form)
                            # Q = product((n_i / n_total)^nu_i) for all species
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            in_comp = inlet.get("composition", {})

                            T_op_c = params.get("outletTemperature", params.get("temperature"))
                            P_op_kpa = params.get("pressure")
                            duty_kw = float(params.get("duty", 0))

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            # Parse stoichiometry JSON
                            stoich_json = params.get("stoichiometry", "{}")
                            stoich: dict[str, Any] = {}
                            try:
                                stoich = json.loads(stoich_json) if isinstance(stoich_json, str) else stoich_json
                            except Exception:
                                stoich = {}

                            stoich_reactants: dict[str, float] = {
                                k: float(v) for k, v in stoich.get("reactants", {}).items()
                            }
                            stoich_products: dict[str, float] = {
                                k: float(v) for k, v in stoich.get("products", {}).items()
                            }

                            # Build stoichiometric coefficient dict: nu_i
                            # Negative for reactants, positive for products
                            nu: dict[str, float] = {}
                            for sp, coeff in stoich_reactants.items():
                                nu[sp] = -abs(coeff)
                            for sp, coeff in stoich_products.items():
                                nu[sp] = abs(coeff)

                            # van't Hoff equilibrium constant
                            keqA = float(params.get("keqA", 0.0))
                            keqB = float(params.get("keqB", 0.0))
                            Keq = math.exp(keqA - keqB / T_out) if T_out > 0 else 1.0

                            # Compute initial moles from feed
                            mw_mix_in = sum(z * _get_mw(c) for c, z in in_comp.items())
                            if mw_mix_in <= 0:
                                mw_mix_in = 28.0  # fallback
                            total_moles_in = mf / (mw_mix_in / 1000.0)  # mol/s
                            n_initial: dict[str, float] = {}
                            for c, z in in_comp.items():
                                n_initial[c] = z * total_moles_in

                            # Ensure all species from stoichiometry exist
                            all_species = set(in_comp.keys()) | set(nu.keys())
                            for sp in all_species:
                                if sp not in n_initial:
                                    n_initial[sp] = 0.0

                            # Determine max extent (limited by limiting reactant)
                            max_extent = float("inf")
                            limiting_reactant = ""
                            for sp, coeff in nu.items():
                                if coeff < 0:  # reactant
                                    n_avail = n_initial.get(sp, 0.0)
                                    if abs(coeff) > 0:
                                        xi_max_sp = n_avail / abs(coeff)
                                        if xi_max_sp < max_extent:
                                            max_extent = xi_max_sp
                                            limiting_reactant = sp

                            if max_extent <= 0 or max_extent == float("inf"):
                                # No reactants present or stoichiometry empty
                                logs.append(f"WARNING: {name} — no valid reactants for equilibrium calculation")
                                max_extent = 0.0

                            # Bisection to find xi where Q(xi) = Keq
                            def reaction_quotient(xi: float) -> float:
                                """Compute Q / Keq - 1 for bisection root finding."""
                                n_total = 0.0
                                n_i: dict[str, float] = {}
                                for sp in all_species:
                                    n_sp = n_initial.get(sp, 0.0) + nu.get(sp, 0.0) * xi
                                    n_sp = max(n_sp, 1e-30)
                                    n_i[sp] = n_sp
                                    n_total += n_sp
                                if n_total <= 0:
                                    return -1.0

                                # Ky = product((n_i / n_total) ^ nu_i) for species with nu != 0
                                ln_Ky = 0.0
                                for sp, coeff in nu.items():
                                    if abs(coeff) > 1e-15:
                                        y_i = n_i.get(sp, 1e-30) / n_total
                                        y_i = max(y_i, 1e-30)
                                        ln_Ky += coeff * math.log(y_i)

                                # Kp = Ky * (P/P_ref)^delta_nu; solve Kp = Keq
                                delta_nu = sum(nu.values())  # net change in moles
                                P_ref = 101325.0
                                ln_Kp = ln_Ky + delta_nu * math.log(max(P_out / P_ref, 1e-30))
                                ln_Keq = math.log(max(Keq, 1e-30))
                                return ln_Kp - ln_Keq

                            xi_eq = 0.0
                            if max_extent > 0 and nu:
                                # Bisection between 0 and max_extent * 0.9999
                                lo = 0.0
                                hi = max_extent * 0.9999
                                f_lo = reaction_quotient(lo)
                                f_hi = reaction_quotient(hi)

                                if f_lo * f_hi < 0:
                                    # Standard bisection
                                    for _ in range(100):
                                        mid = (lo + hi) / 2.0
                                        f_mid = reaction_quotient(mid)
                                        if abs(f_mid) < 1e-10 or (hi - lo) < 1e-15:
                                            xi_eq = mid
                                            break
                                        if f_lo * f_mid < 0:
                                            hi = mid
                                            f_hi = f_mid
                                        else:
                                            lo = mid
                                            f_lo = f_mid
                                    else:
                                        xi_eq = (lo + hi) / 2.0
                                elif abs(f_lo) < 1e-8:
                                    xi_eq = 0.0  # Already at equilibrium
                                elif abs(f_hi) < 1e-8:
                                    xi_eq = hi
                                else:
                                    # Monotone sign — reaction goes to completion or not at all
                                    # Use whichever end is closer to zero
                                    xi_eq = hi if abs(f_hi) < abs(f_lo) else 0.0
                                    logs.append(
                                        f"WARNING: {name} — bisection did not bracket root "
                                        f"(f_lo={f_lo:.4g}, f_hi={f_hi:.4g}), using xi={xi_eq:.6g}"
                                    )

                            # Compute outlet moles at equilibrium extent
                            n_out: dict[str, float] = {}
                            for sp in all_species:
                                n_sp = n_initial.get(sp, 0.0) + nu.get(sp, 0.0) * xi_eq
                                n_sp = max(n_sp, 0.0)
                                n_out[sp] = n_sp
                            n_total_out = sum(n_out.values())

                            # Build outlet composition (mole fractions)
                            out_comp: dict[str, float] = {}
                            if n_total_out > 0:
                                for sp, n_sp in n_out.items():
                                    out_comp[sp] = n_sp / n_total_out
                            else:
                                out_comp = dict(in_comp)

                            # Compute conversion of limiting reactant
                            conversion_eq = 0.0
                            if limiting_reactant and n_initial.get(limiting_reactant, 0) > 0:
                                n_consumed = abs(nu.get(limiting_reactant, 0)) * xi_eq
                                conversion_eq = n_consumed / n_initial[limiting_reactant]
                                conversion_eq = min(conversion_eq, 1.0)

                            # Adiabatic / duty-specified temperature iteration
                            # When no T_out specified, re-solve equilibrium at each trial T
                            # because Keq(T) and thus composition change with temperature
                            user_specified_T = T_op_c is not None
                            if not user_specified_T:
                                h_in_eq = inlet.get("enthalpy", 0.0)
                                duty_w = duty_kw * 1000.0  # kW → W
                                T_lo_ad, T_hi_ad = max(T_in - 200, 273.15), T_in + 500
                                for _iter_ad in range(30):
                                    T_mid_ad = (T_lo_ad + T_hi_ad) / 2.0
                                    # Re-solve equilibrium at T_mid_ad
                                    Keq_mid = math.exp(keqA - keqB / T_mid_ad) if T_mid_ad > 0 else 1.0
                                    def rq_mid(xi_t: float) -> float:
                                        n_t = 0.0
                                        n_i_t: dict[str, float] = {}
                                        for sp_t in all_species:
                                            n_sp_t = n_initial.get(sp_t, 0.0) + nu.get(sp_t, 0.0) * xi_t
                                            n_sp_t = max(n_sp_t, 1e-30)
                                            n_i_t[sp_t] = n_sp_t
                                            n_t += n_sp_t
                                        if n_t <= 0:
                                            return -1.0
                                        ln_Ky_t = 0.0
                                        for sp_t, coeff_t in nu.items():
                                            if abs(coeff_t) > 1e-15:
                                                y_i_t = max(n_i_t.get(sp_t, 1e-30) / n_t, 1e-30)
                                                ln_Ky_t += coeff_t * math.log(y_i_t)
                                        delta_nu_t = sum(nu.values())
                                        ln_Kp_t = ln_Ky_t + delta_nu_t * math.log(max(P_out / 101325.0, 1e-30))
                                        return ln_Kp_t - math.log(max(Keq_mid, 1e-30))
                                    # Bisection for xi at this T
                                    xi_mid = 0.0
                                    if max_extent > 0 and nu:
                                        lo_x, hi_x = 0.0, max_extent * 0.9999
                                        f_lo_x = rq_mid(lo_x)
                                        f_hi_x = rq_mid(hi_x)
                                        if f_lo_x * f_hi_x < 0:
                                            for _ in range(60):
                                                mid_x = (lo_x + hi_x) / 2.0
                                                f_mid_x = rq_mid(mid_x)
                                                if abs(f_mid_x) < 1e-10 or (hi_x - lo_x) < 1e-15:
                                                    xi_mid = mid_x
                                                    break
                                                if f_lo_x * f_mid_x < 0:
                                                    hi_x = mid_x
                                                else:
                                                    lo_x = mid_x
                                                    f_lo_x = f_mid_x
                                            else:
                                                xi_mid = (lo_x + hi_x) / 2.0
                                        else:
                                            xi_mid = hi_x if abs(f_hi_x) < abs(f_lo_x) else 0.0
                                    # Build composition at this T
                                    n_out_mid: dict[str, float] = {}
                                    for sp_m in all_species:
                                        n_out_mid[sp_m] = max(n_initial.get(sp_m, 0.0) + nu.get(sp_m, 0.0) * xi_mid, 0.0)
                                    n_total_mid = sum(n_out_mid.values())
                                    comp_mid: dict[str, float] = {}
                                    if n_total_mid > 0:
                                        comp_mid = {sp_m: n_out_mid[sp_m] / n_total_mid for sp_m in n_out_mid}
                                    else:
                                        comp_mid = dict(in_comp)
                                    # Flash at T_mid for enthalpy
                                    clean_mid = _clean_composition(comp_mid)
                                    fl_mid = self._flash_tp(list(clean_mid.keys()), list(clean_mid.values()), T_mid_ad, P_out, property_package)
                                    if fl_mid and fl_mid.get("MW_mix", 0) > 0:
                                        mw_out_mid = sum(comp_mid.get(sp, 0) * _get_mw(sp) for sp in comp_mid)
                                        mf_out_mid = n_total_mid * (mw_out_mid / 1000.0) if mw_out_mid > 0 else mf
                                        h_out_mid = fl_mid["H"] / (fl_mid["MW_mix"] / 1000.0)
                                        energy_balance = mf_out_mid * h_out_mid - mf * h_in_eq - duty_w
                                        if energy_balance > 0:
                                            T_hi_ad = T_mid_ad
                                        else:
                                            T_lo_ad = T_mid_ad
                                    else:
                                        break
                                    if abs(T_hi_ad - T_lo_ad) < 0.1:
                                        break
                                T_out = (T_lo_ad + T_hi_ad) / 2.0
                                # Final equilibrium solve at converged T_out
                                Keq = math.exp(keqA - keqB / T_out) if T_out > 0 else 1.0
                                # Re-run the main bisection at final T_out
                                xi_eq = 0.0
                                if max_extent > 0 and nu:
                                    lo_f, hi_f = 0.0, max_extent * 0.9999
                                    f_lo_f = reaction_quotient(lo_f)
                                    f_hi_f = reaction_quotient(hi_f)
                                    if f_lo_f * f_hi_f < 0:
                                        for _ in range(100):
                                            mid_f = (lo_f + hi_f) / 2.0
                                            f_mid_f = reaction_quotient(mid_f)
                                            if abs(f_mid_f) < 1e-10 or (hi_f - lo_f) < 1e-15:
                                                xi_eq = mid_f
                                                break
                                            if f_lo_f * f_mid_f < 0:
                                                hi_f = mid_f
                                            else:
                                                lo_f = mid_f
                                                f_lo_f = f_mid_f
                                        else:
                                            xi_eq = (lo_f + hi_f) / 2.0
                                    else:
                                        xi_eq = hi_f if abs(f_hi_f) < abs(f_lo_f) else 0.0
                                # Rebuild outlet at final equilibrium
                                n_out = {}
                                for sp in all_species:
                                    n_out[sp] = max(n_initial.get(sp, 0.0) + nu.get(sp, 0.0) * xi_eq, 0.0)
                                n_total_out = sum(n_out.values())
                                out_comp = {}
                                if n_total_out > 0:
                                    out_comp = {sp: n_out[sp] / n_total_out for sp in n_out}
                                else:
                                    out_comp = dict(in_comp)
                                # Recompute conversion
                                if limiting_reactant and n_initial.get(limiting_reactant, 0) > 0:
                                    n_consumed = abs(nu.get(limiting_reactant, 0)) * xi_eq
                                    conversion_eq = min(n_consumed / n_initial[limiting_reactant], 1.0)
                                logs.append(f"  {name}: adiabatic T iteration → T_out={_k_to_c(T_out):.1f}°C, X={conversion_eq:.1%}")

                            # Compute outlet mass flow from molar balance
                            mw_out_mix = sum(out_comp.get(sp, 0) * _get_mw(sp) for sp in out_comp)
                            if mw_out_mix <= 0:
                                mw_out_mix = mw_mix_in
                            mf_out = n_total_out * (mw_out_mix / 1000.0)

                            # Flash outlet for real properties
                            clean_comp = _clean_composition(out_comp)
                            out_comp_names = list(clean_comp.keys())
                            out_zs = [float(v) for v in clean_comp.values()]
                            flash_out = self._flash_tp(out_comp_names, out_zs, T_out, P_out, property_package)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            outlet["mass_flow"] = mf_out
                            outlet["composition"] = out_comp
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg = flash_out["MW_mix"] / 1000.0
                                outlet["enthalpy"] = flash_out["H"] / mw_kg
                                outlet["vapor_fraction"] = flash_out.get("VF", 0.0)
                            else:
                                outlet["enthalpy"] = _estimate_cp(out_comp) * (T_out - _T_REF)

                            outlets["out-1"] = outlet

                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 2)
                            eq_res["Keq"] = round(Keq, 6)
                            eq_res["equilibriumExtent"] = round(xi_eq, 6)
                            eq_res["conversion"] = round(conversion_eq * 100, 1)
                            # Compute actual duty from energy balance
                            h_in_eq = inlet.get("enthalpy", 0.0)
                            h_out_eq = outlet.get("enthalpy", 0.0)
                            actual_duty_eq = mf_out * h_out_eq - mf * h_in_eq  # W
                            eq_res["duty"] = round(_w_to_kw(actual_duty_eq), 3)
                            eq_res["limitingReactant"] = limiting_reactant
                            eq_res["outletComposition"] = {
                                k: round(v, 6) for k, v in out_comp.items() if v > 1e-10
                            }
                            logs.append(
                                f"{name}: Keq={Keq:.4g}, xi={xi_eq:.4g} mol/s, "
                                f"X({limiting_reactant})={conversion_eq:.1%}"
                            )

                        elif ntype == "GibbsReactor":
                            # Gibbs free energy minimization reactor
                            # Minimizes G_total = sum(n_i * (Gf_i + R*T*ln(y_i * P/P_ref)))
                            # subject to element balance constraints
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            in_comp = inlet.get("composition", {})

                            T_op_c = params.get("outletTemperature", params.get("temperature"))
                            P_op_kpa = params.get("pressure")
                            duty_kw = float(params.get("duty", 0))

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            comp_names_g = list(in_comp.keys())
                            zs_g = [float(v) for v in in_comp.values()]

                            # Auto-expand species: Gibbs minimization needs at
                            # least as many species as element constraints.
                            # Infer elements from feed, then add common small-
                            # molecule products that can be formed from those
                            # elements (e.g. H2, CO, CO2 for C-H-O systems).
                            _GIBBS_CANDIDATES: dict[frozenset[str], list[str]] = {
                                frozenset({"C", "H", "O"}): ["hydrogen", "carbon monoxide", "carbon dioxide"],
                                frozenset({"C", "H"}): ["hydrogen"],
                                frozenset({"H", "O"}): ["hydrogen", "oxygen"],
                                frozenset({"C", "O"}): ["carbon monoxide", "carbon dioxide"],
                                frozenset({"N", "H"}): ["nitrogen", "hydrogen", "ammonia"],
                                frozenset({"N", "H", "O"}): ["nitrogen", "hydrogen", "ammonia", "nitric oxide"],
                                frozenset({"S", "H", "O"}): ["hydrogen", "sulfur dioxide"],
                            }
                            if _thermo_available:
                                try:
                                    _pre_const, _ = ChemicalConstantsPackage.from_IDs(comp_names_g)
                                    _feed_elements: set[str] = set()
                                    if _pre_const.atomss:
                                        for _ad in _pre_const.atomss:
                                            if _ad:
                                                _feed_elements.update(_ad.keys())
                                    # Try each candidate set that is a subset of feed elements
                                    _added_species: list[str] = []
                                    feed_lc = set(c.lower() for c in comp_names_g)
                                    for _el_key, _candidates in _GIBBS_CANDIDATES.items():
                                        if _el_key.issubset(_feed_elements):
                                            for _cand in _candidates:
                                                if _cand.lower() not in feed_lc:
                                                    comp_names_g.append(_cand)
                                                    zs_g.append(0.0)
                                                    feed_lc.add(_cand.lower())
                                                    _added_species.append(_cand)
                                    if _added_species:
                                        logs.append(
                                            f"  {name}: auto-added potential products: "
                                            f"{', '.join(_added_species)}"
                                        )
                                except Exception:
                                    pass  # proceed with original species

                            n_comps = len(comp_names_g)

                            # Compute initial moles from feed
                            mw_mix_in = sum(z * _get_mw(c) for c, z in in_comp.items())
                            if mw_mix_in <= 0:
                                mw_mix_in = 28.0
                            total_moles_in = mf / (mw_mix_in / 1000.0)  # mol/s
                            n0 = [zs_g[i] * total_moles_in for i in range(n_comps)]

                            R_gas = 8.314  # J/(mol*K)
                            P_ref = 101325.0  # 1 atm reference

                            # Get thermodynamic data from thermo library
                            Gf_list: list[float] = []  # Gibbs free energy of formation at T (J/mol)
                            atoms_list: list[dict[str, int]] = []  # element composition per compound

                            gibbs_from_thermo = False
                            if _thermo_available and n_comps > 0:
                                try:
                                    constants_g, _props_g = ChemicalConstantsPackage.from_IDs(comp_names_g)

                                    # Get formation properties
                                    Gfgs = constants_g.Gfgs   # J/mol at 298.15 K (standard Gibbs)
                                    Hfgs = constants_g.Hfgs   # J/mol at 298.15 K
                                    Sfgs = constants_g.Sfgs   # J/(mol*K) at 298.15 K

                                    # Get atomic composition
                                    atomss = constants_g.atomss  # list of dicts, e.g., [{'C': 1, 'H': 4}, ...]

                                    if atomss and (Gfgs or (Hfgs and Sfgs)):
                                        T_ref = 298.15
                                        for i in range(n_comps):
                                            # Prefer Gfgs (standard Gibbs at 298K) over Hf-T*Sf
                                            if Gfgs and Gfgs[i] is not None:
                                                gf_298 = Gfgs[i]
                                            elif Hfgs and Sfgs and Hfgs[i] is not None and Sfgs[i] is not None:
                                                gf_298 = Hfgs[i] - T_ref * Sfgs[i]
                                            else:
                                                gf_298 = 0.0
                                            # Temperature correction: Gf(T) ≈ Gf(298) + (Hf - Gf_298) * (1 - T/T_ref)
                                            # This is the Gibbs-Helmholtz approximation
                                            hf = Hfgs[i] if (Hfgs and Hfgs[i] is not None) else gf_298
                                            gf = gf_298 + (hf - gf_298) * (1.0 - T_out / T_ref)
                                            Gf_list.append(gf)
                                            atoms_list.append(atomss[i] if atomss[i] is not None else {})
                                        gibbs_from_thermo = True
                                except Exception as exc_thermo:
                                    logs.append(
                                        f"WARNING: {name} — thermo data retrieval failed: {exc_thermo}"
                                    )

                            if not gibbs_from_thermo:
                                # Fallback: treat as pass-through (no reaction)
                                logs.append(
                                    f"WARNING: {name} — Gibbs data unavailable, "
                                    f"passing through feed unchanged"
                                )
                                outlet = dict(inlet)
                                outlet["temperature"] = T_out
                                outlet["pressure"] = P_out
                                flash_pass = self._flash_tp(comp_names_g, zs_g, T_out, P_out, property_package)
                                if flash_pass and flash_pass.get("MW_mix", 0) > 0:
                                    mw_kg = flash_pass["MW_mix"] / 1000.0
                                    outlet["enthalpy"] = flash_pass["H"] / mw_kg
                                else:
                                    outlet["enthalpy"] = _estimate_cp(in_comp) * (T_out - _T_REF)
                                outlets["out-1"] = outlet
                                eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                                eq_res["duty"] = round(duty_kw, 3)
                                eq_res["warning"] = "Gibbs data unavailable — pass-through mode"
                            else:
                                # Build element balance matrix
                                # Collect all elements present
                                all_elements: set[str] = set()
                                for atoms_dict in atoms_list:
                                    all_elements.update(atoms_dict.keys())
                                elements = sorted(all_elements)
                                n_elements = len(elements)

                                # Element matrix A: A[j][i] = number of atoms of element j in compound i
                                A_mat = []
                                for el in elements:
                                    row = [float(atoms_list[i].get(el, 0)) for i in range(n_comps)]
                                    A_mat.append(row)

                                # Element totals from feed: b_j = sum(A[j][i] * n0[i])
                                b_vec = []
                                for j in range(n_elements):
                                    b_j = sum(A_mat[j][i] * n0[i] for i in range(n_comps))
                                    b_vec.append(b_j)

                                # Fugacity coefficients for high-pressure correction
                                lnphi = [0.0] * n_comps  # ideal gas default
                                if P_out > 500000:  # >5 bar — fugacity matters
                                    flash_fug = self._flash_tp(comp_names_g, zs_g, T_out, P_out, property_package)
                                    if flash_fug and flash_fug.get("lnphis_gas"):
                                        lnphi = flash_fug["lnphis_gas"]

                                # Objective: minimize G_total = sum(n_i * (Gf_i + R*T*(ln(y_i * P/P_ref) + lnphi_i)))
                                def gibbs_objective(n_vec: list[float]) -> float:
                                    n_total = sum(n_vec)
                                    if n_total <= 0:
                                        return 1e30
                                    G_total = 0.0
                                    for i in range(n_comps):
                                        ni = max(n_vec[i], 1e-30)
                                        yi = ni / n_total
                                        yi = max(yi, 1e-30)
                                        G_i = Gf_list[i] + R_gas * T_out * (math.log(yi * P_out / P_ref) + lnphi[i])
                                        G_total += ni * G_i
                                    return G_total

                                # Element balance constraints: sum(A[j][i] * n_i) - b_j = 0
                                constraints = []
                                for j in range(n_elements):
                                    def make_constraint(j_idx: int):
                                        def con_func(n_vec: list[float]) -> float:
                                            return sum(A_mat[j_idx][i] * n_vec[i] for i in range(n_comps)) - b_vec[j_idx]
                                        return con_func
                                    constraints.append({
                                        "type": "eq",
                                        "fun": make_constraint(j),
                                    })

                                # Analytical gradient: dG/dn_k = Gf_k + R*T*(ln(y_k * P/P_ref) + lnphi_k)
                                def gibbs_gradient(n_vec: list[float]) -> list[float]:
                                    n_total = sum(n_vec)
                                    if n_total <= 0:
                                        return [0.0] * n_comps
                                    grad = []
                                    for k in range(n_comps):
                                        nk = max(n_vec[k], 1e-30)
                                        yk = nk / n_total
                                        yk = max(yk, 1e-30)
                                        grad.append(Gf_list[k] + R_gas * T_out * (math.log(yk * P_out / P_ref) + lnphi[k]))
                                    return grad

                                # Bounds: n_i >= 1e-15 (avoid log(0))
                                bounds = [(1e-15, None) for _ in range(n_comps)]

                                # Initial guess: feed moles
                                n0_guess = [max(ni, 1e-12) for ni in n0]

                                try:
                                    from scipy.optimize import minimize as scipy_minimize

                                    result = scipy_minimize(
                                        gibbs_objective,
                                        n0_guess,
                                        method="SLSQP",
                                        jac=gibbs_gradient,
                                        bounds=bounds,
                                        constraints=constraints,
                                        options={"maxiter": 500, "ftol": 1e-12},
                                    )

                                    if result.success:
                                        n_opt = result.x
                                    else:
                                        logs.append(
                                            f"WARNING: {name} — Gibbs minimization did not converge: "
                                            f"{result.message}. Using best iterate."
                                        )
                                        n_opt = result.x
                                except Exception as exc_opt:
                                    logs.append(
                                        f"WARNING: {name} — scipy optimization failed: {exc_opt}. "
                                        f"Falling back to feed composition."
                                    )
                                    n_opt = n0_guess

                                # Build outlet composition
                                n_total_out = sum(n_opt)
                                out_comp_g: dict[str, float] = {}
                                if n_total_out > 0:
                                    for i in range(n_comps):
                                        y_i = n_opt[i] / n_total_out
                                        if y_i > 1e-12:
                                            out_comp_g[comp_names_g[i]] = y_i
                                else:
                                    out_comp_g = dict(in_comp)

                                # Renormalize
                                total_z = sum(out_comp_g.values())
                                if total_z > 0 and abs(total_z - 1.0) > 1e-9:
                                    out_comp_g = {k: v / total_z for k, v in out_comp_g.items()}

                                # Adiabatic / duty-specified temperature iteration
                                # Re-run Gibbs minimization at each trial T because
                                # Gf(T) and equilibrium composition change with temperature
                                user_specified_T_g = T_op_c is not None
                                if not user_specified_T_g:
                                    h_in_g_iter = inlet.get("enthalpy", 0.0)
                                    duty_w_g = duty_kw * 1000.0
                                    T_lo_g, T_hi_g = max(T_in - 200, 273.15), T_in + 500
                                    T_ref_g = 298.15
                                    for _iter_tg in range(20):
                                        T_mid_g = (T_lo_g + T_hi_g) / 2.0
                                        # Recompute Gf_list at T_mid_g
                                        Gf_mid_list: list[float] = []
                                        for i_g in range(n_comps):
                                            if Gfgs and Gfgs[i_g] is not None:
                                                gf_298_m = Gfgs[i_g]
                                            elif Hfgs and Sfgs and Hfgs[i_g] is not None and Sfgs[i_g] is not None:
                                                gf_298_m = Hfgs[i_g] - T_ref_g * Sfgs[i_g]
                                            else:
                                                gf_298_m = 0.0
                                            hf_m = Hfgs[i_g] if (Hfgs and Hfgs[i_g] is not None) else gf_298_m
                                            gf_m = gf_298_m + (hf_m - gf_298_m) * (1.0 - T_mid_g / T_ref_g)
                                            Gf_mid_list.append(gf_m)
                                        # Fugacity at T_mid_g for high-pressure correction
                                        lnphi_mid = [0.0] * n_comps
                                        if P_out > 500000:
                                            fl_fug_mid = self._flash_tp(comp_names_g, zs_g, T_mid_g, P_out, property_package)
                                            if fl_fug_mid and fl_fug_mid.get("lnphis_gas"):
                                                lnphi_mid = fl_fug_mid["lnphis_gas"]
                                        # Build objective and gradient at T_mid_g
                                        def gibbs_obj_mid(n_vec_m: list[float]) -> float:
                                            n_t_m = sum(n_vec_m)
                                            if n_t_m <= 0:
                                                return 1e30
                                            G_t = 0.0
                                            for i_m in range(n_comps):
                                                ni_m = max(n_vec_m[i_m], 1e-30)
                                                yi_m = max(ni_m / n_t_m, 1e-30)
                                                G_t += ni_m * (Gf_mid_list[i_m] + R_gas * T_mid_g * (math.log(yi_m * P_out / P_ref) + lnphi_mid[i_m]))
                                            return G_t
                                        def gibbs_grad_mid(n_vec_m: list[float]) -> list[float]:
                                            n_t_m = sum(n_vec_m)
                                            if n_t_m <= 0:
                                                return [0.0] * n_comps
                                            gr = []
                                            for k_m in range(n_comps):
                                                nk_m = max(n_vec_m[k_m], 1e-30)
                                                yk_m = max(nk_m / n_t_m, 1e-30)
                                                gr.append(Gf_mid_list[k_m] + R_gas * T_mid_g * (math.log(yk_m * P_out / P_ref) + lnphi_mid[k_m]))
                                            return gr
                                        try:
                                            res_mid = scipy_minimize(
                                                gibbs_obj_mid, n0_guess, method="SLSQP",
                                                jac=gibbs_grad_mid, bounds=bounds,
                                                constraints=constraints,
                                                options={"maxiter": 200, "ftol": 1e-10},
                                            )
                                            n_opt_mid = res_mid.x
                                        except Exception:
                                            n_opt_mid = n0_guess
                                        # Build composition at T_mid_g
                                        n_total_mid = sum(n_opt_mid)
                                        comp_mid_g: dict[str, float] = {}
                                        if n_total_mid > 0:
                                            for i_m in range(n_comps):
                                                y_m = n_opt_mid[i_m] / n_total_mid
                                                if y_m > 1e-12:
                                                    comp_mid_g[comp_names_g[i_m]] = y_m
                                        else:
                                            comp_mid_g = dict(in_comp)
                                        total_z_m = sum(comp_mid_g.values())
                                        if total_z_m > 0 and abs(total_z_m - 1.0) > 1e-9:
                                            comp_mid_g = {k: v / total_z_m for k, v in comp_mid_g.items()}
                                        # Flash for enthalpy at T_mid_g
                                        clean_mid_g = _clean_composition(comp_mid_g)
                                        fl_mid_g = self._flash_tp(list(clean_mid_g.keys()), list(clean_mid_g.values()), T_mid_g, P_out, property_package)
                                        if fl_mid_g and fl_mid_g.get("MW_mix", 0) > 0:
                                            mw_out_mid_g = sum(comp_mid_g.get(sp, 0) * _get_mw(sp) for sp in comp_mid_g)
                                            mf_out_mid_g = n_total_mid * (mw_out_mid_g / 1000.0) if mw_out_mid_g > 0 else mf
                                            h_out_mid_g = fl_mid_g["H"] / (fl_mid_g["MW_mix"] / 1000.0)
                                            eb_g = mf_out_mid_g * h_out_mid_g - mf * h_in_g_iter - duty_w_g
                                            if eb_g > 0:
                                                T_hi_g = T_mid_g
                                            else:
                                                T_lo_g = T_mid_g
                                        else:
                                            break
                                        if abs(T_hi_g - T_lo_g) < 0.1:
                                            break
                                    T_out = (T_lo_g + T_hi_g) / 2.0
                                    # Final Gibbs solve at converged T_out
                                    Gf_list_final: list[float] = []
                                    for i_g in range(n_comps):
                                        if Gfgs and Gfgs[i_g] is not None:
                                            gf_298_f = Gfgs[i_g]
                                        elif Hfgs and Sfgs and Hfgs[i_g] is not None and Sfgs[i_g] is not None:
                                            gf_298_f = Hfgs[i_g] - T_ref_g * Sfgs[i_g]
                                        else:
                                            gf_298_f = 0.0
                                        hf_f = Hfgs[i_g] if (Hfgs and Hfgs[i_g] is not None) else gf_298_f
                                        Gf_list_final.append(gf_298_f + (hf_f - gf_298_f) * (1.0 - T_out / T_ref_g))
                                    Gf_list = Gf_list_final  # Update for final objective eval
                                    # Fugacity at final T_out
                                    lnphi_final = [0.0] * n_comps
                                    if P_out > 500000:
                                        fl_fug_final = self._flash_tp(comp_names_g, zs_g, T_out, P_out, property_package)
                                        if fl_fug_final and fl_fug_final.get("lnphis_gas"):
                                            lnphi_final = fl_fug_final["lnphis_gas"]
                                    lnphi = lnphi_final  # Update outer scope for final G_in/G_out eval
                                    def gibbs_obj_final(n_vec_f: list[float]) -> float:
                                        n_t_f = sum(n_vec_f)
                                        if n_t_f <= 0:
                                            return 1e30
                                        G_t = 0.0
                                        for i_f in range(n_comps):
                                            ni_f = max(n_vec_f[i_f], 1e-30)
                                            yi_f = max(ni_f / n_t_f, 1e-30)
                                            G_t += ni_f * (Gf_list_final[i_f] + R_gas * T_out * (math.log(yi_f * P_out / P_ref) + lnphi_final[i_f]))
                                        return G_t
                                    def gibbs_grad_final(n_vec_f: list[float]) -> list[float]:
                                        n_t_f = sum(n_vec_f)
                                        if n_t_f <= 0:
                                            return [0.0] * n_comps
                                        gr = []
                                        for k_f in range(n_comps):
                                            nk_f = max(n_vec_f[k_f], 1e-30)
                                            yk_f = max(nk_f / n_t_f, 1e-30)
                                            gr.append(Gf_list_final[k_f] + R_gas * T_out * (math.log(yk_f * P_out / P_ref) + lnphi_final[k_f]))
                                        return gr
                                    try:
                                        result_final = scipy_minimize(
                                            gibbs_obj_final, n0_guess, method="SLSQP",
                                            jac=gibbs_grad_final, bounds=bounds,
                                            constraints=constraints,
                                            options={"maxiter": 500, "ftol": 1e-12},
                                        )
                                        n_opt = result_final.x
                                    except Exception:
                                        pass  # keep n_opt from original solve
                                    # Rebuild outlet composition
                                    n_total_out = sum(n_opt)
                                    out_comp_g = {}
                                    if n_total_out > 0:
                                        for i in range(n_comps):
                                            y_i = n_opt[i] / n_total_out
                                            if y_i > 1e-12:
                                                out_comp_g[comp_names_g[i]] = y_i
                                    else:
                                        out_comp_g = dict(in_comp)
                                    total_z = sum(out_comp_g.values())
                                    if total_z > 0 and abs(total_z - 1.0) > 1e-9:
                                        out_comp_g = {k: v / total_z for k, v in out_comp_g.items()}
                                    logs.append(f"  {name}: adiabatic T iteration → T_out={_k_to_c(T_out):.1f}°C")

                                # Compute outlet mass flow
                                mw_out_mix = sum(
                                    out_comp_g.get(sp, 0) * _get_mw(sp) for sp in out_comp_g
                                )
                                if mw_out_mix <= 0:
                                    mw_out_mix = mw_mix_in
                                mf_out = n_total_out * (mw_out_mix / 1000.0)

                                # Flash outlet for real properties
                                clean_comp_g = _clean_composition(out_comp_g)
                                out_comp_names_g = list(clean_comp_g.keys())
                                out_zs_g = [float(v) for v in clean_comp_g.values()]
                                flash_out = self._flash_tp(
                                    out_comp_names_g, out_zs_g, T_out, P_out, property_package
                                )

                                outlet = dict(inlet)
                                outlet["temperature"] = T_out
                                outlet["pressure"] = P_out
                                outlet["mass_flow"] = mf_out
                                outlet["composition"] = out_comp_g
                                if flash_out and flash_out.get("MW_mix", 0) > 0:
                                    mw_kg = flash_out["MW_mix"] / 1000.0
                                    outlet["enthalpy"] = flash_out["H"] / mw_kg
                                    outlet["vapor_fraction"] = flash_out.get("VF", 0.0)
                                else:
                                    outlet["enthalpy"] = _estimate_cp(out_comp_g) * (T_out - _T_REF)

                                if outlet.get("vapor_fraction", 1.0) < 0.99:
                                    logs.append(f"WARNING: {name} outlet is two-phase (VF={outlet['vapor_fraction']:.3f}) — "
                                                f"Gibbs minimization used gas-phase-only model, liquid formation not predicted")

                                outlets["out-1"] = outlet

                                # Compute total Gibbs energy change
                                G_in = gibbs_objective(n0_guess)
                                G_out = gibbs_objective(list(n_opt))
                                delta_G = G_out - G_in

                                eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                                eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 2)
                                # Compute actual duty from energy balance
                                h_in_g = inlet.get("enthalpy", 0.0)
                                h_out_g = outlet.get("enthalpy", 0.0)
                                actual_duty_g = mf_out * h_out_g - mf * h_in_g  # W
                                eq_res["duty"] = round(_w_to_kw(actual_duty_g), 3)
                                eq_res["deltaG_kW"] = round(delta_G / 1000.0, 3)
                                if total_moles_in > 0:
                                    eq_res["deltaG_kJ_per_mol"] = round(delta_G / total_moles_in / 1000.0, 3)
                                eq_res["outletComposition"] = {
                                    k: round(v, 6) for k, v in out_comp_g.items() if v > 1e-10
                                }
                                eq_res["elementBalance"] = {
                                    elements[j]: round(b_vec[j], 6) for j in range(n_elements)
                                }

                                logs.append(
                                    f"{name}: Gibbs minimization converged, "
                                    f"dG={delta_G / 1000:.2f} kJ/s, "
                                    f"{n_comps} species, {n_elements} elements"
                                )

                        elif ntype in ("Absorber", "Stripper"):
                            # Absorber: gas feed (in-1) + solvent (in-2) → lean gas (out-1) + rich solvent (out-2)
                            # Stripper: rich solvent (in-1) + stripping gas (in-2) → overhead gas (out-1) + lean solvent (out-2)
                            # Uses Kremser equation: N = ln[(y_in/y_out)(1 - 1/A) + 1/A] / ln(A)
                            # where A = L / (m * G), m = K-value of key component

                            # Match inlets by handle
                            feed1 = None  # gas (absorber) or rich solvent (stripper)
                            feed2 = None  # solvent (absorber) or stripping gas (stripper)
                            for i, handle in enumerate(inlet_handles):
                                if i < len(inlets):
                                    if handle == "in-1":
                                        feed1 = inlets[i]
                                    elif handle == "in-2":
                                        feed2 = inlets[i]
                            if feed1 is None and len(inlets) >= 1:
                                feed1 = inlets[0]
                            if feed2 is None and len(inlets) >= 2:
                                feed2 = inlets[1]
                            if feed1 is None:
                                feed1 = self._build_feed_from_params(params, property_package)
                            n_stages = int(params.get("numberOfStages", 10))
                            P_op_kpa = params.get("pressure")
                            P_op = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else feed1["pressure"]

                            mf1 = feed1["mass_flow"]

                            _reboiled_stripper = False
                            if feed2 is None:
                                if ntype == "Stripper":
                                    # Reboiled stripper: internal G generated from reboiler
                                    # This vapor comes FROM the liquid feed, not new mass
                                    _reboiled_stripper = True
                                    reboil_ratio = float(params.get("reboilRatio", 0.3))
                                    feed2 = dict(feed1)
                                    feed2["mass_flow"] = mf1 * reboil_ratio
                                    feed2["vapor_fraction"] = 1.0
                                    # Flash at reboiler temperature to get vapor composition for stripping gas
                                    reb_temp_c = params.get("reboilerTemperature")
                                    T_reb = (float(reb_temp_c) + 273.15) if reb_temp_c is not None else (feed1["temperature"] + 20.0)
                                    cn_reb = list(feed1.get("composition", {}).keys())
                                    zs_reb = [float(v) for v in feed1.get("composition", {}).values()]
                                    if cn_reb:
                                        flash_reb = self._flash_tp(cn_reb, zs_reb, T_reb, P_op, property_package)
                                        if flash_reb and flash_reb.get("VF", 0) > 0.01:
                                            gas_zs_reb = flash_reb.get("gas_zs", zs_reb)
                                            feed2["composition"] = {cn_reb[i]: gas_zs_reb[i] for i in range(len(cn_reb))}
                                            feed2["temperature"] = T_reb
                                    logs.append(f"{name}: reboiled stripper — estimated internal G = {reboil_ratio*100:.0f}% of feed ({feed2['mass_flow']:.1f} kg/s)")
                                else:
                                    feed2 = dict(_DEFAULT_FEED)
                                    feed2["mass_flow"] = 0.0
                                    logs.append(f"WARNING: {name} has no solvent feed — operating with zero solvent flow")
                            mf2 = feed2["mass_flow"]
                            comp1 = feed1.get("composition", {})
                            comp2 = feed2.get("composition", {})
                            T1 = feed1["temperature"]
                            T2 = feed2["temperature"]

                            # Flash both feeds for K-values
                            all_comps = set(comp1.keys()) | set(comp2.keys())
                            comp_names_all = sorted(all_comps)

                            # Build combined composition for K-value estimation
                            total_moles1 = mf1 / max(sum(z * _get_mw(c) for c, z in comp1.items()) / 1000.0, 1e-12)
                            total_moles2 = mf2 / max(sum(z * _get_mw(c) for c, z in comp2.items()) / 1000.0, 1e-12)
                            combined_zs: dict[str, float] = {}
                            for c in comp_names_all:
                                n1 = comp1.get(c, 0.0) * total_moles1
                                n2 = comp2.get(c, 0.0) * total_moles2
                                combined_zs[c] = n1 + n2
                            total_n = sum(combined_zs.values())
                            if total_n > 0:
                                combined_zs = {k: v / total_n for k, v in combined_zs.items()}

                            cn = list(combined_zs.keys())
                            zs_comb = list(combined_zs.values())
                            T_avg = (T1 + T2) / 2

                            # Get K-values from flash
                            K_vals: dict[str, float] = {}
                            flash_abs = self._flash_tp(cn, zs_comb, T_avg, P_op, property_package)
                            if flash_abs:
                                vf_abs = flash_abs.get("VF", 0.0)
                                if 0.001 < vf_abs < 0.999:
                                    # Two-phase result: K = y/x directly
                                    gas_zs_abs = flash_abs["gas_zs"]
                                    liq_zs_abs = flash_abs["liquid_zs"]
                                    for i, c in enumerate(cn):
                                        x_i = liq_zs_abs[i] if liq_zs_abs[i] > 1e-12 else 1e-12
                                        y_i = gas_zs_abs[i] if gas_zs_abs[i] > 1e-12 else 1e-12
                                        K_vals[c] = y_i / x_i
                                else:
                                    # Single-phase: bubble-point flash for equilibrium K-values
                                    bp_ok = False
                                    try:
                                        state_bp = flash_abs["flasher"].flash(VF=0, P=P_op, zs=flash_abs["zs"])
                                        gas_bp = getattr(state_bp, 'gas', None)
                                        liq_bp = getattr(state_bp, 'liquid0', None)
                                        if gas_bp and liq_bp:
                                            for i, c in enumerate(cn):
                                                x_i = liq_bp.zs[i] if liq_bp.zs[i] > 1e-12 else 1e-12
                                                y_i = gas_bp.zs[i] if gas_bp.zs[i] > 1e-12 else 1e-12
                                                K_vals[c] = y_i / x_i
                                            bp_ok = True
                                            logs.append(f"{name}: used bubble-point flash for K-values (combined feed VF={vf_abs:.3f})")
                                    except Exception as e_bp:
                                        logs.append(f"{name}: bubble-point flash failed ({e_bp}), using Wilson K")
                                    if not bp_ok:
                                        # Wilson K-value correlation fallback
                                        consts = flash_abs.get("constants")
                                        if consts and hasattr(consts, 'Tcs'):
                                            for i, c in enumerate(cn):
                                                Tc_i = consts.Tcs[i]
                                                Pc_i = consts.Pcs[i]
                                                omega_i = consts.omegas[i]
                                                K_vals[c] = (Pc_i / P_op) * math.exp(
                                                    5.37 * (1.0 + omega_i) * (1.0 - Tc_i / T_avg)
                                                )
                                            logs.append(f"{name}: used Wilson K-value correlation")
                                        else:
                                            for c in cn:
                                                mw = _get_mw(c)
                                                K_vals[c] = max(0.1, 5.0 - mw / 50.0)
                            else:
                                # Fallback: light components K>1, heavy K<1
                                for c in cn:
                                    mw = _get_mw(c)
                                    K_vals[c] = max(0.1, 5.0 - mw / 50.0)

                            # Detect reactive absorption: acid gas + amine solvent
                            # PR/SRK EOS gives physical VLE K-values that are 100-1000x too high
                            # for systems where chemical reaction drives absorption
                            acid_gases_present = {c for c in comp_names_all if c in _REACTIVE_K_EFF}
                            amines_present = {c for c in comp_names_all if c in _AMINE_SOLVENTS}
                            has_water = "water" in comp_names_all
                            if acid_gases_present and ntype in ("Absorber", "Stripper"):
                                # CO2/H2S require amine solvent; SO2/NH3 work with water alone
                                reactive_comps: set[str] = set()
                                for c in acid_gases_present:
                                    if c in _AQUEOUS_REACTIVE and has_water:
                                        reactive_comps.add(c)
                                    elif amines_present:
                                        reactive_comps.add(c)
                                if reactive_comps:
                                    R_gas = 8.314e-3  # kJ/(mol·K)
                                    for c in reactive_comps:
                                        K_ref, T_ref, dH = _REACTIVE_K_EFF[c]
                                        K_eff = K_ref * math.exp(-dH / R_gas * (1.0 / T_avg - 1.0 / T_ref))
                                        K_eff = max(K_eff, 1e-4)  # floor
                                        K_vals[c] = K_eff
                                    logs.append(
                                        f"{name}: reactive absorption detected — using effective K-values for "
                                        f"{', '.join(sorted(reactive_comps))} (chemical + physical equilibrium)"
                                    )

                            # C5: Kremser equation with consistent molar basis
                            # Absorber: feed1=gas (in-1), feed2=solvent (in-2)
                            # Stripper: feed1=rich solvent (in-1), feed2=stripping gas (in-2)
                            if ntype == "Absorber":
                                G = total_moles1  # gas molar flow (mol/s)
                                L = total_moles2  # liquid molar flow (mol/s)
                            else:  # Stripper
                                L = total_moles1  # rich solvent (liquid) molar flow
                                G = total_moles2  # stripping gas molar flow
                            # Track actual moles per component in each outlet
                            n_out1: dict[str, float] = {}  # lean gas / overhead (mol/s)
                            n_out2: dict[str, float] = {}  # rich solvent / lean solvent (mol/s)

                            for c in comp_names_all:
                                K = K_vals.get(c, 1.0)
                                m = K  # equilibrium ratio
                                if ntype == "Absorber":
                                    A = L / (m * G) if (m * G) > 1e-12 else 10.0
                                    n_gas_in_c = comp1.get(c, 0.0) * G
                                    n_liq_in_c = comp2.get(c, 0.0) * L
                                    if A > 1.001 and n_stages > 0 and n_gas_in_c > 1e-15:
                                        frac_absorbed = (A ** (n_stages + 1) - A) / (A ** (n_stages + 1) - 1)
                                        frac_absorbed = max(0.0, min(1.0, frac_absorbed))
                                    elif A > 0.999:
                                        frac_absorbed = n_stages / (n_stages + 1)
                                    else:
                                        frac_absorbed = 0.0
                                    n_out1[c] = n_gas_in_c * (1 - frac_absorbed)
                                    n_out2[c] = n_liq_in_c + n_gas_in_c * frac_absorbed
                                else:  # Stripper
                                    S = (m * G) / L if L > 1e-12 else 10.0
                                    n_liq_in_c = comp1.get(c, 0.0) * L
                                    n_gas_in_c = comp2.get(c, 0.0) * G
                                    if S > 1.001 and n_stages > 0 and n_liq_in_c > 1e-15:
                                        frac_stripped = (S ** (n_stages + 1) - S) / (S ** (n_stages + 1) - 1)
                                        frac_stripped = max(0.0, min(1.0, frac_stripped))
                                    elif S > 0.999:
                                        frac_stripped = n_stages / (n_stages + 1)
                                    else:
                                        frac_stripped = 0.0
                                    n_out1[c] = n_gas_in_c + n_liq_in_c * frac_stripped
                                    n_out2[c] = n_liq_in_c * (1 - frac_stripped)

                            # Compute mass flows from moles: mf = Σ(n_c * MW_c)
                            mf_out1 = 0.0
                            mf_out2 = 0.0
                            for c in comp_names_all:
                                mw_c = _get_mw(c) / 1000.0  # kg/mol
                                mf_out1 += n_out1.get(c, 0.0) * mw_c
                                mf_out2 += n_out2.get(c, 0.0) * mw_c
                            # Scale to enforce overall mass balance
                            # For reboiled strippers, the internal G comes from the feed itself
                            # (not new mass), so total_in = mf1 only
                            total_in = mf1 if _reboiled_stripper else mf1 + mf2
                            total_out = mf_out1 + mf_out2
                            if total_out > 1e-12:
                                scale = total_in / total_out
                                mf_out1 *= scale
                                mf_out2 *= scale
                            else:
                                mf_out1 = mf1 * 0.8
                                mf_out2 = total_in - mf_out1

                            # Normalize compositions from moles vectors
                            n1_total = sum(n_out1.values()) or 1e-12
                            n2_total = sum(n_out2.values()) or 1e-12
                            out1_comp = {k: v / n1_total for k, v in n_out1.items()}
                            out2_comp = {k: v / n2_total for k, v in n_out2.items()}

                            # Outlet temperatures with heat of absorption
                            if ntype == "Absorber":
                                T_out1 = T2 + 5.0  # Lean gas approaches solvent inlet temp in countercurrent
                                # Heat of absorption raises rich solvent temperature
                                Q_abs = 0.0  # kW
                                for c in comp_names_all:
                                    if c in _HEAT_OF_ABSORPTION:
                                        # Use actual moles: n_gas_in - n_out1 (not fraction * G which has wrong total)
                                        n_gas_in_c = comp1.get(c, 0.0) * G
                                        moles_absorbed = n_gas_in_c - n_out1.get(c, 0.0)
                                        Q_abs += moles_absorbed * _HEAT_OF_ABSORPTION[c]
                                Cp_solvent = 3500.0  # J/(kg·K), ~aqueous amine
                                delta_T = Q_abs * 1000.0 / (mf2 * Cp_solvent) if mf2 > 0.01 else 0.0
                                T_out2 = T_avg + min(delta_T, 60.0)  # cap at +60K
                            else:  # Stripper
                                # Overhead exits near cooler feed, bottoms near hotter feed
                                T_out1 = min(T1, T2)  # overhead gas near cooler temp
                                T_out2 = max(T1, T2)  # lean solvent near hotter feed
                                # Endothermic heat of desorption cools the bottoms
                                Q_strip = 0.0
                                for c in comp_names_all:
                                    if c in _HEAT_OF_ABSORPTION:
                                        # Moles stripped from liquid into gas (L is rich solvent flow for stripper)
                                        n_liq_in_c = comp1.get(c, 0.0) * L
                                        n_stripped = max(0, n_liq_in_c - n_out2.get(c, 0.0))
                                        Q_strip += n_stripped * _HEAT_OF_ABSORPTION[c]
                                if Q_strip > 0 and mf_out2 > 0.01:
                                    Cp_s = 3500.0  # J/(kg·K)
                                    dT_strip = Q_strip * 1000.0 / (mf_out2 * Cp_s)
                                    T_out2 = T_out2 - min(dT_strip, 40.0)  # endothermic cooling, cap 40K

                            # Phase 15 §3.3: Try stage-by-stage model for improved accuracy
                            stagewise_ok = False
                            if n_stages >= 3 and _thermo_available:
                                try:
                                    from app.services.absorber_stagewise import solve_absorber_stagewise
                                    # Build reactive K-values dict for the solver
                                    reactive_k = None
                                    if acid_gases_present:
                                        reactive_k = {}
                                        for c in acid_gases_present:
                                            if c in _REACTIVE_K_EFF:
                                                K_ref, T_ref_r, dH_r = _REACTIVE_K_EFF[c]
                                                reactive_k[c] = {"K_ref": K_ref, "T_ref": T_ref_r, "dH": dH_r}

                                    if ntype == "Absorber":
                                        gas_cn = list(comp1.keys())
                                        gas_zs_abs = [float(v) for v in comp1.values()]
                                        liq_cn = list(comp2.keys())
                                        liq_zs_abs = [float(v) for v in comp2.values()]
                                    else:
                                        liq_cn = list(comp1.keys())
                                        liq_zs_abs = [float(v) for v in comp1.values()]
                                        gas_cn = list(comp2.keys())
                                        gas_zs_abs = [float(v) for v in comp2.values()]

                                    solute_list = list(acid_gases_present) if acid_gases_present else []

                                    sw_result = solve_absorber_stagewise(
                                        gas_comp_names=gas_cn,
                                        gas_zs=gas_zs_abs,
                                        gas_T=T1 if ntype == "Absorber" else T2,
                                        gas_P=P_op,
                                        gas_flow=mf1 if ntype == "Absorber" else mf2,
                                        liquid_comp_names=liq_cn,
                                        liquid_zs=liq_zs_abs,
                                        liquid_T=T2 if ntype == "Absorber" else T1,
                                        liquid_P=P_op,
                                        liquid_flow=mf2 if ntype == "Absorber" else mf1,
                                        n_stages=n_stages,
                                        solutes=solute_list,
                                        property_package=property_package,
                                        reactive_k_eff=reactive_k,
                                    )

                                    if sw_result.get("converged"):
                                        # Use stagewise results
                                        out1_comp = sw_result.get("gas_out_comp", out1_comp)
                                        out2_comp = sw_result.get("liquid_out_comp", out2_comp)
                                        T_out1 = sw_result.get("gas_out_T", T_out1)
                                        T_out2 = sw_result.get("liquid_out_T", T_out2)
                                        # Recalculate mass flows from stagewise results
                                        removal_eff = sw_result.get("removal_efficiency", {})
                                        eq_res["removal_efficiency"] = removal_eff
                                        eq_res["stage_temperatures"] = sw_result.get("stage_temperatures", [])
                                        eq_res["solver"] = "stagewise"
                                        stagewise_ok = True
                                        logs.append(f"{name}: Stage-by-stage solver converged in {sw_result.get('iterations', 0)} iterations")
                                        for sol, eff_val in removal_eff.items():
                                            logs.append(f"  {sol} removal: {eff_val:.1f}%")
                                except ImportError:
                                    pass
                                except Exception as sw_exc:
                                    logger.debug("Absorber stagewise failed: %s — using Kremser", sw_exc)

                            if not stagewise_ok:
                                eq_res["solver"] = "kremser"

                            eq_res["numberOfStages"] = n_stages
                            eq_res["pressure"] = round(_pa_to_kpa(P_op), 3)

                            # Flash outlet streams for VF (H7)
                            flash_o1 = self._flash_tp(list(out1_comp.keys()), list(out1_comp.values()), T_out1, P_op, property_package)
                            flash_o2 = self._flash_tp(list(out2_comp.keys()), list(out2_comp.values()), T_out2, P_op, property_package)
                            h_o1 = flash_o1["H"] / (flash_o1["MW_mix"] / 1000.0) if flash_o1 and flash_o1.get("MW_mix", 0) > 0 else feed1.get("enthalpy", 0.0)
                            h_o2 = flash_o2["H"] / (flash_o2["MW_mix"] / 1000.0) if flash_o2 and flash_o2.get("MW_mix", 0) > 0 else feed2.get("enthalpy", 0.0)

                            # Compute actual duty from first law (H_out - H_in)
                            # so energy balance checker sees exact consistency
                            _h_in_total = mf1 * feed1.get("enthalpy", 0.0)
                            if not _reboiled_stripper and feed2 is not None:
                                _h_in_total += mf2 * feed2.get("enthalpy", 0.0)
                            _h_out_total = max(mf_out1, 1e-10) * h_o1 + max(mf_out2, 1e-10) * h_o2
                            _actual_duty_w = _h_out_total - _h_in_total
                            eq_res["duty"] = round(_w_to_kw(_actual_duty_w), 3)
                            # H7: VF from flash instead of hardcoded
                            vf_o1 = flash_o1.get("VF", 1.0 if ntype == "Absorber" else 0.5) if flash_o1 else (1.0 if ntype == "Absorber" else 0.5)
                            vf_o2 = flash_o2.get("VF", 0.0) if flash_o2 else 0.0

                            outlets["out-1"] = {
                                "temperature": T_out1,
                                "pressure": P_op,
                                "mass_flow": max(mf_out1, 1e-10),
                                "vapor_fraction": vf_o1,
                                "enthalpy": h_o1,
                                "composition": out1_comp,
                            }
                            outlets["out-2"] = {
                                "temperature": T_out2,
                                "pressure": P_op,
                                "mass_flow": max(mf_out2, 1e-10),
                                "vapor_fraction": vf_o2,
                                "enthalpy": h_o2,
                                "composition": out2_comp,
                            }
                            logs.append(f"{name}: {n_stages} stages, {ntype}")

                        elif ntype == "Cyclone":
                            # Cyclone separator: pressure drop device, splits gas from solids
                            # Shepherd-Lapple correlation: ΔP = K * ρ_gas * V_inlet² / 2
                            # K typically 6-8 for standard cyclone
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})

                            # Cyclone pressure drop
                            K_cyclone = float(params.get("pressureDropCoeff", 8.0))
                            inlet_diameter = float(params.get("inletDiameter", 0.3))  # m
                            efficiency = float(params.get("efficiency", 95)) / 100.0

                            # Gas density
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            rho_gas = self._get_density(comp_names, zs, T_in, P_in, property_package)

                            # Inlet velocity
                            A_inlet = math.pi * (inlet_diameter / 2) ** 2
                            V_inlet = mf / (rho_gas * A_inlet) if (rho_gas * A_inlet) > 0 else 10.0

                            # Pressure drop (Pa)
                            dp = K_cyclone * rho_gas * V_inlet ** 2 / 2.0
                            P_out = P_in - dp

                            # H5: Composition-aware split using solidsFraction parameter
                            solids_frac_cyc = float(params.get("solidsFraction", 0.05))
                            solids_frac_cyc = max(0.0, min(1.0, solids_frac_cyc))
                            gas_flow = mf * (1 - solids_frac_cyc * efficiency)
                            solids_flow = mf - gas_flow

                            # Composition: user-specified solids component or heaviest fallback
                            gas_comp_cyc = dict(comp)
                            solids_comp_cyc = dict(comp)
                            if comp and len(comp) >= 2:
                                solids_comp_name = params.get("solidsComponent", "")
                                if solids_comp_name and solids_comp_name in comp:
                                    heaviest_c = solids_comp_name
                                else:
                                    mws_cyc = [(c, _get_mw(c)) for c in comp.keys()]
                                    mws_cyc.sort(key=lambda x: x[1], reverse=True)
                                    heaviest_c = mws_cyc[0][0]
                                    if not solids_comp_name:
                                        logs.append(f"WARNING: {name} no solidsComponent specified — using heaviest component '{heaviest_c}' as solids proxy")
                                # Convert mole-fraction removal to mass-fraction basis for consistency
                                mw_heavy = _get_mw(heaviest_c)
                                mw_mix_cyc = sum(float(z) * _get_mw(c) for c, z in comp.items()) if comp else 1.0
                                mass_frac_heavy = (comp.get(heaviest_c, 0) * mw_heavy / mw_mix_cyc) if mw_mix_cyc > 0 else 0
                                # Fraction of heaviest component remaining in gas (mass basis -> mole basis)
                                gc = dict(comp)
                                if mass_frac_heavy > 0 and solids_frac_cyc > 0:
                                    removed_mass_frac = min(solids_frac_cyc * efficiency / mass_frac_heavy, 1.0)
                                    gc[heaviest_c] = max(0, comp.get(heaviest_c, 0) * (1 - removed_mass_frac))
                                else:
                                    gc[heaviest_c] = comp.get(heaviest_c, 0)
                                gt = sum(gc.values()) or 1
                                gas_comp_cyc = {k: v / gt for k, v in gc.items()}
                                # Solids outlet: enriched in solids component
                                solids_comp_cyc = {heaviest_c: 1.0}

                            eq_res["pressureDrop"] = round(_pa_to_kpa(dp), 3)
                            eq_res["inletVelocity"] = round(V_inlet, 2)
                            eq_res["efficiency"] = round(efficiency * 100, 1)
                            eq_res["solidsFraction"] = round(solids_frac_cyc, 4)

                            # Per-outlet enthalpy from flash at outlet composition
                            h_gas_cyc = inlet.get("enthalpy", 0.0)
                            h_sol_cyc = inlet.get("enthalpy", 0.0)
                            gc_names = list(gas_comp_cyc.keys())
                            gc_zs = list(gas_comp_cyc.values())
                            if gc_names and gas_flow > 0:
                                flash_gc = self._flash_tp(gc_names, gc_zs, T_in, P_out, property_package)
                                if flash_gc and flash_gc.get("MW_mix", 0) > 0:
                                    h_gas_cyc = flash_gc["H"] / (flash_gc["MW_mix"] / 1000.0)
                            sc_names = list(solids_comp_cyc.keys())
                            sc_zs = list(solids_comp_cyc.values())
                            if sc_names and solids_flow > 0:
                                flash_sc = self._flash_tp(sc_names, sc_zs, T_in, P_out, property_package)
                                if flash_sc and flash_sc.get("MW_mix", 0) > 0:
                                    h_sol_cyc = flash_sc["H"] / (flash_sc["MW_mix"] / 1000.0)

                            outlets["out-1"] = {
                                "temperature": T_in,
                                "pressure": P_out,
                                "mass_flow": gas_flow,
                                "vapor_fraction": 1.0,
                                "enthalpy": h_gas_cyc,
                                "composition": gas_comp_cyc,
                            }
                            outlets["out-2"] = {
                                "temperature": T_in,
                                "pressure": P_out,
                                "mass_flow": solids_flow,
                                "vapor_fraction": 0.0,
                                "enthalpy": h_sol_cyc,
                                "composition": solids_comp_cyc,
                            }
                            logs.append(f"{name}: ΔP = {_pa_to_kpa(dp):.1f} kPa, V_inlet = {V_inlet:.1f} m/s, solids={solids_frac_cyc:.1%}")

                        elif ntype == "ThreePhaseSeparator":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]

                            # --- Phase 17.7: Try rigorous VLLE flash first ---
                            vlle_result = None
                            if len(comp_names) >= 2:
                                vlle_result = flash_vlle(comp_names, T_in, P_in, zs)

                            VF = 0.0
                            vapor_comp = dict(comp)
                            liquid_comp = dict(comp)
                            flash_result = None
                            light_zs = dict(comp)
                            heavy_zs = dict(comp)
                            light_frac = 0.5
                            used_vlle = False

                            if vlle_result and vlle_result.get("status") == "success" and vlle_result.get("n_liquid_phases", 0) >= 2:
                                # Rigorous VLLE succeeded with two liquid phases
                                used_vlle = True
                                VF = vlle_result.get("VF", 0.0)
                                vapor_comp = vlle_result.get("vapor_comp", dict(comp))
                                light_zs = vlle_result.get("liquid1_comp", dict(comp))
                                heavy_zs = vlle_result.get("liquid2_comp", dict(comp))
                                betas = vlle_result.get("phase_fractions", [])

                                # Compute liquid fractions from phase betas
                                if len(betas) >= 3:
                                    # betas: [vapor, liquid1, liquid2]
                                    liq1_beta = betas[1]
                                    liq2_beta = betas[2]
                                    total_liq_beta = liq1_beta + liq2_beta
                                    light_frac = liq1_beta / total_liq_beta if total_liq_beta > 0 else 0.5
                                else:
                                    light_frac = 0.5

                                # Reconstruct overall liquid comp for mass split
                                liquid_comp = {}
                                for c in comp_names:
                                    liquid_comp[c] = light_zs.get(c, 0.0) * light_frac + heavy_zs.get(c, 0.0) * (1 - light_frac)
                                liq_sum = sum(liquid_comp.values())
                                if liq_sum > 0:
                                    liquid_comp = {c: v / liq_sum for c, v in liquid_comp.items()}

                                # Use VF for mass split (approximate: assume equal MW for simplicity)
                                mass_vap_frac = VF  # VLLE betas are molar; approximate
                                vapor_flow = mf * mass_vap_frac
                                liquid_flow = mf * (1 - mass_vap_frac)

                                logs.append(f"{name}: VLLE flash → {vlle_result['n_liquid_phases']} liquid phases, VF={VF:.3f}, light_frac={light_frac:.3f}")

                            else:
                                # Fallback: VLE flash + heuristic liquid split
                                if len(comp_names) >= 1:
                                    flash_result = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                                    if flash_result:
                                        VF = flash_result["VF"]
                                        vapor_comp = {comp_names[i]: flash_result["gas_zs"][i] for i in range(len(comp_names))}
                                        liquid_comp = {comp_names[i]: flash_result["liquid_zs"][i] for i in range(len(comp_names))}

                                # Mass-based vapor/liquid split
                                if flash_result and VF > 0 and VF < 1:
                                    MWs = flash_result["MWs"]
                                    MW_vap = sum(z * mw for z, mw in zip(flash_result["gas_zs"], MWs))
                                    MW_liq = sum(z * mw for z, mw in zip(flash_result["liquid_zs"], MWs))
                                    denom = VF * MW_vap + (1 - VF) * MW_liq
                                    mass_vap_frac = (VF * MW_vap) / denom if denom > 0 else VF
                                else:
                                    mass_vap_frac = VF  # 0 or 1

                                vapor_flow = mf * mass_vap_frac
                                liquid_flow = mf * (1 - mass_vap_frac)

                                # Heuristic liquid split (original code)
                                llf_override = params.get("lightLiquidFraction")
                                if llf_override is not None:
                                    light_frac = max(0.0, min(1.0, float(llf_override)))
                                else:
                                    light_frac = 0.5
                                if len(comp_names) >= 2 and liquid_flow > 0:
                                    liq_zs_list = [liquid_comp.get(c, 0.0) for c in comp_names]
                                    _AQUEOUS_COMPOUNDS_SET = {
                                        "water", "methanol", "ethanol", "1-propanol", "2-propanol",
                                        "acetic acid", "formic acid", "monoethanolamine", "diethanolamine",
                                        "ammonia", "formaldehyde", "triethylene glycol", "acetone",
                                    }
                                    organic_mass = 0.0
                                    aqueous_mass = 0.0
                                    lz, hz = {}, {}
                                    for c, z in zip(comp_names, liq_zs_list):
                                        if z < 1e-15:
                                            continue
                                        c_mass = z * _get_mw(c)
                                        if c.lower() in _AQUEOUS_COMPOUNDS_SET:
                                            aqueous_mass += c_mass
                                            hz[c] = z
                                        else:
                                            organic_mass += c_mass
                                            lz[c] = z
                                    l_sum = sum(lz.values())
                                    h_sum = sum(hz.values())
                                    if l_sum > 0:
                                        light_zs = {c: v / l_sum for c, v in lz.items()}
                                    if h_sum > 0:
                                        heavy_zs = {c: v / h_sum for c, v in hz.items()}
                                    if llf_override is None:
                                        if organic_mass + aqueous_mass > 1e-10:
                                            computed_llf = organic_mass / (organic_mass + aqueous_mass)
                                        else:
                                            computed_llf = 0.5
                                        light_frac = computed_llf
                                        logs.append(f"{name}: computed oil/water split = {computed_llf*100:.1f}% oil (heuristic)")

                            eq_res["vaporFraction"] = round(VF, 4)
                            eq_res["vaporFlow"] = round(vapor_flow, 4)
                            eq_res["lightLiquidFlow"] = round(liquid_flow * light_frac, 4)
                            eq_res["heavyLiquidFlow"] = round(liquid_flow * (1 - light_frac), 4)

                            # Per-phase enthalpy: vapor from _flash_tp result, liquids from separate flashes
                            h_vap_3p = inlet.get("enthalpy", 0.0)
                            h_liq_3p = inlet.get("enthalpy", 0.0)
                            h_light = h_liq_3p
                            h_heavy = h_liq_3p
                            if flash_result:
                                # Vapor enthalpy directly from flash result (no re-flash)
                                MWs_3p = flash_result["MWs"]
                                gas_zs_3p = flash_result["gas_zs"]
                                liq_zs_3p = flash_result["liquid_zs"]
                                MW_vap_3p = sum(z * mw for z, mw in zip(gas_zs_3p, MWs_3p))
                                MW_liq_3p = sum(z * mw for z, mw in zip(liq_zs_3p, MWs_3p))
                                H_gas_mol_3p = flash_result.get("H_gas")  # J/mol or None
                                H_liq_mol_3p = flash_result.get("H_liquid")  # J/mol or None
                                if H_gas_mol_3p is not None and MW_vap_3p > 0:
                                    h_vap_3p = H_gas_mol_3p / (MW_vap_3p / 1000.0)  # J/kg
                                if H_liq_mol_3p is not None and MW_liq_3p > 0:
                                    h_liq_3p = H_liq_mol_3p / (MW_liq_3p / 1000.0)  # J/kg
                                    h_light = h_liq_3p  # default if per-phase flash fails
                                    h_heavy = h_liq_3p

                                # Flash each liquid phase separately for correct per-phase enthalpy
                                try:
                                    light_names = list(light_zs.keys())
                                    light_vals = list(light_zs.values())
                                    if len(light_names) >= 1 and liquid_flow * light_frac > 1e-12:
                                        flash_light = self._flash_tp(light_names, light_vals, T_in, P_in, property_package)
                                        if flash_light and flash_light.get("MW_mix", 0) > 0:
                                            h_light = flash_light["H"] / (flash_light["MW_mix"] / 1000.0)
                                except Exception:
                                    pass
                                try:
                                    heavy_names = list(heavy_zs.keys())
                                    heavy_vals = list(heavy_zs.values())
                                    if len(heavy_names) >= 1 and liquid_flow * (1 - light_frac) > 1e-12:
                                        flash_heavy = self._flash_tp(heavy_names, heavy_vals, T_in, P_in, property_package)
                                        if flash_heavy and flash_heavy.get("MW_mix", 0) > 0:
                                            h_heavy = flash_heavy["H"] / (flash_heavy["MW_mix"] / 1000.0)
                                except Exception:
                                    pass

                            # Enforce energy balance: scale outlet enthalpies
                            h_in_3p = inlet.get("enthalpy", 0.0)
                            mf_light_3p = liquid_flow * light_frac
                            mf_heavy_3p = liquid_flow * (1 - light_frac)
                            total_out_3p = vapor_flow * h_vap_3p + mf_light_3p * h_light + mf_heavy_3p * h_heavy
                            total_in_3p = mf * h_in_3p
                            if abs(total_out_3p) > 1e-6:
                                eb_scale_3p = total_in_3p / total_out_3p
                                h_vap_3p *= eb_scale_3p
                                h_light *= eb_scale_3p
                                h_heavy *= eb_scale_3p

                            outlets["out-1"] = {"temperature": T_in, "pressure": P_in, "mass_flow": vapor_flow, "vapor_fraction": 1.0, "enthalpy": h_vap_3p, "composition": vapor_comp}
                            outlets["out-2"] = {"temperature": T_in, "pressure": P_in, "mass_flow": mf_light_3p, "vapor_fraction": 0.0, "enthalpy": h_light, "composition": light_zs}
                            outlets["out-3"] = {"temperature": T_in, "pressure": P_in, "mass_flow": mf_heavy_3p, "vapor_fraction": 0.0, "enthalpy": h_heavy, "composition": heavy_zs}
                            logs.append(f"{name}: VF={VF:.3f}, vapor={vapor_flow:.3f} kg/s, light_liq={liquid_flow * light_frac:.3f}, heavy_liq={liquid_flow * (1 - light_frac):.3f}")

                        elif ntype == "Crystallizer":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            cryst_temp = float(params.get("crystallizationTemp", 5))
                            T_cryst = _c_to_k(cryst_temp)
                            T_in_c = _k_to_c(T_in)

                            crystal_frac = 0.0
                            crystal_zs = dict(comp)
                            mother_zs = dict(comp)

                            if comp_names:
                                mws = [_get_mw(c) for c in comp_names]
                                key_idx = mws.index(max(mws))
                                key_comp = comp_names[key_idx]

                                # C4: Try solubility-based yield for known compounds
                                sol_in = _get_solubility(key_comp, T_in_c)
                                sol_out = _get_solubility(key_comp, cryst_temp)
                                # Pre-compute for CR1A/CR1C
                                mw_key_cr = _get_mw(key_comp)
                                mw_water_cr = _get_mw("water") if "water" in comp else 18.015
                                z_key_cr = zs[key_idx]
                                z_water_cr = float(comp.get("water", 0))
                                mass_key_cr = z_key_cr * mw_key_cr
                                mass_water_cr = z_water_cr * mw_water_cr

                                if sol_in is not None and sol_out is not None and sol_in > sol_out:
                                    # CR1A: Check actual feed concentration vs saturation
                                    if z_water_cr > 0 and mw_key_cr > 0:
                                        # Convert mole fractions to mass ratio (g solute / 100g water)
                                        feed_conc = (mass_key_cr / mass_water_cr) * 100 if mass_water_cr > 0 else 0
                                        # Can only crystallize amount above outlet solubility
                                        excess = max(0, feed_conc - sol_out)
                                        crystal_frac = min(0.95, excess / feed_conc) if feed_conc > 0 else 0
                                    else:
                                        crystal_frac = max(0.0, min(0.95, (sol_in - sol_out) / sol_in)) if sol_in > 0 else 0
                                    logs.append(f"  Crystallizer: solubility-based yield, sol@{T_in_c:.0f}°C={sol_in:.1f}, sol@{cryst_temp:.0f}°C={sol_out:.1f}")
                                else:
                                    # Empirical fallback
                                    delta_T = max(0, T_in - T_cryst)
                                    crystal_frac = min(0.9, delta_T / 200.0)
                                    if sol_in is None:
                                        logs.append(f"WARNING: {name} no solubility data for '{key_comp}' — using empirical ΔT/200 correlation")

                                # Convert mole fraction to mass fraction for mass flow calc
                                mw_mix_cryst = sum(z * _get_mw(c) for c, z in comp.items())
                                w_key = (zs[key_idx] * mw_key_cr / mw_mix_cryst) if mw_mix_cryst > 0 else zs[key_idx]
                                crystal_flow = mf * w_key * crystal_frac
                                mother_flow = mf - crystal_flow
                                crystal_zs = {key_comp: 1.0}
                                # CR1C: Mother liquor composition — convert mass-basis removal to mole-basis
                                m_zs = dict(comp)
                                if z_water_cr > 0 and mw_key_cr > 0:
                                    # Remaining solute mass fraction after crystallization
                                    remaining_mass = mass_key_cr * (1 - crystal_frac)
                                    # Convert back to mole fraction
                                    remaining_moles = remaining_mass / mw_key_cr
                                    water_moles = mass_water_cr / mw_water_cr
                                    other_moles = sum(float(z) for c, z in comp.items() if c != key_comp and c != "water")
                                    total_moles = remaining_moles + water_moles + other_moles
                                    if total_moles > 0:
                                        m_zs[key_comp] = remaining_moles / total_moles
                                        m_zs["water"] = water_moles / total_moles
                                        for c in comp:
                                            if c != key_comp and c != "water":
                                                m_zs[c] = float(comp[c]) / total_moles
                                else:
                                    m_zs[key_comp] = zs[key_idx] * (1 - crystal_frac)
                                mt = sum(m_zs.values()) or 1
                                mother_zs = {c: v / mt for c, v in m_zs.items()}
                            else:
                                crystal_flow = 0.0
                                mother_flow = mf

                            eq_res["crystalYield"] = round(crystal_frac * 100, 1)
                            eq_res["crystallizationTemp"] = cryst_temp

                            # Flash outlets for real enthalpies at crystallization T
                            h_cryst_1 = inlet.get("enthalpy", 0.0)
                            h_cryst_2 = inlet.get("enthalpy", 0.0)
                            if crystal_zs:
                                fl_cr1 = self._flash_tp(list(crystal_zs.keys()), list(crystal_zs.values()), T_cryst, P_in, property_package)
                                if fl_cr1 and fl_cr1.get("MW_mix", 0) > 0:
                                    h_cryst_1 = fl_cr1["H"] / (fl_cr1["MW_mix"] / 1000.0)
                            if mother_zs:
                                fl_cr2 = self._flash_tp(list(mother_zs.keys()), list(mother_zs.values()), T_cryst, P_in, property_package)
                                if fl_cr2 and fl_cr2.get("MW_mix", 0) > 0:
                                    h_cryst_2 = fl_cr2["H"] / (fl_cr2["MW_mix"] / 1000.0)

                            outlets["out-1"] = {"temperature": T_cryst, "pressure": P_in, "mass_flow": crystal_flow, "vapor_fraction": 0.0, "enthalpy": h_cryst_1, "composition": crystal_zs}
                            outlets["out-2"] = {"temperature": T_cryst, "pressure": P_in, "mass_flow": mother_flow, "vapor_fraction": 0.0, "enthalpy": h_cryst_2, "composition": mother_zs}
                            logs.append(f"{name}: crystallization at {cryst_temp}°C, yield={crystal_frac * 100:.1f}%")

                        elif ntype == "Dryer":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            target_moisture = float(params.get("outletMoisture", 5)) / 100.0

                            water_keys = [c for c in comp if c.lower() in ("water", "h2o")]
                            if water_keys:
                                wk = water_keys[0]
                                water_mol_frac = float(comp.get(wk, 0))
                                # C3: Convert mole fraction to mass fraction before computing removal
                                mw_water = _get_mw(wk)
                                mw_mix = sum(float(z) * _get_mw(c) for c, z in comp.items())
                                water_mass_frac = (water_mol_frac * mw_water / mw_mix) if mw_mix > 0 else water_mol_frac
                                water_removed = max(0, water_mass_frac - target_moisture)
                                moisture_flow = mf * water_removed
                                dry_flow = mf - moisture_flow
                                # Convert target moisture (mass frac) back to mole fraction
                                # for consistent composition basis
                                # target_moisture is mass fraction of water in dry product
                                # Other components have mass fraction = (1 - target_moisture) * (their mass share of non-water)
                                non_water_comps = {c: float(z) for c, z in comp.items() if c != wk}
                                non_water_mw = sum(z * _get_mw(c) for c, z in non_water_comps.items())
                                if non_water_mw > 0 and mw_water > 0 and target_moisture < 1.0:
                                    # Mass fractions → mole fractions
                                    # w_water = target_moisture, w_other = (1 - target_moisture) * z_i*MW_i / non_water_mw
                                    # n_water = target_moisture / MW_water
                                    # n_i = (1 - target_moisture) * z_i * MW_i / (non_water_mw * MW_i) = (1 - target_moisture) * z_i / non_water_mw
                                    n_water = target_moisture / mw_water
                                    dry_zs = {}
                                    for c, z in non_water_comps.items():
                                        mw_c = _get_mw(c)
                                        mass_frac_c = (1 - target_moisture) * (float(z) * mw_c) / non_water_mw if non_water_mw > 0 else 0
                                        dry_zs[c] = mass_frac_c / mw_c if mw_c > 0 else 0
                                    dry_zs[wk] = n_water
                                    dt = sum(dry_zs.values()) or 1
                                    dry_zs = {c: v / dt for c, v in dry_zs.items()}
                                else:
                                    dry_zs = dict(comp)
                                    dry_zs[wk] = 0.0
                                    dt = sum(dry_zs.values()) or 1
                                    dry_zs = {c: v / dt for c, v in dry_zs.items()}
                                vapor_zs = {wk: 1.0}
                                hvap = 2260000.0
                                calc_duty = moisture_flow * hvap
                                eq_res["duty"] = round(calc_duty / 1000, 2)
                            else:
                                dry_flow = mf
                                moisture_flow = 0.0
                                dry_zs = dict(comp)
                                vapor_zs = {"water": 1.0}
                                eq_res["duty"] = 0

                            eq_res["outletMoisture"] = float(params.get("outletMoisture", 5))
                            eq_res["waterRemoved"] = round(moisture_flow, 4)

                            # Flash outlets for real enthalpies
                            h_dry = inlet.get("enthalpy", 0.0)
                            h_vap = inlet.get("enthalpy", 0.0)
                            if dry_zs and dry_flow > 0:
                                fl_dry = self._flash_tp(list(dry_zs.keys()), list(dry_zs.values()), T_in, P_in, property_package)
                                if fl_dry and fl_dry.get("MW_mix", 0) > 0:
                                    h_dry = fl_dry["H"] / (fl_dry["MW_mix"] / 1000.0)
                            if vapor_zs and moisture_flow > 0:
                                fl_vap = self._flash_tp(list(vapor_zs.keys()), list(vapor_zs.values()), T_in, P_in, property_package)
                                if fl_vap and fl_vap.get("MW_mix", 0) > 0:
                                    h_vap = fl_vap["H"] / (fl_vap["MW_mix"] / 1000.0)
                            outlets["out-1"] = {"temperature": T_in, "pressure": P_in, "mass_flow": dry_flow, "vapor_fraction": 0.0, "enthalpy": h_dry, "composition": dry_zs}
                            outlets["out-2"] = {"temperature": T_in, "pressure": P_in, "mass_flow": moisture_flow, "vapor_fraction": 1.0, "enthalpy": h_vap, "composition": vapor_zs}
                            logs.append(f"{name}: moisture {float(params.get('outletMoisture', 5))}%, removed {moisture_flow:.4f} kg/s")

                        elif ntype == "Filter":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            efficiency = float(params.get("efficiency", 95)) / 100.0
                            dp = _kpa_to_pa(float(params.get("pressureDrop", 50)))
                            # H4: Solids-fraction-based split
                            solids_frac = float(params.get("solidsFraction", 0.05))
                            solids_frac = max(0.0, min(1.0, solids_frac))

                            cake_flow = mf * solids_frac * efficiency
                            filtrate_flow = mf - cake_flow
                            P_out = max(P_in - dp, 1000.0)

                            # Composition: user-specified solids component or heaviest fallback
                            cake_comp = dict(comp)
                            filtrate_comp = dict(comp)
                            if comp and len(comp) >= 2:
                                solids_comp_name_f = params.get("solidsComponent", "")
                                if solids_comp_name_f and solids_comp_name_f in comp:
                                    heaviest = solids_comp_name_f
                                else:
                                    comp_names_f = list(comp.keys())
                                    mws_f = [_get_mw(c) for c in comp_names_f]
                                    heaviest_idx = mws_f.index(max(mws_f))
                                    heaviest = comp_names_f[heaviest_idx]
                                cake_comp = {heaviest: 1.0}
                                filt_zs = dict(comp)
                                filt_zs[heaviest] = max(0, comp.get(heaviest, 0) * (1 - efficiency))
                                ft = sum(filt_zs.values()) or 1
                                filtrate_comp = {k: v / ft for k, v in filt_zs.items()}

                            eq_res["efficiency"] = float(params.get("efficiency", 95))
                            eq_res["pressureDrop"] = round(_pa_to_kpa(dp), 2)
                            eq_res["solidsFraction"] = round(solids_frac, 4)
                            eq_res["filtrateFlow"] = round(filtrate_flow, 4)
                            eq_res["cakeFlow"] = round(cake_flow, 4)

                            # F3C: Flash each outlet for correct per-phase enthalpy
                            flash_filt = self._flash_tp(list(filtrate_comp.keys()), list(filtrate_comp.values()), T_in, P_out, property_package)
                            h_filtrate = flash_filt["H"] / (flash_filt["MW_mix"] / 1000.0) if flash_filt and flash_filt.get("MW_mix", 0) > 0 else inlet.get("enthalpy", 0.0)
                            flash_cake = self._flash_tp(list(cake_comp.keys()), list(cake_comp.values()), T_in, P_in, property_package)
                            h_cake = flash_cake["H"] / (flash_cake["MW_mix"] / 1000.0) if flash_cake and flash_cake.get("MW_mix", 0) > 0 else inlet.get("enthalpy", 0.0)

                            outlets["out-1"] = {"temperature": T_in, "pressure": P_out, "mass_flow": filtrate_flow, "vapor_fraction": 0.0, "enthalpy": h_filtrate, "composition": filtrate_comp}
                            outlets["out-2"] = {"temperature": T_in, "pressure": P_in, "mass_flow": cake_flow, "vapor_fraction": 0.0, "enthalpy": h_cake, "composition": cake_comp}
                            logs.append(f"{name}: eff={efficiency * 100:.0f}%, solids={solids_frac:.1%}, ΔP={_pa_to_kpa(dp):.1f} kPa, filtrate={filtrate_flow:.4f}, cake={cake_flow:.4f}")

                        elif ntype == "PipeSegment":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            comp = inlet.get("composition", {})
                            vf_in = inlet.get("vapor_fraction", 0.0)

                            pipe_length = float(params.get("length", 100))
                            pipe_dia = float(params.get("diameter", 0.1))
                            pipe_rough = float(params.get("roughness", 0.000045))
                            pipe_elev = float(params.get("elevation", 0))
                            n_elbows = int(params.get("elbows90", 0))
                            n_tees = int(params.get("tees", 0))
                            n_gvalves = int(params.get("gateValves", 0))

                            # Get density and viscosity from flash
                            comp_names = list(comp.keys())
                            zs_pipe = [float(v) for v in comp.values()]
                            rho = self._get_density(comp_names, zs_pipe, T_in, P_in, property_package) if comp_names else 1000.0
                            mu = 0.001  # default water viscosity Pa·s
                            if comp_names:
                                flash_pipe = self._flash_tp(comp_names, zs_pipe, T_in, P_in, property_package)
                                if flash_pipe:
                                    if vf_in > 0.5 and flash_pipe.get("mu_gas"):
                                        mu = flash_pipe["mu_gas"]
                                    elif flash_pipe.get("mu_liquid"):
                                        mu = flash_pipe["mu_liquid"]

                            from app.services.hydraulics_engine import compute_hydraulics

                            # Phase 15 §3.4: Use fluids library for friction factor
                            # when available, for improved accuracy
                            _fluids_dp = None
                            try:
                                from fluids import friction_factor as ff_fluids  # type: ignore[import-untyped]
                                from fluids import Reynolds as Re_fluids  # type: ignore[import-untyped]
                                A_pipe = math.pi * (pipe_dia / 2) ** 2
                                vel = mf / (rho * A_pipe) if rho > 0 and A_pipe > 0 else 1.0
                                Re_val = Re_fluids(V=vel, D=pipe_dia, rho=rho, mu=mu)
                                fd = ff_fluids(Re=Re_val, eD=pipe_rough / pipe_dia if pipe_dia > 0 else 0.001)
                                # Darcy-Weisbach: dP = fd * (L/D) * (rho*V²/2)
                                dp_friction = fd * (pipe_length / pipe_dia) * 0.5 * rho * vel**2
                                dp_elevation = rho * 9.81 * pipe_elev
                                # Fittings K-values (approximate)
                                K_total = n_elbows * 0.9 + n_tees * 1.8 + n_gvalves * 0.15
                                dp_fittings = K_total * 0.5 * rho * vel**2
                                _fluids_dp = dp_friction + dp_elevation + dp_fittings
                            except Exception:
                                pass

                            hyd_result = compute_hydraulics(
                                mass_flow_rate=mf, density=rho, viscosity=mu,
                                length=pipe_length, diameter=pipe_dia,
                                roughness=pipe_rough, elevation=pipe_elev,
                                elbows_90=n_elbows, tees=n_tees, gate_valves=n_gvalves,
                            )

                            # Use fluids result if available and reasonable
                            if _fluids_dp is not None and _fluids_dp > 0:
                                dp_pa = _fluids_dp
                                eq_res["dp_source"] = "fluids"
                            else:
                                dp_pa = hyd_result.get("pressure_drop_kpa", 0) * 1000.0
                                eq_res["dp_source"] = "hydraulics_engine"
                            P_out = max(P_in - dp_pa, 1000.0)

                            eq_res["pressureDrop"] = round(hyd_result.get("pressure_drop_kpa", 0), 3)
                            eq_res["velocity"] = round(hyd_result.get("velocity_m_s", 0), 4)
                            eq_res["reynoldsNumber"] = hyd_result.get("reynolds_number", 0)
                            eq_res["frictionFactor"] = hyd_result.get("friction_factor", 0)
                            eq_res["flowRegime"] = hyd_result.get("flow_regime", "")
                            eq_res["erosionalVelocity"] = hyd_result.get("erosional_velocity_m_s", 0)
                            eq_res["erosionalRatio"] = hyd_result.get("erosional_ratio", 0)
                            eq_res["erosionalOk"] = hyd_result.get("erosional_ok", True)
                            eq_res["outletTemperature"] = round(_k_to_c(T_in), 2)
                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)

                            outlet = dict(inlet)
                            outlet["pressure"] = P_out

                            # M9: Heat loss to environment
                            T_out_pipe = T_in
                            ambient_temp_c = params.get("ambientTemp")
                            overall_u = float(params.get("overallU", 0))
                            if ambient_temp_c is not None and overall_u > 0:
                                T_ambient = _c_to_k(float(ambient_temp_c))
                                Q_loss = overall_u * math.pi * pipe_dia * pipe_length * (T_in - T_ambient)
                                cp_pipe = _estimate_cp(comp)
                                if comp_names:
                                    flash_pipe_hl = self._flash_tp(comp_names, zs_pipe, T_in, P_in, property_package)
                                    if flash_pipe_hl and flash_pipe_hl.get("Cp") and flash_pipe_hl["MW_mix"] > 0:
                                        cp_pipe = flash_pipe_hl["Cp"] / (flash_pipe_hl["MW_mix"] / 1000.0)
                                dT_loss = Q_loss / (mf * cp_pipe) if mf * cp_pipe > 0 else 0
                                T_out_pipe = T_in - dT_loss
                                eq_res["heatLoss"] = round(Q_loss / 1000, 3)  # kW
                                eq_res["outletTemperature"] = round(_k_to_c(T_out_pipe), 2)
                                logs.append(f"  PipeSegment heat loss: Q={Q_loss / 1000:.2f} kW, ΔT={dT_loss:.1f} K")

                            outlet["temperature"] = T_out_pipe
                            # PS4E: Update enthalpy after heat loss
                            if mf > 0 and ambient_temp_c is not None and overall_u > 0 and abs(Q_loss) > 0:
                                outlet["enthalpy"] = inlet.get("enthalpy", 0.0) - Q_loss / mf
                            # PS4E: Update VF from flash at final conditions
                            if comp_names:
                                flash_pipe_out = self._flash_tp(comp_names, zs_pipe, T_out_pipe, P_out, property_package)
                                if flash_pipe_out:
                                    outlet["vapor_fraction"] = flash_pipe_out.get("VF", inlet.get("vapor_fraction", 0.0))
                            outlets["out-1"] = outlet
                            logs.append(f"{name}: ΔP={hyd_result.get('pressure_drop_kpa', 0):.3f} kPa, V={hyd_result.get('velocity_m_s', 0):.2f} m/s, Re={hyd_result.get('reynolds_number', 0):.0f}")

                        else:
                            # Unknown equipment – pass through
                            if inlets:
                                outlets["out-1"] = dict(inlets[0])
                            logs.append(f"{name}: pass-through (no model for {ntype})")

                        # Store outlet port conditions for downstream propagation
                        # (T3-07: clean pseudo-components so downstream flash works)
                        for port_id, cond in outlets.items():
                            if "composition" in cond:
                                cond["composition"] = _clean_composition(cond["composition"])
                            port_conditions[(nid, port_id)] = cond

                        # Build the public result (remove internal _outlets)
                        equipment_results[nid] = eq_res

                        # Progress callback for SSE streaming
                        if progress_callback:
                            try:
                                eq_idx = sorted_ids.index(nid) + 1
                                await progress_callback(name, eq_idx, len(sorted_ids))
                            except Exception:
                                pass
                    except Exception as exc:
                        name = node.get("name", nid)
                        logger.exception("Equipment %s (%s) failed", name, nid)
                        logs.append(f"ERROR: {name} simulation failed: {exc}")
                        equipment_results[nid] = {"error": str(exc)}
                        has_errors = True

                # --- end of equipment loop for this iteration ---

                # Check tear-stream convergence
                if not tear_edges:
                    converged_recycle = True
                    break  # No recycle — single pass is sufficient

                max_error = 0.0
                new_tear_conditions: dict[str, dict[str, Any]] = {}
                for te in tear_edges:
                    src = te.get("source", "")
                    sh = te.get("sourceHandle", "out-1")
                    te_key = f"{src}_{sh}"
                    computed = port_conditions.get((src, sh))
                    if not computed:
                        continue
                    old = tear_stream_conditions.get(te_key, dict(_DEFAULT_FEED))

                    # Compare T, P, mass_flow
                    for field in ("temperature", "pressure", "mass_flow"):
                        old_val = old.get(field, 0.0)
                        new_val = computed.get(field, 0.0)
                        denom = max(abs(old_val), abs(new_val), 1e-12)
                        err = abs(new_val - old_val) / denom
                        max_error = max(max_error, err)

                    # Damping + Wegstein acceleration
                    blended = {}
                    for field in ("temperature", "pressure", "mass_flow", "enthalpy", "vapor_fraction"):
                        x_old = old.get(field, 0.0)
                        g_new = computed.get(field, 0.0)
                        wkey = f"{te_key}_{field}"
                        if wkey in wegstein_prev:
                            x_prev, g_prev = wegstein_prev[wkey]
                            dg = g_new - g_prev
                            dx = x_old - x_prev
                            if abs(dx) > 1e-15:
                                s = dg / dx
                                q = s / (s - 1.0)
                                q = max(-5.0, min(0.9, q))  # clamp Wegstein parameter
                                blended[field] = (1.0 - q) * g_new + q * x_old
                            else:
                                blended[field] = damping * g_new + (1.0 - damping) * x_old
                            wegstein_prev[wkey] = [x_old, g_new]
                        else:
                            # First iteration: simple damping
                            blended[field] = damping * g_new + (1.0 - damping) * x_old
                            wegstein_prev[wkey] = [x_old, g_new]

                    blended["composition"] = computed.get("composition", old.get("composition", {}))
                    new_tear_conditions[te_key] = blended

                tear_stream_conditions = new_tear_conditions

                # T2-5: Record convergence diagnostics for this iteration
                iter_data: dict[str, Any] = {
                    "iteration": iteration,
                    "max_error": max_error,
                }
                for te in tear_edges:
                    te_src = te.get("source", "")
                    te_sh = te.get("sourceHandle", "out-1")
                    te_key2 = f"{te_src}_{te_sh}"
                    tc = new_tear_conditions.get(te_key2, {})
                    iter_data[f"{te_key2}_T"] = round(tc.get("temperature", 0), 2)
                    iter_data[f"{te_key2}_P"] = round(tc.get("pressure", 0), 1)
                    iter_data[f"{te_key2}_mf"] = round(tc.get("mass_flow", 0), 6)
                convergence_history.append(iter_data)

                if max_error < tolerance:
                    converged_recycle = True
                    logs.append(f"Tear-stream converged in {iteration} iterations (max error: {max_error:.2e})")
                    break

                if iteration == max_iterations:
                    logs.append(
                        f"WARNING: Tear-stream did NOT converge after {max_iterations} iterations "
                        f"(max error: {max_error:.2e}, tolerance: {tolerance:.0e})"
                    )

            # ----------------------------------------------------------
            # T4-3: Mass/energy balance validation
            # ----------------------------------------------------------
            mass_balance_ok = True
            energy_balance_ok = True
            for node in nodes:
                nid = node.get("id", "")
                ntype = node.get("type", "")
                nname = node.get("name", nid)
                eq_r = equipment_results.get(nid, {})
                if "error" in eq_r:
                    continue  # skip failed equipment

                # Sum inlet mass flows
                inlet_mass = 0.0
                inlet_enthalpy_rate = 0.0
                for src_id, _sh, _th in upstream.get(nid, []):
                    for tgt_id, sh2, _th2 in downstream.get(src_id, []):
                        if tgt_id == nid:
                            cond = port_conditions.get((src_id, sh2))
                            if cond:
                                inlet_mass += cond.get("mass_flow", 0.0)
                                inlet_enthalpy_rate += cond.get("mass_flow", 0.0) * cond.get("enthalpy", 0.0)
                            break

                # Sum outlet mass flows
                outlet_mass = 0.0
                outlet_enthalpy_rate = 0.0
                for _tgt_id, sh, _th in downstream.get(nid, []):
                    cond = port_conditions.get((nid, sh))
                    if cond:
                        outlet_mass += cond.get("mass_flow", 0.0)
                        outlet_enthalpy_rate += cond.get("mass_flow", 0.0) * cond.get("enthalpy", 0.0)

                # Mass balance check (skip nodes with no upstream = feed nodes)
                if inlet_mass > 0 and outlet_mass > 0:
                    mass_err = abs(inlet_mass - outlet_mass)
                    if mass_err > 1e-6 * max(inlet_mass, 1e-12):
                        # Splitter/separator may have rounding differences
                        rel_err = mass_err / max(inlet_mass, 1e-12)
                        if rel_err > 0.01:  # >1% mass imbalance
                            mass_balance_ok = False
                            logs.append(
                                f"WARNING: {nname} mass imbalance: in={inlet_mass:.4f} kg/s, "
                                f"out={outlet_mass:.4f} kg/s ({rel_err:.1%} error)"
                            )

                # Energy balance check (Q/W from equipment results)
                # M10: Skip duty/work adjustment for HeatExchanger (internal heat transfer, not external Q)
                # Skip: DistillationColumn (internal condenser/reboiler), Cyclone (heuristic splits),
                # ConversionReactor/PFRReactor/CSTRReactor ("products" pseudo-component → enthalpy
                # reference state mismatch between pre/post _clean_composition flash),
                # Crystallizer/Dryer (phase change heuristics with solubility/moisture models)
                _EB_SKIP = ("DistillationColumn", "Cyclone", "Crystallizer", "Dryer")
                if inlet_mass > 0 and outlet_mass > 0 and ntype not in _EB_SKIP:
                    if ntype == "HeatExchanger":
                        # For HX, check Σ(mf*h)_in ≈ Σ(mf*h)_out directly (no external Q)
                        denom = max(abs(inlet_enthalpy_rate), abs(outlet_enthalpy_rate), 1e-6)
                        energy_err = abs(inlet_enthalpy_rate - outlet_enthalpy_rate) / denom
                    else:
                        duty_w = 0.0
                        if "duty" in eq_r:
                            duty_w = _kw_to_w(float(eq_r["duty"]))
                        elif "work" in eq_r:
                            duty_w = _kw_to_w(float(eq_r["work"]))
                        energy_in = inlet_enthalpy_rate + abs(duty_w) if duty_w > 0 else inlet_enthalpy_rate
                        energy_out = outlet_enthalpy_rate + abs(duty_w) if duty_w < 0 else outlet_enthalpy_rate
                        denom = max(abs(energy_in), abs(energy_out), 1e-6)
                        energy_err = abs(energy_in - energy_out) / denom
                    if energy_err > 0.05:  # >5% energy imbalance
                        energy_balance_ok = False
                        # Only log for significant imbalances, not rounding
                        if energy_err > 0.10:
                            logs.append(
                                f"WARNING: {nname} energy imbalance: {energy_err:.1%} "
                                f"(H_in={inlet_enthalpy_rate:.0f} W, H_out={outlet_enthalpy_rate:.0f} W)"
                            )

            # ----------------------------------------------------------
            # T5-2: Post-simulation equipment sizing correlations
            # ----------------------------------------------------------
            for node in nodes:
                nid = node.get("id", "")
                ntype = node.get("type", "")
                eq_r = equipment_results.get(nid, {})
                if "error" in eq_r:
                    continue
                sizing: dict[str, Any] = {}

                if ntype == "Separator":
                    # Souders-Brown: V_max = K_sb * sqrt((ρ_L - ρ_V) / ρ_V)
                    # K_sb ≈ 0.05-0.1 m/s for vertical separators
                    rho_L = 800.0  # default liquid density
                    rho_V = 5.0    # default vapor density
                    mf = 0.0
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf = c.get("mass_flow", 0.0)
                                break
                    # Fallback: use feed parameters for standalone equipment
                    if mf <= 0:
                        in_port = port_conditions.get((nid, "in-1"))
                        if in_port:
                            mf = in_port.get("mass_flow", 0.0)
                    if mf <= 0:
                        mf = float(node.get("parameters", {}).get("feedFlowRate", 0.0))
                    if mf > 0:
                        K_sb = 0.07  # typical for gas-liquid
                        rho_L = 800.0  # approximate
                        rho_V = 5.0
                        # Try to get from flash
                        vap_port = port_conditions.get((nid, "out-1"))
                        liq_port = port_conditions.get((nid, "out-2"))
                        if vap_port:
                            cn = list(vap_port.get("composition", {}).keys())
                            zs_v = list(vap_port.get("composition", {}).values())
                            if cn:
                                rho_V = max(self._get_density(cn, zs_v, vap_port["temperature"], vap_port["pressure"], property_package), 0.1)
                        if liq_port:
                            cn = list(liq_port.get("composition", {}).keys())
                            zs_l = list(liq_port.get("composition", {}).values())
                            if cn:
                                rho_L = max(self._get_density(cn, zs_l, liq_port["temperature"], liq_port["pressure"], property_package), 1.0)
                        V_max = K_sb * math.sqrt(max((rho_L - rho_V) / max(rho_V, 0.01), 0))
                        if V_max > 0:
                            # Use gas mass flow (not total) for Souders-Brown area
                            mf_gas = mf  # fallback to total
                            if vap_port:
                                mf_gas = vap_port.get("mass_flow", mf * 0.5)
                            A_min = mf_gas / (rho_V * V_max) if rho_V > 0 else 1.0
                            D_min = math.sqrt(4 * A_min / math.pi)
                            sizing["diameter_m"] = round(D_min, 3)
                            sizing["K_sb"] = K_sb
                            sizing["V_max_m_s"] = round(V_max, 3)

                    # Stokes' law settling velocity for droplet separation (API 12J)
                    # v_t = d_p² · g · (ρ_L - ρ_V) / (18 · μ_gas)
                    sz_params = node.get("parameters", {})
                    d_p = float(sz_params.get("dropletDiameter", 150)) * 1e-6  # μm → m
                    mu_gas = 1.8e-5  # Pa·s fallback (air viscosity)
                    # Try flash for gas viscosity
                    mu_gas_from_flash = False
                    try:
                        vap_port_s = port_conditions.get((nid, "out-1"))
                        if vap_port_s:
                            cn_vs = list(vap_port_s.get("composition", {}).keys())
                            zs_vs = list(vap_port_s.get("composition", {}).values())
                            if cn_vs:
                                fl_vs = self._flash_tp(cn_vs, zs_vs, vap_port_s["temperature"], vap_port_s["pressure"], property_package)
                                if fl_vs and fl_vs.get("state"):
                                    gas_ph = getattr(fl_vs["state"], 'gas', None)
                                    if gas_ph and hasattr(gas_ph, 'mu'):
                                        try:
                                            mu_gas = max(gas_ph.mu(), 1e-7)
                                            mu_gas_from_flash = True
                                        except Exception:
                                            logger.warning("Separator settling: gas viscosity extraction failed; using air fallback 1.8e-5 Pa·s")
                                    else:
                                        logger.warning("Separator settling: no gas phase in flash result; using air fallback 1.8e-5 Pa·s")
                            else:
                                logger.warning("Separator settling: vapor port has no composition; using air viscosity fallback 1.8e-5 Pa·s")
                        else:
                            logger.warning("Separator settling: no vapor port conditions; using air viscosity fallback 1.8e-5 Pa·s")
                    except Exception:
                        logger.warning("Separator settling: gas viscosity flash failed; using air fallback 1.8e-5 Pa·s")
                    if rho_L > rho_V and mu_gas > 0:
                        g = 9.81
                        v_settling = d_p ** 2 * g * (rho_L - rho_V) / (18.0 * mu_gas)
                        # Check Stokes regime; apply Oseen correction for Re_p > 1
                        Re_p = rho_V * v_settling * d_p / max(mu_gas, 1e-10)
                        if Re_p > 1.0:
                            # Oseen first-order correction: v_corrected = v_stokes / (1 + 3/16 * Re_p)
                            v_settling = v_settling / (1.0 + 3.0 / 16.0 * Re_p)
                            Re_p = rho_V * v_settling * d_p / max(mu_gas, 1e-10)  # recompute
                            logger.info("Separator settling: Oseen correction applied (Re_p=%.1f)", Re_p)
                        # Vertical separator: L/D = 3-5 (API 12J); settling time = D/v_t
                        D_ref = sizing.get("diameter_m", 1.0)
                        t_settling = D_ref / max(v_settling, 1e-10)
                        L_D = 4.0  # typical vertical separator L/D
                        vessel_length = L_D * D_ref
                        vessel_length = max(vessel_length, 1.5)  # minimum 1.5m
                        sizing["v_settling_m_s"] = round(v_settling, 6)
                        sizing["t_settling_s"] = round(t_settling, 1)
                        sizing["vessel_length_m"] = round(vessel_length, 2)
                        sizing["L_D_ratio"] = round(L_D, 2)
                        sizing["droplet_diameter_um"] = round(d_p * 1e6, 0)
                        sizing["mu_gas_Pa_s"] = round(mu_gas, 7)
                        sizing["Re_particle"] = round(Re_p, 2)

                elif ntype == "ThreePhaseSeparator":
                    # Gas-liquid: Souders-Brown (same as Separator)
                    sz_params = node.get("parameters", {})
                    mf_3p = 0.0
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf_3p = c.get("mass_flow", 0.0)
                                break
                    if mf_3p > 0:
                        rho_V_3p = 5.0
                        rho_L_light = 750.0
                        rho_L_heavy = 1000.0
                        mu_gas_3p = 1.8e-5
                        mu_heavy = 0.001  # Pa·s fallback
                        sigma_ll = 0.025  # N/m fallback
                        vap_port_3p = port_conditions.get((nid, "out-1"))
                        light_port = port_conditions.get((nid, "out-2"))
                        heavy_port = port_conditions.get((nid, "out-3"))
                        if vap_port_3p:
                            cn_v3 = list(vap_port_3p.get("composition", {}).keys())
                            zs_v3 = list(vap_port_3p.get("composition", {}).values())
                            if cn_v3:
                                rho_V_3p = max(self._get_density(cn_v3, zs_v3, vap_port_3p["temperature"], vap_port_3p["pressure"], property_package), 0.1)
                                try:
                                    fl_v3 = self._flash_tp(cn_v3, zs_v3, vap_port_3p["temperature"], vap_port_3p["pressure"], property_package)
                                    if fl_v3 and fl_v3.get("state"):
                                        gp = getattr(fl_v3["state"], 'gas', None)
                                        if gp and hasattr(gp, 'mu'):
                                            mu_gas_3p = max(gp.mu(), 1e-7)
                                        else:
                                            logger.warning("3-Phase Sep sizing: no gas phase for viscosity; using air fallback")
                                except Exception:
                                    logger.warning("3-Phase Sep sizing: gas viscosity flash failed; using air fallback 1.8e-5 Pa·s")
                        if light_port:
                            cn_ll = list(light_port.get("composition", {}).keys())
                            zs_ll = list(light_port.get("composition", {}).values())
                            if cn_ll:
                                rho_L_light = max(self._get_density(cn_ll, zs_ll, light_port["temperature"], light_port["pressure"], property_package), 1.0)
                        if heavy_port:
                            cn_hl = list(heavy_port.get("composition", {}).keys())
                            zs_hl = list(heavy_port.get("composition", {}).values())
                            if cn_hl:
                                rho_L_heavy = max(self._get_density(cn_hl, zs_hl, heavy_port["temperature"], heavy_port["pressure"], property_package), 1.0)
                                try:
                                    fl_hl = self._flash_tp(cn_hl, zs_hl, heavy_port["temperature"], heavy_port["pressure"], property_package)
                                    if fl_hl and fl_hl.get("state"):
                                        liq_ph = getattr(fl_hl["state"], 'liquid0', None)
                                        if liq_ph:
                                            if hasattr(liq_ph, 'mu'):
                                                try:
                                                    mu_heavy = max(liq_ph.mu(), 1e-6)
                                                except Exception:
                                                    pass
                                            if hasattr(liq_ph, 'sigma'):
                                                try:
                                                    sigma_ll = max(liq_ph.sigma(), 1e-4)
                                                except Exception:
                                                    pass
                                except Exception:
                                    pass
                        # Gas-liquid Souders-Brown
                        K_sb_3p = 0.07
                        V_max_3p = K_sb_3p * math.sqrt(max((rho_L_light - rho_V_3p) / max(rho_V_3p, 0.01), 0))
                        if V_max_3p > 0:
                            # Use gas mass flow (not total) for Souders-Brown area
                            mf_gas_3p = mf_3p  # fallback
                            if vap_port_3p:
                                mf_gas_3p = vap_port_3p.get("mass_flow", mf_3p * 0.3)
                            A_3p = mf_gas_3p / (rho_V_3p * V_max_3p) if rho_V_3p > 0 else 1.0
                            D_3p = math.sqrt(4 * A_3p / math.pi)
                            sizing["diameter_m"] = round(D_3p, 3)
                            sizing["V_max_m_s"] = round(V_max_3p, 3)
                        # Liquid-liquid Stokes settling (light droplets rising through heavy phase)
                        d_p_ll = float(sz_params.get("liquidDropletDiameter", 500)) * 1e-6  # μm → m
                        delta_rho_ll = abs(rho_L_heavy - rho_L_light)
                        if delta_rho_ll > 1.0 and mu_heavy > 0:
                            g = 9.81
                            v_settle_ll = d_p_ll ** 2 * g * delta_rho_ll / (18.0 * mu_heavy)
                            # Oseen correction for Re_p > 1 (same pattern as gas-liquid Separator)
                            Re_p_ll = rho_L_heavy * v_settle_ll * d_p_ll / max(mu_heavy, 1e-10)
                            if Re_p_ll > 1.0:
                                v_settle_ll = v_settle_ll / (1.0 + 3.0 / 16.0 * Re_p_ll)
                                Re_p_ll = rho_L_heavy * v_settle_ll * d_p_ll / max(mu_heavy, 1e-10)
                                logger.info("3-Phase Sep LL settling: Oseen correction applied (Re_p=%.1f)", Re_p_ll)
                            sizing["v_settle_liquid_liquid_m_s"] = round(v_settle_ll, 6)
                            sizing["rho_light_liquid"] = round(rho_L_light, 1)
                            sizing["rho_heavy_liquid"] = round(rho_L_heavy, 1)
                            sizing["mu_heavy_Pa_s"] = round(mu_heavy, 6)
                            # Retention time heuristic (API 12J):
                            # Light oil (Δρ > 300): 180s, medium (Δρ 100-300): 300s, heavy/emulsion: 600s
                            if delta_rho_ll > 300:
                                t_retention = 180.0  # 3 min — light oil
                            elif delta_rho_ll > 100:
                                t_retention = 300.0  # 5 min — medium oil
                            else:
                                t_retention = 600.0  # 10 min — heavy/emulsion
                            sizing["retention_time_s"] = round(t_retention, 0)
                            # Vessel sizing: retention time drives liquid compartment volume
                            D_3p_ref = sizing.get("diameter_m", 1.5)
                            A_cross = math.pi * D_3p_ref ** 2 / 4.0
                            # Liquid occupies ~60% of cross-section in horizontal 3-phase sep
                            A_liquid = 0.6 * A_cross
                            # Estimate total liquid volumetric flow from outlet mass flows
                            mf_light = 0.0
                            mf_heavy = 0.0
                            if light_port:
                                mf_light = light_port.get("mass_flow", 0.0)
                            if heavy_port:
                                mf_heavy = heavy_port.get("mass_flow", 0.0)
                            Q_liquid = 0.0
                            if mf_light > 0 and rho_L_light > 1:
                                Q_liquid += mf_light / rho_L_light
                            if mf_heavy > 0 and rho_L_heavy > 1:
                                Q_liquid += mf_heavy / rho_L_heavy
                            if Q_liquid <= 0:
                                # Fallback: assume 50% of inlet goes to liquid
                                Q_liquid = 0.5 * mf_3p / max(rho_L_light, 500.0)
                            # V_liquid = Q_liquid * t_retention → L_liquid = V / A_liquid
                            V_liquid = Q_liquid * t_retention
                            L_retention = V_liquid / max(A_liquid, 0.01)
                            # Also compute L/D = 4 minimum
                            L_LD = 4.0 * D_3p_ref
                            vessel_len_3p = max(L_retention, L_LD, 2.5)  # take the larger
                            L_D_3p = vessel_len_3p / max(D_3p_ref, 0.1)
                            sizing["vessel_length_m"] = round(vessel_len_3p, 2)
                            sizing["L_D_ratio"] = round(L_D_3p, 2)
                            sizing["V_liquid_m3"] = round(V_liquid, 3)
                            sizing["liquid_droplet_diameter_um"] = round(d_p_ll * 1e6, 0)

                elif ntype == "Cyclone":
                    # Lapple d50 cut point: d50 = sqrt(9·μ·W / (π·N·V_in·(ρ_p - ρ_g)))
                    # W = inlet width (~ inletDiameter), N = effective turns, V_in = inlet velocity
                    sz_params = node.get("parameters", {})
                    mf_cyc = 0.0
                    rho_g_cyc = 1.2
                    mu_g_cyc = 1.8e-5
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf_cyc = c.get("mass_flow", 0.0)
                                break
                    if mf_cyc > 0:
                        # Standard Lapple cyclone: rectangular tangential inlet
                        # a = D_c/2 (height), b = D_c/4 (width), A_inlet = a*b = D_c²/8
                        D_cyclone = float(sz_params.get("cycloneDiameter", sz_params.get("inletDiameter", 0.3) * 4))
                        inlet_width = D_cyclone / 4.0  # Lapple b = D_c/4
                        inlet_height = D_cyclone / 2.0  # Lapple a = D_c/2
                        N_turns = float(sz_params.get("effectiveTurns", 5))
                        rho_particle = float(sz_params.get("particleDensity", 2500))
                        # Flash inlet for gas properties
                        try:
                            in_port_cyc = None
                            for _src, _sh, _th in upstream.get(nid, []):
                                for _tgt, sh2, _th2 in downstream.get(_src, []):
                                    if _tgt == nid:
                                        in_port_cyc = port_conditions.get((_src, sh2))
                                        break
                            if in_port_cyc:
                                cn_cyc = list(in_port_cyc.get("composition", {}).keys())
                                zs_cyc = list(in_port_cyc.get("composition", {}).values())
                                if cn_cyc:
                                    rho_g_cyc = max(self._get_density(cn_cyc, zs_cyc, in_port_cyc["temperature"], in_port_cyc["pressure"], property_package), 0.1)
                                    fl_cyc = self._flash_tp(cn_cyc, zs_cyc, in_port_cyc["temperature"], in_port_cyc["pressure"], property_package)
                                    if fl_cyc and fl_cyc.get("state"):
                                        gp_cyc = getattr(fl_cyc["state"], 'gas', None)
                                        if gp_cyc and hasattr(gp_cyc, 'mu'):
                                            try:
                                                mu_g_cyc = max(gp_cyc.mu(), 1e-7)
                                            except Exception:
                                                pass
                        except Exception:
                            pass
                        A_inlet = inlet_width * inlet_height  # rectangular inlet
                        V_in = mf_cyc / (rho_g_cyc * A_inlet) if rho_g_cyc > 0 and A_inlet > 0 else 15.0
                        # Lapple model: d50 = sqrt(9·μ·W / (π·N·V_in·(ρ_p - ρ_g)))
                        # W = inlet width (perpendicular to cyclone axis)
                        delta_rho_cyc = max(rho_particle - rho_g_cyc, 1.0)
                        d50_sq = 9.0 * mu_g_cyc * inlet_width / (math.pi * max(N_turns, 1) * max(V_in, 0.1) * delta_rho_cyc)
                        d50 = math.sqrt(max(d50_sq, 0)) * 1e6  # m → μm
                        # Terminal velocity at d50 as sanity check
                        d50_m = d50 * 1e-6
                        v_t_d50 = d50_m ** 2 * 9.81 * delta_rho_cyc / (18.0 * mu_g_cyc)
                        sizing["d50_cut_point_um"] = round(d50, 2)
                        sizing["inlet_velocity_m_s"] = round(V_in, 2)
                        sizing["N_turns"] = N_turns
                        sizing["rho_particle"] = rho_particle
                        sizing["rho_gas"] = round(rho_g_cyc, 3)
                        sizing["mu_gas_Pa_s"] = round(mu_g_cyc, 7)
                        sizing["v_terminal_d50_m_s"] = round(v_t_d50, 6)

                elif ntype == "HeatExchanger":
                    duty_kw = eq_r.get("duty", 0)
                    lmtd = eq_r.get("LMTD", 0)
                    if duty_kw and lmtd and float(lmtd) > 0:
                        Q_w = abs(_kw_to_w(float(duty_kw)))
                        # T2-2: Kern method U calculation using transport properties
                        U = 500.0  # fallback W/(m²·K)
                        h_tube = 0.0
                        h_shell = 0.0
                        try:
                            # Get hot and cold side conditions
                            hot_port = port_conditions.get((nid, "in-hot")) or port_conditions.get((nid, "in-1"))
                            cold_port = port_conditions.get((nid, "in-cold")) or port_conditions.get((nid, "in-2"))
                            if hot_port and cold_port:
                                for side_label, side_port in [("tube", hot_port), ("shell", cold_port)]:
                                    cn_s = list(side_port.get("composition", {}).keys())
                                    zs_s = list(side_port.get("composition", {}).values())
                                    if cn_s:
                                        fl_s = self._flash_tp(cn_s, zs_s, side_port["temperature"], side_port["pressure"], property_package)
                                        if fl_s:
                                            rho_s = fl_s.get("rho_liquid", 800.0) if fl_s.get("VF", 0) < 0.5 else max(side_port["pressure"] * fl_s.get("MW_mix", 28) / 1000 / (8.314 * side_port["temperature"]), 0.5)
                                            Cp_s = fl_s.get("Cp", 100) / max(fl_s.get("MW_mix", 28) / 1000, 0.01)  # J/kg·K
                                            # Get transport props from thermo state
                                            state = fl_s.get("state")
                                            mu_s = 0.001  # Pa·s fallback
                                            k_s = 0.1  # W/m·K fallback
                                            if state:
                                                liq_phase = getattr(state, 'liquid0', None)
                                                gas_phase = getattr(state, 'gas', None)
                                                phase = liq_phase if fl_s.get("VF", 0) < 0.5 else gas_phase
                                                if phase:
                                                    try:
                                                        mu_s = phase.mu() if hasattr(phase, 'mu') else mu_s
                                                    except Exception:
                                                        pass
                                                    try:
                                                        k_s = phase.k() if hasattr(phase, 'k') else k_s
                                                    except Exception:
                                                        pass
                                            # Dittus-Boelter: Nu = 0.023 * Re^0.8 * Pr^0.4
                                            D_tube_od = 0.019  # 3/4" tube OD
                                            D_tube_id = 0.016  # tube inner diameter
                                            A_tube = math.pi * D_tube_id**2 / 4  # single tube flow area
                                            # Estimate tube count from target velocity (~1 m/s liquid, ~15 m/s gas)
                                            v_target = 1.0 if fl_s.get("VF", 0) < 0.5 else 15.0
                                            vol_flow = side_port.get("mass_flow", 1.0) / max(rho_s, 0.1)
                                            if side_label == "tube":
                                                n_tubes = max(1, int(vol_flow / (v_target * A_tube)))
                                                v_s = vol_flow / (n_tubes * A_tube) if n_tubes > 0 else v_target
                                                D_h = D_tube_id  # tube hydraulic diameter
                                            else:
                                                # Shell side: use equivalent diameter for square pitch
                                                # D_eq = 4*(P_t^2 - pi*D_o^2/4) / (pi*D_o) for square pitch
                                                P_t = 0.025  # tube pitch 25mm
                                                D_eq = 4 * (P_t**2 - math.pi * D_tube_od**2 / 4) / (math.pi * D_tube_od)
                                                D_h = max(D_eq, 0.01)  # shell hydraulic diameter
                                                v_s = vol_flow / max(math.pi * 0.2**2 / 4, 0.01)  # ~200mm shell ID estimate
                                            Re = rho_s * abs(v_s) * D_h / max(mu_s, 1e-8)
                                            Pr = Cp_s * mu_s / max(k_s, 1e-6)
                                            if Re > 0 and Pr > 0:
                                                if side_label == "tube":
                                                    # Dittus-Boelter for tube-side turbulent flow
                                                    Nu = 0.023 * max(Re, 100) ** 0.8 * max(Pr, 0.1) ** 0.4
                                                    h_tube = Nu * k_s / D_h
                                                else:
                                                    # Kern method for shell-side cross-flow
                                                    Nu = 0.36 * max(Re, 10) ** 0.55 * max(Pr, 0.1) ** (1.0 / 3.0)
                                                    h_shell = Nu * k_s / D_h
                                R_f = 0.0003  # fouling resistance m²·K/W
                                if h_tube > 0 and h_shell > 0:
                                    U = 1.0 / (1.0 / h_tube + 1.0 / h_shell + R_f)
                                    sizing["h_tube"] = round(h_tube, 1)
                                    sizing["h_shell"] = round(h_shell, 1)
                                    sizing["U_calculated"] = round(U, 1)
                        except Exception:
                            pass
                        A = Q_w / (U * float(lmtd))
                        sizing["area_m2"] = round(A, 2)
                        if "U_calculated" not in sizing:
                            sizing["U_assumed"] = U

                elif ntype == "DistillationColumn":
                    # T2-2: Fair's flooding with real phase densities + surface tension correction
                    mf_val = 0.0
                    feed_port = None
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf_val = c.get("mass_flow", 0.0)
                                    feed_port = c
                                break
                    if mf_val > 0:
                        rho_V_col = 2.0  # fallback
                        rho_L_col = 800.0  # fallback
                        sigma = 0.02  # N/m fallback surface tension
                        # Use real densities from distillate (vapor) and bottoms (liquid) ports
                        dist_port = port_conditions.get((nid, "out-1"))
                        bot_port = port_conditions.get((nid, "out-2"))
                        if dist_port:
                            cn_d = list(dist_port.get("composition", {}).keys())
                            zs_d = list(dist_port.get("composition", {}).values())
                            if cn_d:
                                rho_V_col = max(self._get_density(cn_d, zs_d, dist_port["temperature"], dist_port["pressure"], property_package), 0.1)
                        if bot_port:
                            cn_b = list(bot_port.get("composition", {}).keys())
                            zs_b = list(bot_port.get("composition", {}).values())
                            if cn_b:
                                rho_L_col = max(self._get_density(cn_b, zs_b, bot_port["temperature"], bot_port["pressure"], property_package), 1.0)
                                # Try to get surface tension from flash
                                try:
                                    fl_b = self._flash_tp(cn_b, zs_b, bot_port["temperature"], bot_port["pressure"], property_package)
                                    if fl_b and fl_b.get("state"):
                                        liq_b = getattr(fl_b["state"], 'liquid0', None)
                                        if liq_b and hasattr(liq_b, 'sigma'):
                                            sigma = max(liq_b.sigma(), 0.001)
                                except Exception:
                                    pass
                        # Surface tension correction: C_sb = 0.08 * (20/σ)^0.2 where σ in mN/m
                        sigma_mNm = sigma * 1000  # N/m → mN/m
                        C_sb = 0.08 * (20.0 / max(sigma_mNm, 1.0)) ** 0.2
                        V_flood = C_sb * math.sqrt(max((rho_L_col - rho_V_col) / max(rho_V_col, 0.01), 0))
                        if V_flood > 0:
                            V_dot = mf_val / max(rho_V_col, 0.1)
                            A_col = V_dot / (V_flood * 0.8)
                            D_col = math.sqrt(4 * max(A_col, 0.01) / math.pi)
                            sizing["diameter_m"] = round(D_col, 3)
                            sizing["flooding_velocity_m_s"] = round(V_flood, 3)
                            sizing["rho_vapor"] = round(rho_V_col, 2)
                            sizing["rho_liquid"] = round(rho_L_col, 1)
                            sizing["C_sb"] = round(C_sb, 4)

                elif ntype in ("Pump", "Compressor"):
                    # T2-2: Sizing with actual volumetric flow from flash density
                    work_kw = float(eq_r.get("work", 0))
                    if work_kw > 0:
                        in_port = None
                        for _src, _sh, _th in upstream.get(nid, []):
                            for _tgt, sh2, _th2 in downstream.get(_src, []):
                                if _tgt == nid:
                                    in_port = port_conditions.get((_src, sh2))
                                    break
                        if in_port:
                            cn_p = list(in_port.get("composition", {}).keys())
                            zs_p = list(in_port.get("composition", {}).values())
                            mf_p = in_port.get("mass_flow", 0)
                            if cn_p and mf_p > 0:
                                rho_p = self._get_density(cn_p, zs_p, in_port["temperature"], in_port["pressure"], property_package)
                                if rho_p > 0:
                                    vol_flow = mf_p / rho_p  # m³/s
                                    sizing["volumetric_flow_m3_s"] = round(vol_flow, 6)
                                    sizing["volumetric_flow_m3_h"] = round(vol_flow * 3600, 2)
                                    sizing["inlet_density"] = round(rho_p, 2)

                if sizing:
                    eq_r["sizing"] = sizing

            # ----------------------------------------------------------
            # Equipment costing (CEPCI-adjusted correlations)
            # ----------------------------------------------------------
            CEPCI_BASE = 397   # 2004
            CEPCI_CURR = 816   # 2024
            cepci_ratio = CEPCI_CURR / CEPCI_BASE

            for node in nodes:
                nid = node.get("id", "")
                ntype = node.get("type", "")
                eq_r = equipment_results.get(nid, {})
                if "error" in eq_r:
                    continue
                costing: dict[str, Any] = {}
                try:
                    if ntype == "Pump":
                        Q = float(eq_r.get("work", 0))
                        if Q > 0:
                            C_base = 3540 * (Q ** 0.71)
                            costing["purchaseCost"] = round(C_base * cepci_ratio)
                            costing["method"] = "Seider pump correlation"
                    elif ntype == "Compressor":
                        W = float(eq_r.get("work", 0))
                        if W > 0:
                            C_base = 7090 * (W ** 0.61)
                            costing["purchaseCost"] = round(C_base * cepci_ratio)
                            costing["method"] = "Seider compressor correlation"
                    elif ntype == "HeatExchanger":
                        sizing_d = eq_r.get("sizing", {})
                        A = float(sizing_d.get("area_m2", 0))
                        if A > 0:
                            C_base = 32800 * (A ** 0.65)
                            costing["purchaseCost"] = round(C_base * cepci_ratio)
                            costing["method"] = "A-based HX correlation"
                    elif ntype == "DistillationColumn":
                        sizing_d = eq_r.get("sizing", {})
                        N = float(eq_r.get("stages", sizing_d.get("stages", 10)))
                        D = float(sizing_d.get("diameter_m", 1.0))
                        if N > 0 and D > 0:
                            C_base = 17640 * ((N * D ** 2) ** 0.802)
                            costing["purchaseCost"] = round(C_base * cepci_ratio)
                            costing["method"] = "Column vessel correlation"
                    elif ntype in ("Separator", "ThreePhaseSeparator"):
                        sizing_d = eq_r.get("sizing", {})
                        D_sep = float(sizing_d.get("diameter_m", 1.0))
                        if D_sep > 0:
                            V_est = math.pi * (D_sep / 2) ** 2 * D_sep * 3
                            C_base = 10200 * (V_est ** 0.62)
                            costing["purchaseCost"] = round(C_base * cepci_ratio)
                            costing["method"] = "Vessel correlation"
                    if costing:
                        costing["cepciYear"] = 2024
                        costing["cepciIndex"] = CEPCI_CURR
                        eq_r["costing"] = costing
                except Exception:
                    pass

            # Process ProductStream nodes — read from upstream port conditions
            for ps_node in product_stream_nodes:
                ps_id = ps_node.get("id", "")
                ps_name = ps_node.get("name", ps_id)
                try:
                    # Find upstream condition
                    ps_inlets = upstream.get(ps_id, [])
                    if ps_inlets:
                        src_id, _sh, _th = ps_inlets[0]
                        # Find matching source outlet
                        cond = None
                        for tgt_id, sh2, _th2 in downstream.get(src_id, []):
                            if tgt_id == ps_id:
                                cond = port_conditions.get((src_id, sh2))
                                break
                        if cond:
                            T_c = _k_to_c(cond["temperature"])
                            P_kpa = _pa_to_kpa(cond["pressure"])
                            mf = cond.get("mass_flow", 0.0)
                            vf = cond.get("vapor_fraction", 0.0)
                            comp = cond.get("composition", {})
                            _ps_comp_props = _compute_component_properties(comp, mf)
                            _ps_h_kj = round(cond.get("enthalpy", 0.0) / 1000.0, 4)  # J/kg → kJ/kg
                            equipment_results[ps_id] = {
                                "equipment_id": ps_id,
                                "equipment_type": "ProductStream",
                                "name": ps_name,
                                "outletTemperature": T_c,
                                "outletPressure": P_kpa,
                                "massFlow": mf,
                                "vaporFraction": vf,
                                "composition": comp,
                                **_ps_comp_props,
                                "inlet_streams": {
                                    "in-1": {
                                        "temperature": T_c,
                                        "pressure": P_kpa,
                                        "flowRate": mf,
                                        "vapor_fraction": vf,
                                        "composition": comp,
                                        "enthalpy": _ps_h_kj,
                                        **_ps_comp_props,
                                    },
                                },
                            }
                            logs.append(f"Product stream '{ps_name}': T={T_c:.1f}°C, P={P_kpa:.1f} kPa, flow={mf:.3f} kg/s, VF={vf:.3f}")
                        else:
                            equipment_results[ps_id] = {
                                "equipment_id": ps_id,
                                "equipment_type": "ProductStream",
                                "name": ps_name,
                                "error": "No upstream conditions available",
                            }
                    else:
                        equipment_results[ps_id] = {
                            "equipment_id": ps_id,
                            "equipment_type": "ProductStream",
                            "name": ps_name,
                            "error": "Product stream has no inlet connection",
                        }
                except Exception as exc:
                    equipment_results[ps_id] = {
                        "equipment_id": ps_id,
                        "equipment_type": "ProductStream",
                        "name": ps_name,
                        "error": str(exc),
                    }
                    has_errors = True

            # Process DesignSpec nodes — outer secant/bisection loop
            for ds_node in design_spec_nodes:
                ds_id = ds_node.get("id", "")
                ds_name = ds_node.get("name", ds_id)
                ds_params = ds_node.get("parameters", {})
                try:
                    target_stream_id = ds_params.get("targetStreamId", "")
                    target_property = ds_params.get("targetProperty", "temperature")
                    target_value = float(ds_params.get("targetValue", 0))
                    manip_node_id = ds_params.get("manipulatedNodeId", "")
                    manip_param = ds_params.get("manipulatedParam", "")
                    lower_bound = float(ds_params.get("lowerBound", 0))
                    upper_bound = float(ds_params.get("upperBound", 1000))
                    tolerance = float(ds_params.get("tolerance", 0.01))

                    if not target_stream_id or not manip_node_id or not manip_param:
                        equipment_results[ds_id] = {
                            "equipment_id": ds_id, "equipment_type": "DesignSpec",
                            "name": ds_name, "status": "skipped",
                            "info": "DesignSpec not fully configured — skipped. Configure target and manipulated variables to activate.",
                        }
                        logs.append(f"INFO: DesignSpec '{ds_name}' not fully configured — skipped")
                        continue

                    # Property mapping for equipment results
                    prop_map = {
                        "temperature": "outletTemperature",
                        "pressure": "outletPressure",
                        "flowRate": "massFlow",
                        "vapor_fraction": "vaporFraction",
                    }
                    result_key = prop_map.get(target_property, target_property)

                    def _get_target_value(eq_results_local: dict) -> float | None:
                        """Extract target value from current results."""
                        tr = eq_results_local.get(target_stream_id, {})
                        v = tr.get(result_key)
                        if v is None:
                            return None
                        return float(v)

                    # Secant method with bisection fallback
                    a, b = lower_bound, upper_bound
                    x0_ds, x1_ds = a, a + (b - a) * 0.1
                    f0 = None
                    f1 = None
                    ds_converged = False
                    ds_iterations = 0
                    # Deep copy nodes EXCLUDING DesignSpec to avoid infinite recursion
                    ds_nodes = copy.deepcopy([n for n in nodes if n.get("type") != "DesignSpec"])

                    for ds_iter in range(30):
                        ds_iterations = ds_iter + 1
                        # Set manipulated param on the deep copy
                        for n in ds_nodes:
                            if n.get("id") == manip_node_id:
                                n_params = n.get("parameters", n.get("data", {}).get("parameters", {}))
                                n_params[manip_param] = x1_ds
                                break

                        # Re-run simulation (simplified: just re-execute _simulate_basic)
                        # We re-use the current method but this is a simplified inner call
                        inner_result = await self.simulate({
                            "nodes": [dict(n) for n in ds_nodes],
                            "edges": [dict(e) for e in edges],
                            "property_package": property_package,
                            "simulation_basis": simulation_basis,
                        })
                        inner_eq = inner_result.get("results", inner_result).get("equipment_results", inner_result.get("equipment_results", {}))
                        current_val = _get_target_value(inner_eq)

                        if current_val is None:
                            logs.append(f"WARNING: DesignSpec '{ds_name}' — cannot read target value")
                            break

                        f1 = current_val - target_value
                        if abs(f1) < tolerance:
                            ds_converged = True
                            break

                        if f0 is not None and abs(f1 - f0) > 1e-12:
                            # Secant step
                            x_new = x1_ds - f1 * (x1_ds - x0_ds) / (f1 - f0)
                            x_new = max(a, min(b, x_new))
                        else:
                            # Bisection
                            x_new = (a + b) / 2.0

                        # Update bounds for bisection fallback
                        if f1 > 0:
                            b = x1_ds
                        else:
                            a = x1_ds

                        x0_ds, f0 = x1_ds, f1
                        x1_ds = x_new

                    equipment_results[ds_id] = {
                        "equipment_id": ds_id, "equipment_type": "DesignSpec",
                        "name": ds_name,
                        "converged": ds_converged,
                        "iterations": ds_iterations,
                        "targetValue": target_value,
                        "achievedValue": round(current_val, 4) if current_val is not None else None,
                        "manipulatedValue": round(x1_ds, 4),
                        "error": round(abs(f1), 6) if f1 is not None else None,
                    }
                    if ds_converged:
                        # Merge converged inner simulation results into outer results
                        inner_wrap = inner_result.get("results", inner_result)
                        inner_eq_merged = inner_wrap.get("equipment_results", inner_result.get("equipment_results", {}))
                        inner_sr_merged = inner_wrap.get("stream_results", inner_result.get("stream_results", {}))
                        for k, v in inner_eq_merged.items():
                            if k != ds_id:
                                equipment_results[k] = v
                        for k, v in inner_sr_merged.items():
                            stream_results[k] = v
                        logs.append(f"DesignSpec '{ds_name}': converged in {ds_iterations} iter, {manip_param}={x1_ds:.4f}")
                    else:
                        logs.append(f"WARNING: DesignSpec '{ds_name}': did NOT converge after {ds_iterations} iter")
                        has_errors = True
                except Exception as exc:
                    equipment_results[ds_id] = {
                        "equipment_id": ds_id, "equipment_type": "DesignSpec",
                        "name": ds_name, "error": str(exc),
                    }
                    has_errors = True

            # Process energy stream edges — propagate duty/power from source to target
            for edge in edges:
                edge_type = edge.get("type", "stream")
                if edge_type != "energy-stream":
                    continue
                src_id = edge.get("source", "")
                tgt_id = edge.get("target", "")
                edge_id = edge.get("id", f"{src_id}_energy_{tgt_id}")
                src_result = equipment_results.get(src_id, {})
                duty_w = src_result.get("duty")
                work_w = src_result.get("work")
                energy_kw = None
                if duty_w is not None:
                    energy_kw = duty_w  # already in kW from equipment results
                elif work_w is not None:
                    energy_kw = work_w
                stream_results[edge_id] = {
                    "type": "energy",
                    "duty_kW": energy_kw,
                    "source": src_id,
                    "target": tgt_id,
                }
                if energy_kw is not None:
                    logs.append(f"Energy stream {src_result.get('name', src_id)} → {node_map.get(tgt_id, {}).get('name', tgt_id)}: {energy_kw:.1f} kW")

            # Build stream results from edges (convert to frontend units)
            for edge in edges:
                edge_type = edge.get("type", "stream")
                if edge_type == "energy-stream":
                    continue  # already handled above
                src = edge.get("source", "")
                sh = edge.get("sourceHandle", "out-1")
                edge_id = edge.get("id", f"{src}_{sh}")
                cond = port_conditions.get((src, sh))
                if cond:
                    _edge_comp = cond.get("composition", {})
                    _edge_mf = cond["mass_flow"]
                    _edge_cp = _compute_component_properties(_edge_comp, _edge_mf)
                    _edge_h_kj = round(cond.get("enthalpy", 0.0) / 1000.0, 4)  # J/kg → kJ/kg
                    _edge_s_kj = round(cond.get("entropy", 0.0) / 1000.0, 6)  # J/(kg·K) → kJ/(kg·K)
                    _sr: dict[str, Any] = {
                        "temperature": round(_k_to_c(cond["temperature"]), 2),
                        "pressure": round(_pa_to_kpa(cond["pressure"]), 3),
                        "flowRate": round(_edge_mf, 4),
                        "vapor_fraction": round(cond.get("vapor_fraction", 0.0), 4),
                        "composition": _edge_comp,
                        "enthalpy": _edge_h_kj,
                        "entropy": _edge_s_kj,
                        **_edge_cp,
                    }
                    # Flash for extended transport/thermo properties
                    _sr_flash = self._flash_tp(
                        list(_edge_comp.keys()), [float(v) for v in _edge_comp.values()],
                        cond["temperature"], cond["pressure"], property_package
                    ) if _edge_comp and _edge_mf > 0 else None
                    if _sr_flash:
                        mw = _sr_flash.get("MW_mix", 0)
                        _sr["density"] = round(_sr_flash["rho_mix"], 4) if _sr_flash.get("rho_mix") is not None else None
                        _sr["viscosity"] = _sr_flash.get("mu_liquid") if _sr_flash.get("VF", 0) < 0.5 else _sr_flash.get("mu_gas")
                        _sr["thermal_conductivity"] = _sr_flash.get("k_liquid") if _sr_flash.get("VF", 0) < 0.5 else _sr_flash.get("k_gas")
                        _sr["surface_tension"] = _sr_flash.get("sigma")
                        _sr["Cp_mass"] = round(_sr_flash["Cp_mass_mix"], 2) if _sr_flash.get("Cp_mass_mix") is not None else None
                        _sr["Cv_mass"] = round(_sr_flash["Cv"], 2) if _sr_flash.get("Cv") is not None and mw > 0 else None
                        if _sr["Cv_mass"] is not None and mw > 0:
                            # Convert Cv from J/(mol·K) to J/(kg·K)
                            _sr["Cv_mass"] = round(_sr_flash["Cv"] * 1000.0 / mw, 2)
                        _sr["Z_factor"] = round(_sr_flash["Z"], 6) if _sr_flash.get("Z") is not None else None
                        # Phase-specific properties
                        _sr["phase_properties"] = {
                            "liquid": {
                                "density": round(_sr_flash["rho_liquid"], 2) if _sr_flash.get("rho_liquid") is not None else None,
                                "viscosity": _sr_flash.get("mu_liquid"),
                                "thermal_conductivity": _sr_flash.get("k_liquid"),
                                "Cp": round(_sr_flash["Cp_liquid"], 2) if _sr_flash.get("Cp_liquid") is not None else None,
                                "Cv": round(_sr_flash["Cv_liquid"], 2) if _sr_flash.get("Cv_liquid") is not None else None,
                                "enthalpy": round(_sr_flash["H_liquid"] * 1000.0 / mw / 1000.0, 4) if _sr_flash.get("H_liquid") is not None and mw > 0 else None,
                                "entropy": round(_sr_flash["S_liquid"] * 1000.0 / mw / 1000.0, 6) if _sr_flash.get("S_liquid") is not None and mw > 0 else None,
                                "Z": round(_sr_flash["Z_liquid"], 6) if _sr_flash.get("Z_liquid") is not None else None,
                                "composition": {k: round(v, 6) for k, v in zip(_sr_flash["comp_names"], _sr_flash["liquid_zs"])},
                            },
                            "vapor": {
                                "density": round(_sr_flash["rho_gas"], 4) if _sr_flash.get("rho_gas") is not None else None,
                                "viscosity": _sr_flash.get("mu_gas"),
                                "thermal_conductivity": _sr_flash.get("k_gas"),
                                "Cp": round(_sr_flash["Cp_gas"], 2) if _sr_flash.get("Cp_gas") is not None else None,
                                "Cv": round(_sr_flash["Cv_gas"], 2) if _sr_flash.get("Cv_gas") is not None else None,
                                "enthalpy": round(_sr_flash["H_gas"] * 1000.0 / mw / 1000.0, 4) if _sr_flash.get("H_gas") is not None and mw > 0 else None,
                                "entropy": round(_sr_flash["S_gas"] * 1000.0 / mw / 1000.0, 6) if _sr_flash.get("S_gas") is not None and mw > 0 else None,
                                "Z": round(_sr_flash["Z_gas"], 6) if _sr_flash.get("Z_gas") is not None else None,
                                "composition": {k: round(v, 6) for k, v in zip(_sr_flash["comp_names"], _sr_flash["gas_zs"])},
                            },
                        }
                        # Volumetric flows
                        if _sr.get("density") and _sr["density"] > 0:
                            _sr["volumetric_flow"] = round(_edge_mf / _sr["density"], 6)  # m³/s
                    stream_results[edge_id] = _sr

            engine_name = "basic"
            if _thermo_available:
                engine_name = "thermo_fallback"
            if _coolprop_available:
                engine_name = "thermo_coolprop_fallback"

            converged = not has_errors and converged_recycle
            status = "partial" if has_errors else "success"
            convergence_info: dict[str, Any] = {
                "iterations": actual_iterations,
                "converged": converged,
                "error": 0.0,
            }
            convergence_info["mass_balance_ok"] = mass_balance_ok
            convergence_info["energy_balance_ok"] = energy_balance_ok
            if tear_edges:
                convergence_info["recycle_detected"] = True
                convergence_info["tear_streams"] = len(tear_edges)
            if convergence_history:
                convergence_info["history"] = convergence_history

            return {
                "status": status,
                "engine": engine_name,
                "property_package": property_package,
                "stream_results": stream_results,
                "equipment_results": equipment_results,
                "convergence_info": convergence_info,
                "logs": logs,
            }

        except Exception as exc:
            logger.exception("Simulation failed")
            return {"status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_lmtd(
        T_h_in: float, T_h_out: float, T_c_in: float, T_c_out: float
    ) -> float:
        """Log-mean temperature difference (counter-current)."""
        dT1 = T_h_in - T_c_out
        dT2 = T_h_out - T_c_in
        if dT1 <= 0 or dT2 <= 0:
            return 0.0
        if abs(dT1 - dT2) < 1e-6:
            return dT1
        return (dT1 - dT2) / math.log(dT1 / dT2)
