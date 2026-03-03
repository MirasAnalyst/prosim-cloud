import { test, expect } from '@playwright/test';

test.describe('Wave 2: Pump Curves, Multi-Stage Compressor, Valve Cv', () => {
  test('pump with NPSH check warns on low NPSH', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'pump1',
              type: 'Pump',
              name: 'Test Pump',
              parameters: {
                feedTemperature: 25,
                feedPressure: 101.325,
                feedFlowRate: 2.0,
                outletPressure: 500,
                efficiency: 80,
                npshAvailable: 2,
                feedComposition: '{"water": 1.0}',
              },
            },
          ],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const pumpResult = result.results?.equipment_results?.pump1;
    expect(pumpResult).toBeDefined();
    expect(pumpResult.work).toBeGreaterThan(0);
    // Should have NPSH warning in logs (npshAvailable=2 < npshRequired=3)
    const logs: string[] = result.results?.logs ?? [];
    expect(logs.some((l: string) => l.includes('NPSH') || l.includes('cavitation'))).toBe(true);
  });

  test('multi-stage compressor splits work across stages', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'comp1',
              type: 'Compressor',
              name: 'Multi-Stage',
              parameters: {
                feedTemperature: 25,
                feedPressure: 101.325,
                feedFlowRate: 1.0,
                outletPressure: 1000,
                efficiency: 75,
                stages: 3,
                intercoolTemp: 35,
                feedComposition: '{"methane": 0.9, "ethane": 0.1}',
              },
            },
          ],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const compResult = result.results?.equipment_results?.comp1;
    expect(compResult).toBeDefined();
    expect(compResult.work).toBeGreaterThan(0);
    expect(compResult.stages).toBe(3);
  });

  test('valve Cv calculation with choked flow check', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'valve1',
              type: 'Valve',
              name: 'Test Valve',
              parameters: {
                feedTemperature: 25,
                feedPressure: 500,
                feedFlowRate: 1.0,
                outletPressure: 101.325,
                chokedFlowCheck: true,
                feedComposition: '{"water": 1.0}',
              },
            },
          ],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const valveResult = result.results?.equipment_results?.valve1;
    expect(valveResult).toBeDefined();
    expect(valveResult.pressureDrop).toBeGreaterThan(0);
    // Cv should be calculated
    expect(valveResult.cv).toBeGreaterThan(0);
  });
});
