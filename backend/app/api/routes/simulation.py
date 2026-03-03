import uuid
import copy
import json
import logging
import asyncio
from datetime import datetime, timezone
from itertools import product

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flowsheet import Flowsheet
from app.models.simulation import SimulationResult
from app.schemas.simulation import SimulationRequest, SimulationResponse, BatchSimulationRequest
from app.services.dwsim_engine import DWSIMEngine
from app.schemas.sensitivity import SensitivityRequest, SensitivityResult
from app.schemas.dynamic import DynamicRequest, DynamicResult
from app.schemas.optimization import OptimizationRequest, OptimizationResult
from app.schemas.pinch import PinchRequest, PinchResult
from app.schemas.utility import UtilityRequest, UtilityResult
from app.schemas.emissions import EmissionsRequest, EmissionsResult
from app.schemas.relief_valve import ReliefValveRequest, ReliefValveResult
from app.schemas.hydraulics import HydraulicsRequest, HydraulicsResult
from app.schemas.control_valve import ControlValveRequest, ControlValveResult
from app.schemas.insights import InsightsRequest, InsightsResult, InsightsSummary
from app.services.phase_envelope import compute_phase_envelope

logger = logging.getLogger(__name__)
router = APIRouter()

engine = DWSIMEngine()


@router.post("/run", response_model=SimulationResponse, status_code=201)
async def run_simulation(body: SimulationRequest, db: AsyncSession = Depends(get_db)):
    nodes = body.nodes
    edges = body.edges
    flowsheet_id = body.flowsheet_id

    if flowsheet_id:
        result = await db.execute(
            select(Flowsheet).where(Flowsheet.id == flowsheet_id)
        )
        flowsheet = result.scalar_one_or_none()
        if not flowsheet:
            raise HTTPException(status_code=404, detail="Flowsheet not found")
        if not nodes:
            nodes = flowsheet.nodes or []
        if not edges:
            edges = flowsheet.edges or []

    if not nodes:
        raise HTTPException(
            status_code=400, detail="Either flowsheet_id or nodes must be provided"
        )

    # Run simulation
    try:
        sim_output = await engine.simulate({
            "nodes": nodes,
            "edges": edges,
            "property_package": body.property_package,
            "convergence_settings": body.convergence_settings.model_dump() if body.convergence_settings else None,
            "simulation_basis": body.simulation_basis,
        })
    except Exception as exc:
        logger.exception("Simulation execution failed")
        sim_output = {"status": "error", "error": str(exc)}

    status = sim_output.get("status", "error")
    error_msg = sim_output.get("error") if status == "error" else None

    # Store result in DB if we have a flowsheet_id
    if flowsheet_id:
        sim_result = SimulationResult(
            flowsheet_id=flowsheet_id,
            status=status,
            results=sim_output,
            error=error_msg,
        )
        db.add(sim_result)
        await db.flush()
        await db.refresh(sim_result)
        return sim_result

    # No flowsheet_id: return result directly without DB storage
    return SimulationResponse(
        id=uuid.uuid4(),
        flowsheet_id=None,
        status=status,
        results=sim_output,
        error=error_msg,
        created_at=datetime.now(timezone.utc),
    )


@router.get("/{simulation_id}/results", response_model=SimulationResponse)
async def get_simulation_results(
    simulation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SimulationResult).where(SimulationResult.id == simulation_id)
    )
    sim_result = result.scalar_one_or_none()
    if not sim_result:
        raise HTTPException(status_code=404, detail="Simulation result not found")
    return sim_result


@router.post("/run/stream")
async def run_simulation_stream(body: SimulationRequest):
    """SSE endpoint for simulation with progress reporting."""
    progress_queue: asyncio.Queue = asyncio.Queue()

    async def progress_callback(equipment_name: str, index: int, total: int):
        await progress_queue.put({
            "event": "progress",
            "data": {"equipment": equipment_name, "index": index, "total": total},
        })

    async def generate():
        nodes = body.nodes
        edges = body.edges
        sim_task = asyncio.create_task(
            engine.simulate({
                "nodes": nodes,
                "edges": edges,
                "property_package": body.property_package,
                "convergence_settings": body.convergence_settings.model_dump() if body.convergence_settings else None,
                "progress_callback": progress_callback,
                "simulation_basis": body.simulation_basis,
            })
        )
        while not sim_task.done():
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
            except asyncio.TimeoutError:
                continue
        while not progress_queue.empty():
            msg = await progress_queue.get()
            yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
        result = await sim_task
        yield f"event: complete\ndata: {json.dumps(result)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/batch")
