import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:8000';

// Helper: build a simple heater flowsheet for API calls
function buildSimpleFlowsheet() {
  return {
    nodes: [
      {
        id: 'feed-1',
        type: 'equipment',
        position: { x: 0, y: 0 },
        data: {
          equipmentType: 'FeedStream',
          name: 'Feed',
          parameters: {
            feedTemperature: 25,
            feedPressure: 101.325,
            feedFlowRate: 1.0,
            feedComposition: JSON.stringify({ water: 1.0 }),
          },
        },
      },
      {
        id: 'heater-1',
        type: 'equipment',
        position: { x: 200, y: 0 },
        data: {
          equipmentType: 'Heater',
          name: 'Heater',
          parameters: { outletTemperature: 80, duty: 0, dutyMode: false },
        },
      },
    ],
    edges: [
      { id: 'e1', source: 'feed-1', target: 'heater-1', sourceHandle: 'out-1', targetHandle: 'in-1' },
    ],
    property_package: 'PengRobinson',
  };
}

// ── Standalone API tests (fast, no simulation engine) ──

// Test 1: Pinch Analysis — streams[] with stream_type auto-detected
test('Pinch analysis returns composite curves', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/pinch`, {
    data: {
      streams: [
        { name: 'H1', supply_temp: 170, target_temp: 60, heat_capacity_flow: 3.0 },
        { name: 'H2', supply_temp: 150, target_temp: 30, heat_capacity_flow: 1.5 },
        { name: 'C1', supply_temp: 20, target_temp: 135, heat_capacity_flow: 2.0 },
        { name: 'C2', supply_temp: 80, target_temp: 140, heat_capacity_flow: 4.0 },
      ],
      dt_min: 10,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.pinch_temperature).toBeDefined();
  expect(res.q_heating_min).toBeGreaterThanOrEqual(0);
  expect(res.q_cooling_min).toBeGreaterThanOrEqual(0);
  expect(res.hot_composite).toBeDefined();
  expect(res.cold_composite).toBeDefined();
});

// Test 2: Relief Valve Sizing API returns orifice selection
test('Relief valve sizing returns orifice selection', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/relief-valve`, {
    data: {
      phase: 'gas',
      scenario: 'blocked_outlet',
      set_pressure: 1000,
      backpressure: 101.325,
      overpressure_pct: 10,
      mass_flow_rate: 5000,
      molecular_weight: 28.97,
      temperature: 25,
      k_ratio: 1.4,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.required_area_mm2).toBeGreaterThan(0);
  expect(res.selected_orifice).toBeDefined();
  expect(typeof res.selected_orifice).toBe('string');
  expect(res.orifice_area_mm2).toBeGreaterThan(0);
});

// Test 3: Control Valve Sizing API returns Cv and percent open
test('Control valve sizing returns Cv', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/control-valve`, {
    data: {
      phase: 'liquid',
      valve_type: 'globe',
      inlet_pressure: 500,
      outlet_pressure: 300,
      temperature: 25,
      volumetric_flow: 10,
      specific_gravity: 1.0,
      pipe_diameter: 0.1,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.calculated_cv).toBeGreaterThan(0);
  expect(res.selected_cv).toBeGreaterThanOrEqual(res.calculated_cv);
  expect(res.percent_open).toBeGreaterThan(0);
  expect(res.percent_open).toBeLessThanOrEqual(100);
});

// Test 4: Pipe Hydraulics standalone API
test('Hydraulics API returns pressure drop breakdown', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/hydraulics`, {
    data: {
      mass_flow_rate: 10,
      density: 1000,
      viscosity: 0.001,
      phase: 'liquid',
      length: 100,
      diameter: 0.1,
      roughness: 0.000045,
      elevation: 5,
      elbows_90: 2,
      tees: 1,
      gate_valves: 1,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.pressure_drop_kpa).toBeGreaterThan(0);
  expect(res.velocity_m_s).toBeGreaterThan(0);
  expect(res.reynolds_number).toBeGreaterThan(0);
  expect(res.flow_regime).toBeDefined();
  expect(res.erosional_velocity_m_s).toBeGreaterThan(0);
});

