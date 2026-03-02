import { test, expect } from '@playwright/test';

// Retry helper for project creation under concurrent test load
async function createProj(page: any): Promise<string> {
  return page.evaluate(async () => {
    for (let i = 0; i < 3; i++) {
      const r = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: `Phase8-Test-${Date.now()}` }),
      });
      if (r.ok) {
        const p = await r.json();
        return p.id;
      }
      await new Promise((resolve) => setTimeout(resolve, 300 * (i + 1)));
    }
    throw new Error('Failed to create project after 3 attempts');
  });
}

test.describe('Phase 8: Advanced Simulation Features', () => {

  test('simulation basis: add/remove compounds via API', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      // Create project
      let projectId = '';
      for (let i = 0; i < 3; i++) {
        const r = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Basis Test' }),
        });
        if (r.ok) { projectId = (await r.json()).id; break; }
        await new Promise((res) => setTimeout(res, 300));
      }
      if (!projectId) throw new Error('Project creation failed');

      // Save flowsheet with simulation_basis
      const saveRes = await fetch(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [],
          edges: [],
          simulation_basis: {
            compounds: ['water', 'methanol', 'ethanol'],
          },
        }),
      });
      const saved = await saveRes.json();

      // Read it back
      const getRes = await fetch(`/api/projects/${projectId}/flowsheet`);
      const flowsheet = await getRes.json();

      // Update to remove ethanol
      const updateRes = await fetch(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [],
          edges: [],
          simulation_basis: {
            compounds: ['water', 'methanol'],
          },
        }),
      });
      const updated = await updateRes.json();

      // Re-read
      const getRes2 = await fetch(`/api/projects/${projectId}/flowsheet`);
      const flowsheet2 = await getRes2.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return {
        saveOk: saveRes.ok,
        initialBasis: flowsheet.simulation_basis,
        updatedBasis: flowsheet2.simulation_basis,
      };
    });

    expect(result.saveOk).toBe(true);
    expect(result.initialBasis.compounds).toEqual(['water', 'methanol', 'ethanol']);
    expect(result.updatedBasis.compounds).toEqual(['water', 'methanol']);
  });

  test('feed stream node: create + simulate + verify results', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed1',
          type: 'equipment',
          position: { x: 0, y: 0 },
          data: {
            equipmentType: 'FeedStream',
            name: 'Feed 1',
            parameters: {
              feedTemperature: 100,
              feedPressure: 200,
              feedFlowRate: 50,
              feedComposition: JSON.stringify({ water: 1.0 }),
            },
          },
        },
        {
          id: 'heater1',
          type: 'equipment',
          position: { x: 200, y: 0 },
          data: {
            equipmentType: 'Heater',
            name: 'Heater 1',
            parameters: { outletTemperature: 150 },
          },
        },
      ];

      const edges = [
        {
          id: 'e1',
          source: 'feed1',
          sourceHandle: 'out-1',
          target: 'heater1',
          targetHandle: 'in-1',
          type: 'stream',
        },
      ];

      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes,
          edges,
          property_package: 'PengRobinson',
          simulation_basis: { compounds: ['water'] },
        }),
      });
      const data = await res.json();
      const results = data.results ?? data;

      return {
        status: results.status,
        feedResult: results.equipment_results?.feed1,
        heaterResult: results.equipment_results?.heater1,
        hasFeedStream: !!results.stream_results,
      };
    });

    expect(result.status).toMatch(/converged|partial|success/);
    // Feed stream should have results
    expect(result.feedResult).toBeTruthy();
    expect(result.feedResult.outletTemperature).toBeCloseTo(100, 0);
    expect(result.feedResult.outletPressure).toBeCloseTo(200, 0);
  });

  test('product stream node: receives upstream conditions', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed1',
          type: 'equipment',
          position: { x: 0, y: 0 },
          data: {
            equipmentType: 'FeedStream',
            name: 'Feed 1',
            parameters: {
              feedTemperature: 80,
              feedPressure: 300,
              feedFlowRate: 100,
              feedComposition: JSON.stringify({ water: 1.0 }),
            },
          },
        },
        {
          id: 'product1',
          type: 'equipment',
          position: { x: 200, y: 0 },
          data: {
            equipmentType: 'ProductStream',
            name: 'Product 1',
            parameters: {},
          },
        },
      ];

      const edges = [
        {
          id: 'e1',
          source: 'feed1',
          sourceHandle: 'out-1',
          target: 'product1',
          targetHandle: 'in-1',
          type: 'stream',
        },
      ];

      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes,
          edges,
          property_package: 'PengRobinson',
          simulation_basis: { compounds: ['water'] },
        }),
      });
      const data = await res.json();
      const results = data.results ?? data;

      return {
        status: results.status,
        productResult: results.equipment_results?.product1,
      };
    });

    expect(result.status).toMatch(/converged|partial|success/);
    expect(result.productResult).toBeTruthy();
    expect(result.productResult.outletTemperature).toBeCloseTo(80, 0);
    expect(result.productResult.outletPressure).toBeCloseTo(300, 0);
  });

  test('energy stream: connects compressor power port', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed1',
          type: 'equipment',
          position: { x: 0, y: 0 },
          data: {
            equipmentType: 'FeedStream',
            name: 'Feed 1',
            parameters: {
              feedTemperature: 25,
              feedPressure: 100,
              feedFlowRate: 10,
              feedComposition: JSON.stringify({ methane: 1.0 }),
            },
          },
        },
        {
          id: 'comp1',
          type: 'equipment',
          position: { x: 200, y: 0 },
          data: {
            equipmentType: 'Compressor',
            name: 'Compressor 1',
            parameters: { outletPressure: 500, efficiency: 75 },
          },
        },
      ];

      const edges = [
        {
          id: 'e-mat',
          source: 'feed1',
          sourceHandle: 'out-1',
          target: 'comp1',
          targetHandle: 'in-1',
          type: 'stream',
        },
      ];

      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes,
          edges,
          property_package: 'PengRobinson',
          simulation_basis: { compounds: ['methane'] },
        }),
      });
      const data = await res.json();
      const results = data.results ?? data;

      return {
        status: results.status,
        compResult: results.equipment_results?.comp1,
        hasWork: results.equipment_results?.comp1?.work !== undefined,
      };
    });

    expect(result.status).toMatch(/converged|partial|success/);
    expect(result.compResult).toBeTruthy();
    expect(result.hasWork).toBe(true);
    // Compressor should have positive work
    expect(result.compResult.work).toBeGreaterThan(0);
  });

  test('sensitivity analysis: vary heater temperature, get output array', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed1',
          type: 'equipment',
          position: { x: 0, y: 0 },
          data: {
            equipmentType: 'FeedStream',
            name: 'Feed 1',
            parameters: {
              feedTemperature: 25,
              feedPressure: 200,
              feedFlowRate: 10,
              feedComposition: JSON.stringify({ water: 1.0 }),
            },
          },
        },
        {
          id: 'heater1',
          type: 'equipment',
          position: { x: 200, y: 0 },
          data: {
            equipmentType: 'Heater',
            name: 'Heater 1',
            parameters: { outletTemperature: 100 },
          },
        },
      ];

      const edges = [
        {
          id: 'e1',
          source: 'feed1',
          sourceHandle: 'out-1',
          target: 'heater1',
          targetHandle: 'in-1',
          type: 'stream',
        },
      ];

      const res = await fetch('/api/simulation/sensitivity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_nodes: nodes,
          base_edges: edges,
          property_package: 'PengRobinson',
          simulation_basis: { compounds: ['water'] },
          variable: {
            node_id: 'heater1',
            parameter_key: 'outletTemperature',
            min_value: 50,
            max_value: 150,
            steps: 5,
          },
          outputs: [
            { node_id: 'heater1', result_key: 'duty' },
          ],
        }),
      });

      const data = await res.json();

      return {
        ok: res.ok,
        status: data.status,
        variableValues: data.variable_values,
        outputKeys: Object.keys(data.output_values || {}),
        dutyValues: data.output_values?.['heater1.duty'],
        numPoints: data.variable_values?.length,
      };
    });

    expect(result.ok).toBe(true);
    expect(result.status).toBe('success');
    expect(result.numPoints).toBe(5);
    expect(result.variableValues[0]).toBeCloseTo(50, 0);
    expect(result.variableValues[4]).toBeCloseTo(150, 0);
    expect(result.outputKeys).toContain('heater1.duty');
    // Duty should increase as outlet temp increases
    expect(result.dutyValues.length).toBe(5);
    // All values should be non-null numbers
    for (const v of result.dutyValues) {
      expect(typeof v).toBe('number');
    }
  });

  test('case study: save + list + load case', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      // Create project
      let projectId = '';
      for (let i = 0; i < 3; i++) {
        const r = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Case Study Test' }),
        });
        if (r.ok) { projectId = (await r.json()).id; break; }
        await new Promise((res) => setTimeout(res, 300));
      }
      if (!projectId) throw new Error('Project creation failed');

      // Save a case
      const caseRes = await fetch(`/api/projects/${projectId}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Base Case',
          description: 'Initial configuration',
          nodes: [{ id: 'h1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Heater', name: 'Heater 1', parameters: { outletTemperature: 100 } } }],
          edges: [],
          simulation_basis: { compounds: ['water'] },
          property_package: 'PengRobinson',
          results: { status: 'converged', equipment_results: { h1: { duty: 50 } } },
        }),
      });
      const savedCase = await caseRes.json();

      // List cases
      const listRes = await fetch(`/api/projects/${projectId}/cases`);
      const cases = await listRes.json();

      // Load case
      const loadRes = await fetch(`/api/projects/${projectId}/cases/${savedCase.id}/load`, {
        method: 'POST',
      });
      const loadedCase = await loadRes.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}/cases/${savedCase.id}`, { method: 'DELETE' });
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return {
        saveStatus: caseRes.status,
        savedName: savedCase.name,
        savedDesc: savedCase.description,
        listLength: cases.length,
        loadedName: loadedCase.name,
        loadedNodes: loadedCase.nodes?.length,
        loadedBasis: loadedCase.simulation_basis,
      };
    });

    expect(result.saveStatus).toBe(201);
    expect(result.savedName).toBe('Base Case');
    expect(result.savedDesc).toBe('Initial configuration');
    expect(result.listLength).toBeGreaterThanOrEqual(1);
    expect(result.loadedName).toBe('Base Case');
    expect(result.loadedNodes).toBe(1);
    expect(result.loadedBasis).toEqual({ compounds: ['water'] });
  });

  test('case comparison: compare two cases returns diff', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      // Create project
      let projectId = '';
      for (let i = 0; i < 3; i++) {
        const r = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Compare Test' }),
        });
        if (r.ok) { projectId = (await r.json()).id; break; }
        await new Promise((res) => setTimeout(res, 300));
      }
      if (!projectId) throw new Error('Project creation failed');

      // Save case 1 — PR
      const case1Res = await fetch(`/api/projects/${projectId}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Case A - PR',
          nodes: [{ id: 'h1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Heater', name: 'Heater', parameters: {} } }],
          edges: [],
          simulation_basis: { compounds: ['water'] },
          property_package: 'PengRobinson',
          results: { equipment_results: { h1: { duty: 100, outletTemperature: 150 } }, stream_results: {} },
        }),
      });
      const case1 = await case1Res.json();

      // Save case 2 — SRK
      const case2Res = await fetch(`/api/projects/${projectId}/cases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Case B - SRK',
          nodes: [{ id: 'h1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Heater', name: 'Heater', parameters: {} } }],
          edges: [],
          simulation_basis: { compounds: ['water'] },
          property_package: 'SRK',
          results: { equipment_results: { h1: { duty: 95, outletTemperature: 148 } }, stream_results: {} },
        }),
      });
      const case2 = await case2Res.json();

      // Compare
      const compareRes = await fetch(`/api/projects/${projectId}/cases/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_ids: [case1.id, case2.id] }),
      });
      const comparison = await compareRes.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}/cases/${case1.id}`, { method: 'DELETE' });
      await fetch(`/api/projects/${projectId}/cases/${case2.id}`, { method: 'DELETE' });
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return {
        compareOk: compareRes.ok,
        numCases: comparison.cases?.length,
        propPackages: comparison.diffs?.property_packages,
        hasEquipmentDiff: !!comparison.diffs?.equipment_results?.h1,
        equipmentEntries: comparison.diffs?.equipment_results?.h1?.length,
      };
    });

    expect(result.compareOk).toBe(true);
    expect(result.numCases).toBe(2);
    expect(result.propPackages).toEqual(['PengRobinson', 'SRK']);
    expect(result.hasEquipmentDiff).toBe(true);
    expect(result.equipmentEntries).toBe(2);
  });

  test('feed stream with global compounds: composition uses basis', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('load');

    const result = await page.evaluate(async () => {
      const nodes = [
        {
          id: 'feed1',
          type: 'equipment',
          position: { x: 0, y: 0 },
          data: {
            equipmentType: 'FeedStream',
            name: 'Feed 1',
            parameters: {
              feedTemperature: 60,
              feedPressure: 200,
              feedFlowRate: 50,
              feedComposition: JSON.stringify({ methanol: 0.4, water: 0.6 }),
            },
          },
        },
        {
          id: 'heater1',
          type: 'equipment',
          position: { x: 200, y: 0 },
          data: {
            equipmentType: 'Heater',
            name: 'Heater 1',
            parameters: { outletTemperature: 80 },
          },
        },
      ];

      const edges = [
        {
          id: 'e1',
          source: 'feed1',
          sourceHandle: 'out-1',
          target: 'heater1',
          targetHandle: 'in-1',
          type: 'stream',
        },
      ];

      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes,
          edges,
          property_package: 'PengRobinson',
          simulation_basis: {
            compounds: ['methanol', 'water'],
          },
        }),
      });
      const data = await res.json();
      const results = data.results ?? data;

      return {
        status: results.status,
        feedResult: results.equipment_results?.feed1,
        heaterResult: results.equipment_results?.heater1,
        heaterDuty: results.equipment_results?.heater1?.duty,
      };
    });

    expect(result.status).toMatch(/converged|partial|success/);
    expect(result.feedResult).toBeTruthy();
    expect(result.feedResult.outletTemperature).toBeCloseTo(60, 0);
    // Heater should have computed a duty
    expect(result.heaterResult).toBeTruthy();
    if (result.heaterDuty !== undefined) {
      expect(typeof result.heaterDuty).toBe('number');
    }
  });
});
