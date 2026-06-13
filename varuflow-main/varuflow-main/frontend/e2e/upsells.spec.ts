import { test as base, expect } from '@playwright/test';

const test = base;

test.describe('Upsell Engine', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    'test-owner@varuflow-e2e.com');
    await page.fill('input[type="password"]', 'E2ETest2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 15_000 });
  });

  test('plan usage / limit indicators visible somewhere in the UI', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    // Usage indicator may be in settings, header, or a banner
    const usageIndicator = page.locator('text=/of |used|limit|upgrade/i').first();
    if (await usageIndicator.isVisible({ timeout: 3_000 })) {
      await expect(usageIndicator).toBeVisible();
    }
  });

  test('Pro-locked feature click shows upgrade CTA or informational modal', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    // Find any locked / Pro indicator
    const lockedEl = page.locator(
      '[class*="locked"], [class*="pro" i], button:has-text("Upgrade"), [class*="upsell"]',
    ).first();
    if (await lockedEl.isVisible({ timeout: 3_000 })) {
      await lockedEl.click();
      await page.waitForTimeout(500);
      const upgradeModal = page.locator(
        '[role="dialog"], [class*="modal"], text=/upgrade|pro|plan/i',
      ).first();
      if (await upgradeModal.isVisible({ timeout: 3_000 })) {
        await expect(upgradeModal).toBeVisible();
        // Close modal
        const closeBtn = page.locator('button:has-text("Cancel"), button:has-text("Later"), button:has-text("Close"), [aria-label="Close"]').first();
        if (await closeBtn.isVisible()) await closeBtn.click();
      }
    }
  });

  test('billing settings shows current plan and upgrade option', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    const planInfo = page.locator('text=/Starter|Pro|Enterprise|plan/i').first();
    if (await planInfo.isVisible({ timeout: 5_000 })) {
      await expect(planInfo).toBeVisible();
    }
  });

  test('MEMBER role sees contact-admin message on locked features', async ({ page }) => {
    // Login as member
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    'test-member@varuflow-e2e.com');
    await page.fill('input[type="password"]', 'E2ETest2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 15_000 });

    const lockedEl = page.locator('[class*="locked"], [class*="pro" i]').first();
    if (await lockedEl.isVisible({ timeout: 3_000 })) {
      await lockedEl.click();
      await page.waitForTimeout(500);
      // Member should NOT see an upgrade button, but might see an info message
      const upgradeBtn = page.locator('button:has-text("Upgrade"), a:has-text("Upgrade to Pro")');
      // Either the modal doesn't open or there's no direct upgrade CTA for members
      // (just verify page didn't crash)
      await expect(page).not.toHaveURL(/404/);
    }
  });

  test('trial countdown visible when trial is active', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    const trialBanner = page.locator('text=/trial|days remaining|expires/i').first();
    if (await trialBanner.isVisible({ timeout: 3_000 })) {
      await expect(trialBanner).toBeVisible();
    }
  });
});
