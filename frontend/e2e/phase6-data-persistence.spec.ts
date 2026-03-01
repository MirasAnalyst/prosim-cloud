import { test, expect } from '@playwright/test';

// Helper to create project with retry for transient DB pool exhaustion under parallel test load
async function createProject(name: string): Promise<{ id: string; [k: string]: unknown }> {
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (res.ok) return res.json();
    if (attempt < 2) await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
  }
  throw new Error(`Failed to create project "${name}" after 3 attempts`);
}

test.describe('Phase 6: Data & Persistence', () => {

  test('version create + list API', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      // Retry helper for project creation under concurrent test load
      async function createProj(name: string) {
        for (let i = 0; i < 3; i++) {
          const r = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          });
          if (r.ok) return r.json();
          await new Promise((resolve) => setTimeout(resolve, 300 * (i + 1)));
        }
        throw new Error('Failed to create project after 3 attempts');
      }

      const project = await createProj('Version Test Project');
      const projectId = project.id;

      // Save some flowsheet data
      await fetch(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{ id: 'h1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Heater', name: 'Heater 1', parameters: {} } }],
          edges: [],
        }),
      });

      // Create a version
      const versionRes = await fetch(`/api/projects/${projectId}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: 'Initial snapshot' }),
      });
      const version = await versionRes.json();

      // List versions
      const listRes = await fetch(`/api/projects/${projectId}/versions`);
      const versions = await listRes.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return { version, versions, versionStatus: versionRes.status };
    });

    expect(result.versionStatus).toBe(201);
    expect(result.version.version_number).toBe(1);
    expect(result.version.label).toBe('Initial snapshot');
    expect(result.versions.length).toBeGreaterThanOrEqual(1);
  });

  test('export flowsheet as JSON (valid structure)', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      async function createProj(name: string) {
        for (let i = 0; i < 3; i++) {
          const r = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          });
          if (r.ok) return r.json();
          await new Promise((resolve) => setTimeout(resolve, 300 * (i + 1)));
        }
        throw new Error('Failed to create project after 3 attempts');
      }

      const project = await createProj('Export Test');
      const projectId = project.id;

      await fetch(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{ id: 'h1', type: 'equipment', position: { x: 100, y: 100 }, data: { equipmentType: 'Heater', name: 'H1', parameters: {} } }],
          edges: [],
        }),
      });

      // Export as JSON
      const exportRes = await fetch(`/api/projects/${projectId}/export?format=json`);
      const exportData = await exportRes.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return { exportData, status: exportRes.status };
    });

    expect(result.status).toBe(200);
    expect(result.exportData.format).toBe('prosim-cloud');
    expect(result.exportData.version).toBe('1.0');
    expect(result.exportData.flowsheet).toBeDefined();
    expect(result.exportData.flowsheet.nodes.length).toBe(1);
  });

  test('import endpoint accepts file upload', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      async function createProj(name: string) {
        for (let i = 0; i < 3; i++) {
          const r = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          });
          if (r.ok) return r.json();
          await new Promise((resolve) => setTimeout(resolve, 300 * (i + 1)));
        }
        throw new Error('Failed to create project after 3 attempts');
      }

      const project = await createProj('Import Test');
      const projectId = project.id;

      // Create a JSON file to import
      const importData = JSON.stringify({
        format: 'prosim-cloud',
        version: '1.0',
        flowsheet: {
          nodes: [
            { id: 'n1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Mixer', name: 'Mixer', parameters: {} } },
            { id: 'n2', type: 'equipment', position: { x: 200, y: 0 }, data: { equipmentType: 'Heater', name: 'Heater', parameters: {} } },
          ],
          edges: [{ id: 'e1', source: 'n1', target: 'n2', sourceHandle: 'out-0', targetHandle: 'in-0' }],
        },
      });

      const blob = new Blob([importData], { type: 'application/json' });
      const formData = new FormData();
      formData.append('file', blob, 'test.json');

      const importRes = await fetch(`/api/projects/${projectId}/import`, {
        method: 'POST',
        body: formData,
      });
      const importResult = await importRes.json();

      // Cleanup
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });

      return { importResult, status: importRes.status };
    });

    expect(result.status).toBe(200);
    expect(result.importResult.nodes_imported).toBe(2);
    expect(result.importResult.edges_imported).toBe(1);
  });

  test('simulation results export CSV', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const mockResults = {
        stream_results: {
          's1': { temperature: 80, pressure: 101.325, flowRate: 1.0, vapor_fraction: 0.0, composition: { water: 1.0 } },
        },
        equipment_results: {
          'h1': { type: 'Heater', duty: 230.5, outlet_temperature: 80 },
        },
        convergence_info: { iterations: 1, converged: true, error: 0 },
      };

      const res = await fetch('/api/simulation/export?format=csv', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mockResults),
      });

      const contentType = res.headers.get('content-type') || '';
      const text = await res.text();

      return { status: res.status, contentType, hasStreamResults: text.includes('Stream Results'), hasEquipmentResults: text.includes('Equipment Results') };
    });

    expect(result.status).toBe(200);
    expect(result.contentType).toContain('text/csv');
    expect(result.hasStreamResults).toBe(true);
    expect(result.hasEquipmentResults).toBe(true);
  });

  test('PFD export buttons exist in UI', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Find the Export dropdown button by its title
    const exportButton = page.locator('button[title="Export"]');
    await expect(exportButton).toBeVisible();

    // Click to open dropdown
    await exportButton.click();

    // Verify PFD export options
    await expect(page.locator('text=SVG').first()).toBeVisible();
    await expect(page.locator('text=PNG').first()).toBeVisible();
    await expect(page.locator('text=PDF').first()).toBeVisible();
  });

  test('validation catches orphan edges', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/flowsheet/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [
            { id: 'n1', name: 'Heater', type: 'Heater', parameters: {} },
          ],
          edges: [
            { id: 'e1', source: 'n1', target: 'nonexistent-node' },
          ],
        }),
      });
      return res.json();
    });

    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors.some((e: string) => e.includes('nonexistent'))).toBe(true);
  });

  test('backup/restore roundtrip', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      async function createProj(name: string) {
        for (let i = 0; i < 3; i++) {
          const r = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          });
          if (r.ok) return r.json();
          await new Promise((resolve) => setTimeout(resolve, 300 * (i + 1)));
        }
        throw new Error('Failed to create project after 3 attempts');
      }

      const project = await createProj('Backup Test Project');
      const projectId = project.id;

      // Save flowsheet data
      await fetch(`/api/projects/${projectId}/flowsheet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{ id: 'b1', type: 'equipment', position: { x: 0, y: 0 }, data: { equipmentType: 'Cooler', name: 'Cooler 1', parameters: {} } }],
          edges: [],
        }),
      });

      // Download backup
      const backupRes = await fetch(`/api/projects/${projectId}/backup`);
      const backupData = await backupRes.json();

      // Restore from backup
      const restoreRes = await fetch('/api/projects/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backupData),
      });
      const restoredProject = await restoreRes.json();

      // Verify restored project
      const restoredFlowsheetRes = await fetch(`/api/projects/${restoredProject.id}/flowsheet`);
      const restoredFlowsheet = await restoredFlowsheetRes.json();

      // Cleanup both projects
      await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
      await fetch(`/api/projects/${restoredProject.id}`, { method: 'DELETE' });

      return {
        backupFormat: backupData.format,
        backupProjectName: backupData.project.name,
        restoredName: restoredProject.name,
        restoredNodesCount: restoredFlowsheet.nodes?.length ?? 0,
        restoreStatus: restoreRes.status,
      };
    });

    expect(result.backupFormat).toBe('prosim-backup');
    expect(result.backupProjectName).toBe('Backup Test Project');
    expect(result.restoredName).toBe('Backup Test Project');
    expect(result.restoredNodesCount).toBe(1);
    expect(result.restoreStatus).toBe(201);
  });

});
