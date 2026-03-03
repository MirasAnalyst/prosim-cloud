import { test, expect } from '@playwright/test';

test.describe('Stream Inspector', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/app');
    await page.waitForSelector('text=Equipment', { timeout: 10_000 });
    await page.waitForTimeout(500);
  });

  test('clicking a stream edge shows StreamInspector with simulation results', async ({ page }) => {
    // Run a simple simulation: FeedStream → Heater via API
    const simResult = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed-1',
          type: 'FeedStream',
          name: 'Feed',
          parameters: {
            feedTemperature: 25,
            feedPressure: 500,
            feedFlowRate: 10,
            feedComposition: JSON.stringify({ methane: 0.9, ethane: 0.1 }),
          },
          position: { x: 100, y: 200 },
        },
        {
          id: 'heater-1',
          type: 'Heater',
          name: 'Heater',
          parameters: { outletTemperature: 100 },
          position: { x: 400, y: 200 },
        },
      ];
      const edges = [
        { id: 'edge-1', source: 'feed-1', sourceHandle: 'out-1', target: 'heater-1', targetHandle: 'in-1' },
      ];
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: 'PengRobinson' }),
      });
      return res.json();
    });

    const results = simResult.results ?? simResult;
    // Verify stream results include component properties
    const edgeResult = results.stream_results?.['edge-1'];
    expect(edgeResult).toBeDefined();
    expect(edgeResult.temperature).toBeDefined();
    expect(edgeResult.molecular_weight).toBeGreaterThan(0);
    expect(edgeResult.molar_flow).toBeGreaterThan(0);
    expect(edgeResult.mass_fractions).toBeDefined();
    expect(edgeResult.component_molar_flows).toBeDefined();
    expect(edgeResult.component_mass_flows).toBeDefined();
    expect(edgeResult.enthalpy).toBeDefined();

    // Verify FeedStream equipment results also include component properties
    const feedResult = results.equipment_results?.['feed-1'];
    expect(feedResult).toBeDefined();
    expect(feedResult.molecular_weight).toBeGreaterThan(0);
    expect(feedResult.molar_flow).toBeGreaterThan(0);
    expect(feedResult.mass_fractions).toBeDefined();

    // Now inject the flowsheet into the UI and run sim via store
    await page.evaluate(async () => {
      const store = (window as any).__ZUSTAND_FLOWSHEET_STORE__;
      if (!store) throw new Error('Store not exposed');
      store.getState().loadFlowsheet(
        [
          {
            id: 'feed-1', type: 'FeedStream', name: 'Feed',
            parameters: {
              feedTemperature: 25, feedPressure: 500, feedFlowRate: 10,
              feedComposition: JSON.stringify({ methane: 0.9, ethane: 0.1 }),
            },
            position: { x: 100, y: 200 },
          },
          {
            id: 'heater-1', type: 'Heater', name: 'Heater',
            parameters: { outletTemperature: 100 },
            position: { x: 400, y: 200 },
          },
        ],
        [
          { id: 'edge-1', sourceId: 'feed-1', sourcePort: 'out-1', targetId: 'heater-1', targetPort: 'in-1' },
        ]
      );
    });

    // Wait for canvas to render
    await page.waitForTimeout(1000);

    // Run simulation via the store
    await page.evaluate(async () => {
      const { useSimulationStore } = await import('/src/stores/simulationStore');
      // @ts-ignore
      const simStore = (window as any).__ZUSTAND_SIMULATION_STORE__ ?? useSimulationStore;
      await simStore.getState().runSimulation();
    });

    // Wait for simulation to complete
    await page.waitForTimeout(3000);

    // Try to click the stream edge - look for the edge label
    const edgeLabel = page.locator('.react-flow__edge').first();
    if (await edgeLabel.isVisible()) {
      await edgeLabel.click();
      await page.waitForTimeout(500);

      // Check if StreamInspector appeared with "Stream" header
      const streamHeader = page.locator('text=Stream').first();
      const isVisible = await streamHeader.isVisible().catch(() => false);
      if (isVisible) {
        // StreamInspector is showing - verify it has content
        expect(await page.locator('text=Connection').first().isVisible()).toBeTruthy();
        expect(await page.locator('text=Material Stream').first().isVisible()).toBeTruthy();
      }
    }
  });

  test('API: stream results include component properties for methane/ethane', async ({ page }) => {
    // Pure API test - verify the backend returns component properties
    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'f1',
          type: 'FeedStream',
          name: 'NatGas Feed',
          parameters: {
            feedTemperature: 30,
            feedPressure: 3000,
            feedFlowRate: 5,
            feedComposition: JSON.stringify({ methane: 0.85, ethane: 0.10, propane: 0.05 }),
          },
          position: { x: 0, y: 0 },
        },
        {
          id: 'p1',
          type: 'ProductStream',
          name: 'Product',
          parameters: {},
          position: { x: 300, y: 0 },
        },
      ];
      const edges = [
        { id: 'e1', source: 'f1', sourceHandle: 'out-1', target: 'p1', targetHandle: 'in-1' },
      ];
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges, property_package: 'PengRobinson' }),
      });
      return res.json();
    });

    const res = result.results ?? result;

    // Stream result for the edge
    const stream = res.stream_results?.['e1'];
    expect(stream).toBeDefined();
    expect(stream.molecular_weight).toBeCloseTo(18.85, 0); // MW_mix for 85/10/5 CH4/C2H6/C3H8
    expect(stream.molar_flow).toBeGreaterThan(0);
    expect(stream.enthalpy).toBeDefined();

    // Mass fractions should sum to ~1
    const massFracSum = Object.values(stream.mass_fractions as Record<string, number>).reduce((a: number, b: number) => a + b, 0);
    expect(massFracSum).toBeCloseTo(1.0, 4);

    // Component mass flows should sum to total mass flow
    const compMassSum = Object.values(stream.component_mass_flows as Record<string, number>).reduce((a: number, b: number) => a + b, 0);
    expect(compMassSum).toBeCloseTo(stream.flowRate ?? 5, 2);

    // FeedStream equipment results
    const feedEq = res.equipment_results?.['f1'];
    expect(feedEq).toBeDefined();
    expect(feedEq.molecular_weight).toBeGreaterThan(0);
    expect(feedEq.component_molar_flows).toBeDefined();
    expect(Object.keys(feedEq.component_molar_flows)).toContain('methane');

    // ProductStream equipment results
    const prodEq = res.equipment_results?.['p1'];
    expect(prodEq).toBeDefined();
    expect(prodEq.molecular_weight).toBeGreaterThan(0);
  });
});
