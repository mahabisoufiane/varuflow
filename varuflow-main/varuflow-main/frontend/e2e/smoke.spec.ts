import { test, expect } from './fixtures/auth';
import { TEST_ACCOUNTS } from './fixtures/auth';

test.describe('Smoke Tests — Run on Every Deploy', () => {

  test('API health check returns healthy', async ({ request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL
      || 'https://varuflow-production.up.railway.app';
    const res = await request.get(`${apiBase}/api/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(body.db).toBe('ok');
  });

  test('frontend loads without JS console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', err => errors.push(err.message));
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Filter known third-party noise
    const realErrors = errors.filter(
      e => !e.includes('chrome-extension') && !e.includes('clarity.ms'),
    );
    expect(realErrors).toHaveLength(0);
  });

  test('auth flow works end-to-end', async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    TEST_ACCOUNTS.owner.email);
    await page.fill('input[type="password"]', TEST_ACCOUNTS.owner.password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });
  });

  test('critical pages load without 404 or error page', async ({ authedPage: page }) => {
    const critical = [
      '/dashboard',
      '/invoices',
      '/inventory',
      '/customers',
      '/pos',
      '/expenses',
      '/analytics',
      '/settings',
    ] as const;

    for (const path of critical) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page).not.toHaveURL(/\/404/);
      await expect(page).not.toHaveURL(/\/error/);
      // Heading or main content visible
      const hasContent = await page.locator('h1, main, [data-testid]').first().isVisible();
      expect(hasContent, `No visible content on ${path}`).toBe(true);
    }
  });

  test('create invoice smoke test', async ({ authedPage: page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    // Select customer
    const customerSelect = page.locator('select').first();
    await customerSelect.selectOption({ index: 1 }); // first real customer

    // Fill line item
    const descInput = page.locator('input[placeholder="Service or item…"]').first();
    await descInput.fill('Smoke Test Product');
    await page.locator('input[type="number"][min="0.001"]').first().fill('1');
    await page.locator('input[type="number"][step="0.01"]').first().fill('100');

    await page.click('button[type="submit"]');
    // Should redirect to the new invoice detail
    await expect(page).toHaveURL(/\/invoices\/[a-z0-9-]+/, { timeout: 10_000 });
  });

  test('dashboard KPI strip renders', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    const kpi = page.locator('[data-testid="kpi-strip"]');
    await expect(kpi).toBeVisible({ timeout: 10_000 });
  });

  test('POS session can be opened', async ({ authedPage: page }) => {
    await page.goto('/pos');
    await page.waitForLoadState('domcontentloaded');
    const openBtn = page.locator('[data-testid="pos-open-session"]');
    if (await openBtn.isVisible()) {
      await openBtn.click();
    }
    await expect(page.locator('[data-testid="pos-layout"]')).toBeVisible({ timeout: 10_000 });
  });
});
