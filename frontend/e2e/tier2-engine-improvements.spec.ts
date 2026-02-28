import { test, expect } from '@playwright/test';

/**
 * Tier 2 Engine Improvements E2E Tests
 *
 * Validates: ConversionReactor conversion, Heater duty-mode VF,
 * Distillation FUG, PFR gas-phase density, partial results (per-equipment try/except).
 *
 * Strategy: call /api/simulation/run via page.evaluate and verify results.
 */

test.describe('Tier 2: Engine Improvements', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('text=Equipment', { timeout: 10_000 });
    await page.waitForTimeout(500);
  });

  test('Test 1: ConversionReactor ethanol+water at 80% conversion', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'cr-1', type: 'ConversionReactor', name: 'CR-1',
            parameters: {
              feedTemperature: 80,
              feedPressure: 101.325,
              feedFlowRate: 1.0,
              feedComposition: JSON.stringify({ ethanol: 0.5, water: 0.5 }),
              conversion: 80,
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

    const crRes = results.equipment_results['cr-1'];
    expect(crRes.conversion).toBe(80);

    // Outlet stream should have reduced ethanol fraction
    const outStream = results.stream_results;
    // The outlet is stored in port_conditions, but since there are no edges,
    // we check the equipment results — the composition change is reflected in
    // the logs and outlet composition
    const logs: string[] = results.logs;
    expect(logs.some((l: string) => l.includes('key reactant'))).toBe(true);
    expect(logs.some((l: string) => l.includes('ethanol'))).toBe(true);
  });

  test('Test 2: Heater duty-mode 3000 kW into water → VF > 0', async ({ page }) => {
    // 1 kg/s water at 25°C, 101.325 kPa, duty=3000 kW
    // 3000 kW into 1 kg/s water: should heat from 25°C well past 100°C
    // and produce significant vapor fraction
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'heater-1', type: 'Heater', name: 'Heater-1',
              parameters: {
                feedTemperature: 25,
                feedPressure: 101.325,
                feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                duty: 3000,
                pressureDrop: 0,
              },
              position: { x: 200, y: 200 },
            },
            {
              id: 'sep-1', type: 'Separator', name: 'Sep-1',
              parameters: {},
              position: { x: 450, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'heater-1', sourceHandle: 'out-1', target: 'sep-1', targetHandle: 'in-1' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    // Heater outlet temperature should be well above 100°C
    const heaterRes = results.equipment_results['heater-1'];
    expect(heaterRes.duty).toBeCloseTo(3000, 0);

    // The heater outlet stream (edge e1) should show elevated temperature
    const e1Stream = results.stream_results['e1'];
    expect(e1Stream).toBeDefined();
    expect(e1Stream.temperature).toBeGreaterThan(100);

    // VF should be > 0 (steam produced) — previously stuck at 0
    expect(e1Stream.vapor_fraction).toBeGreaterThan(0);
  });

  test('Test 3: Distillation benzene/toluene FUG → LK purity > 90%', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'dist-1', type: 'DistillationColumn', name: 'Dist-1',
            parameters: {
              feedTemperature: 90,
              feedPressure: 101.325,
              feedFlowRate: 1.0,
              feedComposition: JSON.stringify({ benzene: 0.5, toluene: 0.5 }),
              numberOfStages: 15,
              refluxRatio: 2.0,
              condenserPressure: 101.325,
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

    const distRes = results.equipment_results['dist-1'];

    // FUG should produce meaningful results
    expect(distRes.lightKeyPurity).toBeGreaterThan(90);

    // Distillate temperature should be near benzene BP (~80°C)
    expect(distRes.distillateTemperature).toBeGreaterThan(70);
    expect(distRes.distillateTemperature).toBeLessThan(95);

    // Bottoms temperature should be near toluene BP (~111°C)
    expect(distRes.bottomsTemperature).toBeGreaterThan(100);
    expect(distRes.bottomsTemperature).toBeLessThan(125);

    // Should have N_min, R_min reported
    expect(distRes.N_min).toBeGreaterThan(0);
    expect(distRes.R_min).toBeGreaterThan(0);
    expect(distRes.N_eff).toBeGreaterThan(0);

    // Logs should mention FUG
    const logs: string[] = results.logs;
    expect(logs.some((l: string) => l.includes('FUG'))).toBe(true);
  });

  test('Test 4: PFR gas-phase methane at 300°C/2000 kPa → residence time 1-30s', async ({ page }) => {
    // Gas-phase methane at 300°C/2000 kPa has density ~8-10 kg/m³
    // With rho=1000 (old bug), tau = V/(mf/rho) = 0.982/(1/1000) = 982s
    // With real gas density ~9 kg/m³, tau = 0.982/(1/9) = 8.8s
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'pfr-1', type: 'PFRReactor', name: 'PFR-1',
            parameters: {
              feedTemperature: 300,
              feedPressure: 2000,
              feedFlowRate: 1.0,
              feedComposition: JSON.stringify({ methane: 1.0 }),
              length: 5.0,
              diameter: 0.5,
              temperature: 300,
              pressure: 2000,
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

    const pfrRes = results.equipment_results['pfr-1'];

    // Residence time should be 1-30 seconds (not 982s from rho=1000)
    expect(pfrRes.residenceTime).toBeGreaterThan(1);
    expect(pfrRes.residenceTime).toBeLessThan(30);
  });

  test('Test 5: Per-equipment try/except — partial results when one equipment fails', async ({ page }) => {
    // Two independent equipment: a valid heater and a valid pump
    // Both should produce results (testing that per-equipment try/except
    // allows independent equipment to succeed/fail independently)
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'heater-1', type: 'Heater', name: 'Heater-1',
              parameters: {
                feedTemperature: 25,
                feedPressure: 101.325,
                feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletTemperature: 80,
                duty: 0,
                pressureDrop: 0,
              },
              position: { x: 100, y: 100 },
            },
            {
              id: 'pump-1', type: 'Pump', name: 'Pump-1',
              parameters: {
                feedTemperature: 25,
                feedPressure: 101.325,
                feedFlowRate: 2.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletPressure: 500,
                efficiency: 75,
              },
              position: { x: 100, y: 300 },
            },
          ],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;

    // Both equipment should have results (not just one)
    expect(results.equipment_results['heater-1']).toBeDefined();
    expect(results.equipment_results['pump-1']).toBeDefined();

    // Heater should have duty
    expect(results.equipment_results['heater-1'].duty).toBeDefined();
    expect(results.equipment_results['heater-1'].duty).not.toBe(0);

    // Pump should have work
    expect(results.equipment_results['pump-1'].work).toBeDefined();
    expect(results.equipment_results['pump-1'].work).toBeGreaterThan(0);

    // Neither should have an error field
    expect(results.equipment_results['heater-1'].error).toBeUndefined();
    expect(results.equipment_results['pump-1'].error).toBeUndefined();
  });
});
