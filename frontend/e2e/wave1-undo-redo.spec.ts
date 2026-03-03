import { test, expect } from '@playwright/test';

test.describe('Wave 1: Undo/Redo + Copy/Paste', () => {
  test('undo and redo buttons are visible and respond to state', async ({ page }) => {
    await page.goto('/app');
    await page.waitForLoadState('networkidle');

    // Verify undo/redo buttons exist
    const undoButton = page.locator('button[title="Undo (Ctrl+Z)"]');
    await expect(undoButton).toBeVisible();

    const redoButton = page.locator('button[title="Redo (Ctrl+Shift+Z)"]');
    await expect(redoButton).toBeVisible();

    // Initially both should be disabled (no history)
    await expect(undoButton).toBeDisabled();
    await expect(redoButton).toBeDisabled();
  });
});
