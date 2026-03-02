"""Pseudo-dynamic simulation engine.

Algorithm: (1) run initial steady state, (2) apply step disturbance,
(3) run new steady state, (4) interpolate with first-order lag τ = V·ρ/F.
"""
import copy
import math
import logging
from typing import Any

from app.services.dwsim_engine import DWSIMEngine

logger = logging.getLogger(__name__)


async def run_dynamic(
    base_nodes: list[dict[str, Any]],
    base_edges: list[dict[str, Any]],
    property_package: str,
    disturbances: list[dict[str, Any]],
    tracked_outputs: list[dict[str, Any]],
    time_horizon: float = 3600.0,
    time_steps: int = 50,
    equipment_volumes: dict[str, float] | None = None,
    simulation_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run pseudo-dynamic step-response simulation."""
    engine = DWSIMEngine()
    volumes = equipment_volumes or {}

    # --- Step 1: initial steady state ---
    initial_result = await engine.simulate({
        "nodes": copy.deepcopy(base_nodes),
        "edges": copy.deepcopy(base_edges),
        "property_package": property_package,
        "simulation_basis": simulation_basis,
    })
    if initial_result.get("status") == "error":
        return {"status": "error", "error": f"Initial SS failed: {initial_result.get('error')}",
                "time_values": [], "output_trajectories": {}}

    # --- Step 2: apply disturbances and get new steady state ---
    disturbed_nodes = copy.deepcopy(base_nodes)
    for dist in disturbances:
        nid = dist["node_id"]
        pkey = dist["parameter_key"]
        step = dist["step_size"]
        for node in disturbed_nodes:
            node_id = node.get("id") if isinstance(node, dict) else None
            if node_id == nid:
                params = node.get("data", {}).get("parameters", node.get("parameters", {}))
                old_val = params.get(pkey, 0)
                params[pkey] = old_val + step

    final_result = await engine.simulate({
        "nodes": disturbed_nodes,
        "edges": copy.deepcopy(base_edges),
        "property_package": property_package,
        "simulation_basis": simulation_basis,
    })
    if final_result.get("status") == "error":
        return {"status": "error", "error": f"Final SS failed: {final_result.get('error')}",
                "time_values": [], "output_trajectories": {}}

    # --- Step 3: extract initial and final tracked values ---
    initial_eq = initial_result.get("results", initial_result).get("equipment_results", {})
    final_eq = final_result.get("results", final_result).get("equipment_results", {})

    initial_vals: dict[str, float | None] = {}
    final_vals: dict[str, float | None] = {}
    for out in tracked_outputs:
        key = f"{out['node_id']}.{out['result_key']}"
        iv = _extract_value(initial_eq, out["node_id"], out["result_key"])
        fv = _extract_value(final_eq, out["node_id"], out["result_key"])
        initial_vals[key] = iv
        final_vals[key] = fv

    # --- Step 4: estimate time constants and interpolate ---
    dt = time_horizon / time_steps
    time_values = [i * dt for i in range(time_steps + 1)]

    # Estimate tau per equipment node from volume and flow
    taus: dict[str, float] = {}
    for out in tracked_outputs:
        nid = out["node_id"]
        if nid not in taus:
            vol = volumes.get(nid, 1.0)  # default 1 m³ if not given
            # Estimate flow from initial results
            flow = _extract_value(initial_eq, nid, "massFlow") or \
                   _extract_value(initial_eq, nid, "totalMassFlow") or 1.0
            density = _extract_value(initial_eq, nid, "density") or 1000.0
            tau = max(vol * density / max(abs(flow), 1e-6), 1.0)  # seconds
            taus[nid] = min(tau, time_horizon * 2)  # cap at 2x horizon

    output_trajectories: dict[str, list[float | None]] = {}
    for out in tracked_outputs:
        key = f"{out['node_id']}.{out['result_key']}"
        iv = initial_vals.get(key)
        fv = final_vals.get(key)
        tau = taus.get(out["node_id"], 60.0)

        if iv is None or fv is None:
            output_trajectories[key] = [None] * len(time_values)
            continue

        trajectory = []
        for t in time_values:
            # First-order step response: y(t) = y0 + (y_ss - y0)(1 - e^(-t/τ))
            val = iv + (fv - iv) * (1.0 - math.exp(-t / tau))
            trajectory.append(round(val, 6))
        output_trajectories[key] = trajectory

    return {
        "time_values": [round(t, 2) for t in time_values],
        "output_trajectories": output_trajectories,
        "steady_state_initial": {k: round(v, 6) if v is not None else None for k, v in initial_vals.items()},
        "steady_state_final": {k: round(v, 6) if v is not None else None for k, v in final_vals.items()},
        "status": "success",
    }


def _extract_value(eq_results: dict, node_id: str, result_key: str) -> float | None:
    """Extract a result value from equipment_results dict."""
    node_res = eq_results.get(node_id, {})
    if not node_res or isinstance(node_res, str):
        return None
    val = node_res.get(result_key)
    if val is None:
        # Try snake_case/camelCase fallback
        alt_key = _camel_to_snake(result_key) if "_" not in result_key else _snake_to_camel(result_key)
        val = node_res.get(alt_key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _camel_to_snake(name: str) -> str:
    import re
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _snake_to_camel(name: str) -> str:
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])
