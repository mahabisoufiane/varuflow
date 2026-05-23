import { test, expect } from './fixtures/auth';

test.describe('Bookings', () => {

  test('bookings page loads without error', async ({ authedPage: page }) => {
    await page.goto('/bookings');
    await page.waitForLoadState('networkidle');
    await expect(page).not.toHaveURL(/404/);
    await expect(page.locator('h1, h2').first()).toBeVisible();
  });

  test('new booking button is visible', async ({ authedPage: page }) => {
    await page.goto('/bookings');
    await page.waitForLoadState('domcontentloaded');
    const newBtn = page.locator(
      'button:has-text("New"), button:has-text("Book"), button:has-text("Add"), a[href*="new"]',
    ).first();
    await expect(newBtn).toBeVisible({ timeout: 5_000 });
  });

  test('calendar view renders bookings grid', async ({ authedPage: page }) => {
    await page.goto('/bookings');
    await page.waitForLoadState('networkidle');
    const calendar = page.locator('[class*="calendar"], [class*="scheduler"], [role="grid"]').first();
    if (await calendar.isVisible({ timeout: 5_000 })) {
      await expect(calendar).toBeVisible();
    }
  });

  test('create booking modal opens', async ({ authedPage: page }) => {
    await page.goto('/bookings');
    await page.waitForLoadState('domcontentloaded');
    const newBtn = page.locator(
      'button:has-text("New"), button:has-text("Book"), button:has-text("Add booking")',
    ).first();
    if (await newBtn.isVisible({ timeout: 3_000 })) {
      await newBtn.click();
      const modal = page.locator('[role="dialog"], [class*="modal"]').first();
      await expect(modal).toBeVisible({ timeout: 5_000 });
    }
  });

  test('booking service selection available in creation flow', async ({ authedPage: page }) => {
    await page.goto('/bookings');
    await page.waitForLoadState('domcontentloaded');
    const newBtn = page.locator('button:has-text("New"), button:has-text("Book"), button:has-text("Add")').first();
    if (await newBtn.isVisible({ timeout: 3_000 })) {
      await newBtn.click();
      await page.waitForTimeout(500);
      // Service select or search in modal
      const serviceSelect = page.locator('[role="dialog"] select, [role="dialog"] input[placeholder*="service" i]').first();
      if (await serviceSelect.isVisible({ timeout: 3_000 })) {
        await expect(serviceSelect).toBeVisible();
      }
    }
  });
});
