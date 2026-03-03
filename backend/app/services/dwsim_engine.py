import copy
import functools
import json
import logging
import math
from typing import Any

from app.core.config import settings

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
    # Try thermo library first
    if _thermo_available:
        try:
            c, _ = ChemicalConstantsPackage.from_IDs([comp_name])
            return c.MWs[0]
        except Exception:
            pass

    # Fallback to builtin table
    return _MW_BUILTIN.get(comp_name.lower(), _MW_BUILTIN.get(comp_name, 18.015))


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

    async def simulate(self, flowsheet_data: dict[str, Any]) -> dict[str, Any]:
        """Run simulation on flowsheet_data = {nodes, edges, property_package}."""
        nodes = self._normalize_nodes(flowsheet_data.get("nodes", []))
        edges = flowsheet_data.get("edges", [])
        property_package = flowsheet_data.get("property_package", "PengRobinson")
        simulation_basis = flowsheet_data.get("simulation_basis") or {}

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
        if not _thermo_available:
            return None
        if not comp_names or not zs:
            return None

        try:
            # Normalize mole fractions
            total = sum(zs)
            if total <= 0:
                return None
            zs_norm = [z / total for z in zs]

            constants, properties = ChemicalConstantsPackage.from_IDs(comp_names)

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

            # Liquid density (kg/m³) — only meaningful if liquid phase exists
            rho_liquid = None
            if liquid_phase is not None:
                try:
                    rho_liquid = liquid_phase.rho_mass()
                except Exception:
                    pass

            # Viscosity (Pa·s)
            mu_liquid = None
            mu_gas = None
            if liquid_phase is not None:
                try:
                    mu_liquid = liquid_phase.mu()
                except Exception:
                    pass
            if gas_phase is not None:
                try:
                    mu_gas = gas_phase.mu()
                except Exception:
                    pass

            return {
                "T": T,
                "P": P,
                "H": H,             # J/mol
                "S": S,             # J/(mol·K)
                "VF": vf,
                "Cp": Cp,           # J/mol/K (may be None)
                "MW_mix": MW_mix,    # g/mol
                "MWs": list(constants.MWs),
                "rho_liquid": rho_liquid,  # kg/m³ or None
                "mu_liquid": mu_liquid,    # Pa·s or None
                "mu_gas": mu_gas,          # Pa·s or None
                "gas_zs": gas_zs,
                "liquid_zs": liquid_zs,
                "comp_names": comp_names,
                "zs": zs_norm,
                "flasher": flasher,
                "constants": constants,
                "properties": properties,
            }
        except Exception as exc:
            logger.warning("_flash_tp failed for %s: %s", comp_names, exc)
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
                "Absorber": 2, "Stripper": 2,
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

            # Initialize tear stream conditions with default feed for first pass
            tear_stream_conditions: dict[str, dict[str, Any]] = {}
            for te in tear_edges:
                te_key = f"{te['source']}_{te.get('sourceHandle', 'out-1')}"
                tear_stream_conditions[te_key] = dict(_DEFAULT_FEED)

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
                        if not inlets:
                            inlets = [self._build_feed_from_params(params, property_package)]

                        # ----------------------------------------------------------
                        # Equipment-specific calculations (all SI internally)
                        # ----------------------------------------------------------
                        eq_res: dict[str, Any] = {"equipment_type": ntype, "name": name}
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
                                if ntype == "Cooler":
                                    duty_w = -abs(duty_w)
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
                            # Store real enthalpy for downstream propagation
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg_out = flash_out["MW_mix"] / 1000.0
                                outlet["enthalpy"] = flash_out["H"] / mw_kg_out  # J/kg
                            else:
                                outlet["enthalpy"] = cp * (T_out - _T_REF)
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
                            # Thermo-based outlet enthalpy for reference state consistency
                            flash_pump_out = self._flash_tp(list(comp.keys()), [float(v) for v in comp.values()], T_out, P_out, property_package)
                            if flash_pump_out and flash_pump_out.get("MW_mix", 0) > 0:
                                outlet["enthalpy"] = flash_pump_out["H"] / (flash_pump_out["MW_mix"] / 1000.0)
                            else:
                                outlet["enthalpy"] = inlet["enthalpy"] + (w_actual / mf if mf > 0 else 0)
                            outlet["composition"] = dict(comp)
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
                                elif vf_in < 0.99:
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
                                    T_out_isen = T_in * (ratio ** ((gamma - 1) / gamma))
                                    T_out = T_in + (T_out_isen - T_in) / eff
                                    work_w = mf * cp * (T_out - T_in)

                            eq_res["work"] = round(_w_to_kw(work_w), 3)
                            eq_res["efficiency"] = round(eff * 100, 1)
                            eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Outlet enthalpy: use work-consistent value when entropy method was used
                            if used_entropy and flash_in and flash_in.get("MW_mix", 0) > 0:
                                mw_kg = flash_in["MW_mix"] / 1000.0
                                h_in_kg = flash_in["H"] / mw_kg  # J/kg
                                outlet["enthalpy"] = h_in_kg + (work_w / mf if mf > 0 else 0)
                            else:
                                # TP flash fallback for gamma method
                                flash_comp_out = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                                if flash_comp_out and flash_comp_out.get("MW_mix", 0) > 0:
                                    outlet["enthalpy"] = flash_comp_out["H"] / (flash_comp_out["MW_mix"] / 1000.0)
                                else:
                                    outlet["enthalpy"] = inlet["enthalpy"] + (work_w / mf if mf > 0 else 0)
                            outlet["composition"] = dict(comp)
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
                            # Thermo-based outlet enthalpy for reference state consistency
                            flash_valve_out = self._flash_tp(comp_names, zs_v, T_out, P_out, property_package)
                            if flash_valve_out and flash_valve_out.get("MW_mix", 0) > 0:
                                outlet["enthalpy"] = flash_valve_out["H"] / (flash_valve_out["MW_mix"] / 1000.0)
                            else:
                                outlet["enthalpy"] = inlet["enthalpy"]  # isenthalpic fallback
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
                                approach_hx = max(10.0, 0.3 * dT_available)
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
                            else:
                                hot_out["enthalpy"] = cp_hot * (T_hot_out - _T_REF)
                            hot_out["composition"] = dict(hot_comp)

                            cold_out = dict(cold)
                            cold_out["temperature"] = T_cold_out
                            cold_out["pressure"] = P_cold_in - dp_cold
                            flash_cold_out = self._flash_tp(cold_comp_names, cold_zs, T_cold_out, P_cold_in - dp_cold, property_package)
                            if flash_cold_out and flash_cold_out["MW_mix"] > 0:
                                cold_out["enthalpy"] = flash_cold_out["H"] / (flash_cold_out["MW_mix"] / 1000.0)
                            else:
                                cold_out["enthalpy"] = cp_cold * (T_cold_out - _T_REF)

                            # Recompute duty from enthalpy difference (correct for phase change)
                            if flash_hot and flash_hot_out and flash_hot["MW_mix"] > 0 and flash_hot_out["MW_mix"] > 0:
                                h_hot_in = flash_hot["H"] / (flash_hot["MW_mix"] / 1000.0)
                                h_hot_out_j = hot_out["enthalpy"]
                                duty = mf_hot * (h_hot_in - h_hot_out_j)
                                # Force cold outlet enthalpy from energy balance for consistency
                                if flash_cold and flash_cold.get("MW_mix", 0) > 0 and mf_cold > 0:
                                    h_cold_in_eb = flash_cold["H"] / (flash_cold["MW_mix"] / 1000.0)
                                    cold_out["enthalpy"] = h_cold_in_eb + duty / mf_cold

                            eq_res["duty"] = round(_w_to_kw(duty), 3)
                            eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out), 2)
                            eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out), 2)
                            eq_res["LMTD"] = round(self._calc_lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out), 2)

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
                                # Recalculate duty from flash enthalpies (more accurate near phase transitions)
                                if flash_hot and flash_hot_ntu and flash_hot.get("MW_mix", 0) > 0 and flash_hot_ntu.get("MW_mix", 0) > 0:
                                    h_hot_in_ntu = flash_hot["H"] / (flash_hot["MW_mix"] / 1000.0)
                                    h_hot_out_ntu = hot_out["enthalpy"]
                                    Q_ntu = mf_hot * (h_hot_in_ntu - h_hot_out_ntu)
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

                                    # Per-phase enthalpy from flash state
                                    h_vap = 0.0
                                    h_liq = 0.0
                                    flasher = flash_result.get("flasher")
                                    if flasher:
                                        try:
                                            state = flasher.flash(T=T_op, P=P_op, zs=flash_result["zs"])
                                            gas_phase = getattr(state, 'gas', None)
                                            liq_phase = getattr(state, 'liquid0', None)
                                            if gas_phase and MW_vap > 0:
                                                h_vap = gas_phase.H() / (MW_vap / 1000.0)  # J/kg
                                            if liq_phase and MW_liq > 0:
                                                h_liq = liq_phase.H() / (MW_liq / 1000.0)  # J/kg
                                        except Exception:
                                            pass

                                    outlets["out-1"] = {
                                        "temperature": T_op,
                                        "pressure": P_op,
                                        "mass_flow": mf * mass_vap_frac,
                                        "vapor_fraction": 1.0,
                                        "enthalpy": h_vap,
                                        "composition": vapor_comp,
                                    }
                                    outlets["out-2"] = {
                                        "temperature": T_op,
                                        "pressure": P_op,
                                        "mass_flow": mf * (1 - mass_vap_frac),
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
                            inlet = inlets[0]
                            mf = inlet["mass_flow"]
                            T_feed = inlet["temperature"]
                            P_feed = inlet["pressure"]
                            comp = inlet.get("composition", {})

                            n_stages = int(params.get("numberOfStages", 10))
                            reflux_ratio = float(params.get("refluxRatio", 1.5))
                            P_cond = _kpa_to_pa(float(params.get("condenserPressure", _pa_to_kpa(P_feed))))

                            comp_names = list(comp.keys())
                            zs = [float(v) for v in comp.values()]
                            fug_ok = False

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
                                            # Using 99% recovery for LK and HK
                                            N_min = math.log((0.99 / 0.01) ** 2) / math.log(alpha_lk_hk)

                                            # Preliminary component split using N_min (for Underwood R_min calc)
                                            d_hk_over_b_hk_pre = 0.01 / 0.99
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
                                            # Assume 99% HK recovery in bottoms
                                            d_hk_over_b_hk = 0.01 / 0.99
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
                                            frac_bott = 1.0 - frac_dist

                                            # Flash distillate and bottoms for temperatures
                                            P_bott = P_cond + N_eff * 1000.0  # ~1 kPa per stage
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
                                            # Q_cond = V_top * (h_vap - h_dist), V_top = D * (R + 1)
                                            Q_cond = D * (reflux_ratio + 1) * (h_vap_dist - h_dist) if flash_d_out else 0.0
                                            # Q_reb from overall energy balance: F*hF + Q_reb = D*hD + B*hB + Q_cond
                                            Q_reb = D * h_dist + B * h_bott + Q_cond - mf * h_feed if (flash_d_out or flash_b_out) else 0.0
                                            # Reboiler must add heat — enforce Q_reb >= 0
                                            if Q_reb < 0:
                                                logs.append(
                                                    f"WARNING: {name} computed Q_reb={_w_to_kw(Q_reb):.1f} kW (negative) "
                                                    f"— using hvap-based estimate"
                                                )
                                                Q_reb = B * _estimate_hvap(bottoms_comp)

                                            # LK purity in distillate
                                            lk_purity = distillate_comp.get(comp_names[lk_idx], 0.0)

                                            eq_res["numberOfStages"] = n_stages
                                            eq_res["refluxRatio"] = reflux_ratio
                                            eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)
                                            eq_res["N_min"] = round(N_min, 1)
                                            eq_res["R_min"] = round(R_min, 3)
                                            eq_res["N_eff"] = round(N_eff, 1)
                                            eq_res["lightKeyPurity"] = round(lk_purity * 100, 1)
                                            eq_res["lightKey"] = comp_names[lk_idx]
                                            eq_res["heavyKey"] = comp_names[hk_idx]
                                            eq_res["condenserDuty"] = round(_w_to_kw(Q_cond), 1)
                                            eq_res["reboilerDuty"] = round(_w_to_kw(Q_reb), 1)
                                            eq_res["distillateTemperature"] = round(_k_to_c(T_dist), 1)
                                            eq_res["bottomsTemperature"] = round(_k_to_c(T_bott), 1)

                                            # M6: Partial condenser support
                                            condenser_type = str(params.get("condenserType", "total")).lower()

                                            # Auto-detect cryogenic distillation: switch to partial condenser
                                            if condenser_type == "total" and T_dist < 123.15:  # -150°C in K
                                                condenser_type = "partial"
                                                logs.append(
                                                    f"WARNING: {name} distillate bubble point {_k_to_c(T_dist):.0f}°C — "
                                                    f"auto-switched to partial condenser for cryogenic column"
                                                )
                                            elif condenser_type == "total" and T_dist < 173.15:  # -100°C in K
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
                                            fug_ok = True
                                            logs.append(
                                                f"{name}: FUG — N_min={N_min:.1f}, R_min={R_min:.3f}, N_eff={N_eff:.1f}, "
                                                f"LK purity={lk_purity:.1%}, T_dist={_k_to_c(T_dist):.1f}°C, T_bott={_k_to_c(T_bott):.1f}°C"
                                            )
                                except Exception as exc:
                                    logger.warning("Distillation FUG failed: %s, using boiling-point fallback", exc)
                                    logs.append(f"WARNING: {name} FUG method failed ({exc}), using boiling-point fallback")

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
                                flash_b_fb = self._flash_tp(b_names_fb, b_zs_fb, T_bott, P_cond + 10000, property_package)
                                if flash_b_fb and flash_b_fb.get("MW_mix", 0) > 0:
                                    h_bott_fb = flash_b_fb["H"] / (flash_b_fb["MW_mix"] / 1000.0)

                                eq_res["numberOfStages"] = n_stages
                                eq_res["refluxRatio"] = reflux_ratio
                                eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)

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
                                    "pressure": P_cond + 10000,
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
                            eq_res["duty"] = round(float(duty_kw), 3)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Thermo-based enthalpy (T3-01)
                            flash_out = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg = flash_out["MW_mix"] / 1000.0
                                outlet["enthalpy"] = flash_out["H"] / mw_kg
                            else:
                                outlet["enthalpy"] = _estimate_cp(comp) * (T_out - _T_REF)
                            outlet["composition"] = dict(comp)

                            # Arrhenius kinetics
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
                                out_comp = dict(comp)
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
                                    outlet["composition"] = out_comp
                                    logs.append(f"  CSTR: {key_r} z={z_before:.4f} → {out_comp.get(key_r, 0):.4f}")

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

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            # Thermo-based enthalpy (T3-01)
                            flash_pfr = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                            if flash_pfr and flash_pfr.get("MW_mix", 0) > 0:
                                mw_kg = flash_pfr["MW_mix"] / 1000.0
                                outlet["enthalpy"] = flash_pfr["H"] / mw_kg
                            else:
                                outlet["enthalpy"] = _estimate_cp(comp) * (T_out - _T_REF)
                            outlet["composition"] = dict(comp)

                            # PFR Ergun pressure drop
                            Ea_kj = float(params.get("activationEnergy", 0))
                            A_pre = float(params.get("preExpFactor", 0))
                            eps = float(params.get("bedVoidFraction", 0.4))
                            d_p = float(params.get("particleDiameter", 0.003))

                            if d_p > 0 and eps > 0:
                                mu = 1e-5  # Pa·s (gas viscosity approx)
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
                                P_out_pfr = max(P_out - dp_total, 10000.0)  # Floor: 10 kPa
                                outlet["pressure"] = P_out_pfr
                                eq_res["pressureDrop"] = round(_pa_to_kpa(dp_total), 2)
                                logs.append(f"  PFR Ergun ΔP = {_pa_to_kpa(dp_total):.1f} kPa")

                            if Ea_kj > 0 and A_pre > 0:
                                R_gas = 8.314e-3
                                k_rate = A_pre * math.exp(-Ea_kj / (R_gas * T_out))
                                X_pfr = 1.0 - math.exp(-k_rate * tau) if tau < 1e6 else 0.999
                                conversion_val = min(X_pfr, 0.999)
                                eq_res["conversion"] = round(conversion_val * 100, 1)
                                eq_res["rateConstant"] = round(k_rate, 4)
                                logs.append(f"  PFR Arrhenius: k={k_rate:.4g} 1/s, X={X_pfr:.4f}")

                                # H1: Apply conversion to outlet composition
                                out_comp = dict(comp)
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
                                    outlet["composition"] = out_comp
                                    logs.append(f"  PFR: {key_r} z={z_before:.4f} → {out_comp.get(key_r, 0):.4f}")

                            outlets["out-1"] = outlet
                            logs.append(f"{name}: L = {length} m, D = {diameter} m, V = {volume:.2f} m³")

                        elif ntype == "ConversionReactor":
                            inlet = inlets[0]
                            T_in = inlet["temperature"]
                            P_in = inlet["pressure"]
                            mf = inlet["mass_flow"]
                            in_comp = inlet.get("composition", {})

                            conversion = float(params.get("conversion", 80)) / 100.0
                            conversion = max(0.0, min(1.0, conversion))
                            T_op_c = params.get("temperature")
                            P_op_kpa = params.get("pressure")
                            duty_kw = params.get("duty", 0)

                            T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                            P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                            # Apply conversion to key reactant (T2-02b)
                            out_comp = dict(in_comp)
                            if out_comp:
                                key_reactant_param = params.get("keyReactant", "")
                                if key_reactant_param and key_reactant_param in out_comp:
                                    key_reactant = key_reactant_param
                                else:
                                    key_reactant = list(out_comp.keys())[0]
                                z_before = out_comp[key_reactant]
                                consumed = z_before * conversion
                                out_comp[key_reactant] = z_before - consumed
                                # Add consumed moles to "products" pseudo-component
                                out_comp["products"] = out_comp.get("products", 0.0) + consumed
                                # Renormalize
                                total_z = sum(out_comp.values())
                                if total_z > 0:
                                    out_comp = {k: v / total_z for k, v in out_comp.items()}
                                logs.append(f"{name}: key reactant '{key_reactant}' z={z_before:.4f} → {out_comp.get(key_reactant, 0):.4f}")
                                if consumed > 1e-6:
                                    logs.append(
                                        f"WARNING: {name} uses 'products' pseudo-component — energy balance will be "
                                        f"approximate (missing heat of reaction). Specify real product species for accuracy."
                                    )

                            # Flash outlet for enthalpy (T3-07: filter pseudo-components)
                            clean_comp = _clean_composition(out_comp)
                            out_comp_names = list(clean_comp.keys())
                            out_zs = [float(v) for v in clean_comp.values()]
                            flash_out = self._flash_tp(out_comp_names, out_zs, T_out, P_out, property_package)

                            eq_res["conversion"] = round(conversion * 100, 1)
                            eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                            eq_res["duty"] = round(float(duty_kw), 3)

                            outlet = dict(inlet)
                            outlet["temperature"] = T_out
                            outlet["pressure"] = P_out
                            if flash_out and flash_out.get("MW_mix", 0) > 0:
                                mw_kg = flash_out["MW_mix"] / 1000.0
                                outlet["enthalpy"] = flash_out["H"] / mw_kg
                            else:
                                outlet["enthalpy"] = _estimate_cp(out_comp) * (T_out - _T_REF)
                            outlet["composition"] = out_comp

                            # Multi-reaction support
                            reaction_count = int(params.get("reactionCount", 1))
                            reactions_json = params.get("reactions", "[]")
                            if reaction_count > 1 and reactions_json and reactions_json != "[]":
                                try:
                                    reactions = json.loads(reactions_json) if isinstance(reactions_json, str) else reactions_json
                                    current_zs = dict(out_comp)
                                    for rxn in reactions[:5]:
                                        reactant = rxn.get("reactant", "")
                                        conv_r = float(rxn.get("conversion", 0))
                                        if reactant in current_zs:
                                            reacted = current_zs[reactant] * conv_r
                                            current_zs[reactant] = max(0, current_zs[reactant] - reacted)
                                            products = rxn.get("products", {})
                                            for prod, stoich in products.items():
                                                current_zs[prod] = current_zs.get(prod, 0) + reacted * float(stoich)
                                    total_z = sum(current_zs.values())
                                    if total_z > 0:
                                        current_zs = {k: v / total_z for k, v in current_zs.items()}
                                    outlet["composition"] = current_zs
                                    eq_res["reactionCount"] = len(reactions)
                                    logs.append(f"  Multi-reaction: {len(reactions)} reactions applied")
                                except Exception as e:
                                    logs.append(f"WARNING: Multi-reaction parse error: {e}")

                            outlets["out-1"] = outlet
                            logs.append(f"{name}: X = {conversion:.0%}")

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
                            if feed2 is None:
                                if ntype == "Stripper":
                                    # Reboiled stripper: no external stripping gas — zero mass input
                                    feed2 = dict(_DEFAULT_FEED)
                                    feed2["mass_flow"] = 0.0
                                    logs.append(f"{name}: operating as reboiled stripper (single feed, no stripping gas)")
                                else:
                                    feed2 = dict(_DEFAULT_FEED)

                            n_stages = int(params.get("numberOfStages", 10))
                            P_op_kpa = params.get("pressure")
                            P_op = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else feed1["pressure"]

                            mf1 = feed1["mass_flow"]
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
                            if acid_gases_present and ntype == "Absorber":
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
                            total_in = mf1 + mf2
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
                                T_out1 = T1  # lean gas exits near gas feed temp
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
                            else:
                                T_out1 = T_avg
                                T_out2 = T_avg

                            eq_res["numberOfStages"] = n_stages
                            eq_res["pressure"] = round(_pa_to_kpa(P_op), 3)
                            # Store heat of absorption as negative duty (exothermic)
                            if ntype == "Absorber" and Q_abs > 0:
                                eq_res["duty"] = round(-Q_abs, 3)  # kW, negative = exothermic

                            # Flash outlet streams for real enthalpies and VF (H7)
                            flash_o1 = self._flash_tp(list(out1_comp.keys()), list(out1_comp.values()), T_out1, P_op, property_package)
                            flash_o2 = self._flash_tp(list(out2_comp.keys()), list(out2_comp.values()), T_out2, P_op, property_package)
                            h_o1 = flash_o1["H"] / (flash_o1["MW_mix"] / 1000.0) if flash_o1 and flash_o1.get("MW_mix", 0) > 0 else feed1.get("enthalpy", 0.0)
                            h_o2 = flash_o2["H"] / (flash_o2["MW_mix"] / 1000.0) if flash_o2 and flash_o2.get("MW_mix", 0) > 0 else feed2.get("enthalpy", 0.0)
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

                            # Composition: identify heaviest component as "solids"
                            gas_comp_cyc = dict(comp)
                            solids_comp_cyc = dict(comp)
                            if comp and len(comp) >= 2:
                                mws_cyc = [(c, _get_mw(c)) for c in comp.keys()]
                                mws_cyc.sort(key=lambda x: x[1], reverse=True)
                                heaviest_c = mws_cyc[0][0]
                                # Gas outlet: reduced heaviest component
                                gc = dict(comp)
                                gc[heaviest_c] = max(0, comp.get(heaviest_c, 0) * (1 - efficiency))
                                gt = sum(gc.values()) or 1
                                gas_comp_cyc = {k: v / gt for k, v in gc.items()}
                                # Solids outlet: enriched in heaviest
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

                            # Flash at T,P — _flash_tp returns a dict
                            VF = 0.0
                            vapor_comp = dict(comp)
                            liquid_comp = dict(comp)
                            flash_result = None
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

                            # H3: Split liquid into light/heavy — user-configurable fraction
                            # Polarity/density-based assignment: aqueous compounds → heavy liquid,
                            # hydrocarbons → light liquid (matches HYSYS/DWSIM convention)
                            _AQUEOUS_COMPOUNDS = {
                                "water", "monoethanolamine", "diethanolamine",
                                "methanol", "ethanol", "1-propanol", "2-propanol",
                                "acetic acid", "formic acid", "formaldehyde",
                                "ammonia", "hydrogen sulfide", "carbon dioxide",
                            }
                            light_zs = dict(liquid_comp)
                            heavy_zs = dict(liquid_comp)
                            light_frac = float(params.get("lightLiquidFraction", 0.5))
                            light_frac = max(0.0, min(1.0, light_frac))
                            if len(comp_names) >= 2 and liquid_flow > 0:
                                liq_zs_list = [liquid_comp.get(c, 0.0) for c in comp_names]
                                l_sum, h_sum = 0.0, 0.0
                                lz, hz = {}, {}
                                for c, z in zip(comp_names, liq_zs_list):
                                    if z < 1e-15:
                                        continue
                                    c_lower = c.lower()
                                    is_aqueous = c_lower in _AQUEOUS_COMPOUNDS
                                    if not is_aqueous:
                                        # Non-aqueous: check pure liquid density > 900 kg/m³
                                        try:
                                            flash_pure = self._flash_tp([c], [1.0], T_in, P_in, property_package)
                                            if flash_pure and flash_pure.get("rho_liquid") and flash_pure["rho_liquid"] > 900:
                                                is_aqueous = True
                                        except Exception:
                                            pass
                                    if is_aqueous:
                                        hz[c] = z
                                        h_sum += z
                                    else:
                                        lz[c] = z
                                        l_sum += z
                                # Dissolved gases (not classified): distribute proportionally
                                for c, z in zip(comp_names, liq_zs_list):
                                    if z >= 1e-15 and c not in lz and c not in hz:
                                        if l_sum + h_sum > 0:
                                            frac_l = l_sum / (l_sum + h_sum)
                                            lz[c] = z * frac_l
                                            hz[c] = z * (1 - frac_l)
                                            l_sum += lz[c]
                                            h_sum += hz[c]
                                if l_sum > 0:
                                    light_zs = {c: v / l_sum for c, v in lz.items()}
                                if h_sum > 0:
                                    heavy_zs = {c: v / h_sum for c, v in hz.items()}
                                if not params.get("lightLiquidFraction"):
                                    light_frac = l_sum / (l_sum + h_sum) if (l_sum + h_sum) > 0 else 0.5
                                    logs.append(f"WARNING: {name} liquid split is polarity-based heuristic — specify lightLiquidFraction for accuracy")

                            eq_res["vaporFraction"] = round(VF, 4)
                            eq_res["vaporFlow"] = round(vapor_flow, 4)
                            eq_res["lightLiquidFlow"] = round(liquid_flow * light_frac, 4)
                            eq_res["heavyLiquidFlow"] = round(liquid_flow * (1 - light_frac), 4)

                            # Per-phase enthalpy from flash (same pattern as Separator)
                            h_vap_3p = inlet.get("enthalpy", 0.0)
                            h_liq_3p = inlet.get("enthalpy", 0.0)
                            if flash_result:
                                flasher_3p = flash_result.get("flasher")
                                if flasher_3p:
                                    try:
                                        state_3p = flasher_3p.flash(T=T_in, P=P_in, zs=flash_result["zs"])
                                        gas_phase_3p = getattr(state_3p, 'gas', None)
                                        liq_phase_3p = getattr(state_3p, 'liquid0', None)
                                        MWs_3p = flash_result["MWs"]
                                        gas_zs_3p = flash_result["gas_zs"]
                                        liq_zs_3p = flash_result["liquid_zs"]
                                        MW_vap_3p = sum(z * mw for z, mw in zip(gas_zs_3p, MWs_3p))
                                        MW_liq_3p = sum(z * mw for z, mw in zip(liq_zs_3p, MWs_3p))
                                        if gas_phase_3p and MW_vap_3p > 0:
                                            h_vap_3p = gas_phase_3p.H() / (MW_vap_3p / 1000.0)
                                        if liq_phase_3p and MW_liq_3p > 0:
                                            h_liq_3p = liq_phase_3p.H() / (MW_liq_3p / 1000.0)
                                    except Exception:
                                        pass

                            outlets["out-1"] = {"temperature": T_in, "pressure": P_in, "mass_flow": vapor_flow, "vapor_fraction": 1.0, "enthalpy": h_vap_3p, "composition": vapor_comp}
                            outlets["out-2"] = {"temperature": T_in, "pressure": P_in, "mass_flow": liquid_flow * light_frac, "vapor_fraction": 0.0, "enthalpy": h_liq_3p, "composition": light_zs}
                            outlets["out-3"] = {"temperature": T_in, "pressure": P_in, "mass_flow": liquid_flow * (1 - light_frac), "vapor_fraction": 0.0, "enthalpy": h_liq_3p, "composition": heavy_zs}
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
                                if sol_in is not None and sol_out is not None and sol_in > sol_out:
                                    # crystal_frac = fraction of solute that crystallizes
                                    crystal_frac = max(0.0, min(0.95, (sol_in - sol_out) / sol_in))
                                    logs.append(f"  Crystallizer: solubility-based yield, sol@{T_in_c:.0f}°C={sol_in:.1f}, sol@{cryst_temp:.0f}°C={sol_out:.1f}")
                                else:
                                    # Empirical fallback
                                    delta_T = max(0, T_in - T_cryst)
                                    crystal_frac = min(0.9, delta_T / 200.0)
                                    if sol_in is None:
                                        logs.append(f"WARNING: {name} no solubility data for '{key_comp}' — using empirical ΔT/200 correlation")

                                # Convert mole fraction to mass fraction for mass flow calc
                                mw_key = _get_mw(key_comp)
                                mw_mix_cryst = sum(z * _get_mw(c) for c, z in comp.items())
                                w_key = (zs[key_idx] * mw_key / mw_mix_cryst) if mw_mix_cryst > 0 else zs[key_idx]
                                crystal_flow = mf * w_key * crystal_frac
                                mother_flow = mf - crystal_flow
                                crystal_zs = {key_comp: 1.0}
                                m_zs = dict(comp)
                                m_zs[key_comp] = zs[key_idx] * (1 - crystal_frac)
                                mt = sum(m_zs.values()) or 1
                                mother_zs = {c: v / mt for c, v in m_zs.items()}
                            else:
                                crystal_flow = 0.0
                                mother_flow = mf

                            eq_res["crystalYield"] = round(crystal_frac * 100, 1)
                            eq_res["crystallizationTemp"] = cryst_temp

                            outlets["out-1"] = {"temperature": T_cryst, "pressure": P_in, "mass_flow": crystal_flow, "vapor_fraction": 0.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": crystal_zs}
                            outlets["out-2"] = {"temperature": T_cryst, "pressure": P_in, "mass_flow": mother_flow, "vapor_fraction": 0.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": mother_zs}
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

                            outlets["out-1"] = {"temperature": T_in, "pressure": P_in, "mass_flow": dry_flow, "vapor_fraction": 0.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": dry_zs}
                            outlets["out-2"] = {"temperature": T_in + 20, "pressure": P_in, "mass_flow": moisture_flow, "vapor_fraction": 1.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": vapor_zs}
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

                            # Composition: cake enriched in heaviest component
                            cake_comp = dict(comp)
                            filtrate_comp = dict(comp)
                            if comp and len(comp) >= 2:
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

                            outlets["out-1"] = {"temperature": T_in, "pressure": P_out, "mass_flow": filtrate_flow, "vapor_fraction": 0.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": filtrate_comp}
                            outlets["out-2"] = {"temperature": T_in, "pressure": P_in, "mass_flow": cake_flow, "vapor_fraction": 0.0, "enthalpy": inlet.get("enthalpy", 0.0), "composition": cake_comp}
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
                            hyd_result = compute_hydraulics(
                                mass_flow_rate=mf, density=rho, viscosity=mu,
                                length=pipe_length, diameter=pipe_dia,
                                roughness=pipe_rough, elevation=pipe_elev,
                                elbows_90=n_elbows, tees=n_tees, gate_valves=n_gvalves,
                            )

                            dp_pa = hyd_result.get("pressure_drop_kpa", 0) * 1000.0
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
                # Skip DistillationColumn (internal condenser/reboiler), Cyclone/Filter (heuristic splits),
                # ConversionReactor/PFRReactor ("products" pseudo-component has no thermo properties)
                _EB_SKIP = ("DistillationColumn", "Cyclone", "Filter", "ConversionReactor", "PFRReactor")
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
                    mf = 0.0
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf = c.get("mass_flow", 0.0)
                                break
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
                            A_min = mf / (rho_V * V_max) if rho_V > 0 else 1.0
                            D_min = math.sqrt(4 * A_min / math.pi)
                            sizing["diameter_m"] = round(D_min, 3)
                            sizing["K_sb"] = K_sb
                            sizing["V_max_m_s"] = round(V_max, 3)

                elif ntype == "HeatExchanger":
                    duty_kw = eq_r.get("duty", 0)
                    lmtd = eq_r.get("LMTD", 0)
                    if duty_kw and lmtd and float(lmtd) > 0:
                        U = 500.0  # W/(m²·K), typical liquid-liquid
                        Q_w = abs(_kw_to_w(float(duty_kw)))
                        A = Q_w / (U * float(lmtd))
                        sizing["area_m2"] = round(A, 2)
                        sizing["U_assumed"] = U

                elif ntype == "DistillationColumn":
                    # Fair's flooding correlation (simplified)
                    mf_val = 0.0
                    for _src, _sh, _th in upstream.get(nid, []):
                        for _tgt, sh2, _th2 in downstream.get(_src, []):
                            if _tgt == nid:
                                c = port_conditions.get((_src, sh2))
                                if c:
                                    mf_val = c.get("mass_flow", 0.0)
                                break
                    if mf_val > 0:
                        # Approximate: D = sqrt(4*V_dot / (pi * V_flood * 0.8))
                        V_flood = 1.5  # m/s approximate
                        rho_V_approx = 2.0  # kg/m³
                        V_dot = mf_val / max(rho_V_approx, 0.1)
                        A_col = V_dot / (V_flood * 0.8)
                        D_col = math.sqrt(4 * max(A_col, 0.01) / math.pi)
                        sizing["diameter_m"] = round(D_col, 3)
                        sizing["flooding_velocity_m_s"] = V_flood

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
                            "name": ds_name, "error": "Missing target or manipulated variable",
                        }
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
                    # Deep copy nodes to avoid mutating shared parameters
                    ds_nodes = copy.deepcopy(nodes)

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
                    stream_results[edge_id] = {
                        "temperature": round(_k_to_c(cond["temperature"]), 2),
                        "pressure": round(_pa_to_kpa(cond["pressure"]), 3),
                        "flowRate": round(_edge_mf, 4),
                        "vapor_fraction": round(cond.get("vapor_fraction", 0.0), 4),
                        "composition": _edge_comp,
                        "enthalpy": _edge_h_kj,
                        **_edge_cp,
                    }

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
