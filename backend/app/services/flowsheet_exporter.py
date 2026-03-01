"""Export flowsheets in JSON, XML, and DWSIM XML formats."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any


def export_json(
    project_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    property_package: str | None = None,
) -> str:
    """Export flowsheet as ProSim native JSON."""
    data = {
        "format": "prosim-cloud",
        "version": "1.0",
        "project_name": project_name,
        "property_package": property_package,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "flowsheet": {
            "nodes": nodes,
            "edges": edges,
        },
    }
    return json.dumps(data, indent=2)


def export_xml(
    project_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    property_package: str | None = None,
) -> str:
    """Export flowsheet as ProSim XML."""
    root = ET.Element("Flowsheet", format="prosim-cloud", version="1.0")

    metadata = ET.SubElement(root, "Metadata")
    ET.SubElement(metadata, "ProjectName").text = project_name
    ET.SubElement(metadata, "PropertyPackage").text = property_package or ""
    ET.SubElement(metadata, "ExportedAt").text = datetime.now(timezone.utc).isoformat()

    nodes_el = ET.SubElement(root, "Nodes")
    for node in nodes:
        eq_type = node.get("data", {}).get("equipmentType", "") or node.get("type", "")
        node_el = ET.SubElement(
            nodes_el, "Node",
            id=str(node.get("id", "")),
            type=str(eq_type),
        )
        name = node.get("data", {}).get("name", "") or node.get("name", "")
        if name:
            node_el.set("name", str(name))
        params = node.get("data", {}).get("parameters", {}) or node.get("parameters", {})
        if params:
            params_el = ET.SubElement(node_el, "Parameters")
            for key, val in params.items():
                param_el = ET.SubElement(params_el, "Parameter", key=key)
                param_el.text = str(val)
        pos = node.get("position", {})
        if pos:
            ET.SubElement(node_el, "Position", x=str(pos.get("x", 0)), y=str(pos.get("y", 0)))

    edges_el = ET.SubElement(root, "Edges")
    for edge in edges:
        ET.SubElement(
            edges_el, "Edge",
            id=str(edge.get("id", "")),
            source=str(edge.get("source", "")),
            target=str(edge.get("target", "")),
            sourceHandle=str(edge.get("sourceHandle", edge.get("source_handle", ""))),
            targetHandle=str(edge.get("targetHandle", edge.get("target_handle", ""))),
        )

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


# Mapping ProSim equipment types to DWSIM SimulationObject names
_PROSIM_TO_DWSIM = {
    "Heater": "Heater",
    "Cooler": "Cooler",
    "Mixer": "Mixer",
    "Splitter": "Splitter",
    "Separator": "Flash3",
    "Pump": "Pump",
    "Compressor": "Compressor",
    "Valve": "Valve",
    "HeatExchanger": "HeatExchanger",
    "DistillationColumn": "DistillationColumn",
    "CSTRReactor": "CSTR",
    "PFRReactor": "PFR",
    "ConversionReactor": "ConversionReactor",
    "Absorber": "AbsorptionColumn",
    "Stripper": "AbsorptionColumn",
    "Cyclone": "ComponentSeparator",
    "ThreePhaseSeparator": "Flash3",
    "Crystallizer": "ComponentSeparator",
    "Dryer": "Heater",
    "Filter": "ComponentSeparator",
}


def export_dwsim_xml(
    project_name: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    property_package: str | None = None,
) -> str:
    """Export flowsheet as best-effort DWSIM XML format."""
    root = ET.Element("DWSIM_Simulation_Data")

    settings = ET.SubElement(root, "Settings")
    ET.SubElement(settings, "SimulationName").text = project_name
    ET.SubElement(settings, "PropertyPackage").text = property_package or "Peng-Robinson (PR)"

    sim_objects = ET.SubElement(root, "SimulationObjects")
    for node in nodes:
        eq_type = node.get("data", {}).get("equipmentType", "") or node.get("type", "")
        dwsim_type = _PROSIM_TO_DWSIM.get(eq_type, eq_type)
        name = node.get("data", {}).get("name", "") or node.get("name", "")
        obj = ET.SubElement(sim_objects, "SimulationObject")
        ET.SubElement(obj, "Type").text = dwsim_type
        ET.SubElement(obj, "Name").text = str(name)
        ET.SubElement(obj, "Tag").text = str(node.get("id", ""))

    graphic_objects = ET.SubElement(root, "GraphicObjects")
    for node in nodes:
        pos = node.get("position", {})
        go = ET.SubElement(graphic_objects, "GraphicObject")
        ET.SubElement(go, "Tag").text = str(node.get("id", ""))
        ET.SubElement(go, "X").text = str(pos.get("x", 0))
        ET.SubElement(go, "Y").text = str(pos.get("y", 0))

    connections = ET.SubElement(root, "Connections")
    for edge in edges:
        conn = ET.SubElement(connections, "Connection")
        ET.SubElement(conn, "From").text = str(edge.get("source", ""))
        ET.SubElement(conn, "To").text = str(edge.get("target", ""))
        ET.SubElement(conn, "FromPort").text = str(edge.get("sourceHandle", edge.get("source_handle", "")))
        ET.SubElement(conn, "ToPort").text = str(edge.get("targetHandle", edge.get("target_handle", "")))

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
