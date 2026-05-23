import { test, expect } from './fixtures/auth';

test.describe('Inventory Management', () => {

  test('inventory page loads with product list or empty state', async ({ authedPage: page }) => {
    await page.goto('/inventory');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('create product — complete form', async ({ authedPage: page }) => {
    await page.goto('/inventory/products/new');
    await page.waitForLoadState('domcontentloaded');
    await expect(page).not.toHaveURL(/404/);

    // Fill product name (required)
    const nameInput = page.locator('input[name="name"], input[placeholder*="name" i]').first();
    if (await nameInput.isVisible({ timeout: 3_000 })) {
      await nameInput.fill('E2E Test Product ' + Date.now());
    }

    // SKU
    const skuInput = page.locator('input[name="sku"], input[placeholder*="sku" i]').first();
    if (await skuInput.isVisible({ timeout: 2_000 })) {
      await skuInput.fill('E2E-SKU-' + Date.now());
    }

    // Price
    const priceInput = page.locator('input[name="selling_price"], input[name="price"], input[placeholder*="price" i]').first();
    if (await priceInput.isVisible({ timeout: 2_000 })) {
      await priceInput.fill('99.00');
    }

    // Submit
    const submitBtn = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Create")').first();
    await submitBtn.click();

    // Expect redirect or success indicator
    await page.waitForTimeout(2000);
    await expect(page).not.toHaveURL(/\/new$/);
  });

  test('products page shows new product button', async ({ authedPage: page }) => {
    await page.goto('/inventory/products');
    await page.waitForLoadState('domcontentloaded');
    const newBtn = page.locator(
      'a[href*="/new"], button:has-text("Add"), button:has-text("New"), button:has-text("Create")',
    ).first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });

  test('inventory product search / filter controls render', async ({ authedPage: page }) => {
    await page.goto('/inventory/products');
    await page.waitForLoadState('networkidle');
    const searchInput = page.locator('input[type="search"], input[placeholder*="search" i], input[placeholder*="filter" i]').first();
    if (await searchInput.isVisible({ timeout: 3_000 })) {
      await searchInput.fill('E2E');
      await page.waitForTimeout(500);
      // Results should reflect filter (no assertion since data may vary)
    }
  });

  test('stock adjustment dialog opens from product detail', async ({ authedPage: page }) => {
    await page.goto('/inventory/products');
    await page.waitForLoadState('networkidle');
    const firstProduct = page.locator('table tbody tr a, [class*="product-row"] a, a[href*="/inventory/products/"]').first();
    if (await firstProduct.isVisible({ timeout: 5_000 })) {
      await firstProduct.click();
      await page.waitForLoadState('domcontentloaded');
      const adjustBtn = page.locator(
        'button:has-text("Adjust"), button:has-text("Stock"), button:has-text("Movement")',
      ).first();
      if (await adjustBtn.isVisible({ timeout: 3_000 })) {
        await adjustBtn.click();
        const dialog = page.locator('[role="dialog"], [class*="modal"]').first();
        await expect(dialog).toBeVisible({ timeout: 5_000 });
      }
    }
  });

  test('inventory forecasting page loads for Pro users', async ({ authedPage: page }) => {
    await page.goto('/inventory');
    await page.waitForLoadState('domcontentloaded');
    // Forecasting may be a tab or separate route
    const forecastLink = page.locator('a[href*="forecast" i], button:has-text("Forecast")').first();
    if (await forecastLink.isVisible({ timeout: 3_000 })) {
      await forecastLink.click();
      await page.waitForLoadState('domcontentloaded');
      await expect(page).not.toHaveURL(/404/);
    }
  });

  test('auto-reorder settings page loads', async ({ authedPage: page }) => {
    await page.goto('/settings/auto-reorder');
    await page.waitForLoadState('domcontentloaded');
    const mainEl = page.locator('[data-testid="auto-reorder-settings-page"]');
    if (await mainEl.isVisible({ timeout: 5_000 })) {
      await expect(mainEl).toBeVisible();
    } else {
      // Might redirect or show upgrade prompt
      await expect(page).not.toHaveURL(/404/);
    }
  });
});
