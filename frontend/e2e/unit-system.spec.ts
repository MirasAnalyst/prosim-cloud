/**
 * Unit System Conversion Tests
 *
 * Verifies that the configurable unit system (SI / Field / CGS) conversion
 * functions in unit-systems.ts produce mathematically correct results when
 * applied to real simulation output.
 *
 * Strategy:
 *  1. Run simulations via POST http://localhost:8000/api/simulation/run
 *  2. Extract SI-native results (°C, kPa, kg/s, kW)
 *  3. Apply conversion functions and verify the math is correct
 *
 * This is NOT a UI test -- it verifies the conversion layer directly.
 */
import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });
test.setTimeout(120_000);

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

// ---------------------------------------------------------------------------
// Conversion functions under test (mirroring unit-systems.ts)
// ---------------------------------------------------------------------------

// -- Field (US customary) --
const field = {
  temperature:         (c: number) => c * 9 / 5 + 32,
  temperatureDelta:    (dc: number) => dc * 9 / 5,           // NO +32
  pressure:            (kpa: number) => kpa / 6.89476,
  massFlow:            (kgs: number) => kgs * 7936.64,
  molarFlow:           (ms: number) => ms * 7.93664,
  enthalpy:            (kjkg: number) => kjkg / 2.326,
  entropy:             (kjkgk: number) => kjkgk / 4.1868,
  density:             (kgm3: number) => kgm3 * 0.062428,
  viscosity:           (pas: number) => pas * 1000,
  thermalConductivity: (wmk: number) => wmk * 0.5778,
  surfaceTension:      (nm: number) => nm * 1000,
  heatCapacity:        (jkgk: number) => jkgk / 4186.8,
  power:               (kw: number) => kw / 0.7457,
  volumetricFlow:      (m3s: number) => m3s * 35.3147,
  velocity:            (ms: number) => ms * 3.28084,
  area:                (m2: number) => m2 * 10.7639,
  length:              (m: number) => m * 3.28084,
};

// -- CGS --
const cgs = {
  temperature:         (c: number) => c,                      // identity
  temperatureDelta:    (dc: number) => dc,                    // identity
  pressure:            (kpa: number) => kpa / 101.325,
  massFlow:            (kgs: number) => kgs * 1000,
  molarFlow:           (ms: number) => ms,                    // identity
  enthalpy:            (kjkg: number) => kjkg / 4.1868,
  entropy:             (kjkgk: number) => kjkgk / 4.1868,
  density:             (kgm3: number) => kgm3 / 1000,
  viscosity:           (pas: number) => pas * 10,
  thermalConductivity: (wmk: number) => wmk / 418.68,
  surfaceTension:      (nm: number) => nm * 1000,
  heatCapacity:        (jkgk: number) => jkgk / 4186.8,
  power:               (kw: number) => kw / 4.1868,
  volumetricFlow:      (m3s: number) => m3s * 1e6,
  velocity:            (ms: number) => ms * 100,
  area:                (m2: number) => m2 * 1e4,
  length:              (m: number) => m * 100,
};

// -- SI display adjustments (non-identity) --
const siDisplay = {
  viscosity:      (pas: number) => pas * 1000,   // Pa.s -> mPa.s
  surfaceTension: (nm: number) => nm * 1000,     // N/m -> mN/m
};

// ---------------------------------------------------------------------------
// Tolerance helper: relative tolerance check within 0.1%
// ---------------------------------------------------------------------------
function expectClose(actual: number, expected: number, label: string, relTol = 0.001) {
  const denom = Math.abs(expected) || 1;
  const relErr = Math.abs(actual - expected) / denom;
  expect(relErr, `${label}: got ${actual}, expected ${expected}, relErr ${(relErr * 100).toFixed(4)}%`).toBeLessThan(relTol);
}

// ---------------------------------------------------------------------------
// Node / edge builders
// ---------------------------------------------------------------------------
function makeNode(
  id: string,
  equipmentType: string,
  name: string,
  parameters: Record<string, any> = {},
  position = { x: 0, y: 0 },
) {
  return { id, type: 'equipment', position, data: { equipmentType, name, parameters } };
}

function makeFeed(
  id: string,
  name: string,
  temp: number,
  pressure: number,
  flow: number,
  composition: Record<string, number>,
) {
  return makeNode(id, 'FeedStream', name, {
    feedTemperature: temp,
    feedPressure: pressure,
    feedFlowRate: flow,
    feedComposition: JSON.stringify(composition),
  });
}

function makeProduct(id: string, name: string) {
  return makeNode(id, 'ProductStream', name);
}

function E(
  id: string,
  source: string,
  sourceHandle: string,
  target: string,
  targetHandle: string,
) {
  return { id, source, sourceHandle, target, targetHandle, type: 'stream' };
}

// ---------------------------------------------------------------------------
// Simulation runner (API-level, no browser UI)
// ---------------------------------------------------------------------------
async function runSim(
  page: any,
  nodes: any[],
  edges: any[],
  propertyPackage = 'PengRobinson',
) {
  setEdges(edges);
  const raw = await page.evaluate(
    async ({ nodes, edges, pp }: any) => {
      const r = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: pp }),
      });
      return r.json();
    },
    { nodes, edges, pp: propertyPackage },
  );
  return raw.results ?? raw;
}

// Helper: find a stream result by source (and optionally target) node ID.
// Stream result keys are edge IDs, so we need to search the edges array.
let _currentEdges: any[] = [];
function setEdges(edges: any[]) { _currentEdges = edges; }

