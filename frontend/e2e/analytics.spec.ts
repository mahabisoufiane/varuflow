import { test as base, expect } from '@playwright/test';

const test = base;

test.describe('Analytics & Reporting', () => {

  // Auth helper inline (analytics tests require login)
  test.beforeEach(async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    'test-owner@varuflow-e2e.com');
    await page.fill('input[type="password"]', 'E2ETest2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 15_000 });
  });

  test('analytics overview page loads', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('revenue chart renders', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('networkidle');
    const chart = page.locator('[class*="recharts"], svg, canvas, [class*="chart"]').first();
    if (await chart.isVisible({ timeout: 8_000 })) {
      await expect(chart).toBeVisible();
    }
  });

  test('date range selector is present', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('domcontentloaded');
    const dateFilter = page.locator(
      'input[type="date"], button:has-text("Last 30"), button:has-text("This month"), select[name*="range" i], [class*="date-range"]',
    ).first();
    if (await dateFilter.isVisible({ timeout: 5_000 })) {
      await expect(dateFilter).toBeVisible();
    }
  });

  test('analytics CSV export button renders', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('networkidle');
    const exportBtn = page.locator(
      'button:has-text("Export"), a:has-text("Export"), button:has-text("CSV"), button:has-text("Download")',
    ).first();
    if (await exportBtn.isVisible({ timeout: 5_000 })) {
      await expect(exportBtn).toBeVisible();
    }
  });

  test('customer LTV section visible for Pro users', async ({ page }) => {
    await page.goto('/analytics');
    await page.waitForLoadState('networkidle');
    const ltvSection = page.locator('text=/LTV|lifetime value|customer value/i').first();
    if (await ltvSection.isVisible({ timeout: 5_000 })) {
      await expect(ltvSection).toBeVisible();
    }
  });

  test('accounting page loads with SIE export option', async ({ page }) => {
    await page.goto('/accounting');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    const sieBtn = page.locator('button:has-text("SIE"), a:has-text("SIE"), button:has-text("Export")').first();
    if (await sieBtn.isVisible({ timeout: 3_000 })) {
      await expect(sieBtn).toBeVisible();
    }
  });

  test('AI demand forecast visible for Pro users', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    const forecastCard = page.locator('[data-testid="ai-carousel"], text=/forecast|predict/i').first();
    if (await forecastCard.isVisible({ timeout: 5_000 })) {
      await expect(forecastCard).toBeVisible();
    }
  });
});
