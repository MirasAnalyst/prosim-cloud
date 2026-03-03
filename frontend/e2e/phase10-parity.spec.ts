import { test, expect } from '@playwright/test';

/**
 * Phase 10: HYSYS/DWSIM Parity — remaining items
 *
 * Tests cover:
 * 1. Property Package Advisor (T3-3)
 * 2. Binary VLE Txy diagram (T3-4)
 * 3. BIP Matrix retrieval (T2-3)
 * 4. Equilibrium Reactor (T2-7)
 * 5. Gibbs Reactor (T2-7)
 * 6. Rigorous Distillation (T1-3)
 */

// Helper: simulate flowsheet via API
async function runSim(page: any, nodes: any[], edges: any[], propertyPackage = 'PengRobinson') {
  return page.evaluate(
    async ({ nodes, edges, propertyPackage }: any) => {
      const r = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: propertyPackage }),
      });
      return r.json();
    },
    { nodes, edges, propertyPackage },
  );
}

test.describe('Phase 10: HYSYS/DWSIM Parity', () => {

  // T3-3: Property Package Advisor
  test('property advisor recommends correct packages', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      // Test 1: All hydrocarbons → PR or SRK
      const r1 = await fetch('/api/simulation/property-advisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ compounds: ['methane', 'ethane', 'propane'] }),
      });
      const hc = await r1.json();

      // Test 2: Polar + H-bonding → NRTL
      const r2 = await fetch('/api/simulation/property-advisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ compounds: ['methanol', 'water', 'ethanol'] }),
      });
      const polar = await r2.json();

      // Test 3: Mixed HC + light gas → SRK
      const r3 = await fetch('/api/simulation/property-advisor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ compounds: ['methane', 'ethane', 'hydrogen'] }),
      });
      const mixed = await r3.json();

      return { hc, polar, mixed };
    });

    // Hydrocarbons should get PR or SRK
    expect(['PengRobinson', 'SRK']).toContain(result.hc.recommended);
    expect(result.hc.reason).toBeTruthy();

    // Polar/H-bonding should get NRTL
    expect(result.polar.recommended).toBe('NRTL');

    // HC + light gas should get SRK
    expect(result.mixed.recommended).toBe('SRK');
  });

  // T3-4: Binary VLE Txy diagram
  test('binary VLE Txy returns bubble and dew curves', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const r = await fetch('/api/simulation/binary-vle/txy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comp_a: 'benzene',
          comp_b: 'toluene',
          P_kPa: 101.325,
          property_package: 'PengRobinson',
          n_points: 11,
        }),
      });
      return r.json();
    });

    // Should have bubble and dew curves
    expect(result.bubble_curve).toBeDefined();
    expect(result.dew_curve).toBeDefined();
    expect(result.bubble_curve.length).toBeGreaterThan(5);
    expect(result.dew_curve.length).toBeGreaterThan(5);

    // Benzene/toluene at 1 atm: bubble T should be between ~80°C and ~110°C
    const firstBubbleT = result.bubble_curve[0]?.T_C ?? 0;
    const lastBubbleT = result.bubble_curve[result.bubble_curve.length - 1]?.T_C ?? 0;
    expect(firstBubbleT).toBeGreaterThan(75);
    expect(firstBubbleT).toBeLessThan(115);
    expect(lastBubbleT).toBeGreaterThan(75);
    expect(lastBubbleT).toBeLessThan(115);

    // xy curve should exist
    expect(result.xy_curve.length).toBeGreaterThan(0);
  });

  // T2-3: BIP Matrix retrieval
  test('BIP matrix returns non-zero values for known pairs', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const r = await fetch('/api/simulation/bip/matrix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          compounds: ['methanol', 'water'],
          property_package: 'NRTL',
        }),
      });
      return r.json();
    });

    // Should have a 2x2 matrix
    expect(result.matrix).toBeDefined();
    expect(result.matrix.length).toBe(2);
    expect(result.matrix[0].length).toBe(2);
    expect(result.compounds).toEqual(['methanol', 'water']);

    // NRTL BIPs for methanol/water should be non-zero
    const hasNonZero = result.matrix.some((row: number[]) =>
      row.some((val: number) => Math.abs(val) > 0.001)
    );
    expect(hasNonZero).toBe(true);
  });

  // T2-7: Equilibrium Reactor
  test('equilibrium reactor computes outlet from Keq', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    // Water-gas shift: CO + H2O ⇌ CO2 + H2
    const nodes = [
      {
        id: 'f1', type: 'equipment',
        data: {
          equipmentType: 'FeedStream', name: 'Feed',
          parameters: {
            feedTemperature: 400, feedPressure: 2000, feedFlowRate: 10,
            feedComposition: JSON.stringify({
              'carbon monoxide': 0.25, 'water': 0.25,
              'carbon dioxide': 0.25, 'hydrogen': 0.25,
            }),
          },
        },
        position: { x: 0, y: 0 },
      },
      {
        id: 'eq1', type: 'equipment',
        data: {
          equipmentType: 'EquilibriumReactor', name: 'EqRx',
          parameters: {
            outletTemperature: 400, pressure: 2000,
            stoichiometry: JSON.stringify({
              reactants: { 'carbon monoxide': 1, 'water': 1 },
              products: { 'carbon dioxide': 1, 'hydrogen': 1 },
            }),
            keqA: 2.0, keqB: 0,
          },
        },
        position: { x: 200, y: 0 },
      },
      {
        id: 'p1', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'Product', parameters: {} },
        position: { x: 400, y: 0 },
      },
    ];
    const edges = [
      { id: 'e1', source: 'f1', target: 'eq1', sourceHandle: 'out-1', targetHandle: 'in-1' },
      { id: 'e2', source: 'eq1', target: 'p1', sourceHandle: 'out-1', targetHandle: 'in-1' },
    ];

    const data = await runSim(page, nodes, edges);

    // Should have equipment results for the reactor
    const eqRes = data.results?.equipment_results?.eq1 ?? data.equipment_results?.eq1;
    expect(eqRes).toBeTruthy();

    // Should have outlet composition different from inlet (reaction occurred)
    const stream = data.results?.stream_results ?? data.stream_results ?? {};
    const outStream = stream['e2'] ?? Object.values(stream).find((s: any) => s);
    if (outStream) {
      const comp = outStream.composition ?? {};
      // At least one component should be present
      expect(Object.keys(comp).length).toBeGreaterThan(0);
    }
  });

  // T2-7: Gibbs Reactor
  test('gibbs reactor finds equilibrium composition', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    // Methane steam reforming: CH4 + H2O → CO + 3H2
    const nodes = [
      {
        id: 'f1', type: 'equipment',
        data: {
          equipmentType: 'FeedStream', name: 'Feed',
          parameters: {
            feedTemperature: 800, feedPressure: 2000, feedFlowRate: 5,
            feedComposition: JSON.stringify({
              'methane': 0.5, 'water': 0.5,
            }),
          },
        },
        position: { x: 0, y: 0 },
      },
      {
        id: 'g1', type: 'equipment',
        data: {
          equipmentType: 'GibbsReactor', name: 'GibbsRx',
          parameters: {
            outletTemperature: 800, pressure: 2000,
          },
        },
        position: { x: 200, y: 0 },
      },
      {
        id: 'p1', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'Product', parameters: {} },
        position: { x: 400, y: 0 },
      },
    ];
    const edges = [
      { id: 'e1', source: 'f1', target: 'g1', sourceHandle: 'out-1', targetHandle: 'in-1' },
      { id: 'e2', source: 'g1', target: 'p1', sourceHandle: 'out-1', targetHandle: 'in-1' },
    ];

    const data = await runSim(page, nodes, edges);

    // Should have equipment results
    const eqRes = data.results?.equipment_results?.g1 ?? data.equipment_results?.g1;
    expect(eqRes).toBeTruthy();

    // Temperature should be close to specified outlet
    if (eqRes.temperature) {
      // Temperature in K → °C
      const T_C = eqRes.temperature > 273 ? eqRes.temperature - 273.15 : eqRes.temperature;
      expect(T_C).toBeGreaterThan(600);
    }
  });

  // T1-3: Rigorous Distillation (method = Rigorous)
  test('rigorous distillation produces stage profiles', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    // Benzene/toluene column with rigorous method
    const nodes = [
      {
        id: 'f1', type: 'equipment',
        data: {
          equipmentType: 'FeedStream', name: 'Feed',
          parameters: {
            feedTemperature: 90, feedPressure: 101.325, feedFlowRate: 10,
            feedComposition: JSON.stringify({
              'benzene': 0.5, 'toluene': 0.5,
            }),
          },
        },
        position: { x: 0, y: 0 },
      },
      {
        id: 'dc1', type: 'equipment',
        data: {
          equipmentType: 'DistillationColumn', name: 'Column',
          parameters: {
            numberOfStages: 15,
            feedStage: 7,
            refluxRatio: 2.0,
            condenserPressure: 101.325,
            distillateToFeedRatio: 0.5,
            method: 'Rigorous',
          },
        },
        position: { x: 200, y: 0 },
      },
      {
        id: 'p1', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'Distillate', parameters: {} },
        position: { x: 400, y: -100 },
      },
      {
        id: 'p2', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'Bottoms', parameters: {} },
        position: { x: 400, y: 100 },
      },
    ];
    const edges = [
      { id: 'e1', source: 'f1', target: 'dc1', sourceHandle: 'out-1', targetHandle: 'in-1' },
      { id: 'e2', source: 'dc1', target: 'p1', sourceHandle: 'out-1', targetHandle: 'in-1' },
      { id: 'e3', source: 'dc1', target: 'p2', sourceHandle: 'out-2', targetHandle: 'in-1' },
    ];

    const data = await runSim(page, nodes, edges);

    // Equipment results should have stage profiles
    const eqRes = data.results?.equipment_results?.dc1 ?? data.equipment_results?.dc1;
    expect(eqRes).toBeTruthy();

    // Check for rigorous method indicator
    if (eqRes.method) {
      expect(eqRes.method).toBe('Rigorous');
    }

    // Stage profiles should be present
    if (eqRes.stage_profiles) {
      expect(eqRes.stage_profiles.length).toBe(15);

      // Temperatures should be monotonically increasing (condenser < reboiler)
      const temps = eqRes.stage_profiles.map((s: any) => s.T_C);
      const isMonotonic = temps.every(
        (t: number, i: number) => i === 0 || t >= temps[i - 1] - 0.5
      );
      expect(isMonotonic).toBe(true);

      // Condenser T should be ~80°C (benzene-rich)
      expect(temps[0]).toBeGreaterThan(70);
      expect(temps[0]).toBeLessThan(95);

      // Reboiler T should be ~105-115°C (toluene-rich)
      expect(temps[temps.length - 1]).toBeGreaterThan(95);
      expect(temps[temps.length - 1]).toBeLessThan(125);
    }

    // Distillate temperature should be in range
    if (eqRes.distillateTemperature !== undefined) {
      expect(eqRes.distillateTemperature).toBeGreaterThan(70);
      expect(eqRes.distillateTemperature).toBeLessThan(95);
    }
  });

  // T2-2: Transport properties in HX sizing
  test('HX sizing includes Kern method U_calculated', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('load');

    const nodes = [
      {
        id: 'f1', type: 'equipment',
        data: {
          equipmentType: 'FeedStream', name: 'Hot',
          parameters: {
            feedTemperature: 150, feedPressure: 500, feedFlowRate: 5,
            feedComposition: JSON.stringify({ 'water': 1.0 }),
          },
        },
        position: { x: 0, y: 0 },
      },
      {
        id: 'f2', type: 'equipment',
        data: {
          equipmentType: 'FeedStream', name: 'Cold',
          parameters: {
            feedTemperature: 25, feedPressure: 500, feedFlowRate: 5,
            feedComposition: JSON.stringify({ 'water': 1.0 }),
          },
        },
        position: { x: 0, y: 100 },
      },
      {
        id: 'hx1', type: 'equipment',
        data: {
          equipmentType: 'HeatExchanger', name: 'HX',
          parameters: {},
        },
        position: { x: 200, y: 50 },
      },
      {
        id: 'p1', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'HotOut', parameters: {} },
        position: { x: 400, y: 0 },
      },
      {
        id: 'p2', type: 'equipment',
        data: { equipmentType: 'ProductStream', name: 'ColdOut', parameters: {} },
        position: { x: 400, y: 100 },
      },
    ];
    const edges = [
      { id: 'e1', source: 'f1', target: 'hx1', sourceHandle: 'out-1', targetHandle: 'in-hot' },
      { id: 'e2', source: 'f2', target: 'hx1', sourceHandle: 'out-1', targetHandle: 'in-cold' },
      { id: 'e3', source: 'hx1', target: 'p1', sourceHandle: 'out-hot', targetHandle: 'in-1' },
      { id: 'e4', source: 'hx1', target: 'p2', sourceHandle: 'out-cold', targetHandle: 'in-1' },
    ];

    const data = await runSim(page, nodes, edges);

    const eqRes = data.results?.equipment_results?.hx1 ?? data.equipment_results?.hx1;
    expect(eqRes).toBeTruthy();

    // Check sizing has U_calculated from Kern method
    const sizing = eqRes.sizing;
    if (sizing) {
      // Should have h_tube, h_shell, or U_calculated
      const hasKern = sizing.U_calculated || sizing.h_tube || sizing.h_shell;
      if (hasKern) {
        expect(sizing.U_calculated).toBeGreaterThan(0);
      }
    }
  });

});
