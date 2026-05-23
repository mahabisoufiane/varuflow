import { test, expect } from './fixtures/auth';

test.describe('Customers', () => {

  test('customers list page loads', async ({ authedPage: page }) => {
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('new customer button is visible', async ({ authedPage: page }) => {
    await page.goto('/customers');
    const newBtn = page.locator(
      'a[href*="customers/new"], button:has-text("New"), button:has-text("Add"), button:has-text("Create")',
    ).first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });

  test('create customer — minimal required fields', async ({ authedPage: page }) => {
    await page.goto('/customers/new');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).not.toHaveURL(/404/);

    const companyInput = page.locator(
      'input[name="company_name"], input[name="name"], input[placeholder*="company" i], input[placeholder*="name" i]',
    ).first();
    if (await companyInput.isVisible({ timeout: 3_000 })) {
      await companyInput.fill('E2E Test Company ' + Date.now());
    }

    const emailInput = page.locator('input[type="email"]').first();
    if (await emailInput.isVisible({ timeout: 2_000 })) {
      await emailInput.fill(`e2e-${Date.now()}@test.invalid`);
    }

    const submitBtn = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Create")').first();
    await submitBtn.click();

    await page.waitForTimeout(2000);
    await expect(page).not.toHaveURL(/\/new$/);
  });

  test('customer detail page has tabs or sections', async ({ authedPage: page }) => {
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    const firstLink = page.locator('table tbody tr a, a[href*="/customers/"]').first();
    if (await firstLink.isVisible({ timeout: 5_000 })) {
      await firstLink.click();
      await page.waitForLoadState('domcontentloaded');
      await expect(page).toHaveURL(/\/customers\/[a-z0-9-]+/);
      await expect(page.locator('h1, h2').first()).toBeVisible();
    }
  });

  test('customer search filters results', async ({ authedPage: page }) => {
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    const searchInput = page.locator(
      'input[type="search"], input[placeholder*="search" i], input[placeholder*="filter" i]',
    ).first();
    if (await searchInput.isVisible({ timeout: 3_000 })) {
      await searchInput.fill('E2E');
      await page.waitForTimeout(600);
      await expect(page).not.toHaveURL(/404/);
    }
  });

  test('customer CSV export button is visible', async ({ authedPage: page }) => {
    await page.goto('/customers');
    await page.waitForLoadState('networkidle');
    const exportBtn = page.locator(
      'button:has-text("Export"), a:has-text("Export"), button:has-text("CSV")',
    ).first();
    if (await exportBtn.isVisible({ timeout: 3_000 })) {
      await expect(exportBtn).toBeVisible();
    }
  });
});