async def run_batch_simulation(body: BatchSimulationRequest):
    """Run multiple simulations with parameter variations (cartesian product)."""
    variation_values = [v.values for v in body.variations]
    combinations = list(product(*variation_values))

    results = []
    parameter_matrix = []

    for combo in combinations[:100]:
        nodes = copy.deepcopy(body.base_nodes)
        edges = copy.deepcopy(body.base_edges)

        param_set = {}
        for i, variation in enumerate(body.variations):
            param_set[f"{variation.node_id}.{variation.parameter_key}"] = combo[i]
            for node in nodes:
                node_id = node.get("id") if isinstance(node, dict) else getattr(node, "id", None)
                if node_id == variation.node_id:
                    if isinstance(node, dict):
                        node.setdefault("parameters", {})[variation.parameter_key] = combo[i]
                    else:
                        params = getattr(node, "parameters", {}) or {}
                        params[variation.parameter_key] = combo[i]

        sim_nodes = nodes if isinstance(nodes[0], dict) else [n.model_dump(by_alias=True) for n in nodes]
        sim_edges = edges if (edges and isinstance(edges[0], dict)) else ([e.model_dump(by_alias=True) for e in edges] if edges else [])

        sim_output = await engine.simulate({
            "nodes": sim_nodes,
            "edges": sim_edges,
            "property_package": body.property_package,
            "convergence_settings": body.convergence_settings.model_dump() if body.convergence_settings else None,
        })
        results.append(sim_output)
        parameter_matrix.append(param_set)

    return {"results": results, "parameter_matrix": parameter_matrix}


@router.post("/sensitivity", response_model=SensitivityResult)
async def run_sensitivity_analysis(body: SensitivityRequest):
    """Run sensitivity analysis by varying one parameter."""
    from app.services.sensitivity_engine import run_sensitivity

    result = await run_sensitivity(
        base_nodes=[n if isinstance(n, dict) else n.model_dump(by_alias=True) for n in body.base_nodes],
        base_edges=[e if isinstance(e, dict) else e.model_dump(by_alias=True) for e in body.base_edges],
        property_package=body.property_package,
        variable_node_id=body.variable.node_id,
        variable_param_key=body.variable.parameter_key,
        min_value=body.variable.min_value,
        max_value=body.variable.max_value,
        steps=body.variable.steps,
        outputs=[{"node_id": o.node_id, "result_key": o.result_key} for o in body.outputs],
        simulation_basis=body.simulation_basis,
    )
    return result


@router.post("/export")
async def export_simulation_results(
    body: dict,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    """Export simulation results as CSV or Excel."""
    from app.services.results_exporter import export_csv, export_xlsx

    if format == "xlsx":
        xlsx_bytes = export_xlsx(body)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="simulation_results.xlsx"'},
        )
    else:
        csv_content = export_csv(body)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="simulation_results.csv"'},
        )


@router.post("/report")
async def generate_report(body: SimulationRequest):
    """Generate PDF or text report from simulation."""
    from app.services.report_generator import generate_pdf_report

    nodes = body.nodes
    edges = body.edges
    sim_output = await engine.simulate({
        "nodes": nodes,
        "edges": edges,
        "property_package": body.property_package,
        "convergence_settings": body.convergence_settings.model_dump() if body.convergence_settings else None,
    })
    pdf_bytes = generate_pdf_report(sim_output.get("results", sim_output), "ProSim Cloud")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=simulation_report.pdf"},
    )


@router.post("/dynamic", response_model=DynamicResult)
async def run_dynamic_simulation(body: DynamicRequest):
    """Run pseudo-dynamic step-response simulation."""
    from app.services.dynamic_engine import run_dynamic

    result = await run_dynamic(
        base_nodes=[n if isinstance(n, dict) else n.model_dump(by_alias=True) for n in body.base_nodes],
        base_edges=[e if isinstance(e, dict) else e.model_dump(by_alias=True) for e in body.base_edges],
        property_package=body.property_package,
        disturbances=[d.model_dump() for d in body.disturbances],
        tracked_outputs=[o.model_dump() for o in body.tracked_outputs],
        time_horizon=body.time_horizon,
        time_steps=body.time_steps,
        equipment_volumes=body.equipment_volumes,
        simulation_basis=body.simulation_basis,
    )
    return result


@router.post("/optimize", response_model=OptimizationResult)
async def run_optimization(body: OptimizationRequest):
    """Run process optimization."""
    from app.services.optimization_engine import run_optimization as _run_opt

    result = await _run_opt(
        base_nodes=[n if isinstance(n, dict) else n.model_dump(by_alias=True) for n in body.base_nodes],
        base_edges=[e if isinstance(e, dict) else e.model_dump(by_alias=True) for e in body.base_edges],
        property_package=body.property_package,
        objective=body.objective.model_dump(),
        decision_variables=[dv.model_dump() for dv in body.decision_variables],
        constraints=[c.model_dump() for c in body.constraints],
        solver=body.solver,
        max_iterations=body.max_iterations,
        simulation_basis=body.simulation_basis,
    )
    return result


