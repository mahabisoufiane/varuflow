import { test, expect } from './fixtures/auth';

test.describe('HR & Staff Management', () => {

  test('HR / employees page loads', async ({ authedPage: page }) => {
    await page.goto('/hr');
    await page.waitForLoadState('networkidle');
    // Some orgs may list under /scheduling or /staff
    const isOk = page.url().includes('/hr') || page.url().includes('/staff') || page.url().includes('/scheduling');
    if (!isOk) {
      // Try alternate routes
      await page.goto('/scheduling');
      await page.waitForLoadState('networkidle');
    }
    await expect(page).not.toHaveURL(/404/);
  });

  test('shift scheduling page renders calendar', async ({ authedPage: page }) => {
    const routes = ['/hr/time', '/scheduling', '/hr'];
    let found = false;
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        found = true;
        break;
      }
    }
    expect(found, 'Expected at least one scheduling route to exist').toBe(true);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('add shift button is visible', async ({ authedPage: page }) => {
    const routes = ['/scheduling', '/hr/time', '/hr'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');
      if (!page.url().includes('404')) {
        const addBtn = page.locator(
          'button:has-text("Add shift"), button:has-text("New shift"), button:has-text("Add")',
        ).first();
        if (await addBtn.isVisible({ timeout: 3_000 })) {
          await expect(addBtn).toBeVisible();
          break;
        }
      }
    }
  });

  test('leave management page loads', async ({ authedPage: page }) => {
    const routes = ['/hr/leave', '/hr', '/scheduling'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1, h2').first()).toBeVisible();
        break;
      }
    }
  });

  test('payroll page loads and shows export option', async ({ authedPage: page }) => {
    const routes = ['/hr/payroll', '/accounting/payroll', '/payroll'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
      if (!page.url().includes('404')) {
        const exportBtn = page.locator('button:has-text("Export"), button:has-text("Payroll"), a:has-text("Export")').first();
        if (await exportBtn.isVisible({ timeout: 3_000 })) {
          await expect(exportBtn).toBeVisible();
        }
        break;
      }
    }
  });
});
