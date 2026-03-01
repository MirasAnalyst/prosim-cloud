import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.flowsheet import Flowsheet
from app.models.project import Project
from app.schemas.flowsheet import FlowsheetUpdate, FlowsheetResponse
from app.schemas.import_export import ImportResult

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


@router.get("/{project_id}/export")
async def export_flowsheet(
    project_id: uuid.UUID,
    format: str = Query("json", pattern="^(json|xml|dwsim_xml)$"),
    db: AsyncSession = Depends(get_db),
):
    from app.services.flowsheet_exporter import export_json, export_xml, export_dwsim_xml

    # Get project and flowsheet
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Flowsheet).where(Flowsheet.project_id == project_id)
    )
    flowsheet = result.scalar_one_or_none()
    if not flowsheet:
        raise HTTPException(status_code=404, detail="Flowsheet not found")

    nodes = flowsheet.nodes or []
    edges = flowsheet.edges or []
    safe_name = project.name.replace('"', '_').replace('\n', '_').replace('\r', '_')

    if format == "json":
        content = export_json(project.name, nodes, edges)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.prosim.json"'},
        )
    elif format == "xml":
        content = export_xml(project.name, nodes, edges)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.prosim.xml"'},
        )
    else:  # dwsim_xml
        content = export_dwsim_xml(project.name, nodes, edges)
        return Response(
            content=content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.dwxml"'},
        )


@router.post("/{project_id}/import", response_model=ImportResult)
async def import_flowsheet(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    from app.services.dwsim_importer import (
        import_dwsim_xml,
        import_dwsim_zip,
        import_prosim_json,
        import_prosim_xml,
    )

    # Verify project exists
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    file_bytes = await file.read()
    filename = file.filename or ""

    if filename.endswith(".dwxmz"):
        result = import_dwsim_zip(file_bytes)
    elif filename.endswith(".json"):
        result = import_prosim_json(file_bytes.decode("utf-8"))
    elif filename.endswith(".xml") or filename.endswith(".dwxml"):
        xml_content = file_bytes.decode("utf-8")
        # Detect if it's DWSIM or ProSim XML
        if "DWSIM_Simulation_Data" in xml_content or "SimulationObject" in xml_content:
            result = import_dwsim_xml(xml_content)
        else:
            result = import_prosim_xml(xml_content)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {filename}. Supported: .json, .xml, .dwxmz",
        )

    nodes = result.get("nodes", [])
    edges = result.get("edges", [])

    if nodes or edges:
        fs_result = await db.execute(
            select(Flowsheet).where(Flowsheet.project_id == project_id)
        )
        flowsheet = fs_result.scalar_one_or_none()
        if flowsheet:
            flowsheet.nodes = nodes
            flowsheet.edges = edges
        else:
            flowsheet = Flowsheet(project_id=project_id, nodes=nodes, edges=edges)
            db.add(flowsheet)
        await db.flush()

    return ImportResult(
        nodes_imported=len(nodes),
        edges_imported=len(edges),
        warnings=result.get("warnings", []),
        skipped_types=result.get("skipped_types", []),
    )
