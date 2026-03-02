"""Sensitivity analysis engine — runs parameter sweeps."""
import copy
import logging
import numpy as np
from typing import Any

from app.services.dwsim_engine import DWSIMEngine

logger = logging.getLogger(__name__)


async def run_sensitivity(
    base_nodes: list[dict[str, Any]],
    base_edges: list[dict[str, Any]],
    property_package: str,
    variable_node_id: str,
    variable_param_key: str,
    min_value: float,
    max_value: float,
    steps: int,
    outputs: list[dict[str, str]],
    simulation_basis: dict[str, Any] | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Run sensitivity analysis by varying one parameter across a range.

    Returns dict with variable_values, output_values, and status.
    """
    engine = DWSIMEngine()

    # Generate sweep values
    variable_values = list(np.linspace(min_value, max_value, steps))

    # Initialize output collection
    output_values: dict[str, list[float | None]] = {}
    for out in outputs:
        key = f"{out['node_id']}.{out['result_key']}"
        output_values[key] = []

    # Find variable label
    variable_label = f"{variable_param_key}"
    for node in base_nodes:
        nid = node.get("id") or node.get("data", {}).get("id", "")
        if nid == variable_node_id:
            variable_label = f"{node.get('name', node.get('data', {}).get('name', nid))}.{variable_param_key}"
            break

    # Run simulations
    for i, val in enumerate(variable_values):
        if progress_callback:
            await progress_callback(f"Sensitivity {i+1}/{steps}", i, steps)

        # Deep copy and modify parameter
        nodes = copy.deepcopy(base_nodes)
        for node in nodes:
            node_id = node.get("id", "")
            # Handle both flat and React Flow formats
            if node_id == variable_node_id:
                if "data" in node and "parameters" in node.get("data", {}):
                    node["data"]["parameters"][variable_param_key] = val
                elif "parameters" in node:
                    node["parameters"][variable_param_key] = val

        edges = copy.deepcopy(base_edges)

        try:
            result = await engine.simulate({
                "nodes": nodes,
                "edges": edges,
                "property_package": property_package,
                "simulation_basis": simulation_basis,
            })

            # Extract output values
            eq_results = result.get("equipment_results", result.get("results", {}).get("equipment_results", {}))
            stream_results = result.get("stream_results", result.get("results", {}).get("stream_results", {}))

            for out in outputs:
                key = f"{out['node_id']}.{out['result_key']}"
                eq_r = eq_results.get(out["node_id"], {})
                value = eq_r.get(out["result_key"])
                if value is None:
                    # Try stream results
                    for sr_key, sr_val in stream_results.items():
                        if isinstance(sr_val, dict) and out["result_key"] in sr_val:
                            value = sr_val[out["result_key"]]
                            break
                output_values[key].append(float(value) if value is not None else None)
        except Exception as exc:
            logger.warning(f"Sensitivity run {i+1} failed: {exc}")
            for out in outputs:
                key = f"{out['node_id']}.{out['result_key']}"
                output_values[key].append(None)

    return {
        "variable_values": variable_values,
        "output_values": output_values,
        "variable_label": variable_label,
        "status": "success",
    }
