import { test, expect } from '@playwright/test';

test.describe('Wave 2: SSE + Batch Simulation', () => {
  test('SSE stream endpoint returns complete event', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            { id: 'h1', type: 'Heater', name: 'Heater 1', parameters: { feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0, outletTemperature: 80, feedComposition: '{"water": 1.0}' }},
          ],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });

      const text = await res.text();
      return { text, ok: res.ok };
    });

    expect(result.ok).toBe(true);
    expect(result.text).toContain('event: complete');
  });

  test('batch simulation returns multiple results', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_nodes: [
            { id: 'h1', type: 'Heater', name: 'Heater', parameters: { feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0, outletTemperature: 80, feedComposition: '{"water": 1.0}' }},
          ],
          base_edges: [],
          property_package: 'PengRobinson',
          variations: [
            { node_id: 'h1', parameter_key: 'outletTemperature', values: [60, 80, 100] },
          ],
        }),
      });
      return res.json();
    });

    expect(result.results).toHaveLength(3);
    expect(result.parameter_matrix).toHaveLength(3);
  });
});
