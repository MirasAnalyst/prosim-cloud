"""Port registry mirroring frontend equipment-library.ts port definitions.

Provides port metadata with a `required` flag for each material port.
Used by the flowsheet completer to validate and auto-complete AI-generated flowsheets.
"""

from typing import TypedDict


class PortDef(TypedDict):
    id: str
    name: str
    type: str  # "inlet" or "outlet"
    required: bool


# Material ports only (energy ports excluded).
# `required=False` means the port is optional — no auto-ProductStream needed.
PORT_REGISTRY: dict[str, list[PortDef]] = {
    "FeedStream": [
        {"id": "out-1", "name": "Outlet", "type": "outlet", "required": True},
    ],
    "ProductStream": [
        {"id": "in-1", "name": "Inlet", "type": "inlet", "required": True},
    ],
    "Heater": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "Cooler": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "Mixer": [
        {"id": "in-1", "name": "Feed 1", "type": "inlet", "required": True},
        {"id": "in-2", "name": "Feed 2", "type": "inlet", "required": True},
        {"id": "in-3", "name": "Feed 3", "type": "inlet", "required": False},
        {"id": "in-4", "name": "Feed 4", "type": "inlet", "required": False},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "Splitter": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product 1", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Product 2", "type": "outlet", "required": True},
    ],
    "Separator": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Vapour", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Liquid", "type": "outlet", "required": True},
    ],
    "Pump": [
        {"id": "in-1", "name": "Inlet", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Outlet", "type": "outlet", "required": True},
    ],
    "Compressor": [
        {"id": "in-1", "name": "Inlet", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Outlet", "type": "outlet", "required": True},
    ],
    "Valve": [
        {"id": "in-1", "name": "Inlet", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Outlet", "type": "outlet", "required": True},
    ],
    "HeatExchanger": [
        {"id": "in-hot", "name": "Hot Inlet", "type": "inlet", "required": True},
        {"id": "in-cold", "name": "Cold Inlet", "type": "inlet", "required": True},
        {"id": "out-hot", "name": "Hot Outlet", "type": "outlet", "required": True},
        {"id": "out-cold", "name": "Cold Outlet", "type": "outlet", "required": True},
    ],
    "DistillationColumn": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "in-2", "name": "Feed 2", "type": "inlet", "required": False},
        {"id": "out-1", "name": "Distillate", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Bottoms", "type": "outlet", "required": True},
        {"id": "out-3", "name": "Side Draw", "type": "outlet", "required": False},
        {"id": "out-4", "name": "Side Draw 2", "type": "outlet", "required": False},
        {"id": "out-5", "name": "Side Draw 3", "type": "outlet", "required": False},
    ],
    "CSTRReactor": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "PFRReactor": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "ConversionReactor": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "Absorber": [
        {"id": "in-1", "name": "Gas Feed", "type": "inlet", "required": True},
        {"id": "in-2", "name": "Solvent", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Lean Gas", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Rich Solvent", "type": "outlet", "required": True},
    ],
    "Stripper": [
        {"id": "in-1", "name": "Rich Solvent", "type": "inlet", "required": True},
        {"id": "in-2", "name": "Stripping Gas", "type": "inlet", "required": False},
        {"id": "out-1", "name": "Overhead Gas", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Lean Solvent", "type": "outlet", "required": True},
    ],
    "Cyclone": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Clean Gas", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Solids", "type": "outlet", "required": True},
    ],
    "ThreePhaseSeparator": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Vapor", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Light Liquid", "type": "outlet", "required": True},
        {"id": "out-3", "name": "Heavy Liquid", "type": "outlet", "required": True},
    ],
    "Crystallizer": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Crystals", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Mother Liquor", "type": "outlet", "required": True},
    ],
    "Dryer": [
        {"id": "in-1", "name": "Wet Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Dry Product", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Vapor", "type": "outlet", "required": True},
    ],
    "Filter": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Filtrate", "type": "outlet", "required": True},
        {"id": "out-2", "name": "Cake", "type": "outlet", "required": True},
    ],
    "DesignSpec": [],
    "PipeSegment": [
        {"id": "in-1", "name": "Inlet", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Outlet", "type": "outlet", "required": True},
    ],
    "EquilibriumReactor": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
    "GibbsReactor": [
        {"id": "in-1", "name": "Feed", "type": "inlet", "required": True},
        {"id": "out-1", "name": "Product", "type": "outlet", "required": True},
    ],
}


def get_all_ports(eq_type: str) -> list[PortDef]:
    """Return all material ports for an equipment type."""
    return PORT_REGISTRY.get(eq_type, [])


def get_required_ports(eq_type: str, port_type: str) -> list[PortDef]:
    """Return required ports of the given type ('inlet' or 'outlet')."""
    return [p for p in get_all_ports(eq_type) if p["type"] == port_type and p["required"]]


def get_optional_ports(eq_type: str, port_type: str) -> list[PortDef]:
    """Return optional ports of the given type ('inlet' or 'outlet')."""
    return [p for p in get_all_ports(eq_type) if p["type"] == port_type and not p["required"]]


def is_optional_port(eq_type: str, port_id: str) -> bool:
    """Check if a specific port is optional."""
    for p in get_all_ports(eq_type):
        if p["id"] == port_id:
            return not p["required"]
    return False


def is_valid_port(eq_type: str, port_id: str) -> bool:
    """Check if a port ID is valid for the equipment type (material ports only)."""
    return any(p["id"] == port_id for p in get_all_ports(eq_type))


def get_port_name(eq_type: str, port_id: str) -> str:
    """Get the display name for a port."""
    for p in get_all_ports(eq_type):
        if p["id"] == port_id:
            return p["name"]
    return port_id


def get_port_type(eq_type: str, port_id: str) -> str | None:
    """Get port direction type ('inlet' or 'outlet'), or None if not found."""
    for p in get_all_ports(eq_type):
        if p["id"] == port_id:
            return p["type"]
    return None
