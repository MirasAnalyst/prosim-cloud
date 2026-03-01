"""Import flowsheets from DWSIM .dwxmz files and other formats."""
import io
import json
import logging
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from uuid import uuid4

logger = logging.getLogger(__name__)

# Mapping DWSIM SimulationObject types to ProSim types
_DWSIM_TO_PROSIM = {
    "Heater": "Heater",
    "Cooler": "Cooler",
    "Mixer": "Mixer",
    "Splitter": "Splitter",
    "Flash3": "Separator",
    "Flash": "Separator",
    "Pump": "Pump",
    "Compressor": "Compressor",
    "Valve": "Valve",
    "HeatExchanger": "HeatExchanger",
    "DistillationColumn": "DistillationColumn",
    "ShortcutColumn": "DistillationColumn",
    "CSTR": "CSTRReactor",
    "PFR": "PFRReactor",
    "ConversionReactor": "ConversionReactor",
    "AbsorptionColumn": "Absorber",
    "ComponentSeparator": "Separator",
}


def import_dwsim_xml(xml_content: str) -> dict[str, Any]:
    """Parse DWSIM XML and map to ProSim format."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped_types: list[str] = []
    id_map: dict[str, str] = {}

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        return {
            "nodes": [], "edges": [],
            "warnings": [f"XML parse error: {e}"],
            "skipped_types": [],
        }

    # Parse graphic objects for positions
    positions: dict[str, dict[str, float]] = {}
    for go in root.iter("GraphicObject"):
        tag = _text(go, "Tag") or _text(go, "Name") or ""
        x = _float(go, "X", 0)
        y = _float(go, "Y", 0)
        if tag:
            positions[tag] = {"x": x, "y": y}

    # Parse simulation objects
    for obj in root.iter("SimulationObject"):
        dwsim_type = _text(obj, "Type") or ""
        name = _text(obj, "Name") or ""
        tag = _text(obj, "Tag") or name

        prosim_type = _DWSIM_TO_PROSIM.get(dwsim_type)
        if not prosim_type:
            skipped_types.append(dwsim_type)
            warnings.append(f"Skipped unrecognized equipment type: {dwsim_type} ({name})")
            continue

        new_id = str(uuid4())
        id_map[tag] = new_id
        pos = positions.get(tag, {"x": len(nodes) * 200, "y": 100})

        nodes.append({
            "id": new_id,
            "type": "equipment",
            "position": pos,
            "data": {
                "equipmentType": prosim_type,
                "name": name or prosim_type,
                "parameters": {},
            },
        })

    # Parse connections
    for conn in root.iter("Connection"):
        from_tag = _text(conn, "From") or ""
        to_tag = _text(conn, "To") or ""
        from_id = id_map.get(from_tag)
        to_id = id_map.get(to_tag)
        if from_id and to_id:
            edges.append({
                "id": str(uuid4()),
                "source": from_id,
                "target": to_id,
                "sourceHandle": _text(conn, "FromPort") or "out-0",
                "targetHandle": _text(conn, "ToPort") or "in-0",
            })
        elif from_tag or to_tag:
            warnings.append(f"Skipped connection {from_tag} → {to_tag}: node not found")

    return {
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
        "skipped_types": list(set(skipped_types)),
    }


def import_dwsim_zip(zip_bytes: bytes) -> dict[str, Any]:
    """Parse .dwxmz ZIP archive and extract XML."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xml_files = [f for f in zf.namelist() if f.endswith(".xml") or f.endswith(".dwxml")]
            if not xml_files:
                # Try the first file
                xml_files = zf.namelist()[:1]
            if not xml_files:
                return {
                    "nodes": [], "edges": [],
                    "warnings": ["No XML file found in archive"],
                    "skipped_types": [],
                }
            xml_content = zf.read(xml_files[0]).decode("utf-8")
            return import_dwsim_xml(xml_content)
    except zipfile.BadZipFile:
        return {
            "nodes": [], "edges": [],
            "warnings": ["Invalid ZIP file"],
            "skipped_types": [],
        }


def import_prosim_json(json_content: str) -> dict[str, Any]:
    """Parse ProSim native JSON format."""
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        return {
            "nodes": [], "edges": [],
            "warnings": [f"JSON parse error: {e}"],
            "skipped_types": [],
        }

    flowsheet = data.get("flowsheet", data)
    nodes = flowsheet.get("nodes", [])
    edges = flowsheet.get("edges", [])

    return {
        "nodes": nodes,
        "edges": edges,
        "warnings": [],
        "skipped_types": [],
    }


def import_prosim_xml(xml_content: str) -> dict[str, Any]:
    """Parse ProSim XML format."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        return {
            "nodes": [], "edges": [],
            "warnings": [f"XML parse error: {e}"],
            "skipped_types": [],
        }

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for node_el in root.iter("Node"):
        node_id = node_el.get("id", str(uuid4()))
        eq_type = node_el.get("type", "")
        name = node_el.get("name", eq_type)
        params: dict[str, Any] = {}
        params_el = node_el.find("Parameters")
        if params_el is not None:
            for p in params_el.findall("Parameter"):
                key = p.get("key", "")
                val = p.text or ""
                try:
                    params[key] = float(val)
                except ValueError:
                    params[key] = val

        pos = {"x": 0.0, "y": 0.0}
        pos_el = node_el.find("Position")
        if pos_el is not None:
            pos["x"] = float(pos_el.get("x", "0"))
            pos["y"] = float(pos_el.get("y", "0"))

        nodes.append({
            "id": node_id,
            "type": "equipment",
            "position": pos,
            "data": {
                "equipmentType": eq_type,
                "name": name,
                "parameters": params,
            },
        })

    for edge_el in root.iter("Edge"):
        edges.append({
            "id": edge_el.get("id", str(uuid4())),
            "source": edge_el.get("source", ""),
            "target": edge_el.get("target", ""),
            "sourceHandle": edge_el.get("sourceHandle", ""),
            "targetHandle": edge_el.get("targetHandle", ""),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "warnings": [],
        "skipped_types": [],
    }


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(tag)
    return child.text if child is not None else None


def _float(el: ET.Element, tag: str, default: float = 0.0) -> float:
    text = _text(el, tag)
    if text is None:
        return default
    try:
        return float(text)
    except ValueError:
        return default
