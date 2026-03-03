import logging
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter()

# Curated list of common process-simulation compounds with CAS and formula.
# Shown as "favorites" and searched first for fast matching.
_COMMON_COMPOUNDS: list[dict[str, str]] = [
    {"name": "water", "cas": "7732-18-5", "formula": "H2O"},
    {"name": "methane", "cas": "74-82-8", "formula": "CH4"},
    {"name": "ethane", "cas": "74-84-0", "formula": "C2H6"},
    {"name": "propane", "cas": "74-98-6", "formula": "C3H8"},
    {"name": "n-butane", "cas": "106-97-8", "formula": "C4H10"},
    {"name": "isobutane", "cas": "75-28-5", "formula": "C4H10"},
    {"name": "n-pentane", "cas": "109-66-0", "formula": "C5H12"},
    {"name": "isopentane", "cas": "78-78-4", "formula": "C5H12"},
    {"name": "n-hexane", "cas": "110-54-3", "formula": "C6H14"},
    {"name": "n-heptane", "cas": "142-82-5", "formula": "C7H16"},
    {"name": "n-octane", "cas": "111-65-9", "formula": "C8H18"},
    {"name": "n-nonane", "cas": "111-84-2", "formula": "C9H20"},
    {"name": "n-decane", "cas": "124-18-5", "formula": "C10H22"},
    {"name": "n-dodecane", "cas": "112-40-3", "formula": "C12H26"},
    {"name": "n-hexadecane", "cas": "544-76-3", "formula": "C16H34"},
    {"name": "ethylene", "cas": "74-85-1", "formula": "C2H4"},
    {"name": "propylene", "cas": "115-07-1", "formula": "C3H6"},
    {"name": "1-butene", "cas": "106-98-9", "formula": "C4H8"},
    {"name": "benzene", "cas": "71-43-2", "formula": "C6H6"},
    {"name": "toluene", "cas": "108-88-3", "formula": "C7H8"},
    {"name": "o-xylene", "cas": "95-47-6", "formula": "C8H10"},
    {"name": "m-xylene", "cas": "108-38-3", "formula": "C8H10"},
    {"name": "p-xylene", "cas": "106-42-3", "formula": "C8H10"},
    {"name": "ethylbenzene", "cas": "100-41-4", "formula": "C8H10"},
    {"name": "styrene", "cas": "100-42-5", "formula": "C8H8"},
    {"name": "cyclohexane", "cas": "110-82-7", "formula": "C6H12"},
    {"name": "methanol", "cas": "67-56-1", "formula": "CH3OH"},
    {"name": "ethanol", "cas": "64-17-5", "formula": "C2H5OH"},
    {"name": "1-propanol", "cas": "71-23-8", "formula": "C3H7OH"},
    {"name": "2-propanol", "cas": "67-63-0", "formula": "C3H7OH"},
    {"name": "1-butanol", "cas": "71-36-3", "formula": "C4H10O"},
    {"name": "ethylene glycol", "cas": "107-21-1", "formula": "C2H6O2"},
    {"name": "diethylene glycol", "cas": "111-46-6", "formula": "C4H10O3"},
    {"name": "triethylene glycol", "cas": "112-27-6", "formula": "C6H14O4"},
    {"name": "glycerol", "cas": "56-81-5", "formula": "C3H8O3"},
    {"name": "acetone", "cas": "67-64-1", "formula": "C3H6O"},
    {"name": "acetic acid", "cas": "64-19-7", "formula": "CH3COOH"},
    {"name": "acrylic acid", "cas": "79-10-7", "formula": "C3H4O2"},
    {"name": "formic acid", "cas": "64-18-6", "formula": "HCOOH"},
    {"name": "formaldehyde", "cas": "50-00-0", "formula": "CH2O"},
    {"name": "diethyl ether", "cas": "60-29-7", "formula": "C4H10O"},
    {"name": "dimethyl ether", "cas": "115-10-6", "formula": "C2H6O"},
    {"name": "tert-butyl methyl ether", "cas": "1634-04-4", "formula": "C5H12O"},
    {"name": "hydrogen", "cas": "1333-74-0", "formula": "H2"},
    {"name": "nitrogen", "cas": "7727-37-9", "formula": "N2"},
    {"name": "oxygen", "cas": "7782-44-7", "formula": "O2"},
    {"name": "carbon dioxide", "cas": "124-38-9", "formula": "CO2"},
    {"name": "carbon monoxide", "cas": "630-08-0", "formula": "CO"},
    {"name": "hydrogen sulfide", "cas": "7783-06-4", "formula": "H2S"},
    {"name": "sulfur dioxide", "cas": "7446-09-5", "formula": "SO2"},
    {"name": "ammonia", "cas": "7664-41-7", "formula": "NH3"},
    {"name": "chlorine", "cas": "7782-50-5", "formula": "Cl2"},
    {"name": "hydrogen chloride", "cas": "7647-01-0", "formula": "HCl"},
    {"name": "argon", "cas": "7440-37-1", "formula": "Ar"},
    {"name": "helium", "cas": "7440-59-7", "formula": "He"},
    {"name": "diethanolamine", "cas": "111-42-2", "formula": "C4H11NO2"},
    {"name": "monoethanolamine", "cas": "141-43-5", "formula": "C2H7NO"},
    {"name": "methyldiethanolamine", "cas": "105-59-9", "formula": "C5H13NO2"},
    {"name": "phenol", "cas": "108-95-2", "formula": "C6H6O"},
    {"name": "aniline", "cas": "62-53-3", "formula": "C6H7N"},
    {"name": "naphthalene", "cas": "91-20-3", "formula": "C10H8"},
    {"name": "acetaldehyde", "cas": "75-07-0", "formula": "C2H4O"},
    {"name": "ethylene oxide", "cas": "75-21-8", "formula": "C2H4O"},
    {"name": "propylene oxide", "cas": "75-56-9", "formula": "C3H6O"},
    {"name": "vinyl chloride", "cas": "75-01-4", "formula": "C2H3Cl"},
    {"name": "dichloromethane", "cas": "75-09-2", "formula": "CH2Cl2"},
    {"name": "chloroform", "cas": "67-66-3", "formula": "CHCl3"},
    {"name": "carbon tetrachloride", "cas": "56-23-5", "formula": "CCl4"},
    {"name": "dimethylformamide", "cas": "68-12-2", "formula": "C3H7NO"},
    {"name": "dimethyl sulfoxide", "cas": "67-68-5", "formula": "C2H6OS"},
    {"name": "tetrahydrofuran", "cas": "109-99-9", "formula": "C4H8O"},
    {"name": "acetonitrile", "cas": "75-05-8", "formula": "C2H3N"},
    {"name": "nitric acid", "cas": "7697-37-2", "formula": "HNO3"},
    {"name": "sulfuric acid", "cas": "7664-93-9", "formula": "H2SO4"},
    {"name": "phosphoric acid", "cas": "7664-38-2", "formula": "H3PO4"},
    {"name": "urea", "cas": "57-13-6", "formula": "CH4N2O"},
    {"name": "sodium chloride", "cas": "7647-14-5", "formula": "NaCl"},
    {"name": "potassium chloride", "cas": "7447-40-7", "formula": "KCl"},
    {"name": "calcium chloride", "cas": "10043-52-4", "formula": "CaCl2"},
    {"name": "sodium hydroxide", "cas": "1310-73-2", "formula": "NaOH"},
]

