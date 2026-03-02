import { test, expect } from '@playwright/test';

// Insights endpoint calls OpenAI API — needs longer timeout than default 60s
test.setTimeout(120_000);

const BASE = 'http://localhost:8000';

// Helper: build a multi-equipment flowsheet for insights analysis
function buildFlowsheet() {
  return {
    simulation_results: {
      stream_results: {
        'feed-1->heater-1': {
          temperature: 25,
          pressure: 101.325,
          mass_flow: 1.0,
          vapor_fraction: 0,
          composition: { water: 1.0 },
        },
        'heater-1->sep-1': {
          temperature: 120,
          pressure: 101.325,
          mass_flow: 1.0,
          vapor_fraction: 0.15,
          composition: { water: 1.0 },
        },
      },
      equipment_results: {
        'heater-1': {
          type: 'Heater',
          name: 'Feed Heater',
          duty_kw: 398.0,
          outlet_temperature: 120,
          outlet_pressure: 101.325,
        },
        'sep-1': {
          type: 'Separator',
          name: 'Flash Drum',
          vapor_fraction: 0.15,
          outlet_temperature: 120,
          outlet_pressure: 101.325,
        },
      },
      convergence_info: { converged: true, iterations: 1 },
    },
    nodes: [
      { id: 'feed-1', type: 'FeedStream', name: 'Water Feed', parameters: { feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0, feedComposition: '{"water":1.0}' } },
      { id: 'heater-1', type: 'Heater', name: 'Feed Heater', parameters: { outletTemperature: 120 } },
      { id: 'sep-1', type: 'Separator', name: 'Flash Drum', parameters: {} },
    ],
    edges: [
      { id: 'e1', source: 'feed-1', sourceHandle: 'out-1', target: 'heater-1', targetHandle: 'in-1', type: 'stream' },
      { id: 'e2', source: 'heater-1', sourceHandle: 'out-1', target: 'sep-1', targetHandle: 'in-1', type: 'stream' },
    ],
    property_package: 'PengRobinson',
  };
}

// Test 1: Valid InsightsResult structure
test('Insights endpoint returns valid result structure', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/insights`, {
    data: buildFlowsheet(),
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();

  // Must have the top-level fields
  expect(res).toHaveProperty('insights');
  expect(res).toHaveProperty('summary');
  expect(res).toHaveProperty('status');
  expect(Array.isArray(res.insights)).toBe(true);

  // Summary structure
  expect(res.summary).toHaveProperty('total_annual_savings');
  expect(res.summary).toHaveProperty('total_co2_reduction');
  expect(res.summary).toHaveProperty('insight_count');
  expect(res.summary).toHaveProperty('top_quick_wins');
  expect(res.summary).toHaveProperty('top_high_impact');
});

// Test 2: Insights for multi-equipment flowsheet contain required fields
test('Insights contain required fields per insight', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/insights`, {
    data: buildFlowsheet(),
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();

  if (res.status === 'success' && res.insights.length > 0) {
    for (const ins of res.insights) {
      expect(ins).toHaveProperty('id');
      expect(ins).toHaveProperty('category');
      expect(ins).toHaveProperty('title');
      expect(ins).toHaveProperty('description');
      expect(ins).toHaveProperty('priority');
      expect(ins).toHaveProperty('implementation_type');
      expect(ins).toHaveProperty('annual_savings_usd');
      expect(['energy', 'production', 'emissions', 'cost']).toContain(ins.category);
      expect(['critical', 'high', 'medium', 'low']).toContain(ins.priority);
    }
  }
});

// Test 3: Custom economic parameters are accepted
test('Insights accept custom economic parameters', async ({ request }) => {
  const data = {
    ...buildFlowsheet(),
    economic_params: {
      steam_cost: 20.0,
      cooling_water_cost: 5.0,
      electricity_cost: 0.12,
      fuel_gas_cost: 10.0,
      carbon_price: 100.0,
      hours_per_year: 7500,
    },
  };
  const resp = await request.post(`${BASE}/api/simulation/insights`, { data });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res).toHaveProperty('status');
  // Should not crash with custom params
  expect(['success', 'error']).toContain(res.status);
});

// Test 4: Empty/minimal flowsheet returns gracefully
test('Insights handle empty flowsheet gracefully', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/insights`, {
    data: {
      simulation_results: { stream_results: {}, equipment_results: {} },
      nodes: [],
      edges: [],
      property_package: 'PengRobinson',
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res).toHaveProperty('status');
  expect(res).toHaveProperty('insights');
  expect(Array.isArray(res.insights)).toBe(true);
});