@router.post("/pinch", response_model=PinchResult)
async def run_pinch_analysis(body: PinchRequest):
    """Run pinch analysis."""
    from app.services.pinch_engine import run_pinch_analysis as _pinch

    result = _pinch(
        streams=[s.model_dump() for s in body.streams],
        dt_min=body.dt_min,
    )
    return result


@router.post("/utility", response_model=UtilityResult)
async def compute_utility_summary(body: UtilityRequest):
    """Compute utility costs from simulation results."""
    from app.services.utility_engine import compute_utilities

    result = compute_utilities(
        simulation_results=body.simulation_results,
        costs=body.costs.model_dump() if body.costs else None,
        hours_per_year=body.hours_per_year,
    )
    return result


@router.post("/emissions", response_model=EmissionsResult)
async def compute_emissions(body: EmissionsRequest):
    """Compute environmental emissions."""
    from app.services.emissions_engine import compute_emissions as _compute

    result = _compute(
        fuel_type=body.fuel.fuel_type,
        fuel_consumption_gj_hr=body.fuel.consumption,
        equipment_counts=body.equipment_counts.model_dump() if body.equipment_counts else None,
        carbon_price=body.carbon_price,
        hours_per_year=body.hours_per_year,
        simulation_results=body.simulation_results,
    )
    return result


@router.post("/relief-valve", response_model=ReliefValveResult)
async def size_relief_valve(body: ReliefValveRequest):
    """Size a relief valve per API 520/521/526."""
    from app.services.relief_valve_engine import size_relief_valve as _size

    result = _size(**body.model_dump())
    return result


@router.post("/hydraulics", response_model=HydraulicsResult)
async def compute_hydraulics(body: HydraulicsRequest):
    """Compute pipe hydraulics."""
    from app.services.hydraulics_engine import compute_hydraulics as _compute

    result = _compute(**body.model_dump())
    return result


@router.post("/control-valve", response_model=ControlValveResult)
async def size_control_valve(body: ControlValveRequest):
    """Size a control valve per ISA 60534."""
    from app.services.control_valve_engine import size_control_valve as _size

    result = _size(**body.model_dump())
    return result


@router.post("/insights", response_model=InsightsResult)
async def run_insights(body: InsightsRequest):
    """Run AI-powered optimization insights analysis."""
    from app.services.insights_engine import analyze_insights

    try:
        result = await analyze_insights(
            simulation_results=body.simulation_results,
            nodes=body.nodes,
            edges=body.edges,
            property_package=body.property_package,
            economic_params=body.economic_params.model_dump(),
        )
        return result
    except Exception as e:
        logger.error("Insights analysis failed: %s", e)
        return InsightsResult(
            insights=[],
            summary=InsightsSummary(
                total_annual_savings=0,
                total_co2_reduction=0,
                insight_count=0,
                top_quick_wins=[],
                top_high_impact=[],
            ),
            status="error",
            error=str(e),
        )


_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_RAW_CONTEXT_TOKENS = 25_000  # ~100K characters — leave room for system + tool defs


