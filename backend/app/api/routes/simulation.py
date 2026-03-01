import uuid
import copy
import json
import logging
import asyncio
from datetime import datetime, timezone
from itertools import product

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flowsheet import Flowsheet
from app.models.simulation import SimulationResult
from app.schemas.simulation import SimulationRequest, SimulationResponse, BatchSimulationRequest
from app.services.dwsim_engine import DWSIMEngine

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
