import { test, expect } from '@playwright/test';

test.describe('Wave 1: Convergence Settings', () => {
  test('convergence_settings accepted by API', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // POST with convergence_settings — verify the API accepts and uses them
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nodes: [{
            id: 'h1', type: 'Heater', name: 'Heater',
            parameters: {
              feedTemperature: 25, feedPressure: 101.325, feedFlowRate: 1.0,
              outletTemperature: 80, feedComposition: '{"water": 1.0}',
            },
          }],
          edges: [],
          property_package: 'PengRobinson',
          convergence_settings: { max_iter: 5, tolerance: 1e-4, damping: 0.5 },
        }),
      });
      return res.json();
    });

    expect(result.results?.status).not.toBe('error');
    expect(result.results?.convergence_info?.iterations).toBeLessThanOrEqual(5);
  });

  test('convergence settings gear icon visible in TopNav', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // The settings gear button should be visible
    const gearButton = page.locator('button[title="Convergence Settings"]');
    await expect(gearButton).toBeVisible();

    // Click it to open the popover
    await gearButton.click();

    // Verify the popover content
    await expect(page.locator('text=Max Iterations')).toBeVisible();
    await expect(page.locator('text=Tolerance')).toBeVisible();
    await expect(page.locator('text=Damping Factor')).toBeVisible();
  });
});