async def _read_upload_chunked(file: UploadFile) -> bytes:
    """Read upload in chunks with early abort if too large (R7 fix)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)  # 64 KB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds 10 MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/insights/parse")
async def parse_insights_file_preview(file: UploadFile = File(...)):
    """Parse an uploaded file and return a preview (no AI call)."""
    from app.services.insights_file_parser import parse_insights_file

    contents = await _read_upload_chunked(file)
    parsed = parse_insights_file(contents, file.filename or "unknown.csv")
    sim_res = parsed.get("simulation_results", {})
    return {
        "stream_count": len(sim_res.get("stream_results", {})),
        "equipment_count": len(sim_res.get("equipment_results", {})),
        "node_count": len(parsed.get("nodes", [])),
        "warnings": parsed.get("warnings", []),
        "raw_context_preview": (parsed.get("raw_context", ""))[:2000],
        "simulation_results": sim_res,
        "nodes": parsed.get("nodes", []),
        "detected_unit_system": parsed.get("detected_unit_system", "unknown"),
        "detected_property_package": parsed.get("detected_property_package"),
    }


@router.post("/insights/upload", response_model=InsightsResult)
async def run_insights_from_file(
    file: UploadFile = File(...),
    economic_params_json: str = Form("{}"),
    property_package: str = Form("PengRobinson"),
):
    """Parse an uploaded file then run AI insights analysis."""
    from app.services.insights_file_parser import parse_insights_file
    from app.services.insights_engine import analyze_insights

    contents = await _read_upload_chunked(file)
    parsed = parse_insights_file(contents, file.filename or "unknown.csv")

    try:
        econ = json.loads(economic_params_json)
    except json.JSONDecodeError:
        econ = {}

    economic_params = {
        "steam_cost": econ.get("steam_cost", econ.get("steamCost", 15.0)),
        "cooling_water_cost": econ.get("cooling_water_cost", econ.get("coolingWaterCost", econ.get("cwCost", 3.0))),
        "electricity_cost": econ.get("electricity_cost", econ.get("electricityCost", econ.get("elecCost", 0.08))),
        "fuel_gas_cost": econ.get("fuel_gas_cost", econ.get("fuelGasCost", econ.get("fuelCost", 8.0))),
        "carbon_price": econ.get("carbon_price", econ.get("carbonPrice", 50.0)),
        "hours_per_year": econ.get("hours_per_year", econ.get("hoursPerYear", 8000)),
    }

    # R3 fix: use user-selected property package, fall back to detected or PR
    pp = property_package
    if pp == "PengRobinson" and parsed.get("detected_property_package"):
        pp = parsed["detected_property_package"]

    # E1 fix: truncate raw_context to token budget (~4 chars per token)
    raw_ctx = parsed.get("raw_context", "")
    max_chars = _MAX_RAW_CONTEXT_TOKENS * 4
    if len(raw_ctx) > max_chars:
        raw_ctx = raw_ctx[:max_chars] + "\n... (context truncated for token limit)"
        logger.warning("raw_context truncated from %d to %d chars", len(parsed.get("raw_context", "")), max_chars)

    try:
        result = await analyze_insights(
            simulation_results=parsed.get("simulation_results", {}),
            nodes=parsed.get("nodes", []),
            edges=parsed.get("edges", []),
            property_package=pp,
            economic_params=economic_params,
            raw_context=raw_ctx,
        )
        return result
    except Exception as e:
        logger.error("File insights analysis failed: %s", e)
        return InsightsResult(
            insights=[],
            summary=InsightsSummary(
                total_annual_savings=0,
                total_co2_reduction=0,
                insight_count=0,
                top_quick_wins=[],
                top_high_impact=[],
            ),
            status="error",
            error=str(e),
        )


@router.post("/property-advisor")
async def property_advisor(body: dict):
    """Recommend a property package based on compounds."""
    from app.services.property_advisor import advise_property_package

    compounds = body.get("compounds", [])
    pressure_bar = body.get("pressure_bar")
    result = advise_property_package(compounds, pressure_bar=pressure_bar)
    return result


@router.post("/bip/matrix")
async def get_bip_matrix(body: dict):
    """Get BIP matrix for given compounds and property package."""
    from app.services.bip_manager import get_bip_matrix as _get_bip

    compounds = body.get("compounds", [])
    property_package = body.get("property_package", "PengRobinson")
    result = _get_bip(compounds, property_package)
    return result


@router.post("/binary-vle/txy")
async def binary_vle_txy(body: dict):
    """Compute Txy diagram for a binary mixture at constant pressure."""
    from app.services.binary_vle import compute_txy

    comp_a = body.get("comp_a", "")
    comp_b = body.get("comp_b", "")
    P = float(body.get("P", 101325))
    property_package = body.get("property_package", "PengRobinson")
    n_points = min(int(body.get("n_points", 51)), 200)

    if not comp_a or not comp_b:
        raise HTTPException(status_code=400, detail="comp_a and comp_b are required")

    result = compute_txy(comp_a, comp_b, P, property_package, n_points)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/binary-vle/pxy")
async def binary_vle_pxy(body: dict):
    """Compute Pxy diagram for a binary mixture at constant temperature."""
    from app.services.binary_vle import compute_pxy

    comp_a = body.get("comp_a", "")
    comp_b = body.get("comp_b", "")
    T = float(body.get("T", 373.15))
    property_package = body.get("property_package", "PengRobinson")
    n_points = min(int(body.get("n_points", 51)), 200)

    if not comp_a or not comp_b:
        raise HTTPException(status_code=400, detail="comp_a and comp_b are required")

    result = compute_pxy(comp_a, comp_b, T, property_package, n_points)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/phase-envelope")
async def phase_envelope(body: dict):
    """Compute PT phase envelope (bubble/dew curves) for a mixture.

    Body: {compounds: ["methane","ethane",...], composition: [0.7,0.3,...],
           property_package: "PengRobinson", n_points: 50}
    """
    compounds = body.get("compounds", [])
    composition = body.get("composition", [])
    property_package = body.get("property_package", "PengRobinson")
    n_points = min(int(body.get("n_points", 50)), 200)

    if not compounds or not composition:
        raise HTTPException(status_code=400, detail="compounds and composition are required")
    if len(compounds) != len(composition):
        raise HTTPException(status_code=400, detail="compounds and composition must have same length")

    result = compute_phase_envelope(compounds, composition, property_package, n_points)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
