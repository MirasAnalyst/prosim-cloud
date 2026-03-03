import { test, expect } from '@playwright/test';

test('dark/light theme toggle', async ({ page }) => {
  await page.goto('/app');
  await page.waitForLoadState('networkidle');

  // Default should be dark
  const html = page.locator('html');
  await expect(html).toHaveClass(/dark/);

  // Find and click the theme toggle button
  const toggleBtn = page.locator('button[title="Switch to Light Mode"]');
  await toggleBtn.click();

  // Should switch to light
  await expect(html).not.toHaveClass(/dark/);

  // Click again to go back to dark
  const toggleBtnLight = page.locator('button[title="Switch to Dark Mode"]');
  await toggleBtnLight.click();
  await expect(html).toHaveClass(/dark/);
});