// Test 5: Emissions API — fuel as FuelInput, equipment_counts as EquipmentCounts
test('Emissions calculation returns CO2e', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/emissions`, {
    data: {
      fuel: { fuel_type: 'natural_gas', consumption: 100 },
      equipment_counts: { valves: 50, pumps: 5, compressors: 2, flanges: 200 },
      carbon_price: 50,
      hours_per_year: 8000,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.total_co2e_tpy).toBeGreaterThan(0);
  expect(res.combustion_co2_tpy).toBeGreaterThan(0);
  expect(res.carbon_cost_annual).toBeGreaterThan(0);
});

// Test 6: Utility Summary — requires simulation_results with equipment_results
test('Utility summary returns cost breakdown', async ({ request }) => {
  const resp = await request.post(`${BASE}/api/simulation/utility`, {
    data: {
      simulation_results: {
        equipment_results: {
          'heater-1': { type: 'Heater', name: 'Heater', duty: 500 },
          'cooler-1': { type: 'Cooler', name: 'Cooler', duty: -300 },
          'pump-1': { type: 'Pump', name: 'Pump', work: 50 },
        },
      },
      costs: {
        steam_cost: 15,
        cooling_water_cost: 3,
        electricity_cost: 0.08,
      },
      hours_per_year: 8000,
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.equipment_utilities).toBeDefined();
  expect(res.equipment_utilities.length).toBeGreaterThan(0);
  expect(res.total_annual_cost).toBeGreaterThan(0);
  expect(res.total_hourly_cost).toBeGreaterThan(0);
});

// ── Simulation engine tests (slower, uses thermo flash) ──

// Test 7: DesignSpec node is recognized — filtered from equipment loop, shows in results with error
test('DesignSpec node filters out of equipment loop', async ({ request }) => {
  const flowsheet = buildSimpleFlowsheet();
  // Add DesignSpec node without triggering the full solver (empty manipulated params)
  (flowsheet.nodes as any[]).push({
    id: 'ds-1',
    type: 'equipment',
    position: { x: 400, y: 0 },
    data: {
      equipmentType: 'DesignSpec',
      name: 'DS-1',
      parameters: {
        targetStreamId: '',
        targetProperty: 'temperature',
        targetValue: 50,
        manipulatedNodeId: '',
        manipulatedParam: '',
        lowerBound: 20,
        upperBound: 200,
        tolerance: 0.1,
      },
    },
  });

  const resp = await request.post(`${BASE}/api/simulation/run`, { data: flowsheet });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const results = body.results ?? body;
  expect(results.equipment_results).toBeDefined();
  // Heater should have normal results
  expect(results.equipment_results['heater-1']).toBeDefined();
  expect(results.equipment_results['heater-1'].duty).toBeDefined();
  // DesignSpec should appear with equipment_type and error (empty target/manipulated)
  const ds = results.equipment_results['ds-1'];
  expect(ds).toBeDefined();
  expect(ds.equipment_type).toBe('DesignSpec');
  expect(ds.error).toBeDefined();
});

// Test 8: PipeSegment calculates pressure drop and velocity (camelCase keys)
test('PipeSegment produces pressure drop and velocity', async ({ request }) => {
  const flowsheet = buildSimpleFlowsheet();
  (flowsheet.nodes as any[]).push({
    id: 'pipe-1',
    type: 'equipment',
    position: { x: 400, y: 0 },
    data: {
      equipmentType: 'PipeSegment',
      name: 'Pipe-1',
      parameters: {
        length: 100,
        diameter: 0.1,
        roughness: 0.000045,
        elevation: 0,
        elbows90: 2,
        tees: 0,
        gateValves: 1,
      },
    },
  });
  (flowsheet.edges as any[]).push({
    id: 'e2',
    source: 'heater-1',
    target: 'pipe-1',
    sourceHandle: 'out-1',
    targetHandle: 'in-1',
  });

  const resp = await request.post(`${BASE}/api/simulation/run`, { data: flowsheet });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const results = body.results ?? body;
  const pipeResult = results.equipment_results?.['pipe-1'];
  expect(pipeResult).toBeDefined();
  // Engine returns camelCase keys
  expect(pipeResult.pressureDrop).toBeDefined();
  expect(pipeResult.velocity).toBeDefined();
  expect(Number(pipeResult.pressureDrop)).toBeGreaterThan(0);
  expect(Number(pipeResult.velocity)).toBeGreaterThan(0);
});

// Test 9: Dynamic Simulation API — base_nodes/base_edges, parameter_key, time_steps
test('Dynamic simulation returns trajectories', async ({ request }) => {
  const flowsheet = buildSimpleFlowsheet();

  // First run a base simulation
  const simResp = await request.post(`${BASE}/api/simulation/run`, { data: flowsheet });
  expect(simResp.ok()).toBeTruthy();

  const resp = await request.post(`${BASE}/api/simulation/dynamic`, {
    data: {
      base_nodes: flowsheet.nodes,
      base_edges: flowsheet.edges,
      property_package: 'PengRobinson',
      disturbances: [
        { node_id: 'feed-1', parameter_key: 'feedTemperature', step_size: 10 },
      ],
      tracked_outputs: [
        { node_id: 'heater-1', result_key: 'duty' },
      ],
      time_horizon: 60,
      time_steps: 20,
      equipment_volumes: { 'heater-1': 5.0 },
    },
  });
  expect(resp.ok()).toBeTruthy();
  const res = await resp.json();
  expect(res.time_values).toBeDefined();
  expect(res.time_values.length).toBeGreaterThanOrEqual(20);
  expect(res.output_trajectories).toBeDefined();
});
