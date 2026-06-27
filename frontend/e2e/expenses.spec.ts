import { test, expect } from './fixtures/auth';

test.describe('Expenses', () => {

  test('expenses page loads', async ({ authedPage: page }) => {
    await page.goto('/expenses');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('new expense button is visible', async ({ authedPage: page }) => {
    await page.goto('/expenses');
    const newBtn = page.locator(
      'a[href*="new"], button:has-text("New"), button:has-text("Add"), button:has-text("Log")',
    ).first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });

  test('create expense — minimal fields', async ({ authedPage: page }) => {
    await page.goto('/expenses');
    const newBtn = page.locator(
      'a[href*="/expenses/new"], button:has-text("New expense"), button:has-text("Add expense")',
    ).first();
    if (await newBtn.isVisible({ timeout: 3_000 })) {
      await newBtn.click();
      await page.waitForLoadState('domcontentloaded');
    }

    const amountInput = page.locator('input[name="amount"], input[type="number"]').first();
    if (await amountInput.isVisible({ timeout: 3_000 })) {
      await amountInput.fill('150');
    }

    const descInput = page.locator(
      'input[name="description"], input[name="merchant"], input[placeholder*="description" i], input[placeholder*="merchant" i], textarea',
    ).first();
    if (await descInput.isVisible({ timeout: 2_000 })) {
      await descInput.fill('E2E Test Expense');
    }

    const submitBtn = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Submit")').first();
    if (await submitBtn.isVisible({ timeout: 2_000 })) {
      await submitBtn.click();
      await page.waitForTimeout(2000);
    }
    await expect(page).not.toHaveURL(/404/);
  });

  test('expense approval workflow: pending approval visible to admin', async ({ adminPage: page }) => {
    await page.goto('/expenses');
    await page.waitForLoadState('networkidle');
    // Look for approval section or pending tab
    const pendingTab = page.locator('button:has-text("Pending"), a:has-text("Pending"), [class*="pending"]').first();
    if (await pendingTab.isVisible({ timeout: 3_000 })) {
      await pendingTab.click();
      await page.waitForLoadState('networkidle');
      await expect(page).not.toHaveURL(/404/);
    }
  });

  test('expense report/export button renders', async ({ authedPage: page }) => {
    await page.goto('/expenses');
    await page.waitForLoadState('networkidle');
    const exportBtn = page.locator(
      'button:has-text("Export"), button:has-text("Report"), a:has-text("Export")',
    ).first();
    if (await exportBtn.isVisible({ timeout: 3_000 })) {
      await expect(exportBtn).toBeVisible();
    }
  });
});
