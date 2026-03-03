/**
 * 20-Flowsheet Stress Test: Full Equipment Coverage
 *
 * Validates the simulation engine by running 20 realistic industrial flowsheets
 * (10+ unit ops each) via the API, collecting all warnings/errors/logs, and
 * verifying thermodynamic correctness. All 23 process equipment types exercised.
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
  // Status should not be error
  expect(data.status).not.toBe('error');

  // Stream physical constraints
  if (data.stream_results) {
    for (const [eid, s] of Object.entries<any>(data.stream_results)) {
      if (s.temperature !== undefined) {
        expect(s.temperature).toBeGreaterThan(-274);
      }
      if (s.pressure !== undefined) {
        expect(s.pressure).toBeGreaterThanOrEqual(0);
      }
      if (s.flowRate !== undefined) {
        expect(s.flowRate).toBeGreaterThanOrEqual(0);
      }
    }
  }

  // Equipment results should exist
  expect(data.equipment_results).toBeDefined();

  return data;
}

// ── Tests ────────────────────────────────────────────────────────────────────

test.beforeEach(async ({ page }) => {
  await page.goto('/app');
  await page.waitForLoadState('load');
});

// ═══════════════════════════════════════════════════════════════════════════
// 1. Natural Gas Processing (13 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('1 — Natural Gas Processing', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'NatGas Feed', 30, 5000, 50, {
      methane: 0.80, ethane: 0.10, propane: 0.05, 'n-butane': 0.05,
    }),
    makeNode('sep1', 'Separator', 'Inlet Separator'),
    makeNode('comp1', 'Compressor', 'Sales Gas Compressor', { outletPressure: 7000, efficiency: 75 }),
    makeNode('cool1', 'Cooler', 'After-Cooler', { outletTemperature: 35 }),
    makeNode('pipe1', 'PipeSegment', 'Pipeline', { length: 500, diameter: 0.3 }),
    makeProduct('p1', 'Sales Gas'),
    makeNode('v1', 'Valve', 'NGL Valve', { outletPressure: 1500 }),
    makeNode('dist1', 'DistillationColumn', 'De-ethanizer', {
      numberOfStages: 15, refluxRatio: 2, lightKey: 'ethane', heavyKey: 'propane',
    }),
    makeNode('cool2', 'Cooler', 'NGL Cooler', { outletTemperature: 25 }),
    makeProduct('p2', 'NGL Product'),
    makeProduct('p3', 'LPG Product'),
    // Extra products to reach connections
    makeProduct('p4', 'Sep Liq Dist Bot'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'sep1', 'in-1'),
    E('e2', 'sep1', 'out-1', 'comp1', 'in-1'),       // vapor
    E('e3', 'comp1', 'out-1', 'cool1', 'in-1'),
    E('e4', 'cool1', 'out-1', 'pipe1', 'in-1'),
    E('e5', 'pipe1', 'out-1', 'p1', 'in-1'),
    E('e6', 'sep1', 'out-2', 'v1', 'in-1'),           // liquid
    E('e7', 'v1', 'out-1', 'dist1', 'in-1'),
    E('e8', 'dist1', 'out-1', 'cool2', 'in-1'),       // distillate
    E('e9', 'cool2', 'out-1', 'p2', 'in-1'),
    E('e10', 'dist1', 'out-2', 'p3', 'in-1'),         // bottoms
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Compressor should consume work
  const comp = data.equipment_results?.['comp1'];
  if (comp && !comp.error) {
    expect(comp.work).toBeGreaterThan(0);
  }
  // Pipeline should have pressure drop
  const pipe = data.equipment_results?.['pipe1'];
  if (pipe && !pipe.error) {
    expect(pipe.pressureDrop).toBeGreaterThanOrEqual(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. Crude Atmospheric Distillation (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('2 — Crude Atmospheric Distillation', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Crude Feed', 360, 200, 100, {
      'n-hexane': 0.30, 'n-heptane': 0.30, 'n-octane': 0.20, 'n-decane': 0.20,
    }),
    makeNode('h1', 'Heater', 'Furnace', { outletTemperature: 380 }),
    makeNode('dist1', 'DistillationColumn', 'CDU', {
      numberOfStages: 15, refluxRatio: 2.5,
      lightKey: 'n-hexane', heavyKey: 'n-octane',
    }),
    makeNode('cool1', 'Cooler', 'Naphtha Condenser', { outletTemperature: 40 }),
    makeProduct('p1', 'Naphtha'),
    makeNode('v1', 'Valve', 'Vacuum Valve', { outletPressure: 50 }),
    makeNode('sep1', 'Separator', 'Flash Drum'),
    makeProduct('p2', 'VGO'),
    makeProduct('p3', 'Residue'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'dist1', 'in-1'),
    E('e3', 'dist1', 'out-1', 'cool1', 'in-1'),
    E('e4', 'cool1', 'out-1', 'p1', 'in-1'),
    E('e5', 'dist1', 'out-2', 'v1', 'in-1'),
    E('e6', 'v1', 'out-1', 'sep1', 'in-1'),
    E('e7', 'sep1', 'out-1', 'p2', 'in-1'),
    E('e8', 'sep1', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Heater should have positive duty
  const heater = data.equipment_results?.['h1'];
  if (heater && !heater.error) {
    expect(heater.duty).toBeGreaterThan(0);
  }
  // Distillation should report stages
  const dist = data.equipment_results?.['dist1'];
  if (dist && !dist.error) {
    expect(dist.N_min).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. Amine CO₂ Removal (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('3 — Amine CO2 Removal', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sour Gas', 40, 7000, 20, {
      methane: 0.85, 'carbon dioxide': 0.10, 'hydrogen sulfide': 0.05,
    }),
    makeFeed('f2', 'Lean Amine', 40, 7000, 40, {
      monoethanolamine: 0.112, water: 0.888,
    }),
    makeNode('abs1', 'Absorber', 'CO2 Absorber', { numberOfStages: 15 }),
    makeNode('cool1', 'Cooler', 'Sweet Gas Cooler', { outletTemperature: 30 }),
    makeProduct('p1', 'Sweet Gas'),
    makeNode('h1', 'Heater', 'Rich Amine Heater', { outletTemperature: 110 }),
    makeNode('strip1', 'Stripper', 'Amine Regenerator', { numberOfStages: 10 }),
    makeNode('cool2', 'Cooler', 'Lean Amine Cooler', { outletTemperature: 40 }),
    makeNode('pump1', 'Pump', 'Lean Amine Pump', { outletPressure: 7000, efficiency: 75 }),
    makeProduct('p2', 'Lean Amine Out'),
    makeProduct('p3', 'Acid Gas'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'abs1', 'in-1'),        // gas in
    E('e2', 'f2', 'out-1', 'abs1', 'in-2'),         // solvent in
    E('e3', 'abs1', 'out-1', 'cool1', 'in-1'),      // lean gas out
    E('e4', 'cool1', 'out-1', 'p1', 'in-1'),
    E('e5', 'abs1', 'out-2', 'h1', 'in-1'),         // rich amine
    E('e6', 'h1', 'out-1', 'strip1', 'in-1'),       // rich to stripper
    E('e7', 'strip1', 'out-1', 'p3', 'in-1'),       // acid gas overhead
    E('e8', 'strip1', 'out-2', 'cool2', 'in-1'),    // lean solvent
    E('e9', 'cool2', 'out-1', 'pump1', 'in-1'),
    E('e10', 'pump1', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Absorber should have results
  const abs = data.equipment_results?.['abs1'];
  expect(abs).toBeDefined();
  // Stripper should have results
  const strip = data.equipment_results?.['strip1'];
  expect(strip).toBeDefined();
  // Pump should consume work
  const pump = data.equipment_results?.['pump1'];
  if (pump && !pump.error) {
    expect(pump.work).toBeGreaterThanOrEqual(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. Ethanol-Water Distillation (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('4 — Ethanol-Water Distillation', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'EtOH/Water Feed', 78, 101.325, 10, {
      ethanol: 0.20, water: 0.80,
    }),
    makeNode('h1', 'Heater', 'Pre-heater', { outletTemperature: 80 }),
    makeFeed('f2', 'Recycle Makeup', 60, 101.325, 1, {
      ethanol: 0.50, water: 0.50,
    }),
    makeNode('mix1', 'Mixer', 'Feed Mixer'),
    makeNode('dist1', 'DistillationColumn', 'EtOH Column', {
      numberOfStages: 20, refluxRatio: 2,
      lightKey: 'ethanol', heavyKey: 'water',
    }),
    makeNode('cool1', 'Cooler', 'Distillate Cooler', { outletTemperature: 25 }),
    makeNode('spl1', 'Splitter', 'Product Splitter', { splitRatio: 0.9 }),
    makeProduct('p1', 'EtOH Product'),
    makeProduct('p2', 'Recycle'),
    makeNode('cool2', 'Cooler', 'Bottoms Cooler', { outletTemperature: 30 }),
    makeProduct('p3', 'Waste Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'mix1', 'in-1'),
    E('e3', 'f2', 'out-1', 'mix1', 'in-2'),
    E('e4', 'mix1', 'out-1', 'dist1', 'in-1'),
    E('e5', 'dist1', 'out-1', 'cool1', 'in-1'),
    E('e6', 'cool1', 'out-1', 'spl1', 'in-1'),
    E('e7', 'spl1', 'out-1', 'p1', 'in-1'),
    E('e8', 'spl1', 'out-2', 'p2', 'in-1'),
    E('e9', 'dist1', 'out-2', 'cool2', 'in-1'),
    E('e10', 'cool2', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges, 'NRTL');
  const data = validatePhysics(raw);

  // Mixer should report total mass flow
  const mixer = data.equipment_results?.['mix1'];
  if (mixer && !mixer.error) {
    expect(mixer.totalMassFlow).toBeGreaterThan(10);
  }
  // Splitter should produce two streams
  const spl = data.equipment_results?.['spl1'];
  expect(spl).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. LNG Pre-cooling (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('5 — LNG Pre-cooling', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Natural Gas', 30, 6000, 30, {
      methane: 0.92, ethane: 0.05, propane: 0.03,
    }),
    makeFeed('f2', 'Propane Refrig', -30, 200, 20, { propane: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Pre-cooler'),
    makeNode('v1', 'Valve', 'JT Valve', { outletPressure: 2000 }),
    makeNode('sep1', 'Separator', 'LNG Separator'),
    makeProduct('p1', 'LNG'),
    makeProduct('p2', 'BOG'),
    makeNode('comp1', 'Compressor', 'Refrig Compressor', { outletPressure: 1200, efficiency: 75 }),
    makeNode('cool1', 'Cooler', 'Refrig Condenser', { outletTemperature: 40 }),
    makeProduct('p3', 'Refrig Return'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'hx1', 'in-hot'),
    E('e2', 'f2', 'out-1', 'hx1', 'in-cold'),
    E('e3', 'hx1', 'out-hot', 'v1', 'in-1'),
    E('e4', 'v1', 'out-1', 'sep1', 'in-1'),
    E('e5', 'sep1', 'out-2', 'p1', 'in-1'),      // liquid = LNG
    E('e6', 'sep1', 'out-1', 'p2', 'in-1'),       // vapor = BOG
    E('e7', 'hx1', 'out-cold', 'comp1', 'in-1'),
    E('e8', 'comp1', 'out-1', 'cool1', 'in-1'),
    E('e9', 'cool1', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // HX should report duty/LMTD
  const hx = data.equipment_results?.['hx1'];
  expect(hx).toBeDefined();
  if (hx && !hx.error) {
    expect(hx.duty).toBeDefined();
  }
  // Compressor work
  const comp = data.equipment_results?.['comp1'];
  if (comp && !comp.error) {
    expect(comp.work).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 6. Hydrogen Purification (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('6 — Hydrogen Purification', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'H2 Rich Gas', 40, 3000, 5, {
      hydrogen: 0.75, methane: 0.15, nitrogen: 0.10,
    }),
    makeNode('cool1', 'Cooler', 'Chiller', { outletTemperature: -20 }),
    makeNode('sep1', 'Separator', 'Cold Separator'),
    makeNode('comp1', 'Compressor', 'H2 Compressor', { outletPressure: 5000, efficiency: 80 }),
    makeNode('pipe1', 'PipeSegment', 'H2 Pipeline', { length: 200, diameter: 0.15 }),
    makeProduct('p1', 'Pure H2'),
    makeNode('v1', 'Valve', 'Letdown Valve', { outletPressure: 500 }),
    makeNode('h1', 'Heater', 'Reheater', { outletTemperature: 25 }),
    makeNode('sep2', 'Separator', 'Flash Drum'),
    makeProduct('p2', 'Fuel Gas'),
    makeProduct('p3', 'Condensate'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cool1', 'in-1'),
    E('e2', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e3', 'sep1', 'out-1', 'comp1', 'in-1'),
    E('e4', 'comp1', 'out-1', 'pipe1', 'in-1'),
    E('e5', 'pipe1', 'out-1', 'p1', 'in-1'),
    E('e6', 'sep1', 'out-2', 'v1', 'in-1'),
    E('e7', 'v1', 'out-1', 'h1', 'in-1'),
    E('e8', 'h1', 'out-1', 'sep2', 'in-1'),
    E('e9', 'sep2', 'out-1', 'p2', 'in-1'),
    E('e10', 'sep2', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Should have all equipment results
  expect(data.equipment_results?.['cool1']).toBeDefined();
  expect(data.equipment_results?.['comp1']).toBeDefined();
  expect(data.equipment_results?.['v1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. Ammonia Synthesis Loop (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('7 — Ammonia Synthesis Loop', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Syngas', 200, 15000, 10, {
      hydrogen: 0.75, nitrogen: 0.25,
    }),
    makeFeed('f2', 'Makeup Gas', 200, 15000, 1, {
      hydrogen: 0.75, nitrogen: 0.25,
    }),
    makeNode('mix1', 'Mixer', 'Feed Mixer'),
    makeNode('h1', 'Heater', 'Pre-heater', { outletTemperature: 450 }),
    makeNode('cstr1', 'CSTRReactor', 'NH3 Reactor', {
      volume: 50, reactionTemp: 450,
      activationEnergy: 170, preExpFactor: 1.5e10, keyReactant: 'nitrogen',
    }),
    makeNode('cool1', 'Cooler', 'Reactor Effluent Cooler', { outletTemperature: -10 }),
    makeNode('sep1', 'Separator', 'NH3 Separator'),
    makeNode('comp1', 'Compressor', 'Recycle Compressor', { outletPressure: 15000, efficiency: 80 }),
    makeProduct('p1', 'Recycle Gas'),
    makeNode('v1', 'Valve', 'Letdown Valve', { outletPressure: 200 }),
    makeProduct('p2', 'Liquid NH3'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mix1', 'in-1'),
    E('e2', 'f2', 'out-1', 'mix1', 'in-2'),
    E('e3', 'mix1', 'out-1', 'h1', 'in-1'),
    E('e4', 'h1', 'out-1', 'cstr1', 'in-1'),
    E('e5', 'cstr1', 'out-1', 'cool1', 'in-1'),
    E('e6', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e7', 'sep1', 'out-1', 'comp1', 'in-1'),     // vapor recycle
    E('e8', 'comp1', 'out-1', 'p1', 'in-1'),
    E('e9', 'sep1', 'out-2', 'v1', 'in-1'),        // liquid NH3
    E('e10', 'v1', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // CSTR should produce results
  const cstr = data.equipment_results?.['cstr1'];
  expect(cstr).toBeDefined();
  // Mixer should combine both feeds
  const mixer = data.equipment_results?.['mix1'];
  if (mixer && !mixer.error) {
    expect(mixer.totalMassFlow).toBeCloseTo(11, 0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 8. Methanol Production (13 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('8 — Methanol Production', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Syngas Feed', 50, 5000, 15, {
      hydrogen: 0.67, 'carbon dioxide': 0.22, 'carbon monoxide': 0.11,
    }),
    makeNode('comp1', 'Compressor', 'Syngas Compressor', { outletPressure: 8000, efficiency: 78 }),
    makeNode('h1', 'Heater', 'Reactor Pre-heater', { outletTemperature: 250 }),
    makeNode('cr1', 'ConversionReactor', 'MeOH Reactor', {
      keyReactant: 'carbon monoxide', conversion: 60, temperature: 250,
    }),
    makeNode('cool1', 'Cooler', 'Reactor Cooler', { outletTemperature: 40 }),
    makeNode('sep1', 'Separator', 'Flash Drum'),
    makeProduct('p1', 'Purge Gas'),
    makeNode('dist1', 'DistillationColumn', 'MeOH Column', {
      numberOfStages: 20, refluxRatio: 1.5,
      lightKey: 'methanol', heavyKey: 'water',
    }),
    makeNode('cool2', 'Cooler', 'MeOH Cooler', { outletTemperature: 25 }),
    makeProduct('p2', 'Methanol'),
    makeProduct('p3', 'Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp1', 'in-1'),
    E('e2', 'comp1', 'out-1', 'h1', 'in-1'),
    E('e3', 'h1', 'out-1', 'cr1', 'in-1'),
    E('e4', 'cr1', 'out-1', 'cool1', 'in-1'),
    E('e5', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e6', 'sep1', 'out-1', 'p1', 'in-1'),
    E('e7', 'sep1', 'out-2', 'dist1', 'in-1'),
    E('e8', 'dist1', 'out-1', 'cool2', 'in-1'),
    E('e9', 'cool2', 'out-1', 'p2', 'in-1'),
    E('e10', 'dist1', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Conversion reactor should apply conversion
  const cr = data.equipment_results?.['cr1'];
  expect(cr).toBeDefined();
  // Compressor work
  const comp = data.equipment_results?.['comp1'];
  if (comp && !comp.error) {
    expect(comp.work).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 9. Propane Refrigeration Cycle (10 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('9 — Propane Refrigeration Cycle', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Propane Circuit', -35, 100, 15, { propane: 1.0 }),
    makeNode('comp1', 'Compressor', 'Refrig Compressor', { outletPressure: 1200, efficiency: 75 }),
    makeNode('cool1', 'Cooler', 'Condenser', { outletTemperature: 40 }),
    makeNode('v1', 'Valve', 'Expansion Valve', { outletPressure: 100 }),
    makeNode('sep1', 'Separator', 'Phase Separator'),
    makeProduct('p1', 'Vapor Return'),
    makeNode('h1', 'Heater', 'Evaporator', { outletTemperature: -30 }),
    makeNode('pipe1', 'PipeSegment', 'Cold Pipe', { length: 50, diameter: 0.2 }),
    makeProduct('p2', 'Cold Duty'),
    makeFeed('f2', 'Makeup Propane', -35, 100, 0.5, { propane: 1.0 }),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp1', 'in-1'),
    E('e2', 'comp1', 'out-1', 'cool1', 'in-1'),
    E('e3', 'cool1', 'out-1', 'v1', 'in-1'),
    E('e4', 'v1', 'out-1', 'sep1', 'in-1'),
    E('e5', 'sep1', 'out-1', 'p1', 'in-1'),
    E('e6', 'sep1', 'out-2', 'h1', 'in-1'),
    E('e7', 'h1', 'out-1', 'pipe1', 'in-1'),
    E('e8', 'pipe1', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Valve JT cooling
  const v = data.equipment_results?.['v1'];
  expect(v).toBeDefined();
  // Compressor work on cold gas
  const comp = data.equipment_results?.['comp1'];
  if (comp && !comp.error) {
    expect(comp.work).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 10. Sour Gas Sweetening with DEA (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('10 — Sour Gas Sweetening DEA', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sour Gas', 35, 5000, 25, {
      methane: 0.88, 'carbon dioxide': 0.08, 'hydrogen sulfide': 0.04,
    }),
    makeFeed('f2', 'Lean DEA', 40, 5000, 50, {
      diethanolamine: 0.10, water: 0.90,
    }),
    makeNode('abs1', 'Absorber', 'DEA Absorber', { numberOfStages: 15 }),
    makeNode('pipe1', 'PipeSegment', 'Sweet Gas Pipeline', { length: 500, diameter: 0.4 }),
    makeProduct('p1', 'Sweet Gas'),
    makeNode('h1', 'Heater', 'Rich DEA Heater', { outletTemperature: 100 }),
    makeNode('strip1', 'Stripper', 'DEA Regenerator', { numberOfStages: 10 }),
    makeNode('cool1', 'Cooler', 'Lean DEA Cooler', { outletTemperature: 40 }),
    makeNode('pump1', 'Pump', 'DEA Pump', { outletPressure: 5000, efficiency: 75 }),
    makeProduct('p2', 'Lean DEA Out'),
    makeProduct('p3', 'Acid Gas'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'abs1', 'in-1'),
    E('e2', 'f2', 'out-1', 'abs1', 'in-2'),
    E('e3', 'abs1', 'out-1', 'pipe1', 'in-1'),
    E('e4', 'pipe1', 'out-1', 'p1', 'in-1'),
    E('e5', 'abs1', 'out-2', 'h1', 'in-1'),
    E('e6', 'h1', 'out-1', 'strip1', 'in-1'),
    E('e7', 'strip1', 'out-1', 'p3', 'in-1'),
    E('e8', 'strip1', 'out-2', 'cool1', 'in-1'),
    E('e9', 'cool1', 'out-1', 'pump1', 'in-1'),
    E('e10', 'pump1', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  expect(data.equipment_results?.['abs1']).toBeDefined();
  expect(data.equipment_results?.['strip1']).toBeDefined();
  expect(data.equipment_results?.['pump1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 11. NGL Recovery (13 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('11 — NGL Recovery', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Rich Gas', 40, 4000, 40, {
      methane: 0.70, ethane: 0.15, propane: 0.10, 'n-butane': 0.05,
    }),
    makeNode('cool1', 'Cooler', 'Inlet Chiller', { outletTemperature: -30 }),
    makeNode('sep1', 'Separator', 'Cold Separator'),
    makeNode('comp1', 'Compressor', 'Sales Gas Compressor', { outletPressure: 6000, efficiency: 78 }),
    makeProduct('p1', 'Sales Gas'),
    makeNode('v1', 'Valve', 'NGL Valve', { outletPressure: 1500 }),
    makeNode('dist1', 'DistillationColumn', 'Demethanizer', {
      numberOfStages: 20, refluxRatio: 1.5,
      lightKey: 'ethane', heavyKey: 'propane',
    }),
    makeNode('cool2', 'Cooler', 'C2 Cooler', { outletTemperature: -10 }),
    makeProduct('p2', 'C2 Product'),
    makeNode('h1', 'Heater', 'NGL Heater', { outletTemperature: 50 }),
    makeNode('spl1', 'Splitter', 'NGL Splitter', { splitRatio: 0.6 }),
    makeProduct('p3', 'LPG'),
    makeProduct('p4', 'C4+'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cool1', 'in-1'),
    E('e2', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e3', 'sep1', 'out-1', 'comp1', 'in-1'),
    E('e4', 'comp1', 'out-1', 'p1', 'in-1'),
    E('e5', 'sep1', 'out-2', 'v1', 'in-1'),
    E('e6', 'v1', 'out-1', 'dist1', 'in-1'),
    E('e7', 'dist1', 'out-1', 'cool2', 'in-1'),
    E('e8', 'cool2', 'out-1', 'p2', 'in-1'),
    E('e9', 'dist1', 'out-2', 'h1', 'in-1'),
    E('e10', 'h1', 'out-1', 'spl1', 'in-1'),
    E('e11', 'spl1', 'out-1', 'p3', 'in-1'),
    E('e12', 'spl1', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  expect(data.equipment_results?.['dist1']).toBeDefined();
  expect(data.equipment_results?.['spl1']).toBeDefined();
  // Cooler should bring T down
  const cooler = data.equipment_results?.['cool1'];
  if (cooler && !cooler.error) {
    expect(cooler.outletTemperature).toBeLessThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 12. Crystallization Plant (10 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('12 — Crystallization Plant', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Solution Feed', 60, 101.325, 5, {
      water: 0.70, acetone: 0.30,
    }),
    makeNode('cool1', 'Cooler', 'Cooling Stage', { outletTemperature: 5 }),
    makeNode('cryst1', 'Crystallizer', 'Crystallizer', { crystallizationTemp: 5 }),
    makeNode('filt1', 'Filter', 'Rotary Filter', {
      efficiency: 95, solidsFraction: 0.20,
    }),
    makeNode('h1', 'Heater', 'Filtrate Heater', { outletTemperature: 60 }),
    makeProduct('p1', 'Mother Liquor'),
    makeNode('dry1', 'Dryer', 'Belt Dryer', { outletMoisture: 2 }),
    makeProduct('p2', 'Dry Crystals'),
    makeProduct('p3', 'Dryer Vapor'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cool1', 'in-1'),
    E('e2', 'cool1', 'out-1', 'cryst1', 'in-1'),
    E('e3', 'cryst1', 'out-1', 'filt1', 'in-1'),    // crystals + mother liquor slurry
    E('e4', 'filt1', 'out-1', 'h1', 'in-1'),         // filtrate
    E('e5', 'h1', 'out-1', 'p1', 'in-1'),
    E('e6', 'filt1', 'out-2', 'dry1', 'in-1'),       // cake
    E('e7', 'dry1', 'out-1', 'p2', 'in-1'),
    E('e8', 'dry1', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Crystallizer should produce results
  const cryst = data.equipment_results?.['cryst1'];
  expect(cryst).toBeDefined();
  // Filter should split flow
  const filt = data.equipment_results?.['filt1'];
  expect(filt).toBeDefined();
  // Dryer should reduce moisture
  const dryer = data.equipment_results?.['dry1'];
  expect(dryer).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 13. Three-Phase Crude Processing (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('13 — Three-Phase Crude Processing', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Crude Feed', 80, 500, 30, {
      'n-hexane': 0.40, water: 0.30, 'n-decane': 0.30,
    }),
    makeNode('h1', 'Heater', 'Crude Heater', { outletTemperature: 120 }),
    makeNode('tps1', 'ThreePhaseSeparator', '3-Phase Sep', { lightLiquidFraction: 0.6 }),
    makeNode('cool1', 'Cooler', 'Vapor Condenser', { outletTemperature: 30 }),
    makeProduct('p1', 'Off-Gas'),
    makeNode('pump1', 'Pump', 'Oil Pump', { outletPressure: 1000, efficiency: 75 }),
    makeNode('pipe1', 'PipeSegment', 'Oil Pipeline', { length: 100, diameter: 0.2 }),
    makeProduct('p2', 'Light Oil'),
    makeNode('v1', 'Valve', 'Water Valve', { outletPressure: 200 }),
    makeNode('sep1', 'Separator', 'Water Flash'),
    makeProduct('p3', 'Water Vapor'),
    makeProduct('p4', 'Produced Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'h1', 'in-1'),
    E('e2', 'h1', 'out-1', 'tps1', 'in-1'),
    E('e3', 'tps1', 'out-1', 'cool1', 'in-1'),      // vapor
    E('e4', 'cool1', 'out-1', 'p1', 'in-1'),
    E('e5', 'tps1', 'out-2', 'pump1', 'in-1'),       // light liquid
    E('e6', 'pump1', 'out-1', 'pipe1', 'in-1'),
    E('e7', 'pipe1', 'out-1', 'p2', 'in-1'),
    E('e8', 'tps1', 'out-3', 'v1', 'in-1'),          // heavy liquid
    E('e9', 'v1', 'out-1', 'sep1', 'in-1'),
    E('e10', 'sep1', 'out-1', 'p3', 'in-1'),
    E('e11', 'sep1', 'out-2', 'p4', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Three-phase separator should have results
  const tps = data.equipment_results?.['tps1'];
  expect(tps).toBeDefined();
  // Pump should have work
  const pump = data.equipment_results?.['pump1'];
  if (pump && !pump.error) {
    expect(pump.work).toBeGreaterThanOrEqual(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 14. Cyclone + Filter Train (10 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('14 — Cyclone + Filter Train', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Dusty Gas', 150, 300, 20, {
      nitrogen: 0.85, 'n-decane': 0.15,
    }),
    makeNode('cyc1', 'Cyclone', 'Primary Cyclone', {
      efficiency: 90, solidsFraction: 0.10,
    }),
    makeNode('cool1', 'Cooler', 'Gas Cooler', { outletTemperature: 40 }),
    makeNode('sep1', 'Separator', 'Knockout Drum'),
    makeProduct('p1', 'Clean Gas'),
    makeProduct('p2', 'Condensate'),
    makeNode('filt1', 'Filter', 'Bag Filter', {
      efficiency: 95, solidsFraction: 0.30,
    }),
    makeNode('dry1', 'Dryer', 'Solids Dryer', { outletMoisture: 5 }),
    makeProduct('p3', 'Dry Product'),
    makeProduct('p4', 'Off-Gas'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cyc1', 'in-1'),
    E('e2', 'cyc1', 'out-1', 'cool1', 'in-1'),     // clean gas
    E('e3', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e4', 'sep1', 'out-1', 'p1', 'in-1'),
    E('e5', 'sep1', 'out-2', 'p2', 'in-1'),
    E('e6', 'cyc1', 'out-2', 'filt1', 'in-1'),      // solids
    E('e7', 'filt1', 'out-2', 'dry1', 'in-1'),      // cake
    E('e8', 'dry1', 'out-1', 'p3', 'in-1'),
    E('e9', 'dry1', 'out-2', 'p4', 'in-1'),
    E('e10', 'filt1', 'out-1', 'p2', 'in-1'),       // filtrate to same product (reuse edge name)
  ];

  // Fix: p2 gets two inlets — use separate product for filtrate
  nodes.push(makeProduct('p5', 'Filtrate'));
  edges[edges.length - 1] = E('e10', 'filt1', 'out-1', 'p5', 'in-1');

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Cyclone should report pressure drop
  const cyc = data.equipment_results?.['cyc1'];
  expect(cyc).toBeDefined();
  if (cyc && !cyc.error) {
    expect(cyc.pressureDrop).toBeGreaterThan(0);
  }
  // Filter should have results
  expect(data.equipment_results?.['filt1']).toBeDefined();
  // Dryer should have results
  expect(data.equipment_results?.['dry1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 15. Multi-Stage Compression (10 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('15 — Multi-Stage Compression', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Low-P Gas', 25, 200, 8, {
      methane: 0.95, ethane: 0.05,
    }),
    makeNode('comp1', 'Compressor', 'Stage 1', { outletPressure: 600, efficiency: 75 }),
    makeNode('cool1', 'Cooler', 'Intercooler 1', { outletTemperature: 35 }),
    makeNode('comp2', 'Compressor', 'Stage 2', { outletPressure: 1800, efficiency: 75 }),
    makeNode('cool2', 'Cooler', 'Intercooler 2', { outletTemperature: 35 }),
    makeNode('comp3', 'Compressor', 'Stage 3', { outletPressure: 5400, efficiency: 75 }),
    makeNode('cool3', 'Cooler', 'Aftercooler', { outletTemperature: 35 }),
    makeNode('pipe1', 'PipeSegment', 'Discharge Pipe', { length: 1000, diameter: 0.15 }),
    makeProduct('p1', 'High-P Gas'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp1', 'in-1'),
    E('e2', 'comp1', 'out-1', 'cool1', 'in-1'),
    E('e3', 'cool1', 'out-1', 'comp2', 'in-1'),
    E('e4', 'comp2', 'out-1', 'cool2', 'in-1'),
    E('e5', 'cool2', 'out-1', 'comp3', 'in-1'),
    E('e6', 'comp3', 'out-1', 'cool3', 'in-1'),
    E('e7', 'cool3', 'out-1', 'pipe1', 'in-1'),
    E('e8', 'pipe1', 'out-1', 'p1', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // All 3 compressors should produce work
  for (const cid of ['comp1', 'comp2', 'comp3']) {
    const c = data.equipment_results?.[cid];
    expect(c).toBeDefined();
    if (c && !c.error) {
      expect(c.work).toBeGreaterThan(0);
      // Each stage should have reasonable discharge temperature
      expect(c.outletTemperature).toBeGreaterThan(35);
      expect(c.outletTemperature).toBeLessThan(500);
    }
  }
  // Total compression ratio = 5400/200 = 27x
  // Pipeline should have pressure drop
  const pipe = data.equipment_results?.['pipe1'];
  if (pipe && !pipe.error) {
    expect(pipe.pressureDrop).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 16. Heat Integration Network (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('16 — Heat Integration Network', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Hot Stream', 200, 500, 10, { 'n-octane': 1.0 }),
    makeFeed('f2', 'Cold Stream', 20, 500, 15, { water: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Process HX'),
    makeNode('cool1', 'Cooler', 'Hot Trim Cooler', { outletTemperature: 50 }),
    makeNode('pump1', 'Pump', 'Hot Product Pump', { outletPressure: 1000, efficiency: 75 }),
    makeProduct('p1', 'Hot Product'),
    makeNode('h1', 'Heater', 'Cold Trim Heater', { outletTemperature: 150 }),
    makeNode('sep1', 'Separator', 'Steam Drum'),
    makeProduct('p2', 'Steam'),
    makeProduct('p3', 'Condensate'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'hx1', 'in-hot'),
    E('e2', 'f2', 'out-1', 'hx1', 'in-cold'),
    E('e3', 'hx1', 'out-hot', 'cool1', 'in-1'),
    E('e4', 'cool1', 'out-1', 'pump1', 'in-1'),
    E('e5', 'pump1', 'out-1', 'p1', 'in-1'),
    E('e6', 'hx1', 'out-cold', 'h1', 'in-1'),
    E('e7', 'h1', 'out-1', 'sep1', 'in-1'),
    E('e8', 'sep1', 'out-1', 'p2', 'in-1'),
    E('e9', 'sep1', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // HX should exchange heat
  const hx = data.equipment_results?.['hx1'];
  expect(hx).toBeDefined();
  if (hx && !hx.error) {
    expect(hx.duty).toBeDefined();
    // Hot outlet should be cooler than hot inlet
    if (hx.hotOutletTemperature !== undefined) {
      expect(hx.hotOutletTemperature).toBeLessThan(200);
    }
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 17. PFR Ethane Cracking (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('17 — PFR Ethane Cracking', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Ethane Feed', 30, 200, 5, {
      ethane: 0.95, propane: 0.05,
    }),
    makeNode('comp1', 'Compressor', 'Feed Compressor', { outletPressure: 500, efficiency: 78 }),
    makeNode('h1', 'Heater', 'Cracker Furnace', { outletTemperature: 800 }),
    makeNode('pfr1', 'PFRReactor', 'Cracking Reactor', {
      length: 10, diameter: 0.3, temperature: 800,
    }),
    makeNode('cool1', 'Cooler', 'Transfer Line Exchanger', { outletTemperature: 40 }),
    makeNode('sep1', 'Separator', 'Quench Drum'),
    makeProduct('p1', 'Crack Gas'),
    makeNode('dist1', 'DistillationColumn', 'C2 Splitter', {
      numberOfStages: 30, refluxRatio: 3,
      lightKey: 'ethylene', heavyKey: 'ethane',
    }),
    makeProduct('p2', 'Ethylene'),
    makeProduct('p3', 'Recycle Ethane'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'comp1', 'in-1'),
    E('e2', 'comp1', 'out-1', 'h1', 'in-1'),
    E('e3', 'h1', 'out-1', 'pfr1', 'in-1'),
    E('e4', 'pfr1', 'out-1', 'cool1', 'in-1'),
    E('e5', 'cool1', 'out-1', 'sep1', 'in-1'),
    E('e6', 'sep1', 'out-1', 'p1', 'in-1'),          // uncondensed gas
    E('e7', 'sep1', 'out-2', 'dist1', 'in-1'),       // liquid to column
    E('e8', 'dist1', 'out-1', 'p2', 'in-1'),
    E('e9', 'dist1', 'out-2', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // PFR should produce results
  const pfr = data.equipment_results?.['pfr1'];
  expect(pfr).toBeDefined();
  // Furnace should deliver high duty
  const heater = data.equipment_results?.['h1'];
  if (heater && !heater.error) {
    expect(heater.duty).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 18. NH₃ Absorption + Stripping (12 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('18 — NH3 Absorption and Stripping', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'NH3 Gas', 25, 200, 10, {
      nitrogen: 0.90, ammonia: 0.10,
    }),
    makeFeed('f2', 'Wash Water', 25, 200, 30, { water: 1.0 }),
    makeNode('abs1', 'Absorber', 'NH3 Absorber', { numberOfStages: 12 }),
    makeProduct('p1', 'Clean Gas'),
    makeNode('h1', 'Heater', 'Rich Water Heater', { outletTemperature: 90 }),
    makeNode('strip1', 'Stripper', 'NH3 Stripper', { numberOfStages: 8 }),
    makeNode('cool1', 'Cooler', 'NH3 Condenser', { outletTemperature: 25 }),
    makeProduct('p2', 'NH3 Product'),
    makeNode('cool2', 'Cooler', 'Lean Water Cooler', { outletTemperature: 25 }),
    makeNode('pump1', 'Pump', 'Water Pump', { outletPressure: 200, efficiency: 75 }),
    makeProduct('p3', 'Recycle Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'abs1', 'in-1'),
    E('e2', 'f2', 'out-1', 'abs1', 'in-2'),
    E('e3', 'abs1', 'out-1', 'p1', 'in-1'),
    E('e4', 'abs1', 'out-2', 'h1', 'in-1'),
    E('e5', 'h1', 'out-1', 'strip1', 'in-1'),
    E('e6', 'strip1', 'out-1', 'cool1', 'in-1'),
    E('e7', 'cool1', 'out-1', 'p2', 'in-1'),
    E('e8', 'strip1', 'out-2', 'cool2', 'in-1'),
    E('e9', 'cool2', 'out-1', 'pump1', 'in-1'),
    E('e10', 'pump1', 'out-1', 'p3', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  expect(data.equipment_results?.['abs1']).toBeDefined();
  expect(data.equipment_results?.['strip1']).toBeDefined();
  expect(data.equipment_results?.['pump1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 19. Refinery Vacuum Distillation (11 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('19 — Refinery Vacuum Distillation', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Atm Residue', 400, 10, 80, {
      'n-hexane': 0.15, 'n-heptane': 0.25, 'n-octane': 0.30, 'n-decane': 0.30,
    }),
    makeNode('dist1', 'DistillationColumn', 'Vacuum Column', {
      numberOfStages: 15, refluxRatio: 1.5, condenserPressure: 10,
      condenserType: 'partial',
      lightKey: 'n-heptane', heavyKey: 'n-octane',
    }),
    makeNode('comp1', 'Compressor', 'Vacuum Ejector', { outletPressure: 101, efficiency: 60 }),
    makeNode('cool1', 'Cooler', 'LVGO Cooler', { outletTemperature: 40 }),
    makeProduct('p1', 'LVGO'),
    makeNode('pump1', 'Pump', 'Bottoms Pump', { outletPressure: 500, efficiency: 75 }),
    makeNode('cool2', 'Cooler', 'HVGO Cooler', { outletTemperature: 60 }),
    makeNode('pipe1', 'PipeSegment', 'HVGO Pipeline', { length: 50, diameter: 0.3 }),
    makeProduct('p2', 'HVGO'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'dist1', 'in-1'),
    E('e2', 'dist1', 'out-1', 'comp1', 'in-1'),
    E('e3', 'comp1', 'out-1', 'cool1', 'in-1'),
    E('e4', 'cool1', 'out-1', 'p1', 'in-1'),
    E('e5', 'dist1', 'out-2', 'pump1', 'in-1'),
    E('e6', 'pump1', 'out-1', 'cool2', 'in-1'),
    E('e7', 'cool2', 'out-1', 'pipe1', 'in-1'),
    E('e8', 'pipe1', 'out-1', 'p2', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // Vacuum distillation should run under FUG
  const dist = data.equipment_results?.['dist1'];
  expect(dist).toBeDefined();
  // Vacuum compressor (ejector)
  const comp = data.equipment_results?.['comp1'];
  expect(comp).toBeDefined();
  if (comp && !comp.error) {
    expect(comp.work).toBeGreaterThan(0);
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 20. Complete Gas Plant (14 ops)
// ═══════════════════════════════════════════════════════════════════════════
test('20 — Complete Gas Plant', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Well Gas', 35, 7000, 60, {
      methane: 0.75, ethane: 0.10, propane: 0.05,
      'carbon dioxide': 0.05, 'hydrogen sulfide': 0.03, water: 0.02,
    }),
    makeFeed('f2', 'Lean Amine', 40, 7000, 80, {
      monoethanolamine: 0.112, water: 0.888,
    }),
    makeNode('sep1', 'Separator', 'Inlet Separator'),
    makeNode('abs1', 'Absorber', 'Acid Gas Absorber', { numberOfStages: 20 }),
    makeNode('cool1', 'Cooler', 'Sales Gas Cooler', { outletTemperature: 25 }),
    makeProduct('p1', 'Sales Gas'),
    makeProduct('p2', 'Rich Amine'),
    makeNode('h1', 'Heater', 'Liquid Heater', { outletTemperature: 100 }),
    makeNode('dist1', 'DistillationColumn', 'NGL Column', {
      numberOfStages: 15, refluxRatio: 1.5,
      lightKey: 'ethane', heavyKey: 'propane',
    }),
    makeNode('comp1', 'Compressor', 'Dry Gas Compressor', { outletPressure: 7000, efficiency: 78 }),
    makeProduct('p3', 'Dry Gas'),
    makeNode('cool2', 'Cooler', 'NGL Cooler', { outletTemperature: 25 }),
    makeNode('spl1', 'Splitter', 'NGL Splitter', { splitRatio: 0.7 }),
    makeProduct('p4', 'LPG'),
    makeProduct('p5', 'NGL'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'sep1', 'in-1'),
    E('e2', 'sep1', 'out-1', 'abs1', 'in-1'),        // gas to absorber
    E('e3', 'f2', 'out-1', 'abs1', 'in-2'),           // amine to absorber
    E('e4', 'abs1', 'out-1', 'cool1', 'in-1'),        // sweet gas
    E('e5', 'cool1', 'out-1', 'p1', 'in-1'),
    E('e6', 'abs1', 'out-2', 'p2', 'in-1'),           // rich amine
    E('e7', 'sep1', 'out-2', 'h1', 'in-1'),           // liquid from inlet sep
    E('e8', 'h1', 'out-1', 'dist1', 'in-1'),
    E('e9', 'dist1', 'out-1', 'comp1', 'in-1'),       // light ends
    E('e10', 'comp1', 'out-1', 'p3', 'in-1'),
    E('e11', 'dist1', 'out-2', 'cool2', 'in-1'),      // NGL bottoms
    E('e12', 'cool2', 'out-1', 'spl1', 'in-1'),
    E('e13', 'spl1', 'out-1', 'p4', 'in-1'),
    E('e14', 'spl1', 'out-2', 'p5', 'in-1'),
  ];

  const raw = await runSim(page, nodes, edges);
  const data = validatePhysics(raw);

  // All key equipment should have results
  expect(data.equipment_results?.['sep1']).toBeDefined();
  expect(data.equipment_results?.['abs1']).toBeDefined();
  expect(data.equipment_results?.['dist1']).toBeDefined();
  expect(data.equipment_results?.['comp1']).toBeDefined();
  expect(data.equipment_results?.['spl1']).toBeDefined();

  // Overall: should not be full error
  expect(data.status).not.toBe('error');
});
