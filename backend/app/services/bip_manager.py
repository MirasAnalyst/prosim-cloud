"""BIP (Binary Interaction Parameter) manager.

Retrieves BIP matrices from thermo's IPDB and identifies missing pairs.
Supports user overrides for custom BIP values.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_thermo_available = False
try:
    from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]
    from thermo.interaction_parameters import IPDB  # type: ignore[import-untyped]
    _thermo_available = True
except Exception:
    pass


def get_bip_matrix(
    comp_names: list[str],
    property_package: str = "PengRobinson",
) -> dict[str, Any]:
    """Retrieve BIP matrix for given compounds and property package.

    Args:
        comp_names: list of compound names
        property_package: PengRobinson, SRK, NRTL, or UNIQUAC

    Returns:
        {compounds, matrix (NxN), source, missing_pairs, cas_numbers}
    """
    n = len(comp_names)
    if n < 2:
        return {
            "compounds": comp_names,
            "matrix": [[0.0] * n for _ in range(n)],
            "source": "N/A (single component)",
            "missing_pairs": [],
            "cas_numbers": [],
        }

    if not _thermo_available:
        return {
            "compounds": comp_names,
            "matrix": [[0.0] * n for _ in range(n)],
            "source": "thermo library not available",
            "missing_pairs": _all_pairs(comp_names),
            "cas_numbers": [],
        }

    try:
        constants, _ = ChemicalConstantsPackage.from_IDs(comp_names)
        cas_numbers = list(constants.CASs)
    except Exception as exc:
        logger.warning("Failed to get CAS numbers: %s", exc)
        return {
            "compounds": comp_names,
            "matrix": [[0.0] * n for _ in range(n)],
            "source": f"Error: {exc}",
            "missing_pairs": _all_pairs(comp_names),
            "cas_numbers": [],
        }

    # Determine BIP source based on property package
    if property_package == "NRTL":
        source_name = "ChemSep NRTL"
        param_key = "bij"
    elif property_package == "UNIQUAC":
        source_name = "ChemSep UNIQUAC"
        param_key = "bij"
    elif property_package == "SRK":
        source_name = "ChemSep SRK"
        param_key = "kij"
    else:
        source_name = "ChemSep PR"
        param_key = "kij"

    try:
        matrix = IPDB.get_ip_asymmetric_matrix(source_name, cas_numbers, param_key)
    except Exception:
        matrix = [[0.0] * n for _ in range(n)]
        logger.warning("BIP matrix not found for %s with %s", comp_names, source_name)

    # Identify missing pairs (where BIP = 0 for off-diagonal)
    missing_pairs: list[dict[str, str]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] == 0.0 and matrix[j][i] == 0.0:
                missing_pairs.append({
                    "comp_a": comp_names[i],
                    "comp_b": comp_names[j],
                })

    return {
        "compounds": comp_names,
        "matrix": [[round(v, 6) for v in row] for row in matrix],
        "source": source_name,
        "missing_pairs": missing_pairs,
        "cas_numbers": cas_numbers,
        "parameter_type": param_key,
    }


def apply_bip_overrides(
    matrix: list[list[float]],
    comp_names: list[str],
    overrides: dict[str, float],
) -> list[list[float]]:
    """Apply user BIP overrides to a matrix.

    Args:
        matrix: NxN BIP matrix
        comp_names: compound names (order matches matrix indices)
        overrides: dict with keys "comp_a|comp_b" → kij value

    Returns:
        Updated NxN matrix
    """
    result = [row[:] for row in matrix]  # shallow copy
    name_to_idx = {name: i for i, name in enumerate(comp_names)}

    for key, value in overrides.items():
        parts = key.split("|")
        if len(parts) != 2:
            continue
        comp_a, comp_b = parts
        i = name_to_idx.get(comp_a)
        j = name_to_idx.get(comp_b)
        if i is not None and j is not None:
            result[i][j] = value
            result[j][i] = value  # symmetric

    return result


def _all_pairs(comp_names: list[str]) -> list[dict[str, str]]:
    """Return all unique pairs."""
    pairs = []
    for i in range(len(comp_names)):
        for j in range(i + 1, len(comp_names)):
            pairs.append({"comp_a": comp_names[i], "comp_b": comp_names[j]})
    return pairs
