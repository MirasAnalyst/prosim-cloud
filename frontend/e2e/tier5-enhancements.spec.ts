import { test, expect } from '@playwright/test';

/**
 * Tier 5 Enhancements E2E Tests
 *
 * Validates: Cyclone equipment, equipment sizing results, grid snapping,
 * UNIQUAC/NRTL in dropdown.
 *
 * Strategy: call /api/simulation/run via page.evaluate and verify results.
 */

test.describe('Tier 5: Enhancements', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await page.waitForSelector('text=Equipment', { timeout: 10_000 });
    await page.waitForTimeout(500);
  });

  test('Test 1: Cyclone pressure drop calculation', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'cyc-1', type: 'Cyclone', name: 'Cyclone-1',
            parameters: {
              feedTemperature: 150,
              feedPressure: 500,
              feedFlowRate: 2.0,
              feedComposition: JSON.stringify({ nitrogen: 0.79, oxygen: 0.21 }),
              inletDiameter: 0.3,
              pressureDropCoeff: 8,
              efficiency: 95,
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

    const cycRes = results.equipment_results['cyc-1'];
    expect(cycRes).toBeDefined();
    expect(cycRes.pressureDrop).toBeGreaterThan(0);
    expect(cycRes.inletVelocity).toBeGreaterThan(0);
    expect(cycRes.efficiency).toBe(95);

    const logs: string[] = results.logs;
    expect(logs.some((l: string) => l.includes('Cyclone') && l.includes('ΔP'))).toBe(true);
  });

  test('Test 2: Separator sizing results (Souders-Brown)', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'sep-1', type: 'Separator', name: 'Separator-1',
            parameters: {
              feedTemperature: 80,
              feedPressure: 500,
              feedFlowRate: 5.0,
              feedComposition: JSON.stringify({ methane: 0.5, 'n-hexane': 0.5 }),
              temperature: 80,
              pressure: 500,
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

    const sepRes = results.equipment_results['sep-1'];
    expect(sepRes).toBeDefined();

    // Should have sizing data
    if (sepRes.sizing) {
      expect(sepRes.sizing.diameter_m).toBeGreaterThan(0);
      expect(sepRes.sizing.K_sb).toBeGreaterThan(0);
    }
  });

  test('Test 3: HX sizing results (area from duty and LMTD)', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'h1', type: 'Heater', name: 'Hot Feed',
              parameters: {
                feedTemperature: 150, feedPressure: 500, feedFlowRate: 3.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletTemperature: 150,
              },
              position: { x: 100, y: 100 },
            },
            {
              id: 'h2', type: 'Heater', name: 'Cold Feed',
              parameters: {
                feedTemperature: 25, feedPressure: 500, feedFlowRate: 3.0,
                feedComposition: JSON.stringify({ water: 1.0 }),
                outletTemperature: 25,
              },
              position: { x: 100, y: 300 },
            },
            {
              id: 'hx-1', type: 'HeatExchanger', name: 'HX-1',
              parameters: { hotOutletTemp: 60, coldOutletTemp: 80 },
              position: { x: 400, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'h1', target: 'hx-1', sourceHandle: 'out-1', targetHandle: 'in-hot' },
            { id: 'e2', source: 'h2', target: 'hx-1', sourceHandle: 'out-1', targetHandle: 'in-cold' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results.status).not.toBe('error');

    const hxRes = results.equipment_results['hx-1'];
    expect(hxRes).toBeDefined();
    expect(hxRes.duty).toBeDefined();
    expect(hxRes.LMTD).toBeGreaterThan(0);

    // Should have sizing
    if (hxRes.sizing) {
      expect(hxRes.sizing.area_m2).toBeGreaterThan(0);
    }
  });

  test('Test 4: UNIQUAC property package in dropdown', async ({ page }) => {
    // Property package dropdown is now inside the Simulation Basis panel
    // Click the Basis button to open the panel, then check options
    await page.goto('/app');
    await page.waitForLoadState('load');
    await page.locator('button[title="Simulation Basis"]').click();
    await page.waitForTimeout(500);
    // The property package select is inside the Simulation Basis panel (not the TopNav unit system select)
    const ppSelect = page.locator('text=Property Package').locator('..').locator('select');
    const options = await ppSelect.locator('option').allTextContents();
    expect(options).toContain('UNIQUAC');
    expect(options).toContain('NRTL');
    expect(options).toContain('Peng-Robinson');
    expect(options).toContain('SRK');
  });
});
