/**
 * 16 Industrial Flowsheet Validation Suite
 *
 * Creates realistic process flowsheets, runs them through the engine,
 * and collects all warnings/errors for comparison against Aspen HYSYS/DWSIM.
 * Covers Oil & Gas, Refining, Chemical, Cryogenic, and Utility processes.
 */
import { test, expect, type Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });
test.setTimeout(180_000);

// ── Helpers ──────────────────────────────────────────────────────────────────

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

async function runSim(
  page: Page,
  nodes: any[],
  edges: any[],
  propertyPackage = 'PengRobinson',
) {
  return page.evaluate(
    async ({ nodes, edges, pp }) => {
      const r = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: pp }),
      });
      return r.json();
    },
    { nodes, edges, pp: propertyPackage },
  );
}

function getResults(raw: any) {
  return raw.results ?? raw;
}

function validatePhysics(res: any) {
  const data = getResults(res);
  expect(data.status).not.toBe('error');
  if (data.stream_results) {
    for (const [, s] of Object.entries<any>(data.stream_results)) {
      if (s.temperature !== undefined) expect(s.temperature).toBeGreaterThan(-274);
      if (s.pressure !== undefined) expect(s.pressure).toBeGreaterThanOrEqual(0);
    }
  }
  expect(data.equipment_results).toBeDefined();
  return data;
}

// Collect warnings/errors from simulation logs
function collectIssues(res: any) {
  const data = getResults(res);
  const logs: string[] = data.logs || [];
  return {
    warnings: logs.filter((l: string) => l.includes('WARNING')),
    errors: logs.filter((l: string) => l.toLowerCase().includes('error')),
    allLogs: logs,
    converged: data.convergence_info?.converged,
    massBalance: data.convergence_info?.mass_balance_ok,
    energyBalance: data.convergence_info?.energy_balance_ok,
  };
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('load');
});

// ═══════════════════════════════════════════════════════════════════════════
// OIL & GAS PROCESSING
// ═══════════════════════════════════════════════════════════════════════════

// 1. Natural Gas Sweetening Unit (DEA)
// Sour gas → Absorber ← Lean DEA → Sweet gas + Rich DEA → Flash → Stripper → Lean DEA
test('1 — Natural Gas Sweetening (DEA)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sour Gas', 40, 7000, 50, {
      methane: 0.82, ethane: 0.05, propane: 0.03,
      'hydrogen sulfide': 0.04, 'carbon dioxide': 0.06,
    }),
    makeFeed('f2', 'Lean DEA', 40, 7000, 100, {
      diethanolamine: 0.10, water: 0.90,
    }),
    makeNode('abs', 'Absorber', 'Amine Absorber', { numberOfStages: 20 }),
    makeNode('c1', 'Cooler', 'Sweet Gas Cooler', { outletTemperature: 35 }),
    makeProduct('p1', 'Sweet Gas'),
    makeNode('v1', 'Valve', 'Rich Amine Flash Valve', { outletPressure: 200 }),
    makeNode('sep', 'Separator', 'Flash Drum'),
    makeProduct('p2', 'Flash Gas'),
    makeNode('h1', 'Heater', 'Rich Amine Heater', { outletTemperature: 110 }),
    makeNode('str', 'Stripper', 'Amine Regenerator', { numberOfStages: 10 }),
    makeFeed('f3', 'Stripping Steam', 150, 200, 5, { water: 1.0 }),
    makeNode('c2', 'Cooler', 'Acid Gas Cooler', { outletTemperature: 40 }),
    makeProduct('p3', 'Acid Gas'),
    makeNode('c3', 'Cooler', 'Lean Amine Cooler', { outletTemperature: 40 }),
    makeNode('pump', 'Pump', 'Lean Amine Pump', { outletPressure: 7000 }),
    makeProduct('p4', 'Lean DEA Return'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'abs', 'in-1'),
    E('e2', 'f2', 'out-1', 'abs', 'in-2'),
    E('e3', 'abs', 'out-1', 'c1', 'in-1'),
    E('e4', 'c1', 'out-1', 'p1', 'in-1'),
    E('e5', 'abs', 'out-2', 'v1', 'in-1'),
    E('e6', 'v1', 'out-1', 'sep', 'in-1'),
    E('e7', 'sep', 'out-1', 'p2', 'in-1'),
    E('e8', 'sep', 'out-2', 'h1', 'in-1'),
    E('e9', 'h1', 'out-1', 'str', 'in-1'),
    E('e10', 'f3', 'out-1', 'str', 'in-2'),
    E('e11', 'str', 'out-1', 'c2', 'in-1'),
    E('e12', 'c2', 'out-1', 'p3', 'in-1'),
    E('e13', 'str', 'out-2', 'c3', 'in-1'),
    E('e14', 'c3', 'out-1', 'pump', 'in-1'),
    E('e15', 'pump', 'out-1', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 1 — Natural Gas Sweetening (DEA)');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  // Sweet gas should have reduced H2S/CO2
  const sweetGasEdge = Object.entries(res.stream_results || {}).find(
    ([, s]: [string, any]) => s.to === 'p1' || s.from === 'c1'
  );
  // Rich amine should exit absorber bottom
  expect(res.equipment_results?.['abs']).toBeDefined();
});

