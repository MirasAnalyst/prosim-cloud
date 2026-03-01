"""Flowsheet data validation service."""
import json
from typing import Any


def _get_params(node: dict[str, Any]) -> dict[str, Any]:
    """Extract parameters from node, handling both flat and React Flow nested formats."""
    # React Flow format: {data: {parameters: {...}}}
    data_params = node.get("data", {}).get("parameters", {})
    if data_params:
        return data_params
    # Flat format (simulation request): {parameters: {...}}
    return node.get("parameters", {})


def _get_name(node: dict[str, Any]) -> str:
    """Extract human-readable name from node."""
    return (
        node.get("data", {}).get("name", "")
        or node.get("name", "")
        or node.get("id", "?")
    )


def validate_flowsheet(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate flowsheet data for integrity issues.

    Returns {valid: bool, errors: list[str], warnings: list[str]}
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Duplicate node IDs
    node_ids = [n.get("id", "") for n in nodes]
    seen_node_ids: set[str] = set()
    for nid in node_ids:
        if nid in seen_node_ids:
            errors.append(f"Duplicate node ID: {nid}")
        seen_node_ids.add(nid)

    # Duplicate edge IDs
    edge_ids = [e.get("id", "") for e in edges]
    seen_edge_ids: set[str] = set()
    for eid in edge_ids:
        if eid in seen_edge_ids:
            errors.append(f"Duplicate edge ID: {eid}")
        seen_edge_ids.add(eid)

    node_id_set = set(node_ids)

    # Orphan edges
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if src and src not in node_id_set:
            errors.append(f"Edge {e.get('id', '?')} references nonexistent source node: {src}")
        if tgt and tgt not in node_id_set:
            errors.append(f"Edge {e.get('id', '?')} references nonexistent target node: {tgt}")

    # Self-loops
    for e in edges:
        if e.get("source") and e.get("source") == e.get("target"):
            errors.append(f"Self-loop detected on edge {e.get('id', '?')}: node {e.get('source')}")

    # Feed parameter completeness
    target_nodes = {e.get("target") for e in edges}
    for n in nodes:
        nid = n.get("id", "")
        name = _get_name(n)
        if nid not in target_nodes:
            # This is a feed node (no incoming edges)
            params = _get_params(n)
            if not params.get("feedTemperature") and params.get("feedTemperature") != 0:
                warnings.append(f"Feed node {name}: missing feedTemperature")
            if not params.get("feedPressure"):
                warnings.append(f"Feed node {name}: missing feedPressure")
            if not params.get("feedFlowRate"):
                warnings.append(f"Feed node {name}: missing feedFlowRate")

            # Composition sum check
            comp = params.get("feedComposition")
            if comp:
                try:
                    comp_dict = comp if isinstance(comp, dict) else json.loads(comp)
                    total = sum(v for v in comp_dict.values() if isinstance(v, (int, float)))
                    if total > 0 and (total < 0.95 or total > 1.05):
                        warnings.append(
                            f"Feed node {name}: composition sum is {total:.3f} (expected ~1.0)"
                        )
                except (ValueError, TypeError):
                    pass

    # Numeric range validation
    for n in nodes:
        params = _get_params(n)
        name = _get_name(n)
        temp = params.get("feedTemperature")
        if temp is not None and isinstance(temp, (int, float)) and temp < -273.15:
            errors.append(f"Node {name}: temperature {temp}°C is below absolute zero")
        pressure = params.get("feedPressure")
        if pressure is not None and isinstance(pressure, (int, float)) and pressure <= 0:
            errors.append(f"Node {name}: pressure must be positive, got {pressure}")
        flow = params.get("feedFlowRate")
        if flow is not None and isinstance(flow, (int, float)) and flow < 0:
            errors.append(f"Node {name}: flow rate cannot be negative, got {flow}")

    # Disconnected nodes warning
    connected_nodes: set[str] = set()
    for e in edges:
        connected_nodes.add(e.get("source", ""))
        connected_nodes.add(e.get("target", ""))
    for n in nodes:
        nid = n.get("id", "")
        name = _get_name(n)
        if nid not in connected_nodes and len(nodes) > 1:
            warnings.append(f"Node {name} is disconnected")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
