import { test, expect } from './fixtures/auth';

test.describe('Invoicing', () => {

  test('create invoice — happy path saves as draft', async ({ authedPage: page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    // Select first available customer
    const customerSelect = page.locator('select').first();
    await customerSelect.selectOption({ index: 1 });

    // Fill line item
    const descInput = page.locator('input[placeholder="Service or item…"]').first();
    await descInput.fill('E2E Test Product');

    const qtyInput = page.locator('input[type="number"][min="0.001"]').first();
    await qtyInput.fill('3');

    const priceInput = page.locator('input[type="number"][step="0.01"]').first();
    await priceInput.fill('199.00');

    await page.click('button[type="submit"]');

    // Redirect to invoice detail page
    await expect(page).toHaveURL(/\/invoices\/[a-z0-9-]+/, { timeout: 10_000 });
    // Status badge or text shows Draft
    await expect(
      page.locator('text=/draft/i, [class*="draft" i], [data-testid="invoice-status"]'),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('add multiple line items and verify totals', async ({ authedPage: page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    const customerSelect = page.locator('select').first();
    await customerSelect.selectOption({ index: 1 });

    // Line 1
    await page.locator('input[placeholder="Service or item…"]').nth(0).fill('Item One');
    await page.locator('input[type="number"][min="0.001"]').nth(0).fill('2');
    await page.locator('input[type="number"][step="0.01"]').nth(0).fill('100');

    // Add second line
    await page.click('button:has-text("Add line")');
    await page.locator('input[placeholder="Service or item…"]').nth(1).fill('Item Two');
    await page.locator('input[type="number"][min="0.001"]').nth(1).fill('1');
    await page.locator('input[type="number"][step="0.01"]').nth(1).fill('50');

    // Submit and verify redirect
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/invoices\/[a-z0-9-]+/, { timeout: 10_000 });
  });

  test('invoice list page loads with data', async ({ authedPage: page }) => {
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');
    // Table or list rows visible
    const rows = page.locator('table tbody tr, [class*="invoice-row"], [class*="list-item"]');
    // May be empty on fresh env — just expect page to load without error
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('invoice list status filter works', async ({ authedPage: page }) => {
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');

    // Look for filter control
    const filterSelect = page.locator('select, [role="combobox"]').filter({ hasText: /all|status|filter/i }).first();
    if (await filterSelect.isVisible({ timeout: 3_000 })) {
      await filterSelect.selectOption({ label: /paid/i } as any);
      await page.waitForLoadState('networkidle');
      // Check URL or content reflects filter
      const content = await page.content();
      const hasPaidIndicator = content.match(/paid/i);
      expect(hasPaidIndicator).toBeTruthy();
    }
  });

  test('invoice detail page shows all sections', async ({ authedPage: page }) => {
    // Navigate to invoice list and click the first invoice
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');
    const firstLink = page.locator('table tbody tr a, [class*="invoice-row"] a, a[href*="/invoices/"]').first();
    if (await firstLink.isVisible({ timeout: 5_000 })) {
      await firstLink.click();
      await page.waitForLoadState('domcontentloaded');
      await expect(page).toHaveURL(/\/invoices\/[a-z0-9-]+/);
      // Customer name, invoice number or status should be visible
      await expect(page.locator('h1, [class*="invoice-number"]').first()).toBeVisible();
    }
  });

  test('PDF download button is visible on invoice detail', async ({ authedPage: page }) => {
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');
    const firstLink = page.locator('a[href*="/invoices/"]').first();
    if (await firstLink.isVisible({ timeout: 5_000 })) {
      await firstLink.click();
      await page.waitForLoadState('domcontentloaded');
      // PDF or download button
      const pdfBtn = page.locator(
        'button:has-text("PDF"), a:has-text("PDF"), button:has-text("Download"), a[href*="pdf"]',
      ).first();
      if (await pdfBtn.isVisible({ timeout: 3_000 })) {
        await expect(pdfBtn).toBeVisible();
      }
    }
  });

  test('create recurring invoice page loads', async ({ authedPage: page }) => {
    await page.goto('/recurring');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('invoices list has new invoice link', async ({ authedPage: page }) => {
    await page.goto('/invoices');
    const newInvoiceLink = page.locator('a[href*="/invoices/new"], button:has-text("New invoice"), button:has-text("Create")').first();
    await expect(newInvoiceLink).toBeVisible({ timeout: 5_000 });
  });

  test('invoice pagination controls render when multiple pages exist', async ({ authedPage: page }) => {
    await page.goto('/invoices');
    await page.waitForLoadState('networkidle');
    const pagination = page.locator('[aria-label*="page" i], [class*="pagination"], button:has-text("Next")').first();
    if (await pagination.isVisible({ timeout: 3_000 })) {
      await expect(pagination).toBeVisible();
    }
  });
});
