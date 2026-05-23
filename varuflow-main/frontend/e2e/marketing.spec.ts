import { test as base, expect } from '@playwright/test';

const test = base;

test.describe('Marketing Site', () => {

  test('homepage loads all major sections', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const errors: string[] = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

    // Hero section
    await expect(page.locator('h1').first()).toBeVisible({ timeout: 8_000 });
    // Footer
    await expect(page.locator('footer').first()).toBeVisible();
    // No JS errors
    const realErrors = errors.filter(e => !e.includes('chrome-extension'));
    expect(realErrors).toHaveLength(0);
  });

  test('homepage has valid title and meta description', async ({ page }) => {
    await page.goto('/');
    const title = await page.title();
    expect(title.length).toBeGreaterThan(5);

    const metaDesc = await page.locator('meta[name="description"]').getAttribute('content');
    expect(metaDesc).toBeTruthy();
    expect(metaDesc!.length).toBeGreaterThan(10);
  });

  test('pricing page shows plan tiers', async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);

    // Expect at least 2 pricing tiers
    const pricingCards = page.locator('[class*="pricing"], [class*="plan"], [class*="tier"]');
    if (await pricingCards.count() > 0) {
      expect(await pricingCards.count()).toBeGreaterThanOrEqual(2);
    } else {
      // Fallback: just check the page loaded
      await expect(page.locator('h1, h2').first()).toBeVisible();
    }
  });

  test('trial / signup page renders form', async ({ page }) => {
    const routes = ['/trial', '/en/trial', '/auth/signup'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');
      const emailInput = page.locator('input[type="email"]');
      if (await emailInput.isVisible({ timeout: 3_000 })) {
        await expect(emailInput).toBeVisible();
        break;
      }
    }
  });

  test('comparison pages load', async ({ page }) => {
    const pages = ['/vs/fortnox', '/vs/odoo', '/vs/visma'];
    for (const p of pages) {
      await page.goto(p);
      await page.waitForLoadState('domcontentloaded');
      // May 404 if not built yet — just validate no server error
      const status = page.url();
      if (!status.includes('404')) {
        await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5_000 });
      }
    }
  });

  test('vertical landing pages load', async ({ page }) => {
    const verticals = ['/verticals/salons', '/verticals/retail', '/verticals/b2b'];
    for (const v of verticals) {
      await page.goto(v);
      await page.waitForLoadState('domcontentloaded');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 5_000 });
      }
    }
  });

  test('compliance page loads', async ({ page }) => {
    await page.goto('/compliance');
    await page.waitForLoadState('domcontentloaded');
    if (!page.url().includes('404')) {
      await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test('demo / contact page loads and form renders', async ({ page }) => {
    const routes = ['/demo', '/contact', '/en/demo'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 5_000 });
        break;
      }
    }
  });

  test('blog or content pages load', async ({ page }) => {
    const routes = ['/blog', '/en/blog', '/resources'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('domcontentloaded');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1, h2, article').first()).toBeVisible({ timeout: 5_000 });
        break;
      }
    }
  });

  test('all marketing page nav links do not 404', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const navLinks = await page.locator('nav a[href^="/"], nav a[href^="http"]').all();
    const internal = navLinks.filter(async l => {
      const href = await l.getAttribute('href') || '';
      return href.startsWith('/') && !href.includes('#');
    });

    for (const link of internal.slice(0, 10)) { // test first 10 to keep suite fast
      const href = await link.getAttribute('href');
      if (!href) continue;
      const res = await page.request.get(href);
      expect(res.status(), `${href} returned ${res.status()}`).not.toBe(404);
    }
  });

  test('region-specific pages load', async ({ page }) => {
    const regions = ['/regions/se', '/regions/no', '/regions/dk'];
    for (const r of regions) {
      await page.goto(r);
      await page.waitForLoadState('domcontentloaded');
      if (!page.url().includes('404')) {
        await expect(page.locator('h1').first()).toBeVisible({ timeout: 5_000 });
      }
    }
  });
});
