import { test, expect } from '@playwright/test';

test.describe('Wave 1: New Equipment Types', () => {
  test('three-phase separator produces vapor and liquid outlets', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'sep3',
            type: 'ThreePhaseSeparator',
            name: 'Three Phase Sep',
            parameters: {
              feedTemperature: 80,
              feedPressure: 500,
              feedFlowRate: 2.0,
              feedComposition: '{"water": 0.5, "n-hexane": 0.3, "methane": 0.2}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const sepResult = result.results?.equipment_results?.sep3;
    expect(sepResult).toBeDefined();
    expect(sepResult.vaporFraction).toBeGreaterThanOrEqual(0);
  });

  test('crystallizer produces crystal and mother liquor', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'cryst1',
            type: 'Crystallizer',
            name: 'Crystallizer',
            parameters: {
              feedTemperature: 80,
              feedPressure: 101.325,
              feedFlowRate: 1.0,
              crystallizationTemp: 10,
              feedComposition: '{"water": 0.7, "ethanol": 0.3}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const crystResult = result.results?.equipment_results?.cryst1;
    expect(crystResult).toBeDefined();
    expect(crystResult.crystalYield).toBeGreaterThan(0);
  });

  test('dryer removes moisture from feed', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'dryer1',
            type: 'Dryer',
            name: 'Dryer',
            parameters: {
              feedTemperature: 25,
              feedPressure: 101.325,
              feedFlowRate: 1.0,
              outletMoisture: 5,
              feedComposition: '{"water": 0.3, "ethanol": 0.7}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const dryerResult = result.results?.equipment_results?.dryer1;
    expect(dryerResult).toBeDefined();
    expect(dryerResult.waterRemoved).toBeGreaterThan(0);
    expect(dryerResult.duty).toBeGreaterThan(0);
  });

  test('filter separates filtrate and cake', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'filter1',
            type: 'Filter',
            name: 'Filter',
            parameters: {
              feedTemperature: 25,
              feedPressure: 200,
              feedFlowRate: 1.0,
              efficiency: 95,
              pressureDrop: 50,
              feedComposition: '{"water": 1.0}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const filterResult = result.results?.equipment_results?.filter1;
    expect(filterResult).toBeDefined();
    expect(filterResult.efficiency).toBe(95);
    expect(filterResult.pressureDrop).toBe(50);
    expect(filterResult.filtrateFlow).toBeGreaterThan(0);
  });
});
