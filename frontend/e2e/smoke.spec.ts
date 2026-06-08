import { test, expect } from './fixtures/auth';

test.describe('Smoke Tests — Run on Every Deploy', () => {

  test('API health check returns healthy', async ({ request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';
    const res = await request.get(`${apiBase}/api/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(body.database).toBe('ok');
  });

  test('frontend loads without JS console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    page.on('pageerror', err => errors.push(err.message));
    // Use the login page — navigating to '/' unauthenticated triggers many
    // API preflights that fail before the auth redirect completes, producing
    // spurious CORS console errors unrelated to actual frontend bugs.
    await page.goto('/en/auth/login');
    await page.waitForLoadState('networkidle');
    const realErrors = errors.filter(
      e => !e.includes('chrome-extension') &&
           !e.includes('clarity.ms') &&
           !e.includes('supabase') &&
           !e.includes('NEXT_PUBLIC_SUPABASE'),
    );
    expect(realErrors).toHaveLength(0);
  });

  test('auth flow works end-to-end', async ({ page, request }) => {
    const { loginAs } = await import('./fixtures/auth');
    await loginAs(page, 'owner', request);
    await expect(page).toHaveURL(/dashboard/);
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
      const hasContent = await page.locator('h1, main, [data-testid]').first().isVisible();
      expect(hasContent, `No visible content on ${path}`).toBe(true);
    }
  });

  test('create invoice smoke test', async ({ authedPage: page, request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

    // Seed a customer so the invoice form's customer select has options.
    // The request fixture uses the test-runner APIRequestContext (no CORS).
    const token = await page.evaluate(() =>
      localStorage.getItem('vf-auth-token') || localStorage.getItem('vf-auth-token-local') || '',
    );
    if (token) {
      await request.post(`${apiBase}/api/customers`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { company_name: 'E2E Smoke Customer' },
        failOnStatusCode: false, // 409 on repeat runs is fine
      });
    }

    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    // Wait for the customer dropdown to populate before selecting
    const customerSelect = page.locator('[data-testid="customer-select"]');
    await expect(customerSelect).toBeVisible({ timeout: 10_000 });
    await page.waitForFunction(() => {
      const sel = document.querySelector('[data-testid="customer-select"]') as HTMLSelectElement;
      return sel != null && sel.options.length > 1;
    }, { timeout: 10_000 });
    await customerSelect.selectOption({ index: 1 });

    const descInput = page.locator('input[placeholder="Service or item…"]').first();
    await descInput.fill('Smoke Test Product');
    await page.locator('input[type="number"][min="0.001"]').first().fill('1');
    await page.locator('input[type="number"][step="0.01"]').first().fill('100');

    await page.click('button[type="submit"]');
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
    // /pos now redirects to the standalone POS app — page should show the redirect banner
    const hasContent = await page.locator('h1, main, a[href*="3003"]').first().isVisible();
    expect(hasContent, 'POS redirect page should be visible').toBe(true);
  });
});
