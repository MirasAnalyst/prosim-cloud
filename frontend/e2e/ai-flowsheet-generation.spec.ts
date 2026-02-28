import { test, expect } from '@playwright/test';

/**
 * Phase 4 AI Flowsheet Generation E2E Tests
 *
 * Tests the full flow: send a natural language prompt to the AI agent,
 * verify the response contains a flowsheet_action, and verify the
 * flowsheet is rendered on the canvas.
 */

test.describe('AI Flowsheet Generation', () => {
  test('API returns flowsheet_action with equipment and connections', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Call the agent API directly from the browser
    const result = await page.evaluate(async () => {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            {
              role: 'user',
              content:
                'Build a natural gas plant: feed is 90% methane 10% ethane at 25C, 3000 kPa, 5 kg/s. Heat to 200C, then separate, then compress the vapor to 5000 kPa at 80% efficiency',
            },
          ],
        }),
      });
      return res.json();
    });

    // Verify flowsheet_action exists
    expect(result.flowsheet_action).toBeTruthy();
    const action = result.flowsheet_action;

    // Verify 3 equipment items
    expect(action.equipment).toHaveLength(3);
    const types = action.equipment.map((eq: any) => eq.type);
    expect(types).toContain('Heater');
    expect(types).toContain('Separator');
    expect(types).toContain('Compressor');

    // Verify 2 connections
    expect(action.connections).toHaveLength(2);

    // Verify correct port IDs: separator out-1 is vapor
    const sepToComp = action.connections.find(
      (c: any) => {
        const sepId = action.equipment.find((e: any) => e.type === 'Separator')?.id;
        return c.source_id === sepId;
      }
    );
    expect(sepToComp).toBeTruthy();
    expect(sepToComp.source_port).toBe('out-1'); // vapor port

    // Verify heater has feed parameters
    const heater = action.equipment.find((eq: any) => eq.type === 'Heater');
    expect(heater.parameters.outletTemperature).toBe(200);
    expect(heater.parameters.feedFlowRate).toBe(5);
    expect(heater.parameters.feedPressure).toBe(3000);

    // Verify compressor has outlet pressure and efficiency
    const compressor = action.equipment.find((eq: any) => eq.type === 'Compressor');
    expect(compressor.parameters.outletPressure).toBe(5000);
    expect(compressor.parameters.efficiency).toBe(80);

    // Verify text explanation exists
    expect(result.message.content.length).toBeGreaterThan(10);
  });

  test('plain text question returns no flowsheet_action', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const result = await page.evaluate(async () => {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'What is Peng-Robinson equation of state?' }],
        }),
      });
      return res.json();
    });

    expect(result.flowsheet_action).toBeNull();
    expect(result.message.content.length).toBeGreaterThan(50);
    expect(result.message.role).toBe('assistant');
  });

  test('AI-generated flowsheet renders nodes on canvas via UI', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open the AI panel — button has text "AI" with Bot icon in TopNav
    const aiToggle = page.locator('button', { hasText: 'AI' }).first();
    await aiToggle.click();

    // Wait for the AI Assistant panel to appear
    await expect(page.getByRole('heading', { name: 'AI Assistant' })).toBeVisible({ timeout: 5000 });

    // Type a prompt into the chat input
    const input = page.locator('input[type="text"], textarea').last();
    await input.fill('Build a simple plant with a heater to 150C then a separator');
    await input.press('Enter');

    // Wait for the AI response with green badge (AI takes time)
    const badge = page.locator('text=/Created \\d+ equipment/');
    await expect(badge).toBeVisible({ timeout: 60000 });

    // Verify nodes appeared on the canvas
    const nodes = page.locator('.react-flow__node');
    await expect(nodes.first()).toBeVisible({ timeout: 5000 });
    const nodeCount = await nodes.count();
    expect(nodeCount).toBeGreaterThanOrEqual(2); // At least heater + separator
  });
});
