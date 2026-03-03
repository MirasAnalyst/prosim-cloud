/**
 * Unit system definitions and conversion utilities.
 *
 * Engine uses °C/kPa/kW internally (not raw K/Pa/W).
 * Frontend displays values in the selected unit system.
 */
// SI (what the engine outputs — °C/kPa/kW, not raw K/Pa/W)
const SI_SYSTEM = {
    name: 'SI',
    label: 'SI (°C, kPa, kW)',
    units: {
        temperature: '°C',
        pressure: 'kPa',
        massFlow: 'kg/s',
        molarFlow: 'mol/s',
        enthalpy: 'kJ/kg',
        entropy: 'kJ/(kg·K)',
        density: 'kg/m³',
        viscosity: 'mPa·s',
        thermalConductivity: 'W/(m·K)',
        surfaceTension: 'mN/m',
        heatCapacity: 'J/(kg·K)',
        power: 'kW',
        volumetricFlow: 'm³/s',
        area: 'm²',
        velocity: 'm/s',
        length: 'm',
    },
    toSI: {
        temperature: (v) => v, // °C → °C (engine input is °C for params)
        pressure: (v) => v, // kPa → kPa
        massFlow: (v) => v,
        power: (v) => v,
    },
    fromSI: {
        temperature: (v) => v, // °C → °C
        temperatureDelta: (v) => v, // Δ°C → Δ°C
        pressure: (v) => v, // kPa → kPa
        massFlow: (v) => v,
        molarFlow: (v) => v,
        enthalpy: (v) => v,
        entropy: (v) => v,
        density: (v) => v,
        viscosity: (v) => v * 1000, // Pa·s → mPa·s
        thermalConductivity: (v) => v,
        surfaceTension: (v) => v * 1000, // N/m → mN/m
        heatCapacity: (v) => v,
        power: (v) => v,
        volumetricFlow: (v) => v,
        velocity: (v) => v,
        area: (v) => v,
        length: (v) => v,
    },
};
// Field (US customary: °F, psia, BTU, lb)
const FIELD_SYSTEM = {
    name: 'Field',
    label: 'Field (°F, psia, BTU)',
    units: {
        temperature: '°F',
        pressure: 'psia',
        massFlow: 'lb/h',
        molarFlow: 'lbmol/h',
        enthalpy: 'BTU/lb',
        entropy: 'BTU/(lb·°R)',
        density: 'lb/ft³',
        viscosity: 'cP',
        thermalConductivity: 'BTU/(h·ft·°F)',
        surfaceTension: 'dyne/cm',
        heatCapacity: 'BTU/(lb·°F)',
        power: 'hp',
        volumetricFlow: 'ft³/s',
        area: 'ft²',
        velocity: 'ft/s',
        length: 'ft',
    },
    toSI: {
        temperature: (f) => (f - 32) * 5 / 9, // °F → °C
        pressure: (p) => p * 6.89476, // psia → kPa
        massFlow: (m) => m / 7936.64, // lb/h → kg/s
        power: (hp) => hp * 0.7457, // hp → kW
    },
    fromSI: {
        temperature: (c) => c * 9 / 5 + 32, // °C → °F
        temperatureDelta: (dc) => dc * 9 / 5, // Δ°C → Δ°F (no offset)
        pressure: (kpa) => kpa / 6.89476, // kPa → psia
        massFlow: (kgs) => kgs * 7936.64, // kg/s → lb/h
        molarFlow: (ms) => ms * 7.93664, // mol/s → lbmol/h (÷453.592×3600)
        enthalpy: (kjkg) => kjkg / 2.326, // kJ/kg → BTU/lb
        entropy: (kjkgk) => kjkgk / 4.1868, // kJ/(kg·K) → BTU/(lb·°R)
        density: (kgm3) => kgm3 * 0.062428, // kg/m³ → lb/ft³
        viscosity: (pas) => pas * 1000, // Pa·s → cP
        thermalConductivity: (wmk) => wmk * 0.5778, // W/(m·K) → BTU/(h·ft·°F)
        surfaceTension: (nm) => nm * 1000, // N/m → dyne/cm
        heatCapacity: (jkgk) => jkgk / 4186.8, // J/(kg·K) → BTU/(lb·°F)
        power: (kw) => kw / 0.7457, // kW → hp
        volumetricFlow: (m3s) => m3s * 35.3147, // m³/s → ft³/s
        velocity: (ms) => ms * 3.28084, // m/s → ft/s
        area: (m2) => m2 * 10.7639, // m² → ft²
        length: (m) => m * 3.28084, // m → ft
    },
};
// CGS
const CGS_SYSTEM = {
    name: 'CGS',
    label: 'CGS (°C, atm)',
    units: {
        temperature: '°C',
        pressure: 'atm',
        massFlow: 'g/s',
        molarFlow: 'mol/s',
        enthalpy: 'cal/g',
        entropy: 'cal/(g·K)',
        density: 'g/cm³',
        viscosity: 'P',
        thermalConductivity: 'cal/(s·cm·K)',
        surfaceTension: 'dyne/cm',
        heatCapacity: 'cal/(g·K)',
        power: 'kcal/s',
        volumetricFlow: 'cm³/s',
        area: 'cm²',
        velocity: 'cm/s',
        length: 'cm',
    },
    toSI: {
        temperature: (v) => v, // °C → °C
        pressure: (atm) => atm * 101.325, // atm → kPa
        massFlow: (gs) => gs / 1000, // g/s → kg/s
        power: (kcals) => kcals * 4.1868, // kcal/s → kW
    },
    fromSI: {
        temperature: (v) => v,
        temperatureDelta: (v) => v, // Δ°C → Δ°C
        pressure: (kpa) => kpa / 101.325, // kPa → atm
        massFlow: (kgs) => kgs * 1000, // kg/s → g/s
        molarFlow: (v) => v,
        enthalpy: (kjkg) => kjkg / 4.1868, // kJ/kg → cal/g
        entropy: (kjkgk) => kjkgk / 4.1868, // kJ/(kg·K) → cal/(g·K)
        density: (kgm3) => kgm3 / 1000, // kg/m³ → g/cm³
        viscosity: (pas) => pas * 10, // Pa·s → P (poise)
        thermalConductivity: (wmk) => wmk / 418.68, // W/(m·K) → cal/(s·cm·K)
        surfaceTension: (nm) => nm * 1000, // N/m → dyne/cm
        heatCapacity: (jkgk) => jkgk / 4186.8, // J/(kg·K) → cal/(g·K)
        power: (kw) => kw / 4.1868, // kW → kcal/s
        volumetricFlow: (m3s) => m3s * 1e6, // m³/s → cm³/s
        velocity: (ms) => ms * 100, // m/s → cm/s
        area: (m2) => m2 * 1e4, // m² → cm²
        length: (m) => m * 100, // m → cm
    },
};
export const UNIT_SYSTEMS = {
    SI: SI_SYSTEM,
    Field: FIELD_SYSTEM,
    CGS: CGS_SYSTEM,
};
export function getUnitSystem(name) {
    return UNIT_SYSTEMS[name] || SI_SYSTEM;
}
/**
 * Format a value with appropriate precision for display.
 */
export function formatValue(value, type, unitSystem) {
    if (value == null)
        return '—';
    const converted = convertFromSI(value, type, unitSystem);
    if (converted == null)
        return '—';
    // Choose precision based on type
    switch (type) {
        case 'temperature': return converted.toFixed(1);
        case 'pressure': return converted.toFixed(1);
        case 'massFlow': return converted.toFixed(3);
        case 'density': return converted.toFixed(2);
        case 'viscosity': return converted.toFixed(4);
        case 'thermalConductivity': return converted.toFixed(4);
        case 'surfaceTension': return converted.toFixed(2);
        case 'heatCapacity': return converted.toFixed(1);
        case 'power': return converted.toFixed(2);
        default: return converted.toPrecision(4);
    }
}
function convertFromSI(value, type, unitSystem) {
    const fn = unitSystem.fromSI[type];
    if (!fn)
        return value;
    try {
        return fn(value);
    }
    catch {
        return value;
    }
}
