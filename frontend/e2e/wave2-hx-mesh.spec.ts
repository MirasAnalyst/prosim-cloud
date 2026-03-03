import { test, expect } from '@playwright/test';

test.describe('Wave 2: HX NTU + Costing', () => {
  test('HX NTU method calculates effectiveness', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            { id: 'hot-feed', type: 'Heater', name: 'Hot Feed', parameters: { feedTemperature: 150, feedPressure: 200, feedFlowRate: 1.0, outletTemperature: 150, feedComposition: '{"water": 1.0}' }},
            { id: 'cold-feed', type: 'Heater', name: 'Cold Feed', parameters: { feedTemperature: 25, feedPressure: 200, feedFlowRate: 1.0, outletTemperature: 25, feedComposition: '{"water": 1.0}' }},
            { id: 'hx1', type: 'HeatExchanger', name: 'HX NTU', parameters: { method: 'NTU', geometry: 'shell-tube', foulingFactor: 0.0002 }},
          ],
          edges: [
            { id: 'e1', source: 'hot-feed', sourceHandle: 'out-1', target: 'hx1', targetHandle: 'in-hot' },
            { id: 'e2', source: 'cold-feed', sourceHandle: 'out-1', target: 'hx1', targetHandle: 'in-cold' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const hxResult = result.results?.equipment_results?.hx1;
    expect(hxResult).toBeDefined();
    expect(hxResult.method).toBe('NTU');
    expect(hxResult.effectiveness).toBeGreaterThan(0);
    expect(hxResult.effectiveness).toBeLessThanOrEqual(1);
  });

  test('equipment costing returns purchase cost for pump', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'pump1', type: 'Pump', name: 'Test Pump',
            parameters: {
              feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0,
              outletPressure: 500, efficiency: 80,
              feedComposition: '{"water": 1.0}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const pumpResult = result.results?.equipment_results?.pump1;
    expect(pumpResult).toBeDefined();
    expect(pumpResult.work).toBeGreaterThan(0);
    expect(pumpResult.costing).toBeDefined();
    expect(pumpResult.costing.purchaseCost).toBeGreaterThan(0);
  });
});
