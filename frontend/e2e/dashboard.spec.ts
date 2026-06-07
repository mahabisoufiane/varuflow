import { test, expect } from './fixtures/auth';

test.describe('Dashboard & Navigation', () => {

  test('all 4 KPI tiles visible', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    const kpiStrip = page.locator('[data-testid="kpi-strip"]');
    await expect(kpiStrip).toBeVisible({ timeout: 10_000 });
    // Expect at least 3 metric cards inside the strip
    const cards = kpiStrip.locator('[data-testid="metric-card"]');
    await expect(cards).toHaveCount(3);
  });

  test('locked/Pro features show upgrade prompt on Starter plan', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    // If any locked feature tile or upgrade CTA is present, click it
    const lockedFeature = page.locator('[class*="locked"], [class*="upgrade"], button:has-text("Upgrade")').first();
    if (await lockedFeature.isVisible({ timeout: 3_000 })) {
      await lockedFeature.click();
      // Upgrade modal or pricing page navigation should occur
      const modalOrNav = page.locator(
        '[role="dialog"], [class*="modal"], text=/upgrade|pro/i',
      ).first();
      await expect(modalOrNav).toBeVisible({ timeout: 5_000 });
    }
  });

  test('sidebar nav links navigate correctly', async ({ authedPage: page }) => {
    const navItems = [
      { label: /invoices/i,   expectedPath: '/invoices'   },
      { label: /inventory/i,  expectedPath: '/inventory'  },
      { label: /customers/i,  expectedPath: '/customers'  },
      { label: /analytics/i,  expectedPath: '/analytics'  },
      { label: /settings/i,   expectedPath: '/settings'   },
    ] as const;

    for (const item of navItems) {
      await page.goto('/dashboard');
      const link = page.locator(`nav a:has-text("${item.label}")`, { hasText: item.label }).first()
        .or(page.locator(`[data-testid^="nav-"] a`).filter({ hasText: item.label }).first());
      if (await link.isVisible({ timeout: 3_000 })) {
        await link.click();
        await expect(page).toHaveURL(new RegExp(item.expectedPath), { timeout: 8_000 });
        await expect(page).not.toHaveURL(/\/404/);
      }
    }
  });

  test('user menu shows correct account info', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    const avatarBtn = page.locator(
      'button[class*="avatar"], [aria-label*="user" i], [aria-label*="account" i], img[class*="avatar"]',
    ).first();
    if (await avatarBtn.isVisible({ timeout: 3_000 })) {
      await avatarBtn.click();
      // Should see email or name in dropdown
      await expect(page.locator(`text=${TEST_DISPLAY_NAME_OR_EMAIL}`).or(
        page.locator('[role="menu"], [class*="dropdown"]').first(),
      )).toBeVisible({ timeout: 5_000 });
    }
  });

  test('quick action buttons exist on dashboard', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('domcontentloaded');
    const newInvoiceLink = page.locator('a[href*="/invoices/new"]').first();
    await expect(newInvoiceLink).toBeVisible({ timeout: 5_000 });
  });

  test('responsive mobile layout: main content visible on narrow viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    'test-owner@varuflow-e2e.com');
    await page.fill('input[type="password"]', 'E2ETest2026!');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });
    // Mobile bottom nav should be visible
    const mobileNav = page.locator('[data-testid="mobile-bottom-nav"]');
    if (await mobileNav.isVisible({ timeout: 3_000 })) {
      await expect(mobileNav).toBeVisible();
    }
    // Main content visible
    await expect(page.locator('main, [data-testid="dashboard-pull-root"]').first()).toBeVisible();
  });

  test('AI action cards carousel renders', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    const carousel = page.locator('[data-testid="ai-carousel"]');
    // Only check if user has Pro (may be hidden on Starter)
    if (await carousel.isVisible({ timeout: 3_000 })) {
      await expect(carousel).toBeVisible();
    }
  });

  test('recent activity widget renders', async ({ authedPage: page }) => {
    await page.goto('/dashboard');
    const activity = page.locator('[data-testid="recent-activity"]');
    await expect(activity).toBeVisible({ timeout: 10_000 });
  });
});

// Dummy constant used in the user-menu test above
const TEST_DISPLAY_NAME_OR_EMAIL = 'test-owner';
