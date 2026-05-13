import { test as base, Page, expect } from '@playwright/test';
import path from 'path';

// ──────────────────────────────────────────────────────────────────────────────
// Test accounts — must exist in the Supabase test environment (created by seed)
// ──────────────────────────────────────────────────────────────────────────────
export const TEST_ACCOUNTS = {
  owner:  { email: 'test-owner@varuflow-e2e.com',  password: 'E2ETest2026!' },
  admin:  { email: 'test-admin@varuflow-e2e.com',  password: 'E2ETest2026!' },
  member: { email: 'test-member@varuflow-e2e.com', password: 'E2ETest2026!' },
} as const;

export type AccountRole = keyof typeof TEST_ACCOUNTS;

// Saved auth state paths so we only log in once per role per test run
export const AUTH_STATE = {
  owner:  path.resolve(__dirname, '../.auth/owner.json'),
  admin:  path.resolve(__dirname, '../.auth/admin.json'),
  member: path.resolve(__dirname, '../.auth/member.json'),
};

// ──────────────────────────────────────────────────────────────────────────────
// loginAs — drives the UI login flow and waits for the dashboard
// ──────────────────────────────────────────────────────────────────────────────
export async function loginAs(page: Page, role: AccountRole = 'owner') {
  const { email, password } = TEST_ACCOUNTS[role];

  await page.goto('/auth/login');
  await page.waitForLoadState('domcontentloaded');

  // Fill credentials — login page uses HTML5 autocomplete attributes (no data-testid)
  await page.fill('input[type="email"]',    email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  // Wait for post-login redirect (any locale, dashboard or onboarding)
  await page.waitForURL(/\/(en\/|ar\/)?dashboard|onboarding/, { timeout: 15_000 });
}

// ──────────────────────────────────────────────────────────────────────────────
// Extended test fixture — provides an already-authenticated page
// ──────────────────────────────────────────────────────────────────────────────
export const test = base.extend<{
  authedPage:       Page;
  adminPage:        Page;
  memberPage:       Page;
}>({
  authedPage: async ({ page }, use) => {
    await loginAs(page, 'owner');
    await use(page);
  },

  adminPage: async ({ page }, use) => {
    await loginAs(page, 'admin');
    await use(page);
  },

  memberPage: async ({ page }, use) => {
    await loginAs(page, 'member');
    await use(page);
  },
});

export { expect };
