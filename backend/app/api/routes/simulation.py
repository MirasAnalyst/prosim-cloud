import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flowsheet import Flowsheet
from app.models.simulation import SimulationResult
from app.schemas.simulation import SimulationRequest, SimulationResponse
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
