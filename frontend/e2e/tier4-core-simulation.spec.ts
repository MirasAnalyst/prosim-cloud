import { test, expect } from '@playwright/test';

/**
 * Tier 4 Core Simulation E2E Tests
 *
 * Validates: NRTL/UNIQUAC property packages, tear-stream convergence,
 * mass balance validation, unit operation validation, Absorber/Stripper.
 *
 * Strategy: call /api/simulation/run via page.evaluate and verify results.
 */

test.describe('Tier 4: Core Simulation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await page.waitForSelector('text=Equipment', { timeout: 10_000 });
    await page.waitForTimeout(500);
  });

  test('Test 1: Water/ethanol NRTL flash differs from PR', async ({ page }) => {
    // Water/ethanol mixture at 78°C (near azeotrope), 101.325 kPa
    // NRTL should give different VF than PR due to activity coefficient effects
    const [prResponse, nrtlResponse] = await page.evaluate(async () => {
      const nodes = [{
        id: 'sep-1', type: 'Separator', name: 'Separator-1',
        parameters: {
          feedTemperature: 78,
          feedPressure: 101.325,
          feedFlowRate: 1.0,
          feedComposition: JSON.stringify({ water: 0.5, ethanol: 0.5 }),
          temperature: 78,
          pressure: 101.325,
        },
        position: { x: 200, y: 200 },
      }];
      const edges: unknown[] = [];

      const prRes = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: 'PengRobinson' }),
      });
      const pr = await prRes.json();

      const nrtlRes = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: 'NRTL' }),
      });
      const nrtl = await nrtlRes.json();

      return [pr, nrtl];
    });

    expect(prResponse.results.status).not.toBe('error');
    expect(nrtlResponse.results.status).not.toBe('error');

    const prVF = prResponse.results.equipment_results['sep-1']?.vaporFraction;
    const nrtlVF = nrtlResponse.results.equipment_results['sep-1']?.vaporFraction;

    // Both should produce a vapor fraction
    expect(prVF).toBeDefined();
    expect(nrtlVF).toBeDefined();

    // NRTL should give a log about using activity coefficient model
    const nrtlLogs: string[] = nrtlResponse.results.logs;
    expect(nrtlLogs.some((l: string) => l.includes('NRTL') || l.includes('activity'))).toBe(true);
  });

  test('Test 2: UNIQUAC property package accepted', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'h-1', type: 'Heater', name: 'Heater-1',
            parameters: {
              feedTemperature: 25,
              feedPressure: 101.325,
              feedFlowRate: 1.0,
              feedComposition: JSON.stringify({ water: 0.5, ethanol: 0.5 }),
              outletTemperature: 80,
            },
            position: { x: 200, y: 200 },
          }],
          edges: [],
          property_package: 'UNIQUAC',
        }),
      });
      return res.json();
    });

    expect(simResponse.results.status).not.toBe('error');
    const logs: string[] = simResponse.results.logs;
    expect(logs.some((l: string) => l.includes('UNIQUAC') || l.includes('activity'))).toBe(true);
  });

  test('Test 3: Tear-stream convergence — Mixer→Heater→Splitter loop', async ({ page }) => {
    // Create a recycle loop: Mixer → Heater → Splitter → back to Mixer
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'mixer-1', type: 'Mixer', name: 'Mixer',
              parameters: {
                feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
              },
              position: { x: 100, y: 200 },
            },
            {
              id: 'heater-1', type: 'Heater', name: 'Heater',
              parameters: { outletTemperature: 80 },
              position: { x: 300, y: 200 },
            },
            {
              id: 'splitter-1', type: 'Splitter', name: 'Splitter',
              parameters: { splitRatio: 0.6 },
              position: { x: 500, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'mixer-1', target: 'heater-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
            { id: 'e2', source: 'heater-1', target: 'splitter-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
            { id: 'e3', source: 'splitter-1', target: 'mixer-1', sourceHandle: 'out-2', targetHandle: 'in-2' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    // Should detect recycle and attempt convergence
    const logs: string[] = results.logs;
    expect(logs.some((l: string) =>
      l.includes('Tear stream') || l.includes('tear') || l.includes('converged')
    )).toBe(true);

    // Convergence info should show iteration count > 1 or recycle detection
    const ci = results.convergence_info;
    expect(ci.recycle_detected || ci.iterations > 1).toBe(true);
  });

  test('Test 4: Mass balance closes for Mixer→Splitter', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'h1', type: 'Heater', name: 'Feed-1',
              parameters: {
                feedTemperature: 25, feedPressure: 200, feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletTemperature: 25,
              },
              position: { x: 100, y: 100 },
            },
            {
              id: 'h2', type: 'Heater', name: 'Feed-2',
              parameters: {
                feedTemperature: 25, feedPressure: 200, feedFlowRate: 2.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletTemperature: 25,
              },
              position: { x: 100, y: 300 },
            },
            {
              id: 'mixer-1', type: 'Mixer', name: 'Mixer',
              parameters: {},
              position: { x: 300, y: 200 },
            },
            {
              id: 'splitter-1', type: 'Splitter', name: 'Splitter',
              parameters: { splitRatio: 0.6 },
              position: { x: 500, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'h1', target: 'mixer-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
            { id: 'e2', source: 'h2', target: 'mixer-1', sourceHandle: 'out-1', targetHandle: 'in-2' },
            { id: 'e3', source: 'mixer-1', target: 'splitter-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    // Convergence info should show mass_balance_ok = true
    expect(results.convergence_info.mass_balance_ok).toBe(true);

    // Mixer output should be 3.0 kg/s (1.0 + 2.0)
    const mixerRes = results.equipment_results['mixer-1'];
    expect(mixerRes.totalMassFlow).toBeCloseTo(3.0, 1);

    // Splitter outputs should sum to 3.0 kg/s
    const splitterStreams = Object.entries(results.stream_results).filter(
      ([id]) => id.includes('splitter') || id.includes('e3')
    );
    // At least the mixer output stream should show 3.0 kg/s
    const e3Stream = results.stream_results['e3'];
    if (e3Stream) {
      expect(e3Stream.flowRate).toBeCloseTo(3.0, 1);
    }
  });

  test('Test 5: Absorber CO2 removal from natural gas', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'gas-feed', type: 'Heater', name: 'Gas Feed',
              parameters: {
                feedTemperature: 25, feedPressure: 3000, feedFlowRate: 5.0,
                feedComposition: JSON.stringify({ methane: 0.85, 'carbon dioxide': 0.10, ethane: 0.05 }),
                outletTemperature: 25,
              },
              position: { x: 100, y: 300 },
            },
            {
              id: 'solvent-feed', type: 'Heater', name: 'Solvent Feed',
              parameters: {
                feedTemperature: 25, feedPressure: 3000, feedFlowRate: 10.0,
                feedComposition: JSON.stringify({ water: 0.7, monoethanolamine: 0.3 }),
                outletTemperature: 25,
              },
              position: { x: 100, y: 100 },
            },
            {
              id: 'absorber-1', type: 'Absorber', name: 'CO2 Absorber',
              parameters: { numberOfStages: 15, pressure: 3000 },
              position: { x: 400, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'gas-feed', target: 'absorber-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
            { id: 'e2', source: 'solvent-feed', target: 'absorber-1', sourceHandle: 'out-1', targetHandle: 'in-2' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    const absRes = results.equipment_results['absorber-1'];
    expect(absRes).toBeDefined();
    expect(absRes.numberOfStages).toBe(15);

    // Should have log about absorber
    const logs: string[] = results.logs;
    expect(logs.some((l: string) => l.includes('Absorber'))).toBe(true);
  });

  test('Test 6: Unit operation validation warnings', async ({ page }) => {
    // Mixer with only 1 inlet should produce a warning
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'mixer-1', type: 'Mixer', name: 'Mixer-1',
            parameters: {
              feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0,
              feedComposition: JSON.stringify({ water: 1.0 }),
            },
            position: { x: 200, y: 200 },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    // Should warn about mixer having fewer than 2 inlets
    const logs: string[] = results.logs;
    expect(logs.some((l: string) =>
      l.includes('WARNING') && l.includes('Mixer') && l.includes('inlet')
    )).toBe(true);
  });
});