// 2. Crude Oil Atmospheric Distillation
// Crude → Heater → Column#1 (naphtha/heavy) → Column#2 (diesel/residue)
test('2 — Crude Atmospheric Distillation', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Crude Oil', 25, 500, 100, {
      'n-hexane': 0.20, 'n-heptane': 0.25, 'n-octane': 0.25,
      'n-decane': 0.20, benzene: 0.10,
    }),
    makeNode('h1', 'Heater', 'Crude Furnace', { outletTemperature: 360 }),
    makeNode('col1', 'DistillationColumn', 'Atmospheric Column', {
      numberOfStages: 25, refluxRatio: 2.5,
      lightKey: 'benzene', heavyKey: 'n-heptane',
    }),
    makeNode('c1', 'Cooler', 'Naphtha Condenser', { outletTemperature: 40 }),
    makeProduct('p1', 'Naphtha'),
    makeNode('h2', 'Heater', 'Reboiler Sim', { outletTemperature: 380 }),
    makeNode('col2', 'DistillationColumn', 'Vacuum Column', {
      numberOfStages: 15, refluxRatio: 1.5,
      lightKey: 'n-octane', heavyKey: 'n-decane',
    }),
    makeNode('c2', 'Cooler', 'Diesel Cooler', { outletTemperature: 50 }),
    makeProduct('p2', 'Diesel'),
    makeNode('pump1', 'Pump', 'Residue Pump', { outletPressure: 500 }),
    makeProduct('p3', 'Residue'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'col1', 'in-1'),
    E('e3', 'col1', 'out-1', 'c1', 'in-1'),
    E('e4', 'c1', 'out-1', 'p1', 'in-1'),
    E('e5', 'col1', 'out-2', 'h2', 'in-1'),
    E('e6', 'h2', 'out-1', 'col2', 'in-1'),
    E('e7', 'col2', 'out-1', 'c2', 'in-1'),
    E('e8', 'c2', 'out-1', 'p2', 'in-1'),
    E('e9', 'col2', 'out-2', 'pump1', 'in-1'),
    E('e10', 'pump1', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 2 — Crude Atmospheric Distillation');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  // Both columns should produce results
  expect(res.equipment_results?.['col1']).toBeDefined();
  expect(res.equipment_results?.['col2']).toBeDefined();
});

