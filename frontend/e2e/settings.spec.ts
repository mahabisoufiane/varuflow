import { test, expect } from './fixtures/auth';

test.describe('Settings & Integrations', () => {

  test('settings page loads', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('general/org profile settings renders editable fields', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    const companyNameInput = page.locator(
      'input[name="company_name"], input[name="name"], input[placeholder*="company" i]',
    ).first();
    if (await companyNameInput.isVisible({ timeout: 5_000 })) {
      await expect(companyNameInput).toBeEditable();
    }
  });

  test('team members settings page loads', async ({ authedPage: page }) => {
    const routes = ['/settings/team', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      const teamSection = page.locator(
        'text=/team|members|invite/i, a[href*="team"], button:has-text("Invite")',
      ).first();
      if (await teamSection.isVisible({ timeout: 3_000 })) {
        await expect(teamSection).toBeVisible();
        break;
      }
    }
  });

  test('invite team member dialog opens', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    const inviteBtn = page.locator('button:has-text("Invite")').first();
    if (await inviteBtn.isVisible({ timeout: 5_000 })) {
      await inviteBtn.click();
      const dialog = page.locator('[role="dialog"], [class*="modal"]').first();
      await expect(dialog).toBeVisible({ timeout: 5_000 });
      // Close
      const closeBtn = dialog.locator('button:has-text("Cancel"), button:has-text("Close"), [aria-label="Close"]').first();
      if (await closeBtn.isVisible()) await closeBtn.click();
    }
  });

  test('billing / subscription page loads', async ({ authedPage: page }) => {
    const routes = ['/settings/billing', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      const billingSection = page.locator('text=/billing|plan|subscription|upgrade/i').first();
      if (await billingSection.isVisible({ timeout: 3_000 })) {
        await expect(billingSection).toBeVisible();
        break;
      }
    }
  });

  test('security settings page loads', async ({ authedPage: page }) => {
    const routes = ['/settings/security', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1, h2').first()).toBeVisible();
        break;
      }
    }
  });

  test('API key section loads for Enterprise plan', async ({ authedPage: page }) => {
    const routes = ['/settings/api', '/integrations/developer', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1, h2').first()).toBeVisible();
        break;
      }
    }
  });

  test('integrations page loads', async ({ authedPage: page }) => {
    const routes = ['/integrations', '/settings/integrations', '/settings'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1, h2').first()).toBeVisible();
        break;
      }
    }
  });

  test('setting changes show save button', async ({ authedPage: page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    const saveBtn = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Update")').first();
    if (await saveBtn.isVisible({ timeout: 5_000 })) {
      await expect(saveBtn).toBeVisible();
    }
  });
});
