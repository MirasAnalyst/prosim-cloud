"""Validate and auto-complete AI-generated flowsheet actions.

Ensures every required port is connected, removes standalone reboilers/condensers
that should be integral to column models, and cleans up isolated equipment.
"""

import logging
import re

from app.schemas.agent import FlowsheetAction, FlowsheetEquipment, FlowsheetConnection
from app.services.port_registry import (
    get_all_ports,
    get_required_ports,
    is_valid_port,
    get_port_name,
    get_port_type,
)

logger = logging.getLogger(__name__)

# Equipment names that indicate integral column internals (case-insensitive patterns)
_COLUMN_INTERNAL_PATTERNS = [
    r"\breboiler\b",
    r"\breflux\s*drum\b",
    r"\bcondenser\b",
    r"\bpump[\s-]*around\b",
    r"\boverhead\s*accumulator\b",
]

# Descriptive ProductStream names based on port function
_PORT_PRODUCT_NAMES: dict[str, dict[str, str]] = {
    "Separator": {"out-1": "Vapor Product", "out-2": "Liquid Product"},
    "DistillationColumn": {"out-1": "Distillate", "out-2": "Bottoms", "out-3": "Side Draw", "out-4": "Side Draw 2", "out-5": "Side Draw 3"},
    "Absorber": {"out-1": "Lean Gas", "out-2": "Rich Solvent"},
    "Stripper": {"out-1": "Overhead Gas", "out-2": "Lean Solvent"},
    "Cyclone": {"out-1": "Clean Gas", "out-2": "Solids"},
    "ThreePhaseSeparator": {"out-1": "Vapor", "out-2": "Light Liquid", "out-3": "Heavy Liquid"},
    "Crystallizer": {"out-1": "Crystals", "out-2": "Mother Liquor"},
    "Dryer": {"out-1": "Dry Product", "out-2": "Vapor"},
    "Filter": {"out-1": "Filtrate", "out-2": "Cake"},
    "HeatExchanger": {"out-hot": "Hot Product", "out-cold": "Cold Product"},
    "Splitter": {"out-1": "Product 1", "out-2": "Product 2"},
}


def _is_column_internal(name: str) -> bool:
    """Check if equipment name suggests it's a column internal component."""
    name_lower = name.lower()
    return any(re.search(pat, name_lower) for pat in _COLUMN_INTERNAL_PATTERNS)