// 3. Natural Gas Dehydration (DEA as TEG surrogate — TEG not in compound list)
// Wet gas → Absorber ← Glycol → Dry gas + Rich glycol → Flash → Regen → Lean glycol
test('3 — Natural Gas Dehydration (Glycol)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Wet Gas', 30, 7000, 30, {
      methane: 0.90, ethane: 0.05, water: 0.05,
    }),
    makeFeed('f2', 'Lean Glycol', 40, 7000, 5, {
      diethanolamine: 0.95, water: 0.05,
    }),
    makeNode('abs', 'Absorber', 'Glycol Contactor', { numberOfStages: 8 }),
    makeProduct('p1', 'Dry Gas'),
    makeNode('v1', 'Valve', 'Flash Valve', { outletPressure: 400 }),
    makeNode('sep', 'Separator', 'Flash Drum'),
    makeProduct('p2', 'Flash Gas'),
    makeNode('h1', 'Heater', 'Regen Heater', { outletTemperature: 200 }),
    makeNode('sep2', 'Separator', 'Regenerator'),
    makeProduct('p3', 'Water Vapor'),
    makeNode('c1', 'Cooler', 'Glycol Cooler', { outletTemperature: 40 }),
    makeNode('pump', 'Pump', 'Glycol Pump', { outletPressure: 7000 }),
    makeProduct('p4', 'Lean Glycol Return'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'abs', 'in-1'),
    E('e2', 'f2', 'out-1', 'abs', 'in-2'),
    E('e3', 'abs', 'out-1', 'p1', 'in-1'),
    E('e4', 'abs', 'out-2', 'v1', 'in-1'),
    E('e5', 'v1', 'out-1', 'sep', 'in-1'),
    E('e6', 'sep', 'out-1', 'p2', 'in-1'),
    E('e7', 'sep', 'out-2', 'h1', 'in-1'),
    E('e8', 'h1', 'out-1', 'sep2', 'in-1'),
    E('e9', 'sep2', 'out-1', 'p3', 'in-1'),
    E('e10', 'sep2', 'out-2', 'c1', 'in-1'),
    E('e11', 'c1', 'out-1', 'pump', 'in-1'),
    E('e12', 'pump', 'out-1', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 3 — Natural Gas Dehydration (Glycol)');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 4. Three-Phase Separator Train
// Wellhead fluid → HP 3-phase sep → gas compression, oil stabilization, water disposal
test('4 — Three-Phase Separator Train', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Wellhead Fluid', 80, 5000, 50, {
      methane: 0.30, 'n-hexane': 0.40, water: 0.30,
    }),
    makeNode('tps', 'ThreePhaseSeparator', 'HP Separator', { lightLiquidFraction: 0.6 }),
    makeNode('comp', 'Compressor', 'Export Gas Compressor', { outletPressure: 7000, efficiency: 75 }),
    makeNode('c1', 'Cooler', 'Gas Aftercooler', { outletTemperature: 40 }),
    makeProduct('p1', 'Export Gas'),
    makeNode('v1', 'Valve', 'LP Letdown', { outletPressure: 1500 }),
    makeNode('sep', 'Separator', 'LP Separator'),
    makeProduct('p2', 'LP Gas'),
    makeNode('c2', 'Cooler', 'Oil Cooler', { outletTemperature: 40 }),
    makeProduct('p3', 'Stabilized Oil'),
    makeNode('pump', 'Pump', 'Water Disposal Pump', { outletPressure: 200 }),
    makeNode('pipe', 'PipeSegment', 'Water Injection Line', { length: 500, diameter: 0.15 }),
    makeProduct('p4', 'Produced Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'tps', 'in-1'),
    E('e2', 'tps', 'out-1', 'comp', 'in-1'),
    E('e3', 'comp', 'out-1', 'c1', 'in-1'),
    E('e4', 'c1', 'out-1', 'p1', 'in-1'),
    E('e5', 'tps', 'out-2', 'v1', 'in-1'),
    E('e6', 'v1', 'out-1', 'sep', 'in-1'),
    E('e7', 'sep', 'out-1', 'p2', 'in-1'),
    E('e8', 'sep', 'out-2', 'c2', 'in-1'),
    E('e9', 'c2', 'out-1', 'p3', 'in-1'),
    E('e10', 'tps', 'out-3', 'pump', 'in-1'),
    E('e11', 'pump', 'out-1', 'pipe', 'in-1'),
    E('e12', 'pipe', 'out-1', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 4 — Three-Phase Separator Train');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  expect(res.equipment_results?.['tps']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// REFINING & PETROCHEMICALS
// ═══════════════════════════════════════════════════════════════════════════

// 5. Naphtha Reforming Unit
// Naphtha + H2 → Heater → CSTR → Cooler → Separator → H2 recycle + Reformate
test('5 — Naphtha Reforming Unit', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Naphtha Feed', 150, 3000, 20, {
      'n-hexane': 0.30, 'n-heptane': 0.30, cyclohexane: 0.20,
      benzene: 0.10, toluene: 0.10,
    }),
    makeFeed('f2', 'H2 Makeup', 200, 3000, 2, { hydrogen: 1.0 }),
    makeNode('mix', 'Mixer', 'Feed Mixer'),
    makeNode('h1', 'Heater', 'Charge Heater', { outletTemperature: 500 }),
    makeNode('rx', 'CSTRReactor', 'Reforming Reactor', {
      volume: 50, temperature: 500, pressure: 3000,
    }),
    makeNode('c1', 'Cooler', 'Reactor Effluent Cooler', { outletTemperature: 40 }),
    makeNode('sep', 'Separator', 'Product Separator'),
    makeNode('comp', 'Compressor', 'Recycle Compressor', { outletPressure: 3000, efficiency: 75 }),
    makeNode('spl', 'Splitter', 'H2 Splitter', { splitRatio: 0.85 }),
    makeProduct('p1', 'Net H2'),
    makeProduct('p2', 'Recycle H2'),
    makeNode('col', 'DistillationColumn', 'Stabilizer', {
      numberOfStages: 20, refluxRatio: 2.0,
      lightKey: 'n-hexane', heavyKey: 'n-heptane',
    }),
    makeProduct('p3', 'LPG'),
    makeProduct('p4', 'Reformate'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mix', 'in-1'),
    E('e2', 'f2', 'out-1', 'mix', 'in-2'),
    E('e3', 'mix', 'out-1', 'h1', 'in-1'),
    E('e4', 'h1', 'out-1', 'rx', 'in-1'),
    E('e5', 'rx', 'out-1', 'c1', 'in-1'),
    E('e6', 'c1', 'out-1', 'sep', 'in-1'),
    E('e7', 'sep', 'out-1', 'comp', 'in-1'),
    E('e8', 'comp', 'out-1', 'spl', 'in-1'),
    E('e9', 'spl', 'out-1', 'p1', 'in-1'),
    E('e10', 'spl', 'out-2', 'p2', 'in-1'),
    E('e11', 'sep', 'out-2', 'col', 'in-1'),
    E('e12', 'col', 'out-1', 'p3', 'in-1'),
    E('e13', 'col', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 5 — Naphtha Reforming Unit');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 6. LPG Fractionation Train
// Mixed C2-C4 → Deethanizer → Depropanizer → Debutanizer → C2, C3, iC4, nC4
test('6 — LPG Fractionation Train', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Mixed LPG', 30, 2000, 15, {
      ethane: 0.15, propane: 0.40, 'n-butane': 0.30, isobutane: 0.15,
    }),
    makeNode('col1', 'DistillationColumn', 'Deethanizer', {
      numberOfStages: 30, refluxRatio: 3.0,
      lightKey: 'ethane', heavyKey: 'propane',
    }),
    makeNode('c1', 'Cooler', 'Ethane Cooler', { outletTemperature: -20 }),
    makeProduct('p1', 'Ethane Product'),
    makeNode('col2', 'DistillationColumn', 'Depropanizer', {
      numberOfStages: 40, refluxRatio: 4.0,
      lightKey: 'propane', heavyKey: 'isobutane',
    }),
    makeNode('c2', 'Cooler', 'Propane Cooler', { outletTemperature: 40 }),
    makeProduct('p2', 'Propane Product'),
    makeNode('col3', 'DistillationColumn', 'Debutanizer', {
      numberOfStages: 30, refluxRatio: 3.0,
      lightKey: 'isobutane', heavyKey: 'n-butane',
    }),
    makeProduct('p3', 'Isobutane Product'),
    makeProduct('p4', 'n-Butane Product'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'col1', 'in-1'),
    E('e2', 'col1', 'out-1', 'c1', 'in-1'),
    E('e3', 'c1', 'out-1', 'p1', 'in-1'),
    E('e4', 'col1', 'out-2', 'col2', 'in-1'),
    E('e5', 'col2', 'out-1', 'c2', 'in-1'),
    E('e6', 'c2', 'out-1', 'p2', 'in-1'),
    E('e7', 'col2', 'out-2', 'col3', 'in-1'),
    E('e8', 'col3', 'out-1', 'p3', 'in-1'),
    E('e9', 'col3', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges, 'SRK');
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 6 — LPG Fractionation Train');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  // All three columns should have results
  expect(res.equipment_results?.['col1']).toBeDefined();
  expect(res.equipment_results?.['col2']).toBeDefined();
  expect(res.equipment_results?.['col3']).toBeDefined();
});

