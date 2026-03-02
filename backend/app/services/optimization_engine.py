"""Optimization engine — wraps scipy.optimize around simulation."""
import copy
import asyncio
import logging
from typing import Any

from app.services.dwsim_engine import DWSIMEngine

logger = logging.getLogger(__name__)


async def run_optimization(
    base_nodes: list[dict[str, Any]],
    base_edges: list[dict[str, Any]],
    property_package: str,
    objective: dict[str, Any],
    decision_variables: list[dict[str, Any]],
    constraints: list[dict[str, Any]] | None = None,
    solver: str = "SLSQP",
    max_iterations: int = 100,
    simulation_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run optimization to find optimal process parameters."""
    try:
        from scipy.optimize import minimize, differential_evolution
    except ImportError:
        return {"status": "error", "error": "scipy not installed. Run: pip install scipy>=1.11.0",
                "optimal_values": {}, "iterations": 0}

    engine = DWSIMEngine()
    constraints_list = constraints or []
    convergence_history: list[float] = []
    eval_count = 0

    # Build bounds
    bounds = [(dv["min_value"], dv["max_value"]) for dv in decision_variables]
    x0 = [dv.get("initial_value") or (dv["min_value"] + dv["max_value"]) / 2 for dv in decision_variables]

    obj_sense = 1.0 if objective.get("sense", "minimize") == "minimize" else -1.0

    def sync_simulate(x: list[float]) -> float:
        """Synchronous simulation wrapper for scipy."""
        nonlocal eval_count
        eval_count += 1

        nodes = copy.deepcopy(base_nodes)
        for i, dv in enumerate(decision_variables):
            _set_param(nodes, dv["node_id"], dv["parameter_key"], x[i])

        # Run simulation synchronously
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(engine.simulate({
                "nodes": nodes,
                "edges": copy.deepcopy(base_edges),
                "property_package": property_package,
                "simulation_basis": simulation_basis,
            }))
        finally:
            loop.close()

        if result.get("status") == "error":
            return 1e12 * obj_sense  # penalty

        eq_results = result.get("results", result).get("equipment_results", {})
        obj_val = _extract(eq_results, objective["node_id"], objective["result_key"])
        if obj_val is None:
            return 1e12 * obj_sense

        convergence_history.append(obj_val)
        return obj_val * obj_sense

    def sync_constraint(x: list[float], con: dict) -> float:
        """Evaluate constraint: returns value that should be >= 0."""
        nodes = copy.deepcopy(base_nodes)
        for i, dv in enumerate(decision_variables):
            _set_param(nodes, dv["node_id"], dv["parameter_key"], x[i])

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(engine.simulate({
                "nodes": nodes,
                "edges": copy.deepcopy(base_edges),
                "property_package": property_package,
                "simulation_basis": simulation_basis,
            }))
        finally:
            loop.close()

        eq_results = result.get("results", result).get("equipment_results", {})
        val = _extract(eq_results, con["node_id"], con["result_key"])
        if val is None:
            return -1e6

        op = con["operator"]
        target = con["value"]
        if op == "<=":
            return target - val
        elif op == ">=":
            return val - target
        else:  # ==
            return -(abs(val - target) - 0.01)

    # Build scipy constraints
    scipy_constraints = []
    for con in constraints_list:
        scipy_constraints.append({
            "type": "ineq",
            "fun": lambda x, c=con: sync_constraint(x, c),
        })

    # Run optimization in thread to not block async loop
    def _run_opt():
        if solver == "differential_evolution":
            result = differential_evolution(
                sync_simulate, bounds,
                maxiter=max_iterations, seed=42, tol=1e-6,
            )
        else:
            result = minimize(
                sync_simulate, x0,
                method="SLSQP", bounds=bounds,
                constraints=scipy_constraints,
                options={"maxiter": max_iterations, "ftol": 1e-8},
            )
        return result

    try:
        opt_result = await asyncio.to_thread(_run_opt)
    except Exception as e:
        logger.exception("Optimization failed")
        return {"status": "error", "error": str(e),
                "optimal_values": {}, "iterations": eval_count,
                "convergence_history": convergence_history}

    # Build output
    optimal_values = {}
    for i, dv in enumerate(decision_variables):
        key = f"{dv['node_id']}.{dv['parameter_key']}"
        optimal_values[key] = round(float(opt_result.x[i]), 6)

    # Evaluate constraints at optimal point
    constraint_values = {}
    for con in constraints_list:
        key = f"{con['node_id']}.{con['result_key']}"
        cv = sync_constraint(list(opt_result.x), con)
        constraint_values[key] = round(cv, 6)

    return {
        "optimal_values": optimal_values,
        "objective_value": round(float(opt_result.fun) * obj_sense, 6),
        "constraint_values": constraint_values,
        "convergence_history": [round(v, 6) for v in convergence_history],
        "iterations": eval_count,
        "status": "success" if opt_result.success else "partial",
        "message": str(opt_result.message) if hasattr(opt_result, 'message') else "",
    }


def _set_param(nodes: list[dict], node_id: str, param_key: str, value: float):
    """Set parameter value on a node."""
    for node in nodes:
        if node.get("id") == node_id:
            # Handle React Flow wrapper
            data = node.get("data", {})
            params = data.get("parameters", node.get("parameters", {}))
            params[param_key] = value
            if "data" in node:
                node["data"].setdefault("parameters", {})[param_key] = value
            else:
                node.setdefault("parameters", {})[param_key] = value
            break


def _extract(eq_results: dict, node_id: str, result_key: str) -> float | None:
    """Extract result value."""
    node_res = eq_results.get(node_id, {})
    if not node_res or isinstance(node_res, str):
        return None
    val = node_res.get(result_key)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
