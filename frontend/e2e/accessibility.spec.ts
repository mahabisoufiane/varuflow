import { test as base, expect } from '@playwright/test';

const test = base;

test.describe('Accessibility', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    'test-owner@varuflow-e2e.com');
    await page.fill('input[type="password"]', 'E2ETest2026!');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/, { timeout: 15_000 });
  });

  test('all form inputs have associated labels or aria-label', async ({ page }) => {
    const formPages = ['/invoices/new', '/customers/new'];
    for (const path of formPages) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');

      const inputs = await page.locator('input:not([type="hidden"]):not([type="submit"])').all();
      for (const input of inputs) {
        const id       = await input.getAttribute('id');
        const aria     = await input.getAttribute('aria-label');
        const ariaBy   = await input.getAttribute('aria-labelledby');
        const placeholder = await input.getAttribute('placeholder');
        const hasLabel = id
          ? (await page.locator(`label[for="${id}"]`).count()) > 0
          : false;

        const isAccessible = hasLabel || !!aria || !!ariaBy || !!placeholder;
        expect(isAccessible, `Input on ${path} lacks label/aria-label/placeholder`).toBe(true);
      }
    }
  });

  test('all buttons have accessible text', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('domcontentloaded');

    const buttons = await page.locator('button').all();
    let emptyButtons = 0;
    for (const btn of buttons) {
      const text    = (await btn.textContent())?.trim() || '';
      const ariaLabel = await btn.getAttribute('aria-label') || '';
      const ariaDesc  = await btn.getAttribute('aria-describedby') || '';
      const title     = await btn.getAttribute('title') || '';
      if (!text && !ariaLabel && !ariaDesc && !title) emptyButtons++;
    }
    // Allow up to 2 icon-only buttons without strict labelling (common in icon toolbars)
    expect(emptyButtons).toBeLessThanOrEqual(2);
  });

  test('keyboard navigation: Tab moves through invoice form fields', async ({ page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    // Focus first form element
    await page.keyboard.press('Tab');
    const focused = page.locator(':focus');
    const tag = await focused.evaluate(el => el.tagName.toLowerCase());
    expect(['input', 'select', 'textarea', 'button', 'a']).toContain(tag);
  });

  test('error messages are descriptive when form submitted empty', async ({ page }) => {
    await page.goto('/invoices/new');
    await page.waitForLoadState('domcontentloaded');

    // Submit without filling anything
    await page.click('button[type="submit"]');
    await page.waitForTimeout(500);

    // Either validation errors appear, or we're still on the page
    const stillOnPage = page.url().includes('/invoices/new');
    if (stillOnPage) {
      // Some form validation should be present
      const validationErrors = page.locator(
        '[class*="error"], [class*="invalid"], [aria-invalid="true"], :invalid',
      );
      const count = await validationErrors.count();
      // At minimum, the customer field should be required
      expect(count).toBeGreaterThan(0);
    }
  });

  test('focus is visible on interactive elements', async ({ page }) => {
    await page.goto('/auth/login');
    await page.waitForLoadState('domcontentloaded');

    const emailInput = page.locator('input[type="email"]');
    await emailInput.focus();
    // outline or box-shadow should be applied (non-none) — check via CSS
    const outline = await emailInput.evaluate(el => {
      const style = window.getComputedStyle(el);
      return {
        outline: style.outline,
        boxShadow: style.boxShadow,
      };
    });
    const hasFocusStyle = outline.outline !== 'none' || outline.boxShadow !== 'none';
    expect(hasFocusStyle, 'Email input has no visible focus indicator').toBe(true);
  });

  test('images have alt attributes', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const images = await page.locator('img').all();
    let missingAlt = 0;
    for (const img of images) {
      const alt  = await img.getAttribute('alt');
      const role = await img.getAttribute('role');
      // Decorative images should have role="presentation" or empty alt
      if (alt === null && role !== 'presentation') missingAlt++;
    }
    expect(missingAlt).toBe(0);
  });
});