# Set of curated CAS numbers for quick duplicate detection
_CURATED_CAS = {c["cas"] for c in _COMMON_COMPOUNDS}

# Try to use thermo/chemicals for extended search
_thermo_available = False
_chemicals_available = False
try:
    from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]
    _thermo_available = True
except Exception:
    pass

try:
    from chemicals import search_chemical  # type: ignore[import-untyped]
    from chemicals.identifiers import pubchem_db  # type: ignore[import-untyped]
    _chemicals_available = True
except Exception:
    pass


def _search_chemicals_db(query: str, max_results: int = 20) -> list[dict[str, str]]:
    """Search the chemicals library database (70,000+ compounds).

    Uses chemicals.search_chemical for exact/fuzzy name lookup,
    then falls back to name_index prefix search.
    """
    if not _chemicals_available:
        return []

    results: list[dict[str, str]] = []
    seen_cas: set[str] = set()

    # 1. Try exact lookup first (handles aliases, CAS numbers, formulas)
    try:
        chem = search_chemical(query)
        if chem and chem.CASs and chem.CASs not in seen_cas:
            results.append({
                "name": chem.common_name or query,
                "cas": chem.CASs,
                "formula": chem.formula or "",
                "source": "thermo",
            })
            seen_cas.add(chem.CASs)
    except Exception:
        pass

    if len(results) >= max_results:
        return results[:max_results]

    # 2. Search the name index for substring matches
    q_lower = query.lower()
    try:
        if not pubchem_db.loaded_main_db:
            pubchem_db.autoload_main_db()

        # Prioritize starts-with matches, then contains
        starts_with: list[dict[str, str]] = []
        contains: list[dict[str, str]] = []
        count = 0
        for name, chem in pubchem_db.name_index.items():
            if count > 50000:  # safety limit to avoid scanning entire 950k index
                break
            count += 1
            name_lower = name.lower()
            if q_lower in name_lower:
                if chem.CASs in seen_cas:
                    continue
                entry = {
                    "name": chem.common_name or name,
                    "cas": chem.CASs,
                    "formula": chem.formula or "",
                    "source": "thermo",
                }
                seen_cas.add(chem.CASs)
                if name_lower.startswith(q_lower):
                    starts_with.append(entry)
                else:
                    contains.append(entry)
                if len(starts_with) + len(contains) >= max_results * 2:
                    break
        results.extend(starts_with[:max_results])
        remaining = max_results - len(results)
        if remaining > 0:
            results.extend(contains[:remaining])
    except Exception as exc:
        logger.debug("chemicals name_index search failed: %s", exc)

    return results[:max_results]


