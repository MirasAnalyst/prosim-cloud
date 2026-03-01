import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.models.flowsheet import Flowsheet
from app.models.flowsheet_version import FlowsheetVersion
from app.schemas.version import (
    VersionCreate,
    VersionResponse,
    VersionDetailResponse,
    VersionDiffResponse,
)
from app.services.flowsheet_diff import diff_flowsheets

router = APIRouter()


async def _get_flowsheet(project_id: uuid.UUID, db: AsyncSession) -> Flowsheet:
    proj = await db.execute(select(Project).where(Project.id == project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
    result = await db.execute(
        select(Flowsheet).where(Flowsheet.project_id == project_id)
    )
    flowsheet = result.scalar_one_or_none()
    if not flowsheet:
        raise HTTPException(status_code=404, detail="Flowsheet not found")
    return flowsheet


@router.post("/{project_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    project_id: uuid.UUID,
    body: VersionCreate,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)

    # Get next version number
    result = await db.execute(
        select(sa_func.coalesce(sa_func.max(FlowsheetVersion.version_number), 0))
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    max_version = result.scalar()
    next_version = (max_version or 0) + 1

    version = FlowsheetVersion(
        flowsheet_id=flowsheet.id,
        version_number=next_version,
        label=body.label,
        nodes=flowsheet.nodes or [],
        edges=flowsheet.edges or [],
        property_package=None,
    )
    db.add(version)
    await db.flush()
    await db.refresh(version)
    return version


@router.get("/{project_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)
    result = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
        .order_by(FlowsheetVersion.version_number.desc())
    )
    return result.scalars().all()


@router.get(
    "/{project_id}/versions/{version_id}",
    response_model=VersionDetailResponse,
)
async def get_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)
    result = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.id == version_id)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.delete("/{project_id}/versions/{version_id}", status_code=204)
async def delete_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)
    result = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.id == version_id)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    await db.delete(version)


@router.post("/{project_id}/versions/{version_id}/restore", response_model=VersionDetailResponse)
async def restore_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)
    result = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.id == version_id)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    flowsheet.nodes = version.nodes
    flowsheet.edges = version.edges
    await db.flush()
    await db.refresh(flowsheet)
    return version


@router.get(
    "/{project_id}/versions/{v1_id}/diff/{v2_id}",
    response_model=VersionDiffResponse,
)
async def diff_versions(
    project_id: uuid.UUID,
    v1_id: uuid.UUID,
    v2_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    flowsheet = await _get_flowsheet(project_id, db)
    r1 = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.id == v1_id)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    v1 = r1.scalar_one_or_none()
    if not v1:
        raise HTTPException(status_code=404, detail="Version v1 not found")

    r2 = await db.execute(
        select(FlowsheetVersion)
        .where(FlowsheetVersion.id == v2_id)
        .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
    )
    v2 = r2.scalar_one_or_none()
    if not v2:
        raise HTTPException(status_code=404, detail="Version v2 not found")

    return diff_flowsheets(v1.nodes or [], v1.edges or [], v2.nodes or [], v2.edges or [])
