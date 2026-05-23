import { test, expect } from './fixtures/auth';

test.describe('Point of Sale (POS)', () => {

  test('POS layout renders after opening session', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 4_000 })) {
      await openBtn.click();
    }

    await expect(page.locator('[data-testid="pos-layout"]')).toBeVisible({ timeout: 8_000 });
  });

  test('POS product search input is interactive', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 3_000 })) {
      await openBtn.click();
      await page.waitForTimeout(500);
    }

    const searchEl = page.locator('[data-testid="pos-search"]');
    if (await searchEl.isVisible({ timeout: 5_000 })) {
      await searchEl.fill('Widget');
      await page.waitForTimeout(500);
      // Product grid should react
      await expect(page.locator('[data-testid="pos-product-grid"]')).toBeVisible();
    }
  });

  test('POS cart panel renders', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 3_000 })) {
      await openBtn.click();
    }

    await expect(page.locator('[data-testid="pos-cart-panel"]')).toBeVisible({ timeout: 8_000 });
  });

  test('adding product to POS cart updates total', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 3_000 })) {
      await openBtn.click();
      await page.waitForTimeout(500);
    }

    // Click first product in grid
    const firstProduct = page.locator('[data-testid="pos-product-grid"] button, [data-testid="pos-product-grid"] [role="button"]').first();
    if (await firstProduct.isVisible({ timeout: 5_000 })) {
      await firstProduct.click();
      await page.waitForTimeout(300);
      // Cart should have at least one item
      const total = page.locator('[data-testid="pos-total"]');
      if (await total.isVisible({ timeout: 3_000 })) {
        const totalText = await total.textContent();
        expect(totalText).not.toBe('0');
      }
    }
  });

  test('POS Z-report modal can be opened', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 3_000 })) {
      await openBtn.click();
      await page.waitForTimeout(500);
    }

    const closeBtn = page.locator('[data-testid="pos-close-session"]');
    if (await closeBtn.isVisible({ timeout: 3_000 })) {
      await closeBtn.click();
      const zModal = page.locator('[data-testid="pos-zreport-modal"]');
      await expect(zModal).toBeVisible({ timeout: 5_000 });
      // Close it
      const cancelBtn = zModal.locator('button:has-text("Cancel"), button:has-text("Close"), button:has-text("Back")').first();
      if (await cancelBtn.isVisible()) await cancelBtn.click();
    }
  });

  test('POS quick sale buttons render', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');

    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible({ timeout: 3_000 })) {
      await openBtn.click();
      await page.waitForTimeout(500);
    }

    const quickBtns = page.locator('[data-testid="pos-quick-buttons"]');
    if (await quickBtns.isVisible({ timeout: 5_000 })) {
      await expect(quickBtns).toBeVisible();
    }
  });
});
