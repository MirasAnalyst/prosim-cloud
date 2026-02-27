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
    from thermo import ChemicalConstantsPackage, CEOSGas, CEOSLiquid, PRMIX, FlashVL  # type: ignore[import-untyped]
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
                    "name": data.get("label", node.get("id", "")),
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

        Returns dict with: T, P, H (J/mol), VF, Cp (J/mol/K),
        gas_zs, liquid_zs, MW_mix, or None if flash fails.
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

            # Try to get binary interaction parameters
            try:
                kijs = IPDB.get_ip_asymmetric_matrix("ChemSep PR", constants.CASs, "kij")
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
            flasher = FlashVL(constants, properties, liquid=liq, gas=gas)
            state = flasher.flash(T=T, P=P, zs=zs_norm)

            vf = state.VF if state.VF is not None else 0.0

            # Compute mixture molecular weight
            MW_mix = sum(z * mw for z, mw in zip(zs_norm, constants.MWs))

            # Get enthalpy (J/mol) and Cp (J/mol/K)
            H = state.H() if callable(getattr(state, 'H', None)) else 0.0
            try:
                Cp = state.Cp() if callable(getattr(state, 'Cp', None)) else None
            except Exception:
                Cp = None

            gas_phase = getattr(state, 'gas', None)
            liquid_phase = getattr(state, 'liquid0', None)
            gas_zs = list(gas_phase.zs) if gas_phase else zs_norm
            liquid_zs = list(liquid_phase.zs) if liquid_phase else zs_norm

            return {
                "T": T,
                "P": P,
                "H": H,           # J/mol
                "VF": vf,
                "Cp": Cp,         # J/mol/K (may be None)
                "MW_mix": MW_mix,  # g/mol
                "MWs": list(constants.MWs),
                "gas_zs": gas_zs,
                "liquid_zs": liquid_zs,
                "comp_names": comp_names,
                "zs": zs_norm,
            }
        except Exception as exc:
            logger.debug("_flash_tp failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------
    @staticmethod
    def _topological_sort(
        nodes: list[dict], edges: list[dict]
    ) -> list[str]:
        """Return node IDs in topological order (upstream → downstream)."""
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
        for nid in node_ids:
            if nid not in result:
                result.append(nid)
        return result

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
        if ft is not None and float(ft) != 25:  # non-default
            feed["temperature"] = _c_to_k(float(ft))

        fp = params.get("feedPressure")
        if fp is not None and float(fp) != 101.325:
            feed["pressure"] = _kpa_to_pa(float(fp))

        ff = params.get("feedFlowRate")
        if ff is not None and float(ff) != 1.0:
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

        # Recompute enthalpy relative to T_ref
        feed["enthalpy"] = _CP_WATER * (feed["temperature"] - _T_REF)
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
            sorted_ids = self._topological_sort(nodes, edges)

            # Outlet conditions per (node_id, port_id) – in SI units internally
            port_conditions: dict[tuple[str, str], dict[str, Any]] = {}

            for nid in sorted_ids:
                node = node_map.get(nid)
                if not node:
                    continue

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
                    cp = _CP_WATER  # fallback
                    comp_names = list(comp.keys())
                    zs = [float(v) for v in comp.values()]
                    flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                    used_thermo = False

                    if T_out_c is not None and float(T_out_c) != 0:
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
                        T_out = T_in + duty_w / (mf * cp) if mf > 0 else T_in
                    else:
                        T_out = T_in + (50 if ntype == "Heater" else -50)
                        duty_w = mf * cp * (T_out - T_in)

                    eq_res["duty"] = round(_w_to_kw(duty_w), 3)
                    eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                    eq_res["pressureDrop"] = round(_pa_to_kpa(dp), 3)

                    # Get VF from flash at outlet conditions
                    vf_out = 0.0
                    if used_thermo and flash_out:
                        vf_out = flash_out.get("VF", 0.0)

                    outlet = dict(inlet)
                    outlet["temperature"] = T_out
                    outlet["pressure"] = P_out
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
                    T_in = inlet["temperature"]
                    comp = inlet.get("composition", {})
                    rho = 1000.0  # kg/m³ default water density

                    # Try getting density from thermo
                    comp_names = list(comp.keys())
                    zs = [float(v) for v in comp.values()]
                    flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                    if flash_in and flash_in.get("VF", 0) < 0.01:
                        # Liquid phase - estimate density from MW (rough)
                        pass  # keep default rho for now

                    P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in * 2))))
                    eff = float(params.get("efficiency", 75)) / 100.0
                    if eff <= 0:
                        eff = 0.75

                    # Ideal work: W_ideal = V·ΔP = m·ΔP/ρ
                    w_ideal = mf * (P_out - P_in) / rho  # W
                    w_actual = w_ideal / eff  # W

                    # Temperature rise from pump inefficiency
                    cp = _CP_WATER
                    dT_friction = (w_actual - w_ideal) / (mf * cp) if mf > 0 else 0
                    T_out = T_in + dT_friction

                    eq_res["work"] = round(_w_to_kw(w_actual), 3)
                    eq_res["efficiency"] = round(eff * 100, 1)
                    eq_res["outletPressure"] = round(_pa_to_kpa(P_out), 3)
                    eq_res["temperatureRise"] = round(dT_friction, 3)

                    outlet = dict(inlet)
                    outlet["temperature"] = T_out
                    outlet["pressure"] = P_out
                    outlet["enthalpy"] = cp * (T_out - _T_REF)
                    outlet["composition"] = dict(comp)
                    outlets["out-1"] = outlet
                    logs.append(f"{name}: work = {eq_res['work']:.1f} kW, ΔT = {dT_friction:.2f} K")

                elif ntype == "Compressor":
                    inlet = inlets[0]
                    T_in = inlet["temperature"]
                    P_in = inlet["pressure"]
                    mf = inlet["mass_flow"]
                    comp = inlet.get("composition", {})

                    P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in * 3))))
                    eff = float(params.get("efficiency", 75)) / 100.0
                    if eff <= 0:
                        eff = 0.75

                    # Try thermo for real Cp ratio (gamma)
                    gamma = 1.4  # ideal gas default
                    cp = _CP_AIR
                    comp_names = list(comp.keys())
                    zs = [float(v) for v in comp.values()]
                    flash_in = self._flash_tp(comp_names, zs, T_in, P_in, property_package)
                    used_thermo = False

                    if flash_in and flash_in.get("Cp") is not None:
                        try:
                            Cp_mol = flash_in["Cp"]  # J/(mol·K)
                            R = 8.314  # J/(mol·K)
                            Cv_mol = Cp_mol - R
                            if Cv_mol > 0:
                                gamma = Cp_mol / Cv_mol
                            mw_kg = flash_in["MW_mix"] / 1000.0
                            if mw_kg > 0:
                                cp = Cp_mol / mw_kg  # J/(kg·K)
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
                    outlet["enthalpy"] = cp * (T_out - _T_REF)
                    outlet["composition"] = dict(comp)
                    outlets["out-1"] = outlet
                    engine_note = f" (γ={gamma:.2f})" if used_thermo else ""
                    logs.append(f"{name}: work = {eq_res['work']:.1f} kW, T_out = {_k_to_c(T_out):.1f} °C{engine_note}")

                elif ntype == "Valve":
                    inlet = inlets[0]
                    T_in = inlet["temperature"]
                    P_in = inlet["pressure"]
                    mf = inlet["mass_flow"]
                    comp = inlet.get("composition", {})

                    P_out = _kpa_to_pa(float(params.get("outletPressure", _pa_to_kpa(P_in / 2))))

                    # Isenthalpic expansion – Joule-Thomson effect
                    # For ideal gas: dT = 0.  For real fluids, use CoolProp if available.
                    T_out = T_in  # default: ideal gas approximation
                    if _coolprop_available:
                        if len(comp) == 1:
                            comp_name = list(comp.keys())[0]
                            try:
                                h_in = CP.PropsSI("H", "T", T_in, "P", P_in, comp_name)
                                # Flash at same enthalpy, new pressure
                                T_out = CP.PropsSI("T", "H", h_in, "P", P_out, comp_name)
                            except Exception:
                                pass  # keep ideal gas T_out = T_in

                    eq_res["pressureDrop"] = round(_pa_to_kpa(P_in - P_out), 3)
                    eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)

                    outlet = dict(inlet)
                    outlet["temperature"] = T_out
                    outlet["pressure"] = P_out
                    outlet["enthalpy"] = _CP_WATER * (T_out - _T_REF)
                    outlet["composition"] = dict(comp)
                    outlets["out-1"] = outlet
                    logs.append(f"{name}: ΔP = {eq_res['pressureDrop']:.1f} kPa")

                elif ntype == "Mixer":
                    total_mass = 0.0
                    total_enthalpy_rate = 0.0  # W  (mass_flow * specific_enthalpy)
                    mixed_comp: dict[str, float] = {}
                    P_min = float("inf")

                    for s in inlets:
                        mf = s.get("mass_flow", 1.0)
                        h = s.get("enthalpy", 0.0)  # J/kg
                        total_mass += mf
                        total_enthalpy_rate += mf * h
                        P_min = min(P_min, s.get("pressure", 101325.0))
                        for cname, cfrac in s.get("composition", {}).items():
                            mixed_comp[cname] = mixed_comp.get(cname, 0.0) + cfrac * mf

                    if total_mass > 0:
                        h_mix = total_enthalpy_rate / total_mass
                        for cname in mixed_comp:
                            mixed_comp[cname] /= total_mass
                    else:
                        h_mix = 0.0

                    if P_min == float("inf"):
                        P_min = 101325.0

                    # User-specified outlet pressure or pressure drop
                    dp = _kpa_to_pa(float(params.get("pressureDrop", 0)))
                    P_out = P_min - dp

                    # Try thermo flash for correct outlet T
                    cp = _CP_WATER
                    T_out = _T_REF + h_mix / cp if cp > 0 else _T_REF
                    vf_out = 0.0
                    used_thermo = False

                    comp_names = list(mixed_comp.keys())
                    zs = [float(v) for v in mixed_comp.values()]
                    if comp_names and len(comp_names) > 1:
                        # Use flash to find correct T at outlet P
                        # First estimate T, then refine
                        flash_result = self._flash_tp(comp_names, zs, T_out, P_out, property_package)
                        if flash_result:
                            vf_out = flash_result.get("VF", 0.0)
                            used_thermo = True

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
                    hot = dict(_DEFAULT_FEED)
                    cold = dict(_DEFAULT_FEED)

                    for i, handle in enumerate(inlet_handles):
                        if i < len(inlets):
                            if handle == "in-hot":
                                hot = inlets[i]
                            elif handle == "in-cold":
                                cold = inlets[i]

                    # If no handles matched (old-style position-based), use index
                    if hot is _DEFAULT_FEED and len(inlets) >= 1:
                        hot = inlets[0]
                    if cold is _DEFAULT_FEED and len(inlets) >= 2:
                        cold = inlets[1]

                    # Ensure hot is actually hotter
                    if cold["temperature"] > hot["temperature"]:
                        hot, cold = cold, hot

                    T_hot_in = hot["temperature"]
                    T_cold_in = cold["temperature"]
                    mf_hot = hot["mass_flow"]
                    mf_cold = cold["mass_flow"]
                    cp_hot = 4186.0  # J/(kg·K)
                    cp_cold = 4186.0

                    dp_hot = _kpa_to_pa(float(params.get("pressureDropHot", 10)))
                    dp_cold = _kpa_to_pa(float(params.get("pressureDropCold", 10)))

                    # Use specified outlet temps if provided
                    T_hot_out_c = params.get("hotOutletTemp")
                    T_cold_out_c = params.get("coldOutletTemp")

                    if T_hot_out_c is not None:
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

                    eq_res["duty"] = round(_w_to_kw(duty), 3)
                    eq_res["hotOutletTemp"] = round(_k_to_c(T_hot_out), 2)
                    eq_res["coldOutletTemp"] = round(_k_to_c(T_cold_out), 2)
                    eq_res["LMTD"] = round(self._calc_lmtd(T_hot_in, T_hot_out, T_cold_in, T_cold_out), 2)

                    hot_out = dict(hot)
                    hot_out["temperature"] = T_hot_out
                    hot_out["pressure"] = hot["pressure"] - dp_hot
                    hot_out["enthalpy"] = cp_hot * (T_hot_out - _T_REF)
                    hot_out["composition"] = dict(hot.get("composition", {}))

                    cold_out = dict(cold)
                    cold_out["temperature"] = T_cold_out
                    cold_out["pressure"] = cold["pressure"] - dp_cold
                    cold_out["enthalpy"] = cp_cold * (T_cold_out - _T_REF)
                    cold_out["composition"] = dict(cold.get("composition", {}))

                    outlets["out-hot"] = hot_out
                    outlets["out-cold"] = cold_out
                    logs.append(f"{name}: duty = {eq_res['duty']:.1f} kW, LMTD = {eq_res['LMTD']:.1f} K")

                elif ntype == "Separator":
                    inlet = inlets[0]
                    mf = inlet["mass_flow"]
                    comp = inlet.get("composition", {})

                    # Operating conditions from parameters (user-specified T & P)
                    T_op = _c_to_k(float(params.get("temperature", _k_to_c(inlet["temperature"]))))
                    P_op = _kpa_to_pa(float(params.get("pressure", _pa_to_kpa(inlet["pressure"]))))

                    vf = 0.0  # molar vapor fraction
                    comp_names = list(comp.keys())
                    zs = [float(v) for v in comp.values()]

                    # Use shared _flash_tp helper
                    if len(comp_names) > 1:
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

                            outlets["out-1"] = {
                                "temperature": T_op,
                                "pressure": P_op,
                                "mass_flow": mf * mass_vap_frac,
                                "vapor_fraction": 1.0,
                                "enthalpy": 0.0,
                                "composition": vapor_comp,
                            }
                            outlets["out-2"] = {
                                "temperature": T_op,
                                "pressure": P_op,
                                "mass_flow": mf * (1 - mass_vap_frac),
                                "vapor_fraction": 0.0,
                                "enthalpy": 0.0,
                                "composition": liquid_comp,
                            }
                            eq_res["vaporFraction"] = round(vf, 4)
                            eq_res["massVaporFraction"] = round(mass_vap_frac, 4)
                            logs.append(f"{name}: VF = {vf:.3f} (molar), mass VF = {mass_vap_frac:.3f}")

                    if not outlets:
                        # Simple fallback: assume 10% vapor
                        vf_est = 0.1
                        outlets["out-1"] = {
                            "temperature": T_op,
                            "pressure": P_op,
                            "mass_flow": mf * vf_est,
                            "vapor_fraction": 1.0,
                            "enthalpy": 0.0,
                            "composition": comp,
                        }
                        outlets["out-2"] = {
                            "temperature": T_op,
                            "pressure": P_op,
                            "mass_flow": mf * (1 - vf_est),
                            "vapor_fraction": 0.0,
                            "enthalpy": 0.0,
                            "composition": comp,
                        }
                        eq_res["vaporFraction"] = vf_est
                        logs.append(f"{name}: estimated VF = {vf_est:.1%}")

                elif ntype == "DistillationColumn":
                    inlet = inlets[0]
                    mf = inlet["mass_flow"]
                    T_feed = inlet["temperature"]
                    P_feed = inlet["pressure"]
                    comp = inlet.get("composition", {})

                    n_stages = int(params.get("numberOfStages", 10))
                    reflux_ratio = float(params.get("refluxRatio", 1.5))
                    P_cond = _kpa_to_pa(float(params.get("condenserPressure", _pa_to_kpa(P_feed))))

                    # Sort components by volatility (boiling point)
                    comp_bp: list[tuple[str, float, float]] = []
                    for cname, cfrac in comp.items():
                        bp = 373.15  # default
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

                    # Sort by boiling point (ascending = most volatile first)
                    comp_bp.sort(key=lambda x: x[2])

                    distillate_comp: dict[str, float] = {}
                    bottoms_comp: dict[str, float] = {}
                    half = max(1, len(comp_bp) // 2)
                    for i, (cname, cfrac, _bp) in enumerate(comp_bp):
                        if i < half:
                            distillate_comp[cname] = cfrac
                        else:
                            bottoms_comp[cname] = cfrac

                    # Normalize
                    dist_total = sum(distillate_comp.values()) or 1.0
                    bott_total = sum(bottoms_comp.values()) or 1.0
                    distillate_comp = {k: v / dist_total for k, v in distillate_comp.items()}
                    bottoms_comp = {k: v / bott_total for k, v in bottoms_comp.items()}

                    # Approximate temperatures
                    T_dist = T_feed - 20  # condenser is cooler
                    T_bott = T_feed + 20  # reboiler is hotter

                    eq_res["numberOfStages"] = n_stages
                    eq_res["refluxRatio"] = reflux_ratio
                    eq_res["condenserPressure"] = round(_pa_to_kpa(P_cond), 3)

                    outlets["out-1"] = {  # Distillate (top)
                        "temperature": T_dist,
                        "pressure": P_cond,
                        "mass_flow": mf * 0.5,
                        "vapor_fraction": 0.0,
                        "enthalpy": 0.0,
                        "composition": distillate_comp,
                    }
                    outlets["out-2"] = {  # Bottoms
                        "temperature": T_bott,
                        "pressure": P_cond + 10000,  # bottoms at slightly higher P
                        "mass_flow": mf * 0.5,
                        "vapor_fraction": 0.0,
                        "enthalpy": 0.0,
                        "composition": bottoms_comp,
                    }
                    logs.append(f"{name}: {n_stages} stages, RR = {reflux_ratio:.1f}")

                elif ntype == "CSTRReactor":
                    inlet = inlets[0]
                    T_in = inlet["temperature"]
                    P_in = inlet["pressure"]
                    mf = inlet["mass_flow"]

                    volume = float(params.get("volume", 10.0))
                    T_op_c = params.get("temperature")
                    P_op_kpa = params.get("pressure")
                    duty_kw = params.get("duty", 0)

                    T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                    P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                    # Residence time
                    rho = 1000.0  # kg/m³
                    vol_flow = mf / rho if rho > 0 else 0
                    tau = volume / vol_flow if vol_flow > 0 else float("inf")

                    eq_res["volume"] = volume
                    eq_res["residenceTime"] = round(tau, 1) if tau < 1e6 else "∞"
                    eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                    eq_res["duty"] = round(float(duty_kw), 3)

                    outlet = dict(inlet)
                    outlet["temperature"] = T_out
                    outlet["pressure"] = P_out
                    outlet["enthalpy"] = _CP_WATER * (T_out - _T_REF)
                    outlet["composition"] = dict(inlet.get("composition", {}))
                    outlets["out-1"] = outlet
                    logs.append(f"{name}: V = {volume} m³, τ = {tau:.0f} s")

                elif ntype == "PFRReactor":
                    inlet = inlets[0]
                    T_in = inlet["temperature"]
                    P_in = inlet["pressure"]
                    mf = inlet["mass_flow"]

                    length = float(params.get("length", 5.0))
                    diameter = float(params.get("diameter", 0.5))
                    T_op_c = params.get("temperature")
                    P_op_kpa = params.get("pressure")

                    T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                    P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                    volume = math.pi * (diameter / 2) ** 2 * length
                    rho = 1000.0
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
                    outlet["enthalpy"] = _CP_WATER * (T_out - _T_REF)
                    outlet["composition"] = dict(inlet.get("composition", {}))
                    outlets["out-1"] = outlet
                    logs.append(f"{name}: L = {length} m, D = {diameter} m, V = {volume:.2f} m³")

                elif ntype == "ConversionReactor":
                    inlet = inlets[0]
                    T_in = inlet["temperature"]
                    P_in = inlet["pressure"]
                    mf = inlet["mass_flow"]

                    conversion = float(params.get("conversion", 80)) / 100.0
                    T_op_c = params.get("temperature")
                    P_op_kpa = params.get("pressure")
                    duty_kw = params.get("duty", 0)

                    T_out = _c_to_k(float(T_op_c)) if T_op_c is not None else T_in
                    P_out = _kpa_to_pa(float(P_op_kpa)) if P_op_kpa is not None else P_in

                    eq_res["conversion"] = round(conversion * 100, 1)
                    eq_res["outletTemperature"] = round(_k_to_c(T_out), 2)
                    eq_res["duty"] = round(float(duty_kw), 3)

                    outlet = dict(inlet)
                    outlet["temperature"] = T_out
                    outlet["pressure"] = P_out
                    outlet["enthalpy"] = _CP_WATER * (T_out - _T_REF)
                    outlet["composition"] = dict(inlet.get("composition", {}))
                    outlets["out-1"] = outlet
                    logs.append(f"{name}: X = {conversion:.0%}")

                else:
                    # Unknown equipment – pass through
                    if inlets:
                        outlets["out-1"] = dict(inlets[0])
                    logs.append(f"{name}: pass-through (no model for {ntype})")

                # Store outlet port conditions for downstream propagation
                for port_id, cond in outlets.items():
                    port_conditions[(nid, port_id)] = cond

                # Build the public result (remove internal _outlets)
                equipment_results[nid] = eq_res

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

            return {
                "status": "success",
                "engine": engine_name,
                "property_package": property_package,
                "stream_results": stream_results,
                "equipment_results": equipment_results,
                "convergence_info": {
                    "iterations": 1,
                    "converged": True,
                    "error": 0.0,
                },
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