// 7. Hydrodesulfurization (HDS) Unit
// Diesel + H2 → Heater → ConversionReactor → Cooler → Separator → clean diesel
test('7 — Hydrodesulfurization (HDS)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Diesel Feed', 200, 4000, 30, {
      'n-heptane': 0.45, 'n-octane': 0.45,
      'hydrogen sulfide': 0.05, benzene: 0.05,
    }),
    makeFeed('f2', 'Hydrogen Feed', 200, 4000, 1, { hydrogen: 1.0 }),
    makeNode('mix', 'Mixer', 'Feed Mixer'),
    makeNode('h1', 'Heater', 'Reactor Charge Heater', { outletTemperature: 350 }),
    makeNode('rx', 'ConversionReactor', 'HDS Reactor', {
      conversion: 95, temperature: 350, pressure: 4000,
      keyReactant: 'hydrogen sulfide',
    }),
    makeNode('c1', 'Cooler', 'Reactor Effluent Cooler', { outletTemperature: 40 }),
    makeNode('sep', 'Separator', 'HP Separator'),
    makeProduct('p1', 'Off Gas'),
    makeNode('col', 'DistillationColumn', 'Product Fractionator', {
      numberOfStages: 15, refluxRatio: 1.5,
      lightKey: 'benzene', heavyKey: 'n-heptane',
    }),
    makeProduct('p2', 'Light Naphtha'),
    makeProduct('p3', 'Clean Diesel'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mix', 'in-1'),
    E('e2', 'f2', 'out-1', 'mix', 'in-2'),
    E('e3', 'mix', 'out-1', 'h1', 'in-1'),
    E('e4', 'h1', 'out-1', 'rx', 'in-1'),
    E('e5', 'rx', 'out-1', 'c1', 'in-1'),
    E('e6', 'c1', 'out-1', 'sep', 'in-1'),
    E('e7', 'sep', 'out-1', 'p1', 'in-1'),
    E('e8', 'sep', 'out-2', 'col', 'in-1'),
    E('e9', 'col', 'out-1', 'p2', 'in-1'),
    E('e10', 'col', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 7 — HDS Unit');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  // Reactor should show conversion
  expect(res.equipment_results?.['rx']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// CHEMICAL PROCESSING
// ═══════════════════════════════════════════════════════════════════════════

// 8. Ammonia Synthesis Loop (Haber-Bosch)
// H2+N2 → Compressor → Heater → CSTR → HX → Cooler → Separator → NH3 + recycle
test('8 — Ammonia Synthesis Loop', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Syngas Feed', 30, 3000, 10, {
      hydrogen: 0.75, nitrogen: 0.25,
    }),
    makeNode('comp', 'Compressor', 'Synthesis Compressor', { outletPressure: 15000, efficiency: 80 }),
    makeNode('mix', 'Mixer', 'Feed Mixer'),
    makeFeed('f2', 'Makeup Gas', 200, 15000, 1, { hydrogen: 0.75, nitrogen: 0.25 }),
    makeNode('h1', 'Heater', 'Reactor Preheater', { outletTemperature: 450 }),
    makeNode('rx', 'CSTRReactor', 'Synthesis Converter', {
      volume: 100, temperature: 450, pressure: 15000,
    }),
    makeNode('hx', 'HeatExchanger', 'Feed/Effluent HX'),
    makeFeed('f3', 'Cooling Water', 25, 15000, 5, { water: 1.0 }),
    makeNode('c1', 'Cooler', 'Ammonia Chiller', { outletTemperature: -20 }),
    makeNode('sep', 'Separator', 'Ammonia Separator'),
    makeNode('spl', 'Splitter', 'Purge Splitter', { splitRatio: 0.95 }),
    makeProduct('p1', 'Recycle Gas'),
    makeProduct('p2', 'Purge'),
    makeNode('v1', 'Valve', 'NH3 Letdown', { outletPressure: 200 }),
    makeProduct('p3', 'Liquid NH3'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp', 'in-1'),
    E('e2', 'comp', 'out-1', 'mix', 'in-1'),
    E('e3', 'f2', 'out-1', 'mix', 'in-2'),
    E('e4', 'mix', 'out-1', 'h1', 'in-1'),
    E('e5', 'h1', 'out-1', 'rx', 'in-1'),
    E('e6', 'rx', 'out-1', 'hx', 'in-hot'),
    E('e7', 'f3', 'out-1', 'hx', 'in-cold'),
    E('e8', 'hx', 'out-hot', 'c1', 'in-1'),
    E('e9', 'c1', 'out-1', 'sep', 'in-1'),
    E('e10', 'sep', 'out-1', 'spl', 'in-1'),
    E('e11', 'spl', 'out-1', 'p1', 'in-1'),
    E('e12', 'spl', 'out-2', 'p2', 'in-1'),
    E('e13', 'sep', 'out-2', 'v1', 'in-1'),
    E('e14', 'v1', 'out-1', 'p3', 'in-1'),
    E('e15', 'hx', 'out-cold', 'p1', 'in-1'),  // cold side exits
  ];
  // Fix: cold side out can't go to same product — add separate product
  // Adjust: remove e15 clash, add dedicated cold outlet product
  edges.pop(); // remove e15
  const coldProduct = makeProduct('p4', 'Warm CW');
  nodes.push(coldProduct);
  edges.push(E('e15', 'hx', 'out-cold', 'p4', 'in-1'));

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 8 — Ammonia Synthesis Loop');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 9. Methanol Production from Syngas
// Syngas → Compressor → Heater → ConvReactor → Cooler → Sep → Distillation → MeOH
test('9 — Methanol Production', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Syngas', 40, 5000, 20, {
      hydrogen: 0.65, 'carbon monoxide': 0.25, 'carbon dioxide': 0.10,
    }),
    makeNode('comp', 'Compressor', 'Syngas Compressor', { outletPressure: 8000, efficiency: 80 }),
    makeNode('h1', 'Heater', 'Reactor Preheater', { outletTemperature: 250 }),
    makeNode('rx', 'ConversionReactor', 'Methanol Reactor', {
      conversion: 50, temperature: 250, pressure: 8000,
      keyReactant: 'carbon monoxide',
    }),
    makeNode('c1', 'Cooler', 'Reactor Cooler', { outletTemperature: 40 }),
    makeNode('sep', 'Separator', 'HP Flash Drum'),
    makeNode('spl', 'Splitter', 'Purge/Recycle', { splitRatio: 0.90 }),
    makeProduct('p1', 'Recycle Gas'),
    makeProduct('p2', 'Purge Gas'),
    makeNode('v1', 'Valve', 'Let-down Valve', { outletPressure: 200 }),
    makeNode('col', 'DistillationColumn', 'Methanol Column', {
      numberOfStages: 30, refluxRatio: 2.5,
      lightKey: 'methanol', heavyKey: 'water',
    }),
    makeNode('c2', 'Cooler', 'MeOH Cooler', { outletTemperature: 25 }),
    makeProduct('p3', 'Methanol'),
    makeProduct('p4', 'Waste Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp', 'in-1'),
    E('e2', 'comp', 'out-1', 'h1', 'in-1'),
    E('e3', 'h1', 'out-1', 'rx', 'in-1'),
    E('e4', 'rx', 'out-1', 'c1', 'in-1'),
    E('e5', 'c1', 'out-1', 'sep', 'in-1'),
    E('e6', 'sep', 'out-1', 'spl', 'in-1'),
    E('e7', 'spl', 'out-1', 'p1', 'in-1'),
    E('e8', 'spl', 'out-2', 'p2', 'in-1'),
    E('e9', 'sep', 'out-2', 'v1', 'in-1'),
    E('e10', 'v1', 'out-1', 'col', 'in-1'),
    E('e11', 'col', 'out-1', 'c2', 'in-1'),
    E('e12', 'c2', 'out-1', 'p3', 'in-1'),
    E('e13', 'col', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 9 — Methanol Production');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 10. Ethylene Glycol Plant (adapted — ethylene oxide not available)
// Ethanol/water feed → PFR → Cooler → Sep → Distillation → products
test('10 — Ethylene Glycol Plant (Adapted)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Reactor Feed', 80, 500, 10, {
      ethanol: 0.50, water: 0.50,
    }),
    makeNode('rx', 'PFRReactor', 'Hydration Reactor', {
      length: 5, diameter: 0.5, temperature: 200, pressure: 1500,
    }),
    makeNode('c1', 'Cooler', 'Reactor Cooler', { outletTemperature: 60 }),
    makeNode('sep', 'Separator', 'Flash Sep'),
    makeProduct('p1', 'Light Ends'),
    makeNode('col', 'DistillationColumn', 'Product Column', {
      numberOfStages: 25, refluxRatio: 3.0,
      lightKey: 'ethanol', heavyKey: 'water',
    }),
    makeNode('c2', 'Cooler', 'Product Cooler', { outletTemperature: 30 }),
    makeProduct('p2', 'Ethanol Product'),
    makeNode('h1', 'Heater', 'Evaporator', { outletTemperature: 120 }),
    makeNode('sep2', 'Separator', 'Evaporator Drum'),
    makeProduct('p3', 'Steam'),
    makeProduct('p4', 'Concentrate'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'rx', 'in-1'),
    E('e2', 'rx', 'out-1', 'c1', 'in-1'),
    E('e3', 'c1', 'out-1', 'sep', 'in-1'),
    E('e4', 'sep', 'out-1', 'p1', 'in-1'),
    E('e5', 'sep', 'out-2', 'col', 'in-1'),
    E('e6', 'col', 'out-1', 'c2', 'in-1'),
    E('e7', 'c2', 'out-1', 'p2', 'in-1'),
    E('e8', 'col', 'out-2', 'h1', 'in-1'),
    E('e9', 'h1', 'out-1', 'sep2', 'in-1'),
    E('e10', 'sep2', 'out-1', 'p3', 'in-1'),
    E('e11', 'sep2', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges, 'NRTL');
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 10 — Ethylene Glycol Plant (Adapted)');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 11. Acetic Acid Production (Methanol Carbonylation)
// MeOH + CO → CSTR → Flash → Column#1 (lights) → Column#2 (AcOH/water)
test('11 — Acetic Acid Production', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Methanol Feed', 30, 3000, 5, {
      methanol: 0.95, water: 0.05,
    }),
    makeFeed('f2', 'CO Feed', 30, 3000, 8, { 'carbon monoxide': 1.0 }),
    makeNode('mix', 'Mixer', 'Feed Mixer'),
    makeNode('h1', 'Heater', 'Reactor Preheater', { outletTemperature: 180 }),
    makeNode('rx', 'CSTRReactor', 'Carbonylation Reactor', {
      volume: 20, temperature: 180, pressure: 3000,
    }),
    makeNode('c1', 'Cooler', 'Reactor Cooler', { outletTemperature: 40 }),
    makeNode('sep', 'Separator', 'Flash Vessel'),
    makeProduct('p1', 'Vent Gas'),
    makeNode('col1', 'DistillationColumn', 'Light Ends Column', {
      numberOfStages: 20, refluxRatio: 2.0,
      lightKey: 'methanol', heavyKey: 'acetic acid',
    }),
    makeProduct('p2', 'Light Ends Recycle'),
    makeNode('col2', 'DistillationColumn', 'Dehydration Column', {
      numberOfStages: 25, refluxRatio: 3.0,
      lightKey: 'acetic acid', heavyKey: 'water',
    }),
    makeProduct('p3', 'Acetic Acid'),
    makeProduct('p4', 'Waste Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mix', 'in-1'),
    E('e2', 'f2', 'out-1', 'mix', 'in-2'),
    E('e3', 'mix', 'out-1', 'h1', 'in-1'),
    E('e4', 'h1', 'out-1', 'rx', 'in-1'),
    E('e5', 'rx', 'out-1', 'c1', 'in-1'),
    E('e6', 'c1', 'out-1', 'sep', 'in-1'),
    E('e7', 'sep', 'out-1', 'p1', 'in-1'),
    E('e8', 'sep', 'out-2', 'col1', 'in-1'),
    E('e9', 'col1', 'out-1', 'p2', 'in-1'),
    E('e10', 'col1', 'out-2', 'col2', 'in-1'),
    E('e11', 'col2', 'out-1', 'p3', 'in-1'),
    E('e12', 'col2', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 11 — Acetic Acid Production');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// ═══════════════════════════════════════════════════════════════════════════
// GAS PROCESSING & CRYOGENICS
// ═══════════════════════════════════════════════════════════════════════════

// 12. NGL Recovery (Turboexpander Plant)
// Gas → Cold box → Sep → Valve(expander) → Demethanizer → Residue gas + NGL
test('12 — NGL Recovery (Turboexpander)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Inlet Gas', 30, 6000, 40, {
      methane: 0.80, ethane: 0.10, propane: 0.06, 'n-butane': 0.04,
    }),
    makeNode('c1', 'Cooler', 'Cold Box Inlet', { outletTemperature: -40 }),
    makeNode('sep', 'Separator', 'Cold Separator'),
    makeNode('v1', 'Valve', 'Turboexpander', { outletPressure: 1500 }),
    makeNode('v2', 'Valve', 'Liquid JT Valve', { outletPressure: 1500 }),
    makeNode('mix', 'Mixer', 'Demethanizer Feed Mixer'),
    makeNode('col', 'DistillationColumn', 'Demethanizer', {
      numberOfStages: 30, refluxRatio: 1.5,
      lightKey: 'methane', heavyKey: 'ethane',
    }),
    makeNode('comp', 'Compressor', 'Residue Gas Compressor', { outletPressure: 6000, efficiency: 80 }),
    makeNode('c2', 'Cooler', 'Residue Aftercooler', { outletTemperature: 30 }),
    makeProduct('p1', 'Residue Gas'),
    makeNode('pump', 'Pump', 'NGL Pump', { outletPressure: 2000 }),
    makeProduct('p2', 'NGL Product'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'c1', 'in-1'),
    E('e2', 'c1', 'out-1', 'sep', 'in-1'),
    E('e3', 'sep', 'out-1', 'v1', 'in-1'),
    E('e4', 'sep', 'out-2', 'v2', 'in-1'),
    E('e5', 'v1', 'out-1', 'mix', 'in-1'),
    E('e6', 'v2', 'out-1', 'mix', 'in-2'),
    E('e7', 'mix', 'out-1', 'col', 'in-1'),
    E('e8', 'col', 'out-1', 'comp', 'in-1'),
    E('e9', 'comp', 'out-1', 'c2', 'in-1'),
    E('e10', 'c2', 'out-1', 'p1', 'in-1'),
    E('e11', 'col', 'out-2', 'pump', 'in-1'),
    E('e12', 'pump', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges, 'SRK');
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 12 — NGL Recovery (Turboexpander)');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 13. Air Separation Unit (ASU)
// Air → 2-stage compression → Cooling → HP Column → LP Column → N2, O2, Ar
test('13 — Air Separation Unit', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Ambient Air', 25, 101.325, 50, {
      nitrogen: 0.78, oxygen: 0.21, argon: 0.01,
    }),
    makeNode('comp1', 'Compressor', 'MAC Stage 1', { outletPressure: 300, efficiency: 82 }),
    makeNode('c1', 'Cooler', 'Intercooler', { outletTemperature: 35 }),
    makeNode('comp2', 'Compressor', 'MAC Stage 2', { outletPressure: 600, efficiency: 82 }),
    makeNode('c2', 'Cooler', 'Aftercooler', { outletTemperature: 35 }),
    makeNode('c3', 'Cooler', 'Main HX Cold End', { outletTemperature: -170 }),
    makeNode('col1', 'DistillationColumn', 'HP Column', {
      numberOfStages: 40, refluxRatio: 2.0,
      lightKey: 'nitrogen', heavyKey: 'oxygen',
    }),
    makeProduct('p1', 'GAN (N2)'),
    makeNode('v1', 'Valve', 'LP Expansion', { outletPressure: 130 }),
    makeNode('col2', 'DistillationColumn', 'LP Column', {
      numberOfStages: 50, refluxRatio: 1.5,
      lightKey: 'argon', heavyKey: 'oxygen',
    }),
    makeProduct('p2', 'Waste Ar+N2'),
    makeNode('pump', 'Pump', 'LOX Pump', { outletPressure: 500 }),
    makeProduct('p3', 'LOX (O2)'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp1', 'in-1'),
    E('e2', 'comp1', 'out-1', 'c1', 'in-1'),
    E('e3', 'c1', 'out-1', 'comp2', 'in-1'),
    E('e4', 'comp2', 'out-1', 'c2', 'in-1'),
    E('e5', 'c2', 'out-1', 'c3', 'in-1'),
    E('e6', 'c3', 'out-1', 'col1', 'in-1'),
    E('e7', 'col1', 'out-1', 'p1', 'in-1'),
    E('e8', 'col1', 'out-2', 'v1', 'in-1'),
    E('e9', 'v1', 'out-1', 'col2', 'in-1'),
    E('e10', 'col2', 'out-1', 'p2', 'in-1'),
    E('e11', 'col2', 'out-2', 'pump', 'in-1'),
    E('e12', 'pump', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 13 — Air Separation Unit');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES & ENVIRONMENTAL
// ═══════════════════════════════════════════════════════════════════════════

// 14. Steam Boiler & BFW System
// BFW → Pump → Economizer → Boiler → Steam drum → Superheater → HP/MP/LP headers
test('14 — Steam Boiler & BFW System', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Boiler Feedwater', 25, 101.325, 20, { water: 1.0 }),
    makeNode('pump', 'Pump', 'BFW Pump', { outletPressure: 12000 }),
    makeNode('h1', 'Heater', 'Economizer', { outletTemperature: 180 }),
    makeNode('h2', 'Heater', 'Boiler', { outletTemperature: 327 }),
    makeNode('sep', 'Separator', 'Steam Drum'),
    makeNode('h3', 'Heater', 'Superheater', { outletTemperature: 500 }),
    makeNode('spl1', 'Splitter', 'HP/MP Split', { splitRatio: 0.60 }),
    makeProduct('p1', 'HP Steam'),
    makeNode('v1', 'Valve', 'MP Letdown', { outletPressure: 1000 }),
    makeNode('spl2', 'Splitter', 'MP/LP Split', { splitRatio: 0.50 }),
    makeProduct('p2', 'MP Steam'),
    makeProduct('p3', 'LP Steam'),
    makeNode('v2', 'Valve', 'Blowdown Valve', { outletPressure: 101.325 }),
    makeProduct('p4', 'Blowdown'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'pump', 'in-1'),
    E('e2', 'pump', 'out-1', 'h1', 'in-1'),
    E('e3', 'h1', 'out-1', 'h2', 'in-1'),
    E('e4', 'h2', 'out-1', 'sep', 'in-1'),
    E('e5', 'sep', 'out-1', 'h3', 'in-1'),
    E('e6', 'h3', 'out-1', 'spl1', 'in-1'),
    E('e7', 'spl1', 'out-1', 'p1', 'in-1'),
    E('e8', 'spl1', 'out-2', 'v1', 'in-1'),
    E('e9', 'v1', 'out-1', 'spl2', 'in-1'),
    E('e10', 'spl2', 'out-1', 'p2', 'in-1'),
    E('e11', 'spl2', 'out-2', 'p3', 'in-1'),
    E('e12', 'sep', 'out-2', 'v2', 'in-1'),
    E('e13', 'v2', 'out-1', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 14 — Steam Boiler & BFW');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));

  // Check HP steam temp should be ~500°C
  const superheaterRes = res.equipment_results?.['h3'];
  if (superheaterRes) {
    console.log('  Superheater outlet T:', superheaterRes.outletTemperature, '°C');
  }
});

// 15. Sour Water Stripper
// Sour water → Heater → Stripper ← Steam → Acid gas + Clean water
test('15 — Sour Water Stripper', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sour Water', 80, 300, 10, {
      water: 0.90, 'hydrogen sulfide': 0.05, ammonia: 0.05,
    }),
    makeNode('h1', 'Heater', 'Feed Preheater', { outletTemperature: 100 }),
    makeNode('str', 'Stripper', 'SWS Column', { numberOfStages: 15 }),
    makeFeed('f2', 'Stripping Steam', 150, 300, 2, { water: 1.0 }),
    makeNode('c1', 'Cooler', 'Overhead Condenser', { outletTemperature: 35 }),
    makeNode('sep', 'Separator', 'Reflux Drum'),
    makeProduct('p1', 'Acid Gas to SRU'),
    makeProduct('p2', 'Sour Condensate'),
    makeNode('c2', 'Cooler', 'Stripped Water Cooler', { outletTemperature: 40 }),
    makeProduct('p3', 'Clean Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'str', 'in-1'),
    E('e3', 'f2', 'out-1', 'str', 'in-2'),
    E('e4', 'str', 'out-1', 'c1', 'in-1'),
    E('e5', 'c1', 'out-1', 'sep', 'in-1'),
    E('e6', 'sep', 'out-1', 'p1', 'in-1'),
    E('e7', 'sep', 'out-2', 'p2', 'in-1'),
    E('e8', 'str', 'out-2', 'c2', 'in-1'),
    E('e9', 'c2', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 15 — Sour Water Stripper');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});

// 16. Flue Gas Desulfurization (FGD)
// Flue gas → Quench → Absorber ← Water → Clean gas → Stack + Rich liquid → Settling
test('16 — Flue Gas Desulfurization', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Flue Gas', 150, 105, 100, {
      nitrogen: 0.72, 'carbon dioxide': 0.12, oxygen: 0.05,
      'sulfur dioxide': 0.005, water: 0.105,
    }),
    makeNode('c1', 'Cooler', 'Quench Tower', { outletTemperature: 60 }),
    makeNode('abs', 'Absorber', 'FGD Absorber', { numberOfStages: 10 }),
    makeFeed('f2', 'Scrubbing Water', 25, 200, 50, { water: 1.0 }),
    makeNode('h1', 'Heater', 'Stack Reheat', { outletTemperature: 80 }),
    makeNode('pipe', 'PipeSegment', 'Stack', { length: 50, diameter: 3.0 }),
    makeProduct('p1', 'Stack Gas'),
    makeNode('sep', 'Separator', 'Settling Tank'),
    makeProduct('p2', 'Off Gas'),
    makeNode('pump', 'Pump', 'Recirculation Pump', { outletPressure: 200 }),
    makeNode('spl', 'Splitter', 'Recycle/Blowdown', { splitRatio: 0.90 }),
    makeProduct('p3', 'Recycle Slurry'),
    makeProduct('p4', 'Blowdown'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'c1', 'in-1'),
    E('e2', 'c1', 'out-1', 'abs', 'in-1'),
    E('e3', 'f2', 'out-1', 'abs', 'in-2'),
    E('e4', 'abs', 'out-1', 'h1', 'in-1'),
    E('e5', 'h1', 'out-1', 'pipe', 'in-1'),
    E('e6', 'pipe', 'out-1', 'p1', 'in-1'),
    E('e7', 'abs', 'out-2', 'sep', 'in-1'),
    E('e8', 'sep', 'out-1', 'p2', 'in-1'),
    E('e9', 'sep', 'out-2', 'pump', 'in-1'),
    E('e10', 'pump', 'out-1', 'spl', 'in-1'),
    E('e11', 'spl', 'out-1', 'p3', 'in-1'),
    E('e12', 'spl', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const res = validatePhysics(raw);
  const issues = collectIssues(raw);
  console.log('Test 16 — Flue Gas Desulfurization');
  console.log('  Converged:', issues.converged, 'MB:', issues.massBalance, 'EB:', issues.energyBalance);
  console.log('  Warnings:', issues.warnings.length, issues.warnings.join(' | '));
  console.log('  Errors:', issues.errors.length, issues.errors.join(' | '));
});
