import { test as base, expect } from '@playwright/test';
import { TEST_ACCOUNTS, loginAs } from './fixtures/auth';

// Un-authenticated test instance for auth tests
const test = base;

test.describe('Authentication Flows', () => {

  test('login page renders all expected elements', async ({ page }) => {
    await page.goto('/auth/login');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page.locator('a[href*="forgot-password"]')).toBeVisible();
    await expect(page.locator('a[href*="signup"]')).toBeVisible();
  });

  test('login with valid credentials redirects to dashboard', async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    TEST_ACCOUNTS.owner.email);
    await page.fill('input[type="password"]', TEST_ACCOUNTS.owner.password);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });
  });

  test('login with wrong password shows error message', async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[type="email"]',    TEST_ACCOUNTS.owner.email);
    await page.fill('input[type="password"]', 'definitely-wrong-password');
    await page.click('button[type="submit"]');
    // Should stay on login page
    await expect(page).toHaveURL(/auth\/login/);
    // Error must be visible somewhere
    const errorVisible = await page.locator(
      '[role="alert"], .text-red-500, .text-destructive, [class*="error"]',
    ).first().isVisible({ timeout: 5_000 });
    expect(errorVisible, 'Expected an error message to be displayed').toBe(true);
  });

  test('forgot password page renders and accepts email', async ({ page }) => {
    await page.goto('/auth/forgot-password');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await page.fill('input[type="email"]', 'someone@example.com');
    await page.click('button[type="submit"]');
    // Expect a confirmation message (success state)
    await expect(
      page.locator('text=/check your email|sent|instructions/i'),
    ).toBeVisible({ timeout: 8_000 });
  });

  test('signup page renders all required fields', async ({ page }) => {
    await page.goto('/auth/signup');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('rate limiting: shows error after repeated failed logins', async ({ page }) => {
    await page.goto('/auth/login');
    for (let i = 0; i < 5; i++) {
      await page.fill('input[type="email"]',    'ratelimit@test.invalid');
      await page.fill('input[type="password"]', 'wrongpassword');
      await page.click('button[type="submit"]');
      await page.waitForTimeout(300);
    }
    // After multiple failures, an error (rate-limit or generic) must appear
    const errorVisible = await page.locator(
      '[role="alert"], .text-red-500, .text-destructive, [class*="error"], [class*="too-many"]',
    ).first().isVisible({ timeout: 8_000 });
    expect(errorVisible, 'Expected rate-limit or error message after repeated failures').toBe(true);
  });

  test('logout clears session and redirects to login', async ({ page }) => {
    // Log in first
    await loginAs(page, 'owner');
    await expect(page).toHaveURL(/dashboard/, { timeout: 15_000 });

    // Trigger logout — look for user menu then logout link
    const userMenu = page.locator('[aria-label*="user" i], [aria-label*="account" i], button[class*="avatar"]').first();
    if (await userMenu.isVisible({ timeout: 3_000 })) {
      await userMenu.click();
    }
    const logoutLink = page.locator('a[href*="logout"], button:has-text("Logout"), button:has-text("Sign out"), a:has-text("Logout"), a:has-text("Sign out")').first();
    await expect(logoutLink).toBeVisible({ timeout: 5_000 });
    await logoutLink.click();
    await expect(page).toHaveURL(/auth\/login/, { timeout: 10_000 });

    // Attempting to visit dashboard should redirect back to login
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/auth\/login/, { timeout: 10_000 });
  });

  test('authenticated user visiting /auth/login is redirected away', async ({ page }) => {
    await loginAs(page, 'owner');
    // Already logged in — visiting login should redirect to dashboard
    await page.goto('/auth/login');
    await expect(page).toHaveURL(/dashboard|\/(?!auth)/, { timeout: 8_000 });
  });
});