def _next_equip_id(existing_ids: set[str]) -> str:
    """Generate the next sequential equip-N ID."""
    max_n = 0
    for eid in existing_ids:
        m = re.match(r"equip-(\d+)", eid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"equip-{max_n + 1}"


def _get_equipment_by_id(equipment: list[FlowsheetEquipment], eq_id: str) -> FlowsheetEquipment | None:
    """Find equipment by ID."""
    for eq in equipment:
        if eq.id == eq_id:
            return eq
    return None


def validate_and_complete(
    action: FlowsheetAction,
) -> tuple[FlowsheetAction, list[str]]:
    """Validate and auto-complete an AI-generated flowsheet action.

    Returns:
        (completed_action, completion_log) where completion_log lists every auto-fix.
    """
    log: list[str] = []
    equipment = list(action.equipment)
    connections = list(action.connections)
    eq_ids = {eq.id for eq in equipment}

    # ── Step 1: Remove invalid connections ──
    valid_connections: list[FlowsheetConnection] = []
    for conn in connections:
        # Check equipment IDs exist
        if conn.source_id not in eq_ids:
            log.append(f"Removed connection: source '{conn.source_id}' does not exist")
            continue
        if conn.target_id not in eq_ids:
            log.append(f"Removed connection: target '{conn.target_id}' does not exist")
            continue
        # Check port IDs are valid for the equipment type
        src_eq = _get_equipment_by_id(equipment, conn.source_id)
        tgt_eq = _get_equipment_by_id(equipment, conn.target_id)
        if src_eq and not is_valid_port(src_eq.type, conn.source_port):
            log.append(f"Removed connection: invalid port '{conn.source_port}' on {src_eq.type} '{src_eq.name}'")
            continue
        if tgt_eq and not is_valid_port(tgt_eq.type, conn.target_port):
            log.append(f"Removed connection: invalid port '{conn.target_port}' on {tgt_eq.type} '{tgt_eq.name}'")
            continue
        # Check directionality: source must be outlet, target must be inlet
        if src_eq:
            src_dir = get_port_type(src_eq.type, conn.source_port)
            if src_dir and src_dir != "outlet":
                log.append(f"Removed connection: source port '{conn.source_port}' on {src_eq.type} '{src_eq.name}' is an inlet, not outlet")
                continue
        if tgt_eq:
            tgt_dir = get_port_type(tgt_eq.type, conn.target_port)
            if tgt_dir and tgt_dir != "inlet":
                log.append(f"Removed connection: target port '{conn.target_port}' on {tgt_eq.type} '{tgt_eq.name}' is an outlet, not inlet")
                continue
        valid_connections.append(conn)
    connections = valid_connections

    # ── Step 2: Remove standalone column internals ──
    # Build connection sets for quick lookup
    connected_eq_ids = set()
    for conn in connections:
        connected_eq_ids.add(conn.source_id)
        connected_eq_ids.add(conn.target_id)

    # Find column/stripper IDs
    column_ids = {eq.id for eq in equipment if eq.type in ("DistillationColumn", "Stripper")}

    remove_ids: set[str] = set()
    for eq in equipment:
        if eq.type in ("FeedStream", "ProductStream", "DistillationColumn", "Stripper"):
            continue
        if not _is_column_internal(eq.name):
            continue

        # Check if this equipment is only connected to column energy ports or not connected at all
        eq_connections = [c for c in connections if c.source_id == eq.id or c.target_id == eq.id]

        if not eq_connections:
            # Completely disconnected column internal — remove
            remove_ids.add(eq.id)
            log.append(f"Removed standalone column internal: {eq.type} '{eq.name}' (no connections)")
            continue

        # Check if all connections are to/from columns
        only_column_connected = all(
            (c.source_id in column_ids or c.target_id in column_ids)
            for c in eq_connections
        )
        if only_column_connected and eq.type in ("Heater", "Cooler", "HeatExchanger"):
            remove_ids.add(eq.id)
            log.append(f"Removed standalone column internal: {eq.type} '{eq.name}' (integral to column model)")

    if remove_ids:
        equipment = [eq for eq in equipment if eq.id not in remove_ids]
        connections = [c for c in connections if c.source_id not in remove_ids and c.target_id not in remove_ids]
        eq_ids = {eq.id for eq in equipment}

    # ── Step 3: Remove fully isolated equipment ──
    connected_eq_ids_updated = set()
    for conn in connections:
        connected_eq_ids_updated.add(conn.source_id)
        connected_eq_ids_updated.add(conn.target_id)

    isolated_remove: set[str] = set()
    for eq in equipment:
        if eq.type in ("FeedStream", "ProductStream", "DesignSpec"):
            continue
        if eq.id not in connected_eq_ids_updated:
            isolated_remove.add(eq.id)
            log.append(f"Removed isolated equipment: {eq.type} '{eq.name}' (zero connections)")

    if isolated_remove:
        equipment = [eq for eq in equipment if eq.id not in isolated_remove]
        eq_ids = {eq.id for eq in equipment}

    # ── Step 4: Auto-complete unconnected REQUIRED outlets ──
    connected_out_ports = {(c.source_id, c.source_port) for c in connections}

    for eq in list(equipment):
        if eq.type in ("ProductStream", "DesignSpec"):
            continue
        required_outlets = get_required_ports(eq.type, "outlet")
        for port in required_outlets:
            if (eq.id, port["id"]) in connected_out_ports:
                continue

            # Create descriptive ProductStream
            port_names = _PORT_PRODUCT_NAMES.get(eq.type, {})
            prod_name = port_names.get(port["id"], f"{eq.name} {port['name']}")

            new_id = _next_equip_id(eq_ids)
            eq_ids.add(new_id)

            equipment.append(FlowsheetEquipment(
                id=new_id,
                type="ProductStream",
                name=prod_name,
                parameters={},
            ))
            connections.append(FlowsheetConnection(
                source_id=eq.id,
                source_port=port["id"],
                target_id=new_id,
                target_port="in-1",
            ))
            connected_out_ports.add((eq.id, port["id"]))
            log.append(f"Auto-created ProductStream '{prod_name}' for {eq.type} '{eq.name}' port {port['id']}")

    # ── Step 4b: Auto-complete DistillationColumn side draws when configured ──
    # Side-draw ports are optional (required=False), but should get ProductStreams
    # when the user has set sideDrawStage > 0 in the column parameters.
    _SD_PORT_PARAM_MAP = {"out-3": "sideDrawStage", "out-4": "sideDrawStage2", "out-5": "sideDrawStage3"}
    for eq in list(equipment):
        if eq.type != "DistillationColumn":
            continue
        params = eq.parameters or {}
        for port_id, param_key in _SD_PORT_PARAM_MAP.items():
            if (eq.id, port_id) in connected_out_ports:
                continue
            sd_stage = params.get(param_key, 0)
            try:
                sd_val = int(sd_stage) if sd_stage else 0
            except (ValueError, TypeError):
                sd_val = 0
            if sd_val <= 0:
                continue  # Side draw not configured — skip

            prod_name = _PORT_PRODUCT_NAMES.get("DistillationColumn", {}).get(port_id, f"Side Draw")
            new_id = _next_equip_id(eq_ids)
            eq_ids.add(new_id)
            equipment.append(FlowsheetEquipment(
                id=new_id, type="ProductStream", name=prod_name, parameters={},
            ))
            connections.append(FlowsheetConnection(
                source_id=eq.id, source_port=port_id, target_id=new_id, target_port="in-1",
            ))
            connected_out_ports.add((eq.id, port_id))
            log.append(f"Auto-created ProductStream '{prod_name}' for {eq.type} '{eq.name}' side draw port {port_id} (stage {sd_val})")

    # ── Step 5: Auto-complete unconnected REQUIRED inlets ──
    connected_in_ports = {(c.target_id, c.target_port) for c in connections}

    for eq in list(equipment):
        if eq.type in ("FeedStream", "DesignSpec"):
            continue
        required_inlets = get_required_ports(eq.type, "inlet")
        for port in required_inlets:
            if (eq.id, port["id"]) in connected_in_ports:
                continue

            # Create placeholder FeedStream
            feed_name = f"{eq.name} Feed"
            new_id = _next_equip_id(eq_ids)
            eq_ids.add(new_id)

            equipment.append(FlowsheetEquipment(
                id=new_id,
                type="FeedStream",
                name=feed_name,
                parameters={
                    "feedTemperature": 25,
                    "feedPressure": 101.325,
                    "feedFlowRate": 1.0,
                    "feedComposition": '{"water":1.0}',
                },
            ))
            connections.append(FlowsheetConnection(
                source_id=new_id,
                source_port="out-1",
                target_id=eq.id,
                target_port=port["id"],
            ))
            connected_in_ports.add((eq.id, port["id"]))
            log.append(f"WARNING: Auto-created placeholder FeedStream '{feed_name}' for {eq.type} '{eq.name}' port {port['id']} — update composition!")

    # ── Step 6: Detect isolated FeedStreams ──
    connected_sources = {c.source_id for c in connections}
    for eq in equipment:
        if eq.type == "FeedStream" and eq.id not in connected_sources:
            log.append(f"WARNING: FeedStream '{eq.name}' has no outgoing connection")

    # Log summary
    if log:
        logger.info("Flowsheet completer applied %d fixes", len(log))
        for entry in log:
            logger.info("  %s", entry)

    completed = FlowsheetAction(
        equipment=equipment,
        connections=connections,
        mode=action.mode,
    )
    return completed, log
