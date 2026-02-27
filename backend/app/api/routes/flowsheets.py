import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flowsheet import Flowsheet
from app.models.project import Project
from app.schemas.flowsheet import FlowsheetUpdate, FlowsheetResponse

router = APIRouter()


@router.get("/{project_id}/flowsheet", response_model=FlowsheetResponse)
async def get_flowsheet(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Flowsheet).where(Flowsheet.project_id == project_id)
    )
    flowsheet = result.scalar_one_or_none()
    if not flowsheet:
        raise HTTPException(status_code=404, detail="Flowsheet not found")
    return flowsheet


@router.put("/{project_id}/flowsheet", response_model=FlowsheetResponse)
async def update_flowsheet(
    project_id: uuid.UUID,
    body: FlowsheetUpdate,
    db: AsyncSession = Depends(get_db),
):
    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Flowsheet).where(Flowsheet.project_id == project_id)
    )
    flowsheet = result.scalar_one_or_none()
    if not flowsheet:
        # Create flowsheet if it doesn't exist
        flowsheet = Flowsheet(
            project_id=project_id,
            nodes=[n.model_dump() for n in body.nodes],
            edges=[e.model_dump() for e in body.edges],
        )
        db.add(flowsheet)
    else:
        flowsheet.nodes = [n.model_dump() for n in body.nodes]
        flowsheet.edges = [e.model_dump() for e in body.edges]

    await db.flush()
    await db.refresh(flowsheet)
    return flowsheet
