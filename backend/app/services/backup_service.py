"""Project backup and restore service."""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.flowsheet import Flowsheet
from app.models.flowsheet_version import FlowsheetVersion
from app.models.simulation import SimulationResult
from app.models.chat import ChatMessage


async def create_backup(db: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
    """Create a full backup of a project including all related data."""
    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # Get flowsheet
    result = await db.execute(
        select(Flowsheet).where(Flowsheet.project_id == project_id)
    )
    flowsheet = result.scalar_one_or_none()

    # Get versions
    versions_data: list[dict[str, Any]] = []
    if flowsheet:
        result = await db.execute(
            select(FlowsheetVersion)
            .where(FlowsheetVersion.flowsheet_id == flowsheet.id)
            .order_by(FlowsheetVersion.version_number)
        )
        for v in result.scalars().all():
            versions_data.append({
                "version_number": v.version_number,
                "label": v.label,
                "nodes": v.nodes,
                "edges": v.edges,
                "property_package": v.property_package,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })

    # Get simulation results
    sim_results_data: list[dict[str, Any]] = []
    if flowsheet:
        result = await db.execute(
            select(SimulationResult)
            .where(SimulationResult.flowsheet_id == flowsheet.id)
            .order_by(SimulationResult.created_at.desc())
            .limit(10)
        )
        for sr in result.scalars().all():
            sim_results_data.append({
                "status": sr.status,
                "results": sr.results,
                "error": sr.error,
                "created_at": sr.created_at.isoformat() if sr.created_at else None,
            })

    # Get chat messages
    chat_data: list[dict[str, Any]] = []
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at)
    )
    for msg in result.scalars().all():
        chat_data.append({
            "role": msg.role,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return {
        "format": "prosim-backup",
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "name": project.name,
            "description": project.description,
        },
        "flowsheet": {
            "nodes": flowsheet.nodes if flowsheet else [],
            "edges": flowsheet.edges if flowsheet else [],
        },
        "versions": versions_data,
        "simulation_results": sim_results_data,
        "chat_messages": chat_data,
    }


async def restore_backup(db: AsyncSession, backup_data: dict[str, Any]) -> uuid.UUID:
    """Restore a project from backup data. Returns new project ID."""
    project_info = backup_data.get("project", {})
    project = Project(
        name=project_info.get("name", "Restored Project"),
        description=project_info.get("description"),
    )
    db.add(project)
    await db.flush()

    # Create flowsheet
    flowsheet_data = backup_data.get("flowsheet", {})
    flowsheet = Flowsheet(
        project_id=project.id,
        nodes=flowsheet_data.get("nodes", []),
        edges=flowsheet_data.get("edges", []),
    )
    db.add(flowsheet)
    await db.flush()

    # Restore versions
    for v_data in backup_data.get("versions", []):
        version = FlowsheetVersion(
            flowsheet_id=flowsheet.id,
            version_number=v_data.get("version_number", 1),
            label=v_data.get("label"),
            nodes=v_data.get("nodes", []),
            edges=v_data.get("edges", []),
            property_package=v_data.get("property_package"),
        )
        db.add(version)

    # Restore simulation results
    for sr_data in backup_data.get("simulation_results", []):
        sim_result = SimulationResult(
            flowsheet_id=flowsheet.id,
            status=sr_data.get("status", "completed"),
            results=sr_data.get("results"),
            error=sr_data.get("error"),
        )
        db.add(sim_result)

    # Restore chat messages
    for msg_data in backup_data.get("chat_messages", []):
        msg = ChatMessage(
            project_id=project.id,
            role=msg_data.get("role", "user"),
            content=msg_data.get("content", ""),
        )
        db.add(msg)

    await db.flush()
    await db.refresh(project)
    return project.id
