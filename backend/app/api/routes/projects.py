import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.models.flowsheet import Flowsheet
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.api.deps.auth import get_optional_user, CurrentUser

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return projects


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(name=body.name, description=body.description, user_id=current_user.id)
    db.add(project)
    await db.flush()
    # Create an empty flowsheet for the project
    flowsheet = Flowsheet(project_id=project.id, nodes=[], edges=[])
    db.add(flowsheet)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description

    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)


@router.get("/{project_id}/backup")
async def backup_project(
    project_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a full backup of the project."""
    import json
    from app.services.backup_service import create_backup

    # Verify ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        backup_data = await create_backup(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    content = json.dumps(backup_data, indent=2, default=str)
    safe_name = backup_data["project"]["name"].replace('"', '_').replace('\n', '_').replace('\r', '_')
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.prosim-backup.json"'},
    )


@router.post("/restore", response_model=ProjectResponse, status_code=201)
async def restore_project(
    body: dict,
    current_user: CurrentUser = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a project from backup data."""
    from app.services.backup_service import restore_backup

    new_project_id = await restore_backup(db, body)
    result = await db.execute(select(Project).where(Project.id == new_project_id))
    project = result.scalar_one_or_none()
    # Assign the restored project to the current user
    if project:
        project.user_id = current_user.id
        await db.flush()
        await db.refresh(project)
    return project