@router.get("/search")
async def search_compounds(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Search for compounds by name, CAS, or formula.

    Searches curated favorites first, then the full chemicals/thermo database
    (70,000+ compounds). Results include a 'source' field: 'curated' for
    favorites, 'thermo' for extended database.
    """
    query = q.lower().strip()

    # First, search the curated list (always fast)
    results: list[dict[str, str]] = []
    seen_cas: set[str] = set()
    for c in _COMMON_COMPOUNDS:
        if query in c["name"] or query in c["formula"].lower() or query in c["cas"]:
            results.append({**c, "source": "curated"})
            seen_cas.add(c["cas"])

    # Then search the full thermo/chemicals database
    if len(results) < limit:
        remaining = limit - len(results)
        extended = _search_chemicals_db(query, max_results=remaining + 5)
        for ext in extended:
            if ext["cas"] not in seen_cas:
                results.append(ext)
                seen_cas.add(ext["cas"])
                if len(results) >= limit:
                    break

    # If thermo is available and we still don't have results, try exact lookup
    if _thermo_available and len(results) == 0:
        try:
            constants, _ = ChemicalConstantsPackage.from_IDs([q])
            name = constants.names[0] if constants.names else q
            cas = constants.CASs[0] if constants.CASs else ""
            formula = constants.formulas[0] if constants.formulas else ""
            if cas and cas not in seen_cas:
                results.append({"name": name, "cas": cas, "formula": formula, "source": "thermo"})
        except Exception:
            pass

    return results[:limit]


@router.get("/favorites")
async def get_favorites():
    """Return the curated list of common process compounds (favorites)."""
    return [{"name": c["name"], "cas": c["cas"], "formula": c["formula"]} for c in _COMMON_COMPOUNDS]


@router.get("/info")
async def compound_info(name: str = Query(..., min_length=1)):
    """Get detailed properties for a compound by name.

    Returns critical properties, molecular weight, normal boiling point, etc.
    """
    if not _thermo_available:
        # Basic info from curated list
        for c in _COMMON_COMPOUNDS:
            if c["name"].lower() == name.lower():
                return {"name": c["name"], "cas": c["cas"], "formula": c["formula"]}
        return {"error": "Compound not found and thermo library not available"}

    try:
        constants, properties = ChemicalConstantsPackage.from_IDs([name])
        info: dict[str, Any] = {
            "name": constants.names[0] if constants.names else name,
            "cas": constants.CASs[0] if constants.CASs else "",
            "formula": constants.formulas[0] if constants.formulas else "",
            "molecular_weight": constants.MWs[0] if constants.MWs else None,
        }
        # Critical properties
        if constants.Tcs:
            info["Tc_K"] = round(constants.Tcs[0], 2) if constants.Tcs[0] else None
        if constants.Pcs:
            info["Pc_Pa"] = round(constants.Pcs[0], 1) if constants.Pcs[0] else None
        if constants.omegas:
            info["omega"] = round(constants.omegas[0], 4) if constants.omegas[0] else None
        # Normal boiling point
        if constants.Tbs:
            info["Tb_K"] = round(constants.Tbs[0], 2) if constants.Tbs[0] else None
        # Melting point
        if constants.Tms:
            info["Tm_K"] = round(constants.Tms[0], 2) if constants.Tms[0] else None
        return info
    except Exception as exc:
        return {"error": f"Could not find compound: {exc}"}


