"""Pure Python diff utility for comparing two flowsheet versions."""
from typing import Any


def diff_flowsheets(
    v1_nodes: list[dict[str, Any]],
    v1_edges: list[dict[str, Any]],
    v2_nodes: list[dict[str, Any]],
    v2_edges: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compare two flowsheet versions and return differences."""
    return {
        "added_nodes": _find_added(v1_nodes, v2_nodes),
        "removed_nodes": _find_added(v2_nodes, v1_nodes),
        "modified_nodes": _find_modified(v1_nodes, v2_nodes),
        "added_edges": _find_added(v1_edges, v2_edges),
        "removed_edges": _find_added(v2_edges, v1_edges),
        "modified_edges": _find_modified(v1_edges, v2_edges),
    }


def _get_id(item: dict[str, Any]) -> str:
    return str(item.get("id", ""))


def _find_added(
    old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    old_ids = {_get_id(item) for item in old_items}
    return [item for item in new_items if _get_id(item) not in old_ids]


def _find_modified(
    old_items: list[dict[str, Any]], new_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    old_map = {_get_id(item): item for item in old_items}
    modified = []
    for item in new_items:
        item_id = _get_id(item)
        if item_id in old_map and item != old_map[item_id]:
            modified.append({
                "id": item_id,
                "old": old_map[item_id],
                "new": item,
            })
    return modified
