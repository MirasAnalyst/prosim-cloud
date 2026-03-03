"""Property package advisor — decision-tree recommender.

Given a list of compound names, recommends the most appropriate
thermodynamic property package (Peng-Robinson, SRK, NRTL, UNIQUAC).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Classification tables
_POLAR_COMPOUNDS = {
    "water", "methanol", "ethanol", "1-propanol", "2-propanol", "isopropanol",
    "1-butanol", "acetone", "acetic acid", "formic acid", "acetaldehyde",
    "dimethyl sulfoxide", "acetonitrile", "dimethylformamide", "furfural",
    "ethylene glycol", "diethylene glycol", "triethylene glycol",
    "monoethanolamine", "diethanolamine", "methyldiethanolamine",
    "phenol", "aniline", "pyridine", "tetrahydrofuran",
}

_HYDROGEN_BONDING = {
    "water", "methanol", "ethanol", "1-propanol", "2-propanol", "isopropanol",
    "1-butanol", "acetic acid", "formic acid", "ethylene glycol",
    "diethylene glycol", "triethylene glycol",
    "monoethanolamine", "diethanolamine", "methyldiethanolamine",
    "phenol", "aniline",
}

_ELECTROLYTES = {
    "sodium chloride", "potassium chloride", "calcium chloride",
    "sodium hydroxide", "hydrochloric acid", "sulfuric acid",
    "nitric acid", "phosphoric acid", "ammonium chloride",
}

_LIGHT_GASES = {
    "hydrogen", "nitrogen", "oxygen", "carbon monoxide", "carbon dioxide",
    "hydrogen sulfide", "sulfur dioxide", "ammonia", "helium", "argon",
    "methane", "ethane", "ethylene", "propylene",
}

_HYDROCARBONS = {
    "methane", "ethane", "propane", "n-butane", "isobutane", "n-pentane",
    "isopentane", "neopentane", "n-hexane", "n-heptane", "n-octane",
    "n-nonane", "n-decane", "cyclohexane", "methylcyclohexane",
    "benzene", "toluene", "ethylbenzene", "o-xylene", "m-xylene", "p-xylene",
    "styrene", "naphthalene",
    "ethylene", "propylene", "1-butene", "1,3-butadiene",
}

_AMINE_SOLVENTS = {
    "monoethanolamine", "diethanolamine", "methyldiethanolamine",
}

_ACID_GASES = {"carbon dioxide", "hydrogen sulfide"}


def advise_property_package(
    compounds: list[str],
    pressure_bar: float | None = None,
) -> dict[str, Any]:
    """Recommend a property package based on compound classification.

    Args:
        compounds: list of compound names (case-insensitive)
        pressure_bar: optional operating pressure in bar for pressure-aware advice

    Returns:
        {recommended, reason, alternatives, warnings}
    """
    if not compounds:
        return {
            "recommended": "PengRobinson",
            "reason": "No compounds specified. Peng-Robinson is a safe default.",
            "alternatives": [],
            "warnings": [],
        }

    names = {c.lower().strip() for c in compounds}
    warnings: list[str] = []

    # High-pressure warning for activity coefficient models
    if pressure_bar is not None and pressure_bar > 50:
        warnings.append(
            f"Operating pressure ({pressure_bar:.0f} bar) is above 50 bar. "
            "Activity coefficient models (NRTL/UNIQUAC) lose accuracy at high pressure. "
            "Consider Peng-Robinson or SRK with tuned BIPs."
        )

    has_polar = bool(names & _POLAR_COMPOUNDS)
    has_hbond = bool(names & _HYDROGEN_BONDING)
    has_electrolyte = bool(names & _ELECTROLYTES)
    has_light_gas = bool(names & _LIGHT_GASES)
    has_hydrocarbon = bool(names & _HYDROCARBONS)
    has_amine = bool(names & _AMINE_SOLVENTS)
    has_acid_gas = bool(names & _ACID_GASES)

    all_hydrocarbon = names <= (_HYDROCARBONS | _LIGHT_GASES)
    all_polar = names <= (_POLAR_COMPOUNDS | _HYDROGEN_BONDING)

    # Decision tree
    if has_electrolyte:
        return {
            "recommended": "NRTL",
            "reason": "Electrolyte system detected. NRTL with electrolyte extension is recommended for ionic species.",
            "alternatives": ["UNIQUAC"],
            "warnings": ["Electrolyte systems may require specialized models (e-NRTL) beyond standard NRTL."],
        }

    if has_amine and has_acid_gas:
        return {
            "recommended": "NRTL",
            "reason": "Amine gas treating system detected. NRTL is standard for amine-acid gas equilibrium.",
            "alternatives": ["UNIQUAC"],
            "warnings": ["Chemical absorption requires effective K-values; VLE predictions alone may be insufficient."],
        }

    if has_hbond and has_hydrocarbon:
        # Mixed polar + hydrocarbon — activity coefficient models needed
        return {
            "recommended": "NRTL",
            "reason": "Mixture of hydrogen-bonding compounds and hydrocarbons. NRTL handles non-ideal liquid behavior well.",
            "alternatives": ["UNIQUAC"],
            "warnings": [],
        }

    if has_hbond and len(names & _HYDROGEN_BONDING) >= 2:
        return {
            "recommended": "NRTL",
            "reason": "Multiple hydrogen-bonding compounds. NRTL accurately models activity coefficients for associated liquids.",
            "alternatives": ["UNIQUAC"],
            "warnings": [],
        }

    if has_polar and not has_hydrocarbon:
        return {
            "recommended": "UNIQUAC",
            "reason": "Polar compound system. UNIQUAC provides good predictions with fewer parameters than NRTL.",
            "alternatives": ["NRTL"],
            "warnings": [],
        }

    if all_hydrocarbon and has_light_gas:
        # Gas processing / light ends
        if "hydrogen" in names:
            warnings.append("Systems with hydrogen may need special BIP tuning.")
        return {
            "recommended": "SRK",
            "reason": "Hydrocarbon + light gas system. SRK is standard for gas processing and upstream operations.",
            "alternatives": ["PengRobinson"],
            "warnings": warnings,
        }

    if all_hydrocarbon:
        return {
            "recommended": "PengRobinson",
            "reason": "All-hydrocarbon system. Peng-Robinson is the industry standard for refining and petrochemical applications.",
            "alternatives": ["SRK"],
            "warnings": warnings,
        }

    if has_polar:
        return {
            "recommended": "NRTL",
            "reason": "Polar compounds detected. NRTL provides accurate VLE for non-ideal systems.",
            "alternatives": ["UNIQUAC", "PengRobinson"],
            "warnings": [],
        }

    # Default
    return {
        "recommended": "PengRobinson",
        "reason": "General-purpose recommendation. Peng-Robinson provides reliable predictions for most systems.",
        "alternatives": ["SRK", "NRTL"],
        "warnings": [],
    }
