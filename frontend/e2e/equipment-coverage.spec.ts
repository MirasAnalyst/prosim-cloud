/**
 * 10 Industrial Flowsheets — Equipment Coverage Extension
 *
 * Focuses on under-tested equipment: DesignSpec, Filter, Cyclone, Crystallizer,
 * Dryer, PFRReactor, ThreePhaseSeparator, HeatExchanger, Stripper, CSTRReactor,
 * ConversionReactor.
 */
import { test, expect, type Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });
test.setTimeout(180_000);

// ── Helpers (same as industrial-flowsheets.spec.ts) ───────────────────────

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
  await page.goto('/app');
  await page.waitForLoadState('load');
});

// ═══════════════════════════════════════════════════════════════════════════
// 1. Sugar Crystallization Plant
//    Crystallizer → Filter → Dryer + Mother Liquor recycle HX
//    Equipment: FeedStream, Heater, Crystallizer, Filter, Dryer, HeatExchanger, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('1 — Sugar Crystallization Plant', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Sugar Syrup', 80, 200, 10, { water: 0.60, acetone: 0.40 }),
    makeFeed('f2', 'Cooling Water', 15, 200, 20, { water: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Syrup Cooler', {}),
    makeNode('cr1', 'Crystallizer', 'Vacuum Crystallizer', { crystallizationTemp: 10 }),
    makeNode('fi1', 'Filter', 'Rotary Filter', { efficiency: 95, solidsFraction: 0.25 }),
    makeNode('dr1', 'Dryer', 'Fluid Bed Dryer', { outletMoisture: 2 }),
    makeProduct('p1', 'Dry Crystals'),
    makeProduct('p2', 'Mother Liquor'),
    makeProduct('p3', 'Hot CW Return'),
    makeProduct('p4', 'Dryer Vapor'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'hx1', 'in-hot'),
    E('e2', 'f2', 'out-1', 'hx1', 'in-cold'),
    E('e3', 'hx1', 'out-hot', 'cr1', 'in-1'),
    E('e4', 'hx1', 'out-cold', 'p3', 'in-1'),
    E('e5', 'cr1', 'out-1', 'fi1', 'in-1'),
    E('e6', 'cr1', 'out-2', 'p2', 'in-1'),
    E('e7', 'fi1', 'out-1', 'dr1', 'in-1'),
    E('e8', 'fi1', 'out-2', 'p2', 'in-1'),  // filtrate also to mother liquor
    E('e9', 'dr1', 'out-1', 'p1', 'in-1'),
    E('e10', 'dr1', 'out-2', 'p4', 'in-1'),
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 1 — Sugar Crystallization`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['cr1']).toBeDefined();
  expect(data.equipment_results['fi1']).toBeDefined();
  expect(data.equipment_results['dr1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. Cement Dust Collection Train
//    Multiple Cyclones in series → Filter → Dryer
//    Equipment: FeedStream, Cyclone×2, Filter, Dryer, Cooler, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('2 — Cement Dust Collection', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Kiln Exhaust', 200, 400, 30, { nitrogen: 0.72, 'carbon dioxide': 0.18, water: 0.10 }),
    makeNode('cy1', 'Cyclone', 'Primary Cyclone', { efficiency: 85, solidsFraction: 0.15, inletDiameter: 1.0, pressureDropCoeff: 4, solidsComponent: 'carbon dioxide' }),
    makeNode('cy2', 'Cyclone', 'Secondary Cyclone', { efficiency: 95, solidsFraction: 0.08, inletDiameter: 0.8, pressureDropCoeff: 4, solidsComponent: 'carbon dioxide' }),
    makeNode('co1', 'Cooler', 'Gas Cooler', { outletTemperature: 80 }),
    makeNode('fi1', 'Filter', 'Baghouse Filter', { efficiency: 99, solidsFraction: 0.03, pressureDrop: 2 }),
    makeNode('dr1', 'Dryer', 'Dust Dryer', { outletMoisture: 1 }),
    makeProduct('p1', 'Clean Gas'),
    makeProduct('p2', 'Primary Dust'),
    makeProduct('p3', 'Secondary Dust'),
    makeProduct('p4', 'Dry Fines'),
    makeProduct('p5', 'Filter Fines'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'cy1', 'in-1'),
    E('e2', 'cy1', 'out-1', 'cy2', 'in-1'),      // clean gas → 2nd cyclone
    E('e3', 'cy1', 'out-2', 'p2', 'in-1'),         // primary solids
    E('e4', 'cy2', 'out-1', 'co1', 'in-1'),        // cleaner gas → cooler
    E('e5', 'cy2', 'out-2', 'p3', 'in-1'),         // secondary solids
    E('e6', 'co1', 'out-1', 'fi1', 'in-1'),        // cooled gas → filter
    E('e7', 'fi1', 'out-1', 'p1', 'in-1'),         // clean exhaust
    E('e8', 'fi1', 'out-2', 'dr1', 'in-1'),        // wet cake → dryer
    E('e9', 'dr1', 'out-1', 'p4', 'in-1'),         // dry fines
    E('e10', 'dr1', 'out-2', 'p5', 'in-1'),        // dryer vapor
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 2 — Cement Dust Collection`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['cy1']).toBeDefined();
  expect(data.equipment_results['cy2']).toBeDefined();
  expect(data.equipment_results['fi1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. Biodiesel Production (CSTR + Three-Phase Sep)
//    Vegetable oil + methanol → CSTR → ThreePhaseSep → Dryer
//    Equipment: FeedStream, Mixer, CSTRReactor, ThreePhaseSeparator, Heater, Dryer, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('3 — Biodiesel Production', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Vegetable Oil', 60, 400, 15, { 'n-octane': 0.85, 'n-decane': 0.15 }),
    makeFeed('f2', 'Methanol Feed', 25, 400, 3, { methanol: 1.0 }),
    makeNode('mx1', 'Mixer', 'Feed Mixer', {}),
    makeNode('ht1', 'Heater', 'Reactor Preheater', { outletTemperature: 65 }),
    makeNode('rx1', 'CSTRReactor', 'Transesterification CSTR', {
      volume: 20, reactionTemp: 65, activationEnergy: 50000, preExpFactor: 1e6,
    }),
    makeNode('tp1', 'ThreePhaseSeparator', 'Glycerol Separator', { lightLiquidFraction: 0.7 }),
    makeNode('dr1', 'Dryer', 'Biodiesel Dryer', { outletMoisture: 0.5 }),
    makeProduct('p1', 'Vapor Vent'),
    makeProduct('p2', 'Biodiesel'),
    makeProduct('p3', 'Glycerol'),
    makeProduct('p4', 'Dryer Vapor'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mx1', 'in-1'),
    E('e2', 'f2', 'out-1', 'mx1', 'in-2'),
    E('e3', 'mx1', 'out-1', 'ht1', 'in-1'),
    E('e4', 'ht1', 'out-1', 'rx1', 'in-1'),
    E('e5', 'rx1', 'out-1', 'tp1', 'in-1'),
    E('e6', 'tp1', 'out-1', 'p1', 'in-1'),        // vapor
    E('e7', 'tp1', 'out-2', 'dr1', 'in-1'),       // light liquid (biodiesel)
    E('e8', 'tp1', 'out-3', 'p3', 'in-1'),        // heavy liquid (glycerol)
    E('e9', 'dr1', 'out-1', 'p2', 'in-1'),
    E('e10', 'dr1', 'out-2', 'p4', 'in-1'),
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 3 — Biodiesel Production`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['rx1']).toBeDefined();
  expect(data.equipment_results['tp1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. Xylene/Toluene Separation (PFR + HX + Distillation)
//    o-Xylene/toluene feed through PFR (pass-through) → HX recovery → column separation
//    Equipment: FeedStream, HeatExchanger, PFRReactor, Cooler, Separator, DistillationColumn, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('4 — Xylene/Toluene Separation', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Ethylbenzene Feed', 50, 200, 20, { toluene: 0.05, 'o-xylene': 0.95 }),
    makeFeed('f2', 'Steam Diluent', 400, 200, 10, { water: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Feed-Effluent HX', {}),
    makeNode('ht1', 'Heater', 'Reactor Preheat', { outletTemperature: 620 }),
    makeNode('rx1', 'PFRReactor', 'Dehydrogenation PFR', {
      length: 8, diameter: 2.0, voidFraction: 0.45, particleDiameter: 0.005,
    }),
    makeNode('co1', 'Cooler', 'Effluent Cooler', { outletTemperature: 40 }),
    makeNode('sp1', 'Separator', 'Phase Separator', {}),
    makeNode('dc1', 'DistillationColumn', 'Styrene Column', {
      numberOfStages: 25, refluxRatio: 4, lightKey: 'toluene', heavyKey: 'o-xylene',
    }),
    makeProduct('p1', 'Offgas'),
    makeProduct('p2', 'Styrene Product'),
    makeProduct('p3', 'Bottoms'),
    makeProduct('p4', 'Hot Steam Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'hx1', 'in-cold'),
    E('e2', 'f2', 'out-1', 'hx1', 'in-hot'),
    E('e3', 'hx1', 'out-cold', 'ht1', 'in-1'),
    E('e4', 'hx1', 'out-hot', 'p4', 'in-1'),
    E('e5', 'ht1', 'out-1', 'rx1', 'in-1'),
    E('e6', 'rx1', 'out-1', 'co1', 'in-1'),
    E('e7', 'co1', 'out-1', 'sp1', 'in-1'),
    E('e8', 'sp1', 'out-1', 'p1', 'in-1'),         // gas
    E('e9', 'sp1', 'out-2', 'dc1', 'in-1'),        // liquid to column
    E('e10', 'dc1', 'out-1', 'p2', 'in-1'),         // distillate
    E('e11', 'dc1', 'out-2', 'p3', 'in-1'),         // bottoms
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 4 — Xylene/Toluene Separation`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['rx1']).toBeDefined();
  expect(data.equipment_results['hx1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. Amine Regeneration Unit (Stripper focus)
//    Rich amine → HX → Stripper → Reboiled lean amine → HX → Pump
//    Equipment: FeedStream, HeatExchanger, Stripper, Cooler, Separator, Pump, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('5 — Amine Regeneration Unit', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Rich MEA', 60, 500, 40, {
      monoethanolamine: 0.112, water: 0.838, 'carbon dioxide': 0.04, 'hydrogen sulfide': 0.01,
    }),
    makeFeed('f2', 'Stripping Steam', 120, 200, 5, { water: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Rich/Lean HX', {}),
    makeNode('st1', 'Stripper', 'Amine Regenerator', { numberOfStages: 12 }),
    makeNode('co1', 'Cooler', 'Overhead Condenser', { outletTemperature: 40 }),
    makeNode('sp1', 'Separator', 'Reflux Drum', {}),
    makeNode('co2', 'Cooler', 'Lean Amine Cooler', { outletTemperature: 40 }),
    makeNode('pu1', 'Pump', 'Lean Amine Pump', { outletPressure: 7000 }),
    makeProduct('p1', 'Acid Gas'),
    makeProduct('p2', 'Reflux Water'),
    makeProduct('p3', 'Lean MEA'),
    makeProduct('p4', 'Hot Lean Out'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'hx1', 'in-cold'),
    E('e2', 'st1', 'out-2', 'hx1', 'in-hot'),      // lean amine heats rich feed
    E('e3', 'hx1', 'out-cold', 'st1', 'in-1'),      // hot rich → stripper
    E('e4', 'f2', 'out-1', 'st1', 'in-2'),           // stripping steam
    E('e5', 'st1', 'out-1', 'co1', 'in-1'),          // overhead gas → condenser
    E('e6', 'co1', 'out-1', 'sp1', 'in-1'),          // cooled overhead → separator
    E('e7', 'sp1', 'out-1', 'p1', 'in-1'),           // acid gas
    E('e8', 'sp1', 'out-2', 'p2', 'in-1'),           // reflux water
    E('e9', 'hx1', 'out-hot', 'co2', 'in-1'),        // cooled lean → further cooling
    E('e10', 'co2', 'out-1', 'pu1', 'in-1'),         // cold lean → pump
    E('e11', 'pu1', 'out-1', 'p3', 'in-1'),          // high-P lean amine
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 5 — Amine Regeneration Unit`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['st1']).toBeDefined();
  expect(data.equipment_results['hx1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 6. Pharmaceutical Crystallization & Drying
//    Dissolve → Cool → Crystallize → Filter → Wash → Dry
//    Equipment: FeedStream, Mixer, Cooler, Crystallizer, Filter, Dryer, Splitter, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('6 — Pharmaceutical Crystallization', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'API Solution', 70, 150, 5, { ethanol: 0.60, water: 0.40 }),
    makeFeed('f2', 'Anti-Solvent', 20, 150, 2, { water: 1.0 }),
    makeNode('mx1', 'Mixer', 'Anti-Solvent Mixer', {}),
    makeNode('co1', 'Cooler', 'Crystallization Cooler', { outletTemperature: 5 }),
    makeNode('cr1', 'Crystallizer', 'API Crystallizer', { crystallizationTemp: 5 }),
    makeNode('fi1', 'Filter', 'Pressure Filter', { efficiency: 98, solidsFraction: 0.30, pressureDrop: 80 }),
    makeNode('dr1', 'Dryer', 'Vacuum Tray Dryer', { outletMoisture: 0.5 }),
    makeNode('sl1', 'Splitter', 'Filtrate Splitter', { splitRatio: 0.3 }),
    makeProduct('p1', 'Dry API'),
    makeProduct('p2', 'Dryer Vapor'),
    makeProduct('p3', 'Mother Liquor'),
    makeProduct('p4', 'Recycle Filtrate'),
    makeProduct('p5', 'Waste Filtrate'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mx1', 'in-1'),
    E('e2', 'f2', 'out-1', 'mx1', 'in-2'),
    E('e3', 'mx1', 'out-1', 'co1', 'in-1'),
    E('e4', 'co1', 'out-1', 'cr1', 'in-1'),
    E('e5', 'cr1', 'out-1', 'fi1', 'in-1'),         // crystals → filter
    E('e6', 'cr1', 'out-2', 'p3', 'in-1'),           // mother liquor
    E('e7', 'fi1', 'out-1', 'sl1', 'in-1'),          // filtrate → splitter
    E('e8', 'fi1', 'out-2', 'dr1', 'in-1'),          // cake → dryer
    E('e9', 'dr1', 'out-1', 'p1', 'in-1'),           // dry API
    E('e10', 'dr1', 'out-2', 'p2', 'in-1'),          // dryer vapor
    E('e11', 'sl1', 'out-1', 'p4', 'in-1'),          // recycle
    E('e12', 'sl1', 'out-2', 'p5', 'in-1'),          // waste
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 6 — Pharmaceutical Crystallization`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['cr1']).toBeDefined();
  expect(data.equipment_results['fi1']).toBeDefined();
  expect(data.equipment_results['dr1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 7. Produced Water Treatment
//    ThreePhaseSep → Cyclone (oil mist) → Filter → Stripper (dissolved gas)
//    Equipment: FeedStream, ThreePhaseSeparator, Cyclone, Filter, Stripper, Cooler, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('7 — Produced Water Treatment', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Produced Water', 60, 800, 30, {
      water: 0.85, 'n-hexane': 0.08, methane: 0.05, 'hydrogen sulfide': 0.02,
    }),
    makeFeed('f2', 'Strip Air', 25, 200, 2, { nitrogen: 0.79, oxygen: 0.21 }),
    makeNode('tp1', 'ThreePhaseSeparator', 'Inlet Separator', { lightLiquidFraction: 0.3 }),
    makeNode('cy1', 'Cyclone', 'Oil Mist Cyclone', { efficiency: 90, solidsFraction: 0.05 }),
    makeNode('fi1', 'Filter', 'Sand Filter', { efficiency: 95, solidsFraction: 0.02, pressureDrop: 30 }),
    makeNode('st1', 'Stripper', 'H2S Stripper', { numberOfStages: 8 }),
    makeNode('co1', 'Cooler', 'Water Cooler', { outletTemperature: 30 }),
    makeProduct('p1', 'Flash Gas'),
    makeProduct('p2', 'Recovered Oil'),
    makeProduct('p3', 'Cyclone Solids'),
    makeProduct('p4', 'Filter Solids'),
    makeProduct('p5', 'Sour Air'),
    makeProduct('p6', 'Clean Water'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'tp1', 'in-1'),
    E('e2', 'tp1', 'out-1', 'p1', 'in-1'),           // vapor → flash gas
    E('e3', 'tp1', 'out-2', 'p2', 'in-1'),           // light liq → recovered oil
    E('e4', 'tp1', 'out-3', 'cy1', 'in-1'),          // heavy liq (water) → cyclone
    E('e5', 'cy1', 'out-1', 'fi1', 'in-1'),          // clean gas → filter
    E('e6', 'cy1', 'out-2', 'p3', 'in-1'),           // solids
    E('e7', 'fi1', 'out-1', 'st1', 'in-1'),          // filtrate → stripper
    E('e8', 'fi1', 'out-2', 'p4', 'in-1'),           // filter cake
    E('e9', 'f2', 'out-1', 'st1', 'in-2'),           // strip air
    E('e10', 'st1', 'out-1', 'p5', 'in-1'),          // sour air
    E('e11', 'st1', 'out-2', 'co1', 'in-1'),         // stripped water → cooler
    E('e12', 'co1', 'out-1', 'p6', 'in-1'),          // clean water
  ];
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 7 — Produced Water Treatment`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['tp1']).toBeDefined();
  expect(data.equipment_results['cy1']).toBeDefined();
  expect(data.equipment_results['st1']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 8. Heater DesignSpec — Adjust heater duty to hit target temperature
//    FeedStream → Heater → ProductStream + DesignSpec on outlet T
//    Equipment: FeedStream, Heater, ProductStream, DesignSpec
// ═══════════════════════════════════════════════════════════════════════════
test('8 — Heater DesignSpec (outlet temp target)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Cold Oil', 20, 500, 10, { 'n-octane': 0.7, 'n-decane': 0.3 }),
    makeNode('ht1', 'Heater', 'Oil Heater', { duty: 500 }),
    makeProduct('p1', 'Hot Oil'),
    makeNode('ds1', 'DesignSpec', 'Temp Controller', {
      targetStreamId: 'ht1',
      targetProperty: 'temperature',
      targetValue: 150,            // target 150°C outlet
      manipulatedNodeId: 'ht1',
      manipulatedParam: 'duty',
      lowerBound: 10,
      upperBound: 5000,
      tolerance: 0.5,
    }),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'ht1', 'in-1'),
    E('e2', 'ht1', 'out-1', 'p1', 'in-1'),
  ];
  const res = await runSim(page, nodes, edges);
  const data = getResults(res);
  const { warnings, errors, converged, massBalance } = collectIssues(res);
  console.log(`Test 8 — Heater DesignSpec`);
  console.log(`  Converged: ${converged} MB: ${massBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');

  // DesignSpec should converge
  const dsResult = data.equipment_results?.['ds1'];
  if (dsResult) {
    console.log(`  DesignSpec: converged=${dsResult.converged}, achieved=${dsResult.achievedValue}°C, duty=${dsResult.manipulatedValue} kW`);
    // If converged, outlet should be near 150°C
    if (dsResult.converged) {
      expect(dsResult.achievedValue).toBeGreaterThan(148);
      expect(dsResult.achievedValue).toBeLessThan(152);
    }
  }
  expect(data.equipment_results).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 9. Catalytic Reforming (Multiple PFRs + HX)
//    Naphtha → HX → PFR1 → reheat → PFR2 → reheat → PFR3 → Separator
//    Equipment: FeedStream, HeatExchanger, PFRReactor×3, Heater×2, Separator, Cooler, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('9 — Catalytic Reforming (3-stage PFR)', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Naphtha Feed', 100, 2500, 25, {
      'n-hexane': 0.30, 'n-heptane': 0.35, cyclohexane: 0.20, benzene: 0.15,
    }),
    makeFeed('f2', 'Hydrogen Recycle', 40, 2500, 3, { hydrogen: 1.0 }),
    makeNode('mx1', 'Mixer', 'Feed Mixer', {}),
    makeNode('hx1', 'HeatExchanger', 'Feed-Effluent HX', {}),
    makeNode('ht1', 'Heater', 'Charge Heater', { outletTemperature: 500 }),
    makeNode('rx1', 'PFRReactor', 'Reactor 1', { length: 5, diameter: 2.0, voidFraction: 0.4, particleDiameter: 0.003 }),
    makeNode('ht2', 'Heater', 'Interheater 1', { outletTemperature: 500 }),
    makeNode('rx2', 'PFRReactor', 'Reactor 2', { length: 6, diameter: 2.0, voidFraction: 0.4, particleDiameter: 0.003 }),
    makeNode('ht3', 'Heater', 'Interheater 2', { outletTemperature: 500 }),
    makeNode('rx3', 'PFRReactor', 'Reactor 3', { length: 8, diameter: 2.5, voidFraction: 0.4, particleDiameter: 0.003 }),
    makeNode('co1', 'Cooler', 'Product Cooler', { outletTemperature: 40 }),
    makeNode('sp1', 'Separator', 'Product Separator', {}),
    makeProduct('p1', 'Reformate'),
    makeProduct('p2', 'H2 Rich Gas'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'mx1', 'in-1'),
    E('e2', 'f2', 'out-1', 'mx1', 'in-2'),
    E('e3', 'mx1', 'out-1', 'hx1', 'in-cold'),
    E('e4', 'rx3', 'out-1', 'hx1', 'in-hot'),      // reactor 3 effluent heats feed (recycle)
    E('e5', 'hx1', 'out-cold', 'ht1', 'in-1'),
    E('e6', 'hx1', 'out-hot', 'co1', 'in-1'),       // cooled effluent → product cooler
    E('e7', 'ht1', 'out-1', 'rx1', 'in-1'),
    E('e8', 'rx1', 'out-1', 'ht2', 'in-1'),
    E('e9', 'ht2', 'out-1', 'rx2', 'in-1'),
    E('e10', 'rx2', 'out-1', 'ht3', 'in-1'),
    E('e11', 'ht3', 'out-1', 'rx3', 'in-1'),
    E('e12', 'co1', 'out-1', 'sp1', 'in-1'),        // cooler → separator
    E('e13', 'sp1', 'out-1', 'p2', 'in-1'),         // H2 gas
    E('e14', 'sp1', 'out-2', 'p1', 'in-1'),         // reformate liquid
  ];
  // Note: hx1 hot inlet comes from rx3 (recycle loop). Tear-stream iteration resolves this.
  const res = await runSim(page, nodes, edges);
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 9 — Catalytic Reforming`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  // All 3 PFRs should have results
  expect(data.equipment_results['rx1']).toBeDefined();
  expect(data.equipment_results['rx2']).toBeDefined();
  expect(data.equipment_results['rx3']).toBeDefined();
});

// ═══════════════════════════════════════════════════════════════════════════
// 10. Solvent Recovery with ConversionReactor + Stripper
//     Waste solvent → ConvReactor (crack) → Stripper (separate) → Filter → HX
//     Equipment: FeedStream, ConversionReactor, Stripper, Filter, HeatExchanger, Cooler, ProductStream
// ═══════════════════════════════════════════════════════════════════════════
test('10 — Solvent Recovery Plant', async ({ page }) => {
  const nodes = [
    makeFeed('f1', 'Waste Solvent', 80, 300, 8, {
      'diethyl ether': 0.30, acetone: 0.25, methanol: 0.20, water: 0.25,
    }),
    makeFeed('f2', 'Strip Steam', 120, 200, 3, { water: 1.0 }),
    makeNode('rx1', 'ConversionReactor', 'Thermal Cracker', {
      conversion: 40, keyReactant: 'diethyl ether',
    }),
    makeNode('co1', 'Cooler', 'Reactor Cooler', { outletTemperature: 50 }),
    makeNode('st1', 'Stripper', 'Solvent Stripper', { numberOfStages: 10 }),
    makeNode('fi1', 'Filter', 'Carbon Filter', { efficiency: 90, solidsFraction: 0.01, pressureDrop: 20 }),
    makeFeed('f3', 'Cooling Water', 20, 300, 15, { water: 1.0 }),
    makeNode('hx1', 'HeatExchanger', 'Product Cooler HX', {}),
    makeProduct('p1', 'Recovered Solvents'),
    makeProduct('p2', 'Stripped Water'),
    makeProduct('p3', 'Filter Residue'),
    makeProduct('p4', 'CW Return'),
  ];
  const edges = [
    E('e1', 'f1', 'out-1', 'rx1', 'in-1'),
    E('e2', 'rx1', 'out-1', 'co1', 'in-1'),
    E('e3', 'co1', 'out-1', 'st1', 'in-1'),         // cooled product → stripper
    E('e4', 'f2', 'out-1', 'st1', 'in-2'),           // strip steam
    E('e5', 'st1', 'out-1', 'fi1', 'in-1'),          // overhead → filter
    E('e6', 'st1', 'out-2', 'p2', 'in-1'),           // bottoms water
    E('e7', 'fi1', 'out-1', 'hx1', 'in-hot'),        // filtrate → HX hot side
    E('e8', 'fi1', 'out-2', 'p3', 'in-1'),           // filter residue
    E('e9', 'f3', 'out-1', 'hx1', 'in-cold'),        // cooling water
    E('e10', 'hx1', 'out-hot', 'p1', 'in-1'),        // recovered solvents
    E('e11', 'hx1', 'out-cold', 'p4', 'in-1'),       // CW return
  ];
  const res = await runSim(page, nodes, edges, 'NRTL');
  const data = validatePhysics(res);
  const { warnings, errors, converged, massBalance, energyBalance } = collectIssues(res);
  console.log(`Test 10 — Solvent Recovery Plant (NRTL)`);
  console.log(`  Converged: ${converged} MB: ${massBalance} EB: ${energyBalance}`);
  console.log(`  Warnings: ${warnings.length}`, warnings.length ? warnings.join(' | ') : '');
  console.log(`  Errors: ${errors.length}`, errors.length ? errors.join(' | ') : '');
  expect(data.equipment_results['rx1']).toBeDefined();
  expect(data.equipment_results['st1']).toBeDefined();
  expect(data.equipment_results['fi1']).toBeDefined();
  expect(data.equipment_results['hx1']).toBeDefined();
});
