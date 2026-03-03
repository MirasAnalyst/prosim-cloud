import { test, expect } from '@playwright/test';

test.describe('Wave 3: Reactor Enhancements', () => {
  test('CSTR with Arrhenius kinetics calculates rate constant', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'cstr1', type: 'CSTRReactor', name: 'CSTR',
            parameters: {
              feedTemperature: 80, feedPressure: 200, feedFlowRate: 0.5,
              volume: 2.0, temperature: 80,
              activationEnergy: 50, preExpFactor: 1e6,
              feedComposition: '{"ethanol": 0.3, "water": 0.7}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const cstrResult = result.results?.equipment_results?.cstr1;
    expect(cstrResult).toBeDefined();
    expect(cstrResult.rateConstant).toBeGreaterThan(0);
    expect(cstrResult.conversion).toBeGreaterThan(0);
  });

  test('PFR with Ergun calculates pressure drop', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'pfr1', type: 'PFRReactor', name: 'PFR',
            parameters: {
              feedTemperature: 300, feedPressure: 2000, feedFlowRate: 0.5,
              length: 5, diameter: 0.5,
              temperature: 300, pressure: 2000,
              bedVoidFraction: 0.4, particleDiameter: 0.003,
              feedComposition: '{"methane": 0.9, "ethane": 0.1}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const pfrResult = result.results?.equipment_results?.pfr1;
    expect(pfrResult).toBeDefined();
    expect(pfrResult.pressureDrop).toBeGreaterThan(0);
  });
});
