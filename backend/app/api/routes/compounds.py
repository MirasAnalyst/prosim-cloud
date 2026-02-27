import logging

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
router = APIRouter()

# Curated list of common process-simulation compounds with CAS and formula.
# Used for client-side search when the thermo library isn't installed.
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
    {"name": "n-decane", "cas": "124-18-5", "formula": "C10H22"},
    {"name": "ethylene", "cas": "74-85-1", "formula": "C2H4"},
    {"name": "propylene", "cas": "115-07-1", "formula": "C3H6"},
    {"name": "benzene", "cas": "71-43-2", "formula": "C6H6"},
    {"name": "toluene", "cas": "108-88-3", "formula": "C7H8"},
    {"name": "o-xylene", "cas": "95-47-6", "formula": "C8H10"},
    {"name": "methanol", "cas": "67-56-1", "formula": "CH3OH"},
    {"name": "ethanol", "cas": "64-17-5", "formula": "C2H5OH"},
    {"name": "acetone", "cas": "67-64-1", "formula": "C3H6O"},
    {"name": "acetic acid", "cas": "64-19-7", "formula": "CH3COOH"},
    {"name": "hydrogen", "cas": "1333-74-0", "formula": "H2"},
    {"name": "nitrogen", "cas": "7727-37-9", "formula": "N2"},
    {"name": "oxygen", "cas": "7782-44-7", "formula": "O2"},
    {"name": "carbon dioxide", "cas": "124-38-9", "formula": "CO2"},
    {"name": "carbon monoxide", "cas": "630-08-0", "formula": "CO"},
    {"name": "hydrogen sulfide", "cas": "7783-06-4", "formula": "H2S"},
    {"name": "sulfur dioxide", "cas": "7446-09-5", "formula": "SO2"},
    {"name": "ammonia", "cas": "7664-41-7", "formula": "NH3"},
    {"name": "chlorine", "cas": "7782-50-5", "formula": "Cl2"},
    {"name": "argon", "cas": "7440-37-1", "formula": "Ar"},
    {"name": "helium", "cas": "7440-59-7", "formula": "He"},
    {"name": "cyclohexane", "cas": "110-82-7", "formula": "C6H12"},
    {"name": "styrene", "cas": "100-42-5", "formula": "C8H8"},
    {"name": "1-propanol", "cas": "71-23-8", "formula": "C3H7OH"},
    {"name": "2-propanol", "cas": "67-63-0", "formula": "C3H7OH"},
    {"name": "diethyl ether", "cas": "60-29-7", "formula": "C4H10O"},
    {"name": "dimethyl ether", "cas": "115-10-6", "formula": "C2H6O"},
    {"name": "formic acid", "cas": "64-18-6", "formula": "HCOOH"},
    {"name": "formaldehyde", "cas": "50-00-0", "formula": "CH2O"},
    {"name": "diethanolamine", "cas": "111-42-2", "formula": "C4H11NO2"},
    {"name": "monoethanolamine", "cas": "141-43-5", "formula": "C2H7NO"},
]

# Try to use thermo for validation / extended search
_thermo_available = False
try:
    from thermo import ChemicalConstantsPackage  # type: ignore[import-untyped]
    _thermo_available = True
except Exception:
    pass


@router.get("/search")
async def search_compounds(q: str = Query(..., min_length=1)):
    """Search for compounds by name. Returns matching name, CAS, formula."""
    query = q.lower().strip()

    # First, search the curated list
    results: list[dict[str, str]] = []
    for c in _COMMON_COMPOUNDS:
        if query in c["name"] or query in c["formula"].lower() or query in c["cas"]:
            results.append(c)

    # If thermo is available and we didn't find enough matches, try it
    if _thermo_available and len(results) < 5:
        # Try exact lookup via thermo
        try:
            constants, _ = ChemicalConstantsPackage.from_IDs([q])
            name = constants.names[0] if constants.names else q
            cas = constants.CASs[0] if constants.CASs else ""
            formula = constants.formulas[0] if constants.formulas else ""
            # Avoid duplicates
            if not any(r["cas"] == cas for r in results):
                results.append({"name": name, "cas": cas, "formula": formula})
        except Exception:
            pass

    return results[:20]
