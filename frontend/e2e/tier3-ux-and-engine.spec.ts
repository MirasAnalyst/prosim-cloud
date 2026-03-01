import { test, expect } from '@playwright/test';

/**
 * Tier 3 UX & Engine E2E Tests
 *
 * Validates: CSTR→Cooler enthalpy propagation, ConversionReactor→Separator
 * (products filtered), empty flowsheet error, and WARNING log prefix.
 *
 * Strategy: call /api/simulation/run via page.evaluate and verify results.
 */

test.describe('Tier 3: UX & Engine Fixes', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('text=Equipment', { timeout: 10_000 });
    await page.waitForTimeout(500);
  });

  test('Test 1: CSTR outlet feeds Cooler → cooler duty is non-zero', async ({ page }) => {
    // CSTR at 200°C with methane, connected to Cooler at 50°C
    // If CSTR outlet enthalpy is correct (thermo-based, not Cp fallback),
    // the cooler will see correct inlet H and compute non-zero duty.
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'cstr-1', type: 'CSTRReactor', name: 'CSTR-1',
              parameters: {
                feedTemperature: 25,
                feedPressure: 500,
                feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ methane: 0.9, ethane: 0.1 }),
                volume: 10,
                temperature: 200,
                pressure: 500,
                duty: 0,
              },
              position: { x: 100, y: 200 },
            },
            {
              id: 'cooler-1', type: 'Cooler', name: 'Cooler-1',
              parameters: {
                outletTemperature: 50,
                pressureDrop: 0,
              },
              position: { x: 400, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'cstr-1', sourceHandle: 'out-1', target: 'cooler-1', targetHandle: 'in-1' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results).toBeDefined();

    // CSTR should have results
    const cstrRes = results.equipment_results['cstr-1'];
    expect(cstrRes).toBeDefined();
    expect(cstrRes.outletTemperature).toBeCloseTo(200, 0);

    // Cooler should have non-zero duty (cooling from 200°C to 50°C)
    const coolerRes = results.equipment_results['cooler-1'];
    expect(coolerRes).toBeDefined();
    expect(coolerRes.duty).toBeDefined();
    expect(Math.abs(Number(coolerRes.duty))).toBeGreaterThan(10);

    // Cooler outlet temperature should be ~50°C
    expect(coolerRes.outletTemperature).toBeCloseTo(50, 5);
  });

  test('Test 2: ConversionReactor → Separator chain → valid flash (products filtered)', async ({ page }) => {
    // ConversionReactor produces "products" pseudo-component
    // Downstream Separator should flash successfully (not crash on "products")
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            {
              id: 'cr-1', type: 'ConversionReactor', name: 'CR-1',
              parameters: {
                feedTemperature: 80,
                feedPressure: 101.325,
                feedFlowRate: 1.0,
                feedComposition: JSON.stringify({ ethanol: 0.5, water: 0.5 }),
                conversion: 50,
                temperature: 80,
                pressure: 101.325,
              },
              position: { x: 100, y: 200 },
            },
            {
              id: 'sep-1', type: 'Separator', name: 'Sep-1',
              parameters: {},
              position: { x: 400, y: 200 },
            },
          ],
          edges: [
            { id: 'e1', source: 'cr-1', sourceHandle: 'out-1', target: 'sep-1', targetHandle: 'in-1' },
          ],
          property_package: 'PengRobinson',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results).toBeDefined();

    // Separator should have results (not an error from "products" compound)
    const sepRes = results.equipment_results['sep-1'];
    expect(sepRes).toBeDefined();
    expect(sepRes.error).toBeUndefined();

    // Should have a vapor fraction result
    expect(sepRes.vaporFraction).toBeDefined();
    expect(Number(sepRes.vaporFraction)).toBeGreaterThanOrEqual(0);
    expect(Number(sepRes.vaporFraction)).toBeLessThanOrEqual(1);

    // Logs should not contain any ERROR for the separator
    const logs: string[] = results.logs;
    const sepErrors = logs.filter((l: string) => l.includes('Sep-1') && l.includes('ERROR'));
    expect(sepErrors.length).toBe(0);
  });

  test('Test 3: Empty flowsheet → friendly error message', async ({ page }) => {
    const simResponse = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [],
          edges: [],
          property_package: 'PengRobinson',
        }),
      });
      const body = await res.json();
      return { httpStatus: res.status, ...body };
    });

    // Backend should reject with 400 or return error status
    // FastAPI returns {"detail": "..."} for HTTPException
    if (simResponse.httpStatus === 400) {
      expect(simResponse.detail).toBeDefined();
    } else {
      expect(simResponse.status).toBe('error');
      expect(simResponse.error).toBeDefined();
    }
  });

  test('Test 4: Simulation logs contain WARNING prefix for appropriate conditions', async ({ page }) => {
    // Separator fallback (when flash fails for exotic comp) produces WARNING
    // We use a simple setup that triggers a known warning path
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
                pressureDrop: 0,
              },
              position: { x: 100, y: 200 },
            },
          ],
          edges: [],
          property_package: 'NRTL',
        }),
      });
      return res.json();
    });

    const results = simResponse.results;
    expect(results).toBeDefined();

    // NRTL triggers "using Peng-Robinson fallback" warning
    const logs: string[] = results.logs;
    const warningLogs = logs.filter((l: string) => l.includes('WARNING'));
    expect(warningLogs.length).toBeGreaterThan(0);
  });
});
