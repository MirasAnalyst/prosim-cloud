import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.models.simulation_case import SimulationCase
from app.schemas.case_study import CaseCreate, CaseResponse, CaseCompareRequest, CaseCompareResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{project_id}/cases", response_model=CaseResponse, status_code=201)
async def create_case(
    project_id: uuid.UUID,
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    case = SimulationCase(
        project_id=project_id,
        name=body.name,
        description=body.description,
        nodes=body.nodes,
        edges=body.edges,
        simulation_basis=body.simulation_basis,
        property_package=body.property_package,
        results=body.results,
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return case


@router.get("/{project_id}/cases", response_model=list[CaseResponse])
async def list_cases(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(SimulationCase)
        .where(SimulationCase.project_id == project_id)
        .order_by(SimulationCase.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{project_id}/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.id == case_id,
            SimulationCase.project_id == project_id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.put("/{project_id}/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.id == case_id,
            SimulationCase.project_id == project_id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.name = body.name
    case.description = body.description
    case.nodes = body.nodes
    case.edges = body.edges
    case.simulation_basis = body.simulation_basis
    case.property_package = body.property_package
    case.results = body.results
    await db.flush()
    await db.refresh(case)
    return case


@router.delete("/{project_id}/cases/{case_id}", status_code=204)
async def delete_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.id == case_id,
            SimulationCase.project_id == project_id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.flush()


@router.post("/{project_id}/cases/{case_id}/load", response_model=CaseResponse)
async def load_case(
    project_id: uuid.UUID,
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Load a case — returns the case data so the frontend can apply it."""
    result = await db.execute(
        select(SimulationCase).where(
            SimulationCase.id == case_id,
            SimulationCase.project_id == project_id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{project_id}/cases/compare", response_model=CaseCompareResponse)
async def compare_cases(
    project_id: uuid.UUID,
    body: CaseCompareRequest,
    db: AsyncSession = Depends(get_db),
):
    if len(body.case_ids) < 2 or len(body.case_ids) > 3:
        raise HTTPException(status_code=400, detail="Compare requires 2-3 case IDs")

    cases = []
    for cid in body.case_ids:
        result = await db.execute(
            select(SimulationCase).where(
                SimulationCase.id == cid,
                SimulationCase.project_id == project_id,
            )
        )
        case = result.scalar_one_or_none()
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {cid} not found")
        cases.append(case)

    # Build comparison diffs
    diffs: dict = {
        "property_packages": [c.property_package for c in cases],
        "node_counts": [len(c.nodes) for c in cases],
        "edge_counts": [len(c.edges) for c in cases],
        "equipment_results": {},
        "stream_results": {},
    }

    # Compare equipment results if available
    # Support both camelCase (frontend) and snake_case (engine) result keys
    for i, case in enumerate(cases):
        if case.results and isinstance(case.results, dict):
            eq_results = case.results.get("equipment_results", case.results.get("equipmentResults", {}))
            for eq_id, eq_data in eq_results.items():
                if eq_id not in diffs["equipment_results"]:
                    diffs["equipment_results"][eq_id] = [None] * i  # backfill previous cases
                diffs["equipment_results"][eq_id].append(eq_data)

            sr_results = case.results.get("stream_results", case.results.get("streamResults", {}))
            for sr_id, sr_data in sr_results.items():
                if sr_id not in diffs["stream_results"]:
                    diffs["stream_results"][sr_id] = [None] * i
                diffs["stream_results"][sr_id].append(sr_data)

        # Pad missing entries for equipment/streams not in this case
        for eq_id in diffs["equipment_results"]:
            if len(diffs["equipment_results"][eq_id]) <= i:
                diffs["equipment_results"][eq_id].append(None)
        for sr_id in diffs["stream_results"]:
            if len(diffs["stream_results"][sr_id]) <= i:
                diffs["stream_results"][sr_id].append(None)

    return CaseCompareResponse(cases=cases, diffs=diffs)
