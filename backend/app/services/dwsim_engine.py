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

        if not nodes:
            return {"status": "error", "error": "No equipment nodes in flowsheet"}

        if self.use_dwsim:
            try:
                return await self._simulate_dwsim(nodes, edges)
            except Exception as exc:
                logger.exception("DWSIM simulation failed, trying fallback")

        # Fallback: basic calculations (works with or without thermo/CoolProp)
        return await self._simulate_basic(nodes, edges, property_package)

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

            # Try to get binary interaction parameters — match BIP source to EOS
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

            # Select EOS based on property package
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
    def _build_feed_from_params(params: dict[str, Any]) -> dict[str, Any]:
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
        flash = DWSIMEngine._flash_tp(comp_names, zs, feed["temperature"], feed["pressure"])
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
    ) -> dict[str, Any]:
        try:
            logs: list[str] = []
            equipment_results: dict[str, Any] = {}
            has_errors = False

            # NRTL warning (T2-18)
            if property_package == "NRTL":
                logs.append(
                    "WARNING: NRTL not implemented, using Peng-Robinson fallback. "
                    "Results may be inaccurate for non-ideal liquid mixtures."
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
                downstream.setdefault(src, []).append((tgt, sh, th))
                upstream.setdefault(tgt, []).append((src, sh, th))

            node_map = {n["id"]: n for n in nodes}
            sorted_ids, cycle_ids = self._topological_sort(nodes, edges)

            # Recycle loop detection (T2-03)
            if cycle_ids:
                cycle_names = [node_map.get(cid, {}).get("name", cid) for cid in cycle_ids]
                logs.append(
                    f"WARNING: Recycle loop detected involving: {', '.join(cycle_names)}. "
                    "Tear-stream convergence not implemented — results for cycle nodes may be inaccurate."
                )

            # Outlet conditions per (node_id, port_id) – in SI units internally
            port_conditions: dict[tuple[str, str], dict[str, Any]] = {}

            for nid in sorted_ids:
                node = node_map.get(nid)
                if not node:
                    continue

                try:
                    ntype = node.get("type", "")
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
                        inlets = [self._build_feed_from_params(params)]

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
                        eff = float(params.get("efficiency", 75)) / 100.0
                        if eff <= 0:
                            eff = 0.75

                        # Ideal work: W_ideal = V·ΔP = m·ΔP/ρ
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

                        P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in * 3))))
                        if P_out < P_in:
                            logs.append(f"WARNING: {name} P_out < P_in — this is expansion, not compression")

                        eff = float(params.get("efficiency", 75)) / 100.0
                        if eff <= 0:
                            eff = 0.75

                        comp_names = list(comp.keys())
                        zs = [float(v) for v in comp.values()]
                        flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                        used_thermo = False
                        used_entropy = False

                        if flash_in:
                            vf_in = flash_in.get("VF", 1.0)
                            if vf_in < 0.5:
                                logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — compressor expects vapor feed")
                            elif vf_in < 0.99:
                                logs.append(f"WARNING: {name} inlet VF={vf_in:.2f} — wet gas in compressor feed")

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
                            # Fallback: gamma-based method with composition-weighted gamma (T2-04)
                            gamma = 1.4
                            if comp:
                                gamma_sum = 0.0
                                z_sum = 0.0
                                for c_name, z_frac in comp.items():
                                    g = _GAMMA_TABLE.get(c_name.lower(), _GAMMA_TABLE.get(c_name, 1.4))
                                    gamma_sum += z_frac * g
                                    z_sum += z_frac
                                if z_sum > 0:
                                    gamma = gamma_sum / z_sum
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
                        # Thermo-based outlet enthalpy for reference state consistency
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

                        # Estimate T for fallback
                        cp_est = _estimate_cp(mixed_comp)
                        T_out = _T_REF + h_mix / cp_est if cp_est > 0 else _T_REF

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

                        if T_hot_out_c is not None and T_cold_out_c is not None:
                            T_hot_out = _c_to_k(float(T_hot_out_c))
                            T_cold_out = _c_to_k(float(T_cold_out_c))
                            duty_hot = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                            duty_cold = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                            duty = duty_hot  # use hot-side duty as primary
                            if max(abs(duty_hot), abs(duty_cold)) > 0:
                                imbalance = abs(duty_hot - duty_cold) / max(abs(duty_hot), abs(duty_cold))
                                if imbalance > 0.05:
                                    logs.append(
                                        f"WARNING: {name} specified outlet temps imply {imbalance:.0%} energy imbalance "
                                        f"— adjusting cold outlet to match hot-side duty"
                                    )
                                    T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                        elif T_hot_out_c is not None:
                            T_hot_out = _c_to_k(float(T_hot_out_c))
                            duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                            T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in
                        elif T_cold_out_c is not None:
                            T_cold_out = _c_to_k(float(T_cold_out_c))
                            duty = mf_cold * cp_cold * (T_cold_out - T_cold_in)
                            T_hot_out = T_hot_in - duty / (mf_hot * cp_hot) if mf_hot * cp_hot > 0 else T_hot_in
                        else:
                            # Default: 10 K approach on hot side
                            T_hot_out = T_cold_in + 10.0
                            duty = mf_hot * cp_hot * (T_hot_in - T_hot_out)
                            T_cold_out = T_cold_in + duty / (mf_cold * cp_cold) if mf_cold * cp_cold > 0 else T_cold_in

                        # Temperature cross check
                        if T_hot_out < T_cold_in or T_cold_out > T_hot_in:
                            logs.append(f"WARNING: {name} has a temperature cross – results may be infeasible")

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

                        eq_res["duty"] = round(_w_to_kw(duty), 3)
                        eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out), 2)
                        eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out), 2)
                        eq_res["LMTD"] = round(self._calc_lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out), 2)
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

                                    # Identify light key (highest K) and heavy key (lowest K)
                                    lk_idx = K_vals.index(max(K_vals))
                                    hk_idx = K_vals.index(min(K_vals))

                                    K_lk = K_vals[lk_idx]
                                    K_hk = K_vals[hk_idx]

                                    # Relative volatilities: alpha_i = K_i / K_hk
                                    alpha_lk_hk = K_lk / K_hk if K_hk > 1e-12 else 10.0
                                    alphas = [K / K_hk if K_hk > 1e-12 else 1.0 for K in K_vals]

                                    if alpha_lk_hk > 1.01:
                                        # Fenske: N_min
                                        # Using 99% recovery for LK and HK
                                        N_min = math.log((0.99 / 0.01) ** 2) / math.log(alpha_lk_hk)

                                        # Underwood: R_min (simplified)
                                        R_min = 1.0 / (alpha_lk_hk - 1.0)

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
                                        h_feed = inlet.get("enthalpy", 0.0)
                                        D = mf * frac_dist  # distillate mass flow
                                        B = mf * frac_bott  # bottoms mass flow
                                        # Estimate vapor enthalpy at condenser from heat of vaporization
                                        h_vap_dist = h_dist + _estimate_hvap(distillate_comp)
                                        # Q_cond = V_top * (h_vap - h_dist), V_top = D * (R + 1)
                                        Q_cond = D * (reflux_ratio + 1) * (h_vap_dist - h_dist) if flash_d_out else 0.0
                                        # Q_reb from overall energy balance: F*hF + Q_reb = D*hD + B*hB + Q_cond
                                        Q_reb = D * h_dist + B * h_bott + Q_cond - mf * h_feed if (flash_d_out or flash_b_out) else 0.0

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

                                        outlets["out-1"] = {
                                            "temperature": T_dist,
                                            "pressure": P_cond,
                                            "mass_flow": mf * frac_dist,
                                            "vapor_fraction": 0.0,
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

                            eq_res["numberOfStages"] = n_stages
                            eq_res["refluxRatio"] = reflux_ratio
                            eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)

                            outlets["out-1"] = {
                                "temperature": T_dist,
                                "pressure": P_cond,
                                "mass_flow": mf * 0.5,
                                "vapor_fraction": 0.0,
                                "enthalpy": 0.0,
                                "composition": distillate_comp,
                            }
                            outlets["out-2"] = {
                                "temperature": T_bott,
                                "pressure": P_cond + 10000,
                                "mass_flow": mf * 0.5,
                                "vapor_fraction": 0.0,
                                "enthalpy": 0.0,
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

                        # Apply conversion to first component (key reactant) (T2-02b)
                        out_comp = dict(in_comp)
                        if out_comp:
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
                        outlets["out-1"] = outlet
                        logs.append(f"{name}: X = {conversion:.0%}")

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
                except Exception as exc:
                    name = node.get("name", nid)
                    logger.exception("Equipment %s (%s) failed", name, nid)
                    logs.append(f"ERROR: {name} simulation failed: {exc}")
                    equipment_results[nid] = {"error": str(exc)}
                    has_errors = True

            # Build stream results from edges (convert to frontend units)
            stream_results: dict[str, Any] = {}
            for edge in edges:
                src = edge.get("source", "")
                sh = edge.get("sourceHandle", "out-1")
                edge_id = edge.get("id", f"{src}_{sh}")
                cond = port_conditions.get((src, sh))
                if cond:
                    stream_results[edge_id] = {
                        "temperature": round(_k_to_c(cond["temperature"]), 2),
                        "pressure": round(_pa_to_kpa(cond["pressure"]), 3),
                        "flowRate": round(cond["mass_flow"], 4),
                        "vapor_fraction": round(cond.get("vapor_fraction", 0.0), 4),
                        "composition": cond.get("composition", {}),
                    }

            engine_name = "basic"
            if _thermo_available:
                engine_name = "thermo_fallback"
            if _coolprop_available:
                engine_name = "thermo_coolprop_fallback"

            converged = not has_errors and not cycle_ids
            status = "partial" if has_errors else "success"
            convergence_info: dict[str, Any] = {
                "iterations": 1,
                "converged": converged,
                "error": 0.0,
            }
            if cycle_ids:
                convergence_info["recycle_detected"] = True

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