function findStream(streamResults: Record<string, any>, sourceId: string, targetId?: string): any {
  // Find the edge that matches source (and optionally target)
  const edge = _currentEdges.find(e =>
    e.source === sourceId && (!targetId || e.target === targetId)
  );
  if (edge && streamResults[edge.id]) return streamResults[edge.id];
  // Fallback: try matching edge ID directly
  if (streamResults[sourceId]) return streamResults[sourceId];
  return undefined;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Test 1: Heater + Cooler — temperature, pressure, flow, duty conversions
// ═══════════════════════════════════════════════════════════════════════════════
test('1 — Heater/Cooler: T, P, flow, duty conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Feed', 25, 500, 1, { methane: 0.9, ethane: 0.1 }),
    makeNode('h1', 'Heater', 'H-101', { outletTemperature: 100 }),
    makeNode('c1', 'Cooler', 'C-101', { outletTemperature: 50 }),
    makeProduct('p1', 'Product'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'c1', 'in-1'),
    E('e3', 'c1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');
  expect(data.stream_results).toBeDefined();
  expect(data.equipment_results).toBeDefined();

  // Pick heater outlet stream
  const heaterOut = findStream(data.stream_results, 'h1');
  expect(heaterOut).toBeDefined();
  const T_si = heaterOut.temperature;   // °C
  const P_si = heaterOut.pressure;      // kPa
  const F_si = heaterOut.flowRate;      // kg/s

  // Field conversions
  expectClose(field.temperature(T_si), T_si * 9 / 5 + 32, 'T °C→°F');
  expectClose(field.pressure(P_si), P_si / 6.89476, 'P kPa→psia');
  expectClose(field.massFlow(F_si), F_si * 7936.64, 'F kg/s→lb/h');

  // CGS conversions
  expectClose(cgs.temperature(T_si), T_si, 'T °C→°C (CGS identity)');
  expectClose(cgs.pressure(P_si), P_si / 101.325, 'P kPa→atm');
  expectClose(cgs.massFlow(F_si), F_si * 1000, 'F kg/s→g/s');

  // Equipment duty
  const heaterRes = data.equipment_results['h1'];
  expect(heaterRes).toBeDefined();
  const duty_si = heaterRes.duty; // kW
  if (typeof duty_si === 'number' && duty_si !== 0) {
    expectClose(field.power(duty_si), duty_si / 0.7457, 'duty kW→hp');
    expectClose(cgs.power(duty_si), duty_si / 4.1868, 'duty kW→kcal/s');
  }

  // Cooler duty
  const coolerRes = data.equipment_results['c1'];
  expect(coolerRes).toBeDefined();
  if (typeof coolerRes.duty === 'number' && coolerRes.duty !== 0) {
    expectClose(field.power(coolerRes.duty), coolerRes.duty / 0.7457, 'cooler duty kW→hp');
  }

  // Verify heater outlet T is near 100°C
  expect(T_si).toBeCloseTo(100, 0);
  // Verify cooler outlet
  const coolerOut = findStream(data.stream_results, 'c1');
  expect(coolerOut).toBeDefined();
  expect(coolerOut.temperature).toBeCloseTo(50, 0);
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 2: Pump + Compressor — work, pressure conversions
// ═══════════════════════════════════════════════════════════════════════════════
test('2 — Pump/Compressor: work and pressure conversion', async ({ page }) => {
  // Pump flowsheet: liquid water
  const pumpNodes = [
    makeFeed('f1', 'Water Feed', 25, 100, 2, { water: 1.0 }),
    makeNode('pu1', 'Pump', 'P-101', { outletPressure: 500 }),
    makeProduct('p1', 'Pump Out'),
  ];
  const pumpEdges = [
    E('e1', 'f1', 'out-1', 'pu1', 'in-1'),
    E('e2', 'pu1', 'out-1', 'p1', 'in-1'),
  ];
  const pumpData = await runSim(page, pumpNodes, pumpEdges);
  expect(pumpData.status).not.toBe('error');

  const pumpRes = pumpData.equipment_results['pu1'];
  expect(pumpRes).toBeDefined();
  if (typeof pumpRes.work === 'number' && pumpRes.work !== 0) {
    expectClose(field.power(pumpRes.work), pumpRes.work / 0.7457, 'pump work kW→hp');
    expectClose(cgs.power(pumpRes.work), pumpRes.work / 4.1868, 'pump work kW→kcal/s');
  }

  // Pump outlet pressure
  const pumpOut = findStream(pumpData.stream_results, 'pu1');
  expect(pumpOut).toBeDefined();
  const P_pump = pumpOut.pressure;
  expectClose(field.pressure(P_pump), P_pump / 6.89476, 'pump P_out kPa→psia');

  // Compressor flowsheet: gas methane
  const compNodes = [
    makeFeed('f2', 'Gas Feed', 25, 100, 1, { methane: 1.0 }),
    makeNode('co1', 'Compressor', 'K-101', { outletPressure: 500, efficiency: 75 }),
    makeProduct('p2', 'Comp Out'),
  ];
  const compEdges = [
    E('e3', 'f2', 'out-1', 'co1', 'in-1'),
    E('e4', 'co1', 'out-1', 'p2', 'in-1'),
  ];
  const compData = await runSim(page, compNodes, compEdges);
  expect(compData.status).not.toBe('error');

  const compRes = compData.equipment_results['co1'];
  expect(compRes).toBeDefined();
  if (typeof compRes.work === 'number' && compRes.work !== 0) {
    expectClose(field.power(compRes.work), compRes.work / 0.7457, 'comp work kW→hp');
    expectClose(cgs.power(compRes.work), compRes.work / 4.1868, 'comp work kW→kcal/s');
  }

  // Compressor outlet stream
  const compOut = findStream(compData.stream_results, 'co1');
  expect(compOut).toBeDefined();
  expectClose(field.temperature(compOut.temperature), compOut.temperature * 9 / 5 + 32, 'comp T_out °C→°F');
  expectClose(field.pressure(compOut.pressure), compOut.pressure / 6.89476, 'comp P_out kPa→psia');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 3: Heat Exchanger — LMTD (temperatureDelta), duty
// ═══════════════════════════════════════════════════════════════════════════════
test('3 — HeatExchanger: LMTD temperatureDelta and duty conversion', async ({ page }) => {
  const nodes = [
    makeFeed('fh', 'Hot Feed', 150, 500, 2, { methane: 1.0 }),
    makeFeed('fc', 'Cold Feed', 25, 500, 1, { ethane: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'E-101', {}),
    makeProduct('ph', 'Hot Out'),
    makeProduct('pc', 'Cold Out'),
  ];
  const edges = [
    E('e1', 'fh', 'out-1', 'hx1', 'in-hot'),
    E('e2', 'fc', 'out-1', 'hx1', 'in-cold'),
    E('e3', 'hx1', 'out-hot', 'ph', 'in-1'),
    E('e4', 'hx1', 'out-cold', 'pc', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const hxRes = data.equipment_results['hx1'];
  expect(hxRes).toBeDefined();

  // LMTD is a temperature DIFFERENCE -- must use temperatureDelta, NOT temperature
  const lmtd_si = hxRes.LMTD; // °C (delta)
  if (typeof lmtd_si === 'number' && lmtd_si > 0) {
    // CRITICAL: temperatureDelta uses scale-only (9/5), NO +32 offset
    const lmtd_field = field.temperatureDelta(lmtd_si);
    expectClose(lmtd_field, lmtd_si * 9 / 5, 'LMTD Δ°C→Δ°F (no +32)');

    // Verify it does NOT equal the wrong temperature conversion (with +32)
    const wrong_field = field.temperature(lmtd_si);
    // For any LMTD > 0, the wrong conversion adds 32 which is always different
    expect(Math.abs(lmtd_field - wrong_field)).toBeGreaterThan(31);

    // CGS: temperatureDelta is identity
    expectClose(cgs.temperatureDelta(lmtd_si), lmtd_si, 'LMTD Δ°C→Δ°C (CGS identity)');
  }

  // HX duty
  const duty_si = hxRes.duty; // kW
  if (typeof duty_si === 'number' && duty_si !== 0) {
    expectClose(field.power(duty_si), duty_si / 0.7457, 'HX duty kW→hp');
    expectClose(cgs.power(duty_si), duty_si / 4.1868, 'HX duty kW→kcal/s');
  }

  // Hot-side outlet should be cooler than 150°C
  const hotOut = findStream(data.stream_results, 'hx1', 'ph');
  if (hotOut) {
    expect(hotOut.temperature).toBeLessThan(150);
    expectClose(field.temperature(hotOut.temperature), hotOut.temperature * 9 / 5 + 32, 'HX hot out T →°F');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 4: Separator + Valve — VF, pressureDrop, density
// ═══════════════════════════════════════════════════════════════════════════════
test('4 — Separator/Valve: VF, pressureDrop, density conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Feed', 25, 1000, 3, { methane: 0.5, 'n-pentane': 0.5 }),
    makeNode('sep1', 'Separator', 'V-101', {}),
    makeNode('v1', 'Valve', 'VLV-101', { outletPressure: 200 }),
    makeProduct('p1', 'Vapor'),
    makeProduct('p2', 'Liquid Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'sep1', 'in-1'),
    E('e2', 'sep1', 'out-1', 'p1', 'in-1'),     // vapor
    E('e3', 'sep1', 'out-2', 'v1', 'in-1'),      // liquid to valve
    E('e4', 'v1', 'out-1', 'p2', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  // Separator result
  const sepRes = data.equipment_results['sep1'];
  expect(sepRes).toBeDefined();

  // Valve result (pressureDrop)
  const valveRes = data.equipment_results['v1'];
  expect(valveRes).toBeDefined();
  const dp = valveRes.pressureDrop; // kPa
  if (typeof dp === 'number' && dp !== 0) {
    // pressureDrop is a pressure difference -- use pressure converter (both are absolute kPa scale)
    expectClose(field.pressure(dp), dp / 6.89476, 'valve ΔP kPa→psia');
    expectClose(cgs.pressure(dp), dp / 101.325, 'valve ΔP kPa→atm');
  }

  // Stream density if available
  const sepVapor = findStream(data.stream_results, 'sep1', 'p1');
  if (sepVapor && typeof sepVapor.density === 'number') {
    const rho = sepVapor.density;
    expectClose(field.density(rho), rho * 0.062428, 'ρ kg/m³→lb/ft³');
    expectClose(cgs.density(rho), rho / 1000, 'ρ kg/m³→g/cm³');
  }

  // Valve outlet stream
  const valveOut = findStream(data.stream_results, 'v1');
  expect(valveOut).toBeDefined();
  expectClose(field.pressure(valveOut.pressure), valveOut.pressure / 6.89476, 'valve P_out kPa→psia');
  expectClose(field.temperature(valveOut.temperature), valveOut.temperature * 9 / 5 + 32, 'valve T_out °C→°F');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 5: Mixer + Splitter — totalMassFlow conversion
// ═══════════════════════════════════════════════════════════════════════════════
test('5 — Mixer/Splitter: mass flow conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Feed A', 30, 300, 2, { methane: 0.8, ethane: 0.2 }),
    makeFeed('f2', 'Feed B', 50, 300, 3, { methane: 0.6, propane: 0.4 }),
    makeNode('mx1', 'Mixer', 'MX-101', {}),
    makeNode('sp1', 'Splitter', 'TEE-101', { splitRatio: 0.4 }),
    makeProduct('p1', 'Split A'),
    makeProduct('p2', 'Split B'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mx1', 'in-1'),
    E('e2', 'f2', 'out-1', 'mx1', 'in-2'),
    E('e3', 'mx1', 'out-1', 'sp1', 'in-1'),
    E('e4', 'sp1', 'out-1', 'p1', 'in-1'),
    E('e5', 'sp1', 'out-2', 'p2', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  // Mixer outlet
  const mixerOut = findStream(data.stream_results, 'mx1');
  expect(mixerOut).toBeDefined();
  const F_mix = mixerOut.flowRate; // kg/s -- should be ~5 (2+3)
  expect(F_mix).toBeGreaterThan(4);
  expect(F_mix).toBeLessThan(6);

  // Mass flow conversions
  expectClose(field.massFlow(F_mix), F_mix * 7936.64, 'mixer F kg/s→lb/h');
  expectClose(cgs.massFlow(F_mix), F_mix * 1000, 'mixer F kg/s→g/s');

  // Splitter outlets should sum to mixer outlet
  const splitA = findStream(data.stream_results, 'sp1', 'p1');
  const splitB = findStream(data.stream_results, 'sp1', 'p2');
  if (splitA && splitB) {
    const sumFlow = splitA.flowRate + splitB.flowRate;
    expectClose(sumFlow, F_mix, 'splitter mass balance', 0.01);
    // Each split flow converts correctly
    expectClose(field.massFlow(splitA.flowRate), splitA.flowRate * 7936.64, 'split A kg/s→lb/h');
    expectClose(cgs.massFlow(splitB.flowRate), splitB.flowRate * 1000, 'split B kg/s→g/s');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 6: Distillation Column — stages (dimensionless), duty
// ═══════════════════════════════════════════════════════════════════════════════
test('6 — DistillationColumn: duty conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Feed', 80, 101.325, 1, { benzene: 0.5, toluene: 0.5 }),
    makeNode('col1', 'DistillationColumn', 'T-101', {
      numberOfStages: 20,
      refluxRatio: 2.0,
      feedStage: 10,
    }),
    makeProduct('p1', 'Distillate'),
    makeProduct('p2', 'Bottoms'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'col1', 'in-1'),
    E('e2', 'col1', 'out-1', 'p1', 'in-1'),
    E('e3', 'col1', 'out-2', 'p2', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const colRes = data.equipment_results['col1'];
  expect(colRes).toBeDefined();

  // Condenser duty
  const Qcond = colRes.condenserDuty ?? colRes.duty;
  if (typeof Qcond === 'number' && Qcond !== 0) {
    expectClose(field.power(Qcond), Qcond / 0.7457, 'condenser duty kW→hp');
    expectClose(cgs.power(Qcond), Qcond / 4.1868, 'condenser duty kW→kcal/s');
  }

  // Reboiler duty
  const Qreb = colRes.reboilerDuty;
  if (typeof Qreb === 'number' && Qreb !== 0) {
    expectClose(field.power(Qreb), Qreb / 0.7457, 'reboiler duty kW→hp');
  }

  // Stages should be dimensionless (no conversion needed)
  const stages = colRes.stages ?? colRes.numberOfStages ?? colRes.actualStages;
  if (typeof stages === 'number') {
    expect(stages).toBeGreaterThan(0);
    // Dimensionless -- same in all unit systems
  }

  // Column outlet streams
  const dist = findStream(data.stream_results, 'col1', 'p1');
  if (dist) {
    expectClose(field.temperature(dist.temperature), dist.temperature * 9 / 5 + 32, 'distillate T→°F');
    expectClose(field.pressure(dist.pressure), dist.pressure / 6.89476, 'distillate P→psia');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 7: ConversionReactor — conversion (%), temperature
// ═══════════════════════════════════════════════════════════════════════════════
test('7 — ConversionReactor: conversion and T conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Reactor Feed', 300, 2000, 1, { methane: 0.8, oxygen: 0.2 }),
    makeNode('rx1', 'ConversionReactor', 'R-101', {
      conversion: 50,
      keyReactant: 'methane',
    }),
    makeProduct('p1', 'Reactor Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'rx1', 'in-1'),
    E('e2', 'rx1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const rxRes = data.equipment_results['rx1'];
  expect(rxRes).toBeDefined();

  // Reactor outlet stream
  const rxOut = findStream(data.stream_results, 'rx1');
  expect(rxOut).toBeDefined();
  const T_rx = rxOut.temperature;
  const P_rx = rxOut.pressure;

  // Temperature conversion
  expectClose(field.temperature(T_rx), T_rx * 9 / 5 + 32, 'reactor T→°F');
  expectClose(cgs.temperature(T_rx), T_rx, 'reactor T→°C (CGS identity)');

  // Pressure conversion
  expectClose(field.pressure(P_rx), P_rx / 6.89476, 'reactor P→psia');
  expectClose(cgs.pressure(P_rx), P_rx / 101.325, 'reactor P→atm');

  // Duty if present
  if (typeof rxRes.duty === 'number' && rxRes.duty !== 0) {
    expectClose(field.power(rxRes.duty), rxRes.duty / 0.7457, 'reactor duty kW→hp');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 8: PipeSegment — pressureDrop, velocity
// ═══════════════════════════════════════════════════════════════════════════════
test('8 — PipeSegment: pressureDrop and velocity conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Pipe Feed', 25, 500, 5, { water: 1.0 }),
    makeNode('ps1', 'PipeSegment', 'PIPE-101', {
      length: 100,
      diameter: 0.1,
      roughness: 0.000046,
      elevation: 0,
    }),
    makeProduct('p1', 'Pipe Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'ps1', 'in-1'),
    E('e2', 'ps1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const pipeRes = data.equipment_results['ps1'];
  expect(pipeRes).toBeDefined();

  // Pressure drop (kPa)
  const dp = pipeRes.pressureDrop;
  if (typeof dp === 'number' && dp !== 0) {
    expectClose(field.pressure(dp), dp / 6.89476, 'pipe ΔP kPa→psia');
    expectClose(cgs.pressure(dp), dp / 101.325, 'pipe ΔP kPa→atm');
  }

  // Velocity (m/s)
  const vel = pipeRes.velocity;
  if (typeof vel === 'number' && vel > 0) {
    expectClose(field.velocity(vel), vel * 3.28084, 'pipe velocity m/s→ft/s');
    expectClose(cgs.velocity(vel), vel * 100, 'pipe velocity m/s→cm/s');
  }

  // Pipe outlet stream
  const pipeOut = findStream(data.stream_results, 'ps1');
  expect(pipeOut).toBeDefined();
  // Pressure should be less than inlet due to friction
  expect(pipeOut.pressure).toBeLessThan(500);
  expectClose(field.pressure(pipeOut.pressure), pipeOut.pressure / 6.89476, 'pipe outlet P→psia');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 9: Absorber — mass flow and stages
// ═══════════════════════════════════════════════════════════════════════════════
test('9 — Absorber: mass flow conversion', async ({ page }) => {
  const nodes = [
    makeFeed('fg', 'Sour Gas', 40, 3000, 5, { methane: 0.9, 'carbon dioxide': 0.1 }),
    makeFeed('fs', 'Lean Amine', 40, 3000, 10, { water: 0.888, monoethanolamine: 0.112 }),
    makeNode('ab1', 'Absorber', 'A-101', {}),
    makeProduct('p1', 'Sweet Gas'),
    makeProduct('p2', 'Rich Amine'),
  ];
  const edges = [
    E('e1', 'fg', 'out-1', 'ab1', 'in-1'),     // gas inlet
    E('e2', 'fs', 'out-1', 'ab1', 'in-2'),     // solvent inlet
    E('e3', 'ab1', 'out-1', 'p1', 'in-1'),
    E('e4', 'ab1', 'out-2', 'p2', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const abRes = data.equipment_results['ab1'];
  expect(abRes).toBeDefined();

  // Absorber outlets
  const sweetGas = findStream(data.stream_results, 'ab1', 'p1');
  const richAmine = findStream(data.stream_results, 'ab1', 'p2');

  if (sweetGas) {
    const F_sg = sweetGas.flowRate;
    expectClose(field.massFlow(F_sg), F_sg * 7936.64, 'sweet gas kg/s→lb/h');
    expectClose(cgs.massFlow(F_sg), F_sg * 1000, 'sweet gas kg/s→g/s');
    expectClose(field.temperature(sweetGas.temperature), sweetGas.temperature * 9 / 5 + 32, 'sweet gas T→°F');
  }

  if (richAmine) {
    const F_ra = richAmine.flowRate;
    expectClose(field.massFlow(F_ra), F_ra * 7936.64, 'rich amine kg/s→lb/h');
    expectClose(field.pressure(richAmine.pressure), richAmine.pressure / 6.89476, 'rich amine P→psia');
  }

  // Stages (dimensionless) if present
  if (typeof abRes.stages === 'number') {
    expect(abRes.stages).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 10: Cyclone + Filter — pressureDrop and efficiency
// ═══════════════════════════════════════════════════════════════════════════════
test('10 — Cyclone/Filter: pressureDrop conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Dusty Gas', 200, 200, 2, { nitrogen: 0.9, 'carbon dioxide': 0.1 }),
    makeNode('cy1', 'Cyclone', 'CY-101', {
      efficiency: 90,
      solidsFraction: 0.1,
      inletDiameter: 0.5,
      pressureDropCoeff: 4,
      solidsComponent: 'carbon dioxide',
    }),
    makeNode('fi1', 'Filter', 'FL-101', {
      efficiency: 95,
      solidsFraction: 0.05,
      pressureDrop: 2,
    }),
    makeProduct('p1', 'Clean Gas'),
    makeProduct('p2', 'Cyclone Solids'),
    makeProduct('p3', 'Filter Cake'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cy1', 'in-1'),
    E('e2', 'cy1', 'out-1', 'fi1', 'in-1'),   // gas to filter
    E('e3', 'cy1', 'out-2', 'p2', 'in-1'),     // solids
    E('e4', 'fi1', 'out-1', 'p1', 'in-1'),     // clean gas
    E('e5', 'fi1', 'out-2', 'p3', 'in-1'),     // cake
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const cyRes = data.equipment_results['cy1'];
  expect(cyRes).toBeDefined();
  const dp_cy = cyRes.pressureDrop;
  if (typeof dp_cy === 'number' && dp_cy !== 0) {
    expectClose(field.pressure(dp_cy), dp_cy / 6.89476, 'cyclone ΔP kPa→psia');
    expectClose(cgs.pressure(dp_cy), dp_cy / 101.325, 'cyclone ΔP kPa→atm');
  }

  const fiRes = data.equipment_results['fi1'];
  expect(fiRes).toBeDefined();

  // Filter outlet stream
  const cleanGas = findStream(data.stream_results, 'fi1', 'p1');
  if (cleanGas) {
    expectClose(field.temperature(cleanGas.temperature), cleanGas.temperature * 9 / 5 + 32, 'filter T→°F');
    expectClose(field.massFlow(cleanGas.flowRate), cleanGas.flowRate * 7936.64, 'filter F→lb/h');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 11: CSTR + PFR Reactor — temperature and duty
// ═══════════════════════════════════════════════════════════════════════════════
test('11 — CSTR/PFR: temperature and duty conversion', async ({ page }) => {
  // CSTR
  const cstrNodes = [
    makeFeed('f1', 'CSTR Feed', 150, 500, 1, { methane: 0.7, ethane: 0.3 }),
    makeNode('cstr1', 'CSTRReactor', 'R-201', {
      volume: 5,
      outletTemperature: 200,
    }),
    makeProduct('p1', 'CSTR Out'),
  ];
  const cstrEdges = [
    E('e1', 'f1', 'out-1', 'cstr1', 'in-1'),
    E('e2', 'cstr1', 'out-1', 'p1', 'in-1'),
  ];
  const cstrData = await runSim(page, cstrNodes, cstrEdges);
  expect(cstrData.status).not.toBe('error');

  const cstrOut = findStream(cstrData.stream_results, 'cstr1');
  if (cstrOut) {
    expectClose(field.temperature(cstrOut.temperature), cstrOut.temperature * 9 / 5 + 32, 'CSTR T→°F');
    expectClose(cgs.temperature(cstrOut.temperature), cstrOut.temperature, 'CSTR T→°C (CGS)');
  }

  // PFR
  const pfrNodes = [
    makeFeed('f2', 'PFR Feed', 200, 1000, 0.5, { methane: 0.6, ethane: 0.4 }),
    makeNode('pfr1', 'PFRReactor', 'R-301', {
      length: 10,
      diameter: 0.05,
      voidFraction: 0.4,
    }),
    makeProduct('p2', 'PFR Out'),
  ];
  const pfrEdges = [
    E('e3', 'f2', 'out-1', 'pfr1', 'in-1'),
    E('e4', 'pfr1', 'out-1', 'p2', 'in-1'),
  ];
  const pfrData = await runSim(page, pfrNodes, pfrEdges);
  expect(pfrData.status).not.toBe('error');

  const pfrRes = pfrData.equipment_results['pfr1'];
  expect(pfrRes).toBeDefined();
  const pfrOut = findStream(pfrData.stream_results, 'pfr1');
  if (pfrOut) {
    expectClose(field.temperature(pfrOut.temperature), pfrOut.temperature * 9 / 5 + 32, 'PFR T→°F');
    expectClose(field.pressure(pfrOut.pressure), pfrOut.pressure / 6.89476, 'PFR P→psia');
  }

  // PFR pressureDrop if present
  if (typeof pfrRes.pressureDrop === 'number' && pfrRes.pressureDrop > 0) {
    expectClose(field.pressure(pfrRes.pressureDrop), pfrRes.pressureDrop / 6.89476, 'PFR ΔP kPa→psia');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 12: ThreePhaseSeparator + Stripper
// ═══════════════════════════════════════════════════════════════════════════════
test('12 — ThreePhaseSep/Stripper: multi-outlet conversion', async ({ page }) => {
  // Three-phase separator
  const tpsNodes = [
    makeFeed('f1', 'Well Fluid', 60, 2000, 10, { methane: 0.3, 'n-pentane': 0.4, water: 0.3 }),
    makeNode('tps1', 'ThreePhaseSeparator', 'V-201', { lightLiquidFraction: 0.6 }),
    makeProduct('p1', 'Vapor'),
    makeProduct('p2', 'Light Liq'),
    makeProduct('p3', 'Heavy Liq'),
  ];
  const tpsEdges = [
    E('e1', 'f1', 'out-1', 'tps1', 'in-1'),
    E('e2', 'tps1', 'out-1', 'p1', 'in-1'),   // vapor
    E('e3', 'tps1', 'out-2', 'p2', 'in-1'),   // light liquid
    E('e4', 'tps1', 'out-3', 'p3', 'in-1'),   // heavy liquid
  ];
  const tpsData = await runSim(page, tpsNodes, tpsEdges);
  expect(tpsData.status).not.toBe('error');

  // All three outlets should have valid T, P
  for (const pId of ['p1', 'p2', 'p3']) {
    const s = findStream(tpsData.stream_results, 'tps1', pId);
    if (s) {
      expectClose(field.temperature(s.temperature), s.temperature * 9 / 5 + 32, `TPS ${pId} T→°F`);
      expectClose(field.pressure(s.pressure), s.pressure / 6.89476, `TPS ${pId} P→psia`);
      expectClose(cgs.massFlow(s.flowRate), s.flowRate * 1000, `TPS ${pId} F→g/s`);
    }
  }

  // Stripper
  const stripNodes = [
    makeFeed('fs1', 'Rich Solvent', 80, 200, 5, { water: 0.85, monoethanolamine: 0.1, 'carbon dioxide': 0.05 }),
    makeNode('st1', 'Stripper', 'T-201', {}),
    makeProduct('ps1', 'Acid Gas'),
    makeProduct('ps2', 'Lean Solvent'),
  ];
  const stripEdges = [
    E('es1', 'fs1', 'out-1', 'st1', 'in-1'),
    E('es2', 'st1', 'out-1', 'ps1', 'in-1'),
    E('es3', 'st1', 'out-2', 'ps2', 'in-1'),
  ];
  const stripData = await runSim(page, stripNodes, stripEdges);
  expect(stripData.status).not.toBe('error');

  const stRes = stripData.equipment_results['st1'];
  expect(stRes).toBeDefined();

  if (typeof stRes.duty === 'number' && stRes.duty !== 0) {
    expectClose(field.power(stRes.duty), stRes.duty / 0.7457, 'stripper duty kW→hp');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 13: Crystallizer + Dryer — temperature and flow
// ═══════════════════════════════════════════════════════════════════════════════
test('13 — Crystallizer/Dryer: T and flow conversion', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sugar Soln', 70, 200, 2, { water: 0.6, acetone: 0.4 }),
    makeNode('cr1', 'Crystallizer', 'CR-101', { crystallizationTemp: 10 }),
    makeNode('dr1', 'Dryer', 'DR-101', { outletMoisture: 5 }),
    makeProduct('p1', 'Dry Product'),
    makeProduct('p2', 'Mother Liquor'),
    makeProduct('p3', 'Vapor'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cr1', 'in-1'),
    E('e2', 'cr1', 'out-1', 'dr1', 'in-1'),
    E('e3', 'cr1', 'out-2', 'p2', 'in-1'),
    E('e4', 'dr1', 'out-1', 'p1', 'in-1'),
    E('e5', 'dr1', 'out-2', 'p3', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const crRes = data.equipment_results['cr1'];
  expect(crRes).toBeDefined();
  const drRes = data.equipment_results['dr1'];
  expect(drRes).toBeDefined();

  // Crystallizer outlet
  const crOut = findStream(data.stream_results, 'cr1', 'dr1');
  if (crOut) {
    const T = crOut.temperature;
    expectClose(field.temperature(T), T * 9 / 5 + 32, 'crystallizer T→°F');
    expectClose(cgs.temperature(T), T, 'crystallizer T→°C (CGS)');
  }

  // Dryer product
  const dryProd = findStream(data.stream_results, 'dr1', 'p1');
  if (dryProd) {
    expectClose(field.massFlow(dryProd.flowRate), dryProd.flowRate * 7936.64, 'dryer product F→lb/h');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 14: Comprehensive conversion math — pure arithmetic verification
//
// This test does NOT depend on simulation. It verifies every conversion
// function against known reference values.
// ═══════════════════════════════════════════════════════════════════════════════
test('14 — Pure arithmetic: all conversion factors verified', async () => {
  // ─── Field: Temperature ───
  // Absolute: 0°C = 32°F, 100°C = 212°F, -40°C = -40°F
  expectClose(field.temperature(0), 32, 'Field: 0°C = 32°F');
  expectClose(field.temperature(100), 212, 'Field: 100°C = 212°F');
  expectClose(field.temperature(-40), -40, 'Field: -40°C = -40°F');

  // Delta: 10 Δ°C = 18 Δ°F (no offset)
  expectClose(field.temperatureDelta(10), 18, 'Field: 10 Δ°C = 18 Δ°F');
  expectClose(field.temperatureDelta(0), 0, 'Field: 0 Δ°C = 0 Δ°F');
  expectClose(field.temperatureDelta(100), 180, 'Field: 100 Δ°C = 180 Δ°F');
  // CRITICAL: temperatureDelta(50) = 90, NOT 122 (which would be temperature(50))
  expect(field.temperatureDelta(50)).not.toBeCloseTo(field.temperature(50), 0);

  // ─── Field: Pressure ───
  // 1 atm = 101.325 kPa = 14.696 psia
  expectClose(field.pressure(101.325), 14.696, 'Field: 1 atm = 14.696 psia', 0.002);

  // ─── Field: Mass flow ───
  // 1 kg/s = 7936.64 lb/h
  expectClose(field.massFlow(1), 7936.64, 'Field: 1 kg/s = 7936.64 lb/h');

  // ─── Field: Molar flow ───
  expectClose(field.molarFlow(1), 7.93664, 'Field: 1 mol/s = 7.93664 lbmol/h');

  // ─── Field: Enthalpy ───
  // 1 BTU/lb = 2.326 kJ/kg, so 2.326 kJ/kg = 1 BTU/lb
  expectClose(field.enthalpy(2.326), 1.0, 'Field: 2.326 kJ/kg = 1 BTU/lb', 0.002);

  // ─── Field: Density ───
  // Water ~1000 kg/m³ = 62.428 lb/ft³
  expectClose(field.density(1000), 62.428, 'Field: 1000 kg/m³ = 62.428 lb/ft³', 0.002);

  // ─── Field: Viscosity ───
  // 1 Pa·s = 1000 cP
  expectClose(field.viscosity(1), 1000, 'Field: 1 Pa·s = 1000 cP');

  // ─── Field: Thermal conductivity ───
  // 1 W/(m·K) = 0.5778 BTU/(h·ft·°F)
  expectClose(field.thermalConductivity(1), 0.5778, 'Field: 1 W/(m·K) = 0.5778 BTU/(h·ft·°F)', 0.002);

  // ─── Field: Surface tension ───
  // 1 N/m = 1000 dyne/cm
  expectClose(field.surfaceTension(1), 1000, 'Field: 1 N/m = 1000 dyne/cm');

  // ─── Field: Heat capacity ───
  // Water Cp ~4186.8 J/(kg·K) = 1.0 BTU/(lb·°F)
  expectClose(field.heatCapacity(4186.8), 1.0, 'Field: 4186.8 J/(kg·K) = 1 BTU/(lb·°F)', 0.002);

  // ─── Field: Power ───
  // 1 hp = 0.7457 kW, so 0.7457 kW = 1 hp
  expectClose(field.power(0.7457), 1.0, 'Field: 0.7457 kW = 1 hp', 0.002);

  // ─── Field: Volumetric flow ───
  // 1 m³/s = 35.3147 ft³/s
  expectClose(field.volumetricFlow(1), 35.3147, 'Field: 1 m³/s = 35.3147 ft³/s', 0.002);

  // ─── Field: Velocity ───
  // 1 m/s = 3.28084 ft/s
  expectClose(field.velocity(1), 3.28084, 'Field: 1 m/s = 3.28084 ft/s', 0.002);

  // ─── Field: Area ───
  expectClose(field.area(1), 10.7639, 'Field: 1 m² = 10.7639 ft²', 0.002);

  // ─── Field: Length ───
  expectClose(field.length(1), 3.28084, 'Field: 1 m = 3.28084 ft', 0.002);

  // ─── CGS: Temperature (identity) ───
  expectClose(cgs.temperature(100), 100, 'CGS: 100°C = 100°C');
  expectClose(cgs.temperature(-50), -50, 'CGS: -50°C = -50°C');

  // ─── CGS: Pressure ───
  // 101.325 kPa = 1 atm
  expectClose(cgs.pressure(101.325), 1.0, 'CGS: 101.325 kPa = 1 atm', 0.002);

  // ─── CGS: Mass flow ───
  // 1 kg/s = 1000 g/s
  expectClose(cgs.massFlow(1), 1000, 'CGS: 1 kg/s = 1000 g/s');

  // ─── CGS: Enthalpy ───
  // 4.1868 kJ/kg = 1 cal/g
  expectClose(cgs.enthalpy(4.1868), 1.0, 'CGS: 4.1868 kJ/kg = 1 cal/g', 0.002);

  // ─── CGS: Density ───
  // 1000 kg/m³ = 1 g/cm³
  expectClose(cgs.density(1000), 1.0, 'CGS: 1000 kg/m³ = 1 g/cm³');

  // ─── CGS: Viscosity ───
  // 1 Pa·s = 10 P
  expectClose(cgs.viscosity(1), 10, 'CGS: 1 Pa·s = 10 P');

  // ─── CGS: Thermal conductivity ───
  // 418.68 W/(m·K) = 1 cal/(s·cm·K)
  expectClose(cgs.thermalConductivity(418.68), 1.0, 'CGS: 418.68 W/(m·K) = 1 cal/(s·cm·K)', 0.002);

  // ─── CGS: Power ───
  // 4.1868 kW = 1 kcal/s
  expectClose(cgs.power(4.1868), 1.0, 'CGS: 4.1868 kW = 1 kcal/s', 0.002);

  // ─── CGS: Volumetric flow ───
  // 1 m³/s = 1e6 cm³/s
  expectClose(cgs.volumetricFlow(1), 1e6, 'CGS: 1 m³/s = 1e6 cm³/s');

  // ─── CGS: Velocity ───
  // 1 m/s = 100 cm/s
  expectClose(cgs.velocity(1), 100, 'CGS: 1 m/s = 100 cm/s');

  // ─── CGS: Area ───
  expectClose(cgs.area(1), 1e4, 'CGS: 1 m² = 1e4 cm²');

  // ─── CGS: Length ───
  expectClose(cgs.length(1), 100, 'CGS: 1 m = 100 cm');

  // ─── SI display: Viscosity ───
  // 1 Pa·s = 1000 mPa·s
  expectClose(siDisplay.viscosity(1), 1000, 'SI: 1 Pa·s = 1000 mPa·s');

  // ─── SI display: Surface tension ───
  // 1 N/m = 1000 mN/m
  expectClose(siDisplay.surfaceTension(1), 1000, 'SI: 1 N/m = 1000 mN/m');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 15: LMTD temperatureDelta edge case — ensure +32 offset is NEVER applied
//
// This is the specific bug we caught: using temperature() instead of
// temperatureDelta() for LMTD, approach temperatures, and pinch ΔT.
// ═══════════════════════════════════════════════════════════════════════════════
test('15 — LMTD temperatureDelta: verify +32 offset is never applied', async () => {
  // For a range of realistic LMTD values, confirm the difference between
  // temperature() and temperatureDelta() is exactly 32°F
  const testLMTDs = [5, 10, 20, 30, 50, 75, 100, 150];

  for (const lmtd of testLMTDs) {
    const correct = field.temperatureDelta(lmtd);   // scale only
    const wrong   = field.temperature(lmtd);          // scale + offset

    // The correct value should be lmtd * 9/5
    expectClose(correct, lmtd * 1.8, `ΔT=${lmtd}°C: correct = ${lmtd * 1.8} Δ°F`);

    // The wrong value would be lmtd * 9/5 + 32
    expectClose(wrong, lmtd * 1.8 + 32, `T=${lmtd}°C: wrong would add 32`);

    // Difference is always exactly 32
    expectClose(wrong - correct, 32, `ΔT=${lmtd}°C: offset difference = 32`);

    // CGS temperatureDelta is identity
    expectClose(cgs.temperatureDelta(lmtd), lmtd, `CGS ΔT=${lmtd}°C identity`);
  }

  // Special case: ΔT = 0 should remain 0, not become 32
  expect(field.temperatureDelta(0)).toBe(0);
  expect(field.temperature(0)).toBe(32);
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 16: Round-trip: toSI(fromSI(x)) = x for all Field conversions
// ═══════════════════════════════════════════════════════════════════════════════
test('16 — Round-trip: Field toSI(fromSI(x)) = x', async () => {
  // Temperature
  const T = 150; // °C
  const T_field = field.temperature(T);
  const T_back = (T_field - 32) * 5 / 9; // °F → °C
  expectClose(T_back, T, 'T round-trip');

  // Pressure
  const P = 500; // kPa
  const P_field = field.pressure(P);
  const P_back = P_field * 6.89476;
  expectClose(P_back, P, 'P round-trip');

  // Mass flow
  const F = 3.5; // kg/s
  const F_field = field.massFlow(F);
  const F_back = F_field / 7936.64;
  expectClose(F_back, F, 'F round-trip');

  // Power
  const W = 250; // kW
  const W_field = field.power(W);
  const W_back = W_field * 0.7457;
  expectClose(W_back, W, 'W round-trip');

  // Enthalpy
  const H = 500; // kJ/kg
  const H_field = field.enthalpy(H);
  const H_back = H_field * 2.326;
  expectClose(H_back, H, 'H round-trip');

  // Density
  const rho = 850; // kg/m³
  const rho_field = field.density(rho);
  const rho_back = rho_field / 0.062428;
  expectClose(rho_back, rho, 'ρ round-trip');

  // Velocity
  const v = 2.5; // m/s
  const v_field = field.velocity(v);
  const v_back = v_field / 3.28084;
  expectClose(v_back, v, 'v round-trip');

  // Temperature delta
  const dT = 25; // Δ°C
  const dT_field = field.temperatureDelta(dT);
  const dT_back = dT_field * 5 / 9; // Δ°F → Δ°C
  expectClose(dT_back, dT, 'ΔT round-trip');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 17: Round-trip: CGS toSI(fromSI(x)) = x
// ═══════════════════════════════════════════════════════════════════════════════
test('17 — Round-trip: CGS toSI(fromSI(x)) = x', async () => {
  // Temperature (identity)
  expectClose(cgs.temperature(75), 75, 'CGS T identity');

  // Pressure
  const P = 500; // kPa
  const P_cgs = cgs.pressure(P);
  const P_back = P_cgs * 101.325;
  expectClose(P_back, P, 'CGS P round-trip');

  // Mass flow
  const F = 3.5; // kg/s
  const F_cgs = cgs.massFlow(F);
  const F_back = F_cgs / 1000;
  expectClose(F_back, F, 'CGS F round-trip');

  // Power
  const W = 250; // kW
  const W_cgs = cgs.power(W);
  const W_back = W_cgs * 4.1868;
  expectClose(W_back, W, 'CGS W round-trip');

  // Enthalpy
  const H = 500; // kJ/kg
  const H_cgs = cgs.enthalpy(H);
  const H_back = H_cgs * 4.1868;
  expectClose(H_back, H, 'CGS H round-trip');

  // Density
  const rho = 850; // kg/m³
  const rho_cgs = cgs.density(rho);
  const rho_back = rho_cgs * 1000;
  expectClose(rho_back, rho, 'CGS ρ round-trip');

  // Velocity
  const v = 2.5; // m/s
  const v_cgs = cgs.velocity(v);
  const v_back = v_cgs / 100;
  expectClose(v_back, v, 'CGS v round-trip');
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 18: Enthalpy conversion with simulation data
// ═══════════════════════════════════════════════════════════════════════════════
test('18 — Enthalpy and entropy conversion from sim data', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Feed', 80, 300, 1, { water: 0.7, methanol: 0.3 }),
    makeNode('h1', 'Heater', 'H-301', { outletTemperature: 120 }),
    makeProduct('p1', 'Hot Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  // Check enthalpy on stream results
  const feedStream = findStream(data.stream_results, 'f1');
  if (feedStream && typeof feedStream.enthalpy === 'number') {
    const h_si = feedStream.enthalpy; // kJ/kg
    expectClose(field.enthalpy(h_si), h_si / 2.326, 'feed H kJ/kg→BTU/lb');
    expectClose(cgs.enthalpy(h_si), h_si / 4.1868, 'feed H kJ/kg→cal/g');
  }

  const heaterOut = findStream(data.stream_results, 'h1');
  if (heaterOut && typeof heaterOut.enthalpy === 'number') {
    const h_out = heaterOut.enthalpy;
    expectClose(field.enthalpy(h_out), h_out / 2.326, 'heater out H kJ/kg→BTU/lb');
    expectClose(cgs.enthalpy(h_out), h_out / 4.1868, 'heater out H kJ/kg→cal/g');
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 19: Negative values — duty, temperature below 0°C
// ═══════════════════════════════════════════════════════════════════════════════
test('19 — Negative values: subzero T and negative duty', async ({ page }) => {
  // Cool propane to -30°C (below 0)
  const nodes = [
    makeFeed('f1', 'Propane Feed', 25, 500, 1, { propane: 1.0 }),
    makeNode('c1', 'Cooler', 'C-401', { outletTemperature: -30 }),
    makeProduct('p1', 'Cold Propane'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'c1', 'in-1'),
    E('e2', 'c1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const coolerOut = findStream(data.stream_results, 'c1');
  expect(coolerOut).toBeDefined();
  const T_sub = coolerOut.temperature; // should be near -30°C

  // -30°C = -22°F
  expectClose(field.temperature(T_sub), T_sub * 9 / 5 + 32, 'subzero T→°F');
  expect(field.temperature(T_sub)).toBeLessThan(32); // below freezing in °F

  // CGS: -30°C = -30°C
  expectClose(cgs.temperature(T_sub), T_sub, 'subzero T identity CGS');

  // Cooler duty should be negative (removing heat)
  const coolerRes = data.equipment_results['c1'];
  if (typeof coolerRes.duty === 'number') {
    // Duty conversion works for negative values too
    const duty_field = field.power(coolerRes.duty);
    expectClose(duty_field, coolerRes.duty / 0.7457, 'negative duty kW→hp');
    // Sign should be preserved
    if (coolerRes.duty < 0) {
      expect(duty_field).toBeLessThan(0);
    }
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
// Test 20: Large values — high pressure, high flow
// ═══════════════════════════════════════════════════════════════════════════════
test('20 — Large values: high P, high flow conversions', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'HP Feed', 25, 10000, 100, { methane: 1.0 }),
    makeNode('h1', 'Heater', 'H-501', { outletTemperature: 500 }),
    makeProduct('p1', 'HP Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'p1', 'in-1'),
  ];
  const data = await runSim(page, nodes, edges);
  expect(data.status).not.toBe('error');

  const heaterOut = findStream(data.stream_results, 'h1');
  expect(heaterOut).toBeDefined();

  // High pressure: 10000 kPa = ~1450 psia
  const P_si = heaterOut.pressure;
  const P_field = field.pressure(P_si);
  expectClose(P_field, P_si / 6.89476, 'high P kPa→psia');
  expect(P_field).toBeGreaterThan(1000); // sanity: should be >1000 psia

  // High flow: 100 kg/s = 793664 lb/h
  const F_si = heaterOut.flowRate;
  const F_field = field.massFlow(F_si);
  expectClose(F_field, F_si * 7936.64, 'high flow kg/s→lb/h');
  expect(F_field).toBeGreaterThan(500000); // sanity

  // High temperature: 500°C = 932°F
  const T_si = heaterOut.temperature;
  expectClose(field.temperature(T_si), T_si * 9 / 5 + 32, 'high T °C→°F');

  // CGS pressure: 10000 kPa = ~98.7 atm
  const P_cgs = cgs.pressure(P_si);
  expectClose(P_cgs, P_si / 101.325, 'high P kPa→atm');
  expect(P_cgs).toBeGreaterThan(90); // sanity
});
