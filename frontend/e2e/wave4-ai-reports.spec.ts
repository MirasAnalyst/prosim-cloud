import { test, expect } from '@playwright/test';

test.describe('Wave 4: Reports', () => {
  test('report endpoint returns response', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'h1', type: 'Heater', name: 'Heater',
            parameters: { feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0, outletTemperature: 80, feedComposition: '{"water": 1.0}' },
          }],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      return { ok: res.ok, size: (await res.blob()).size };
    });

    expect(result.ok).toBe(true);
    expect(result.size).toBeGreaterThan(0);
  });
});
