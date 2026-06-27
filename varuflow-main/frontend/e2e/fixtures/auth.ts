import { test as base, Page, expect, APIRequestContext } from '@playwright/test';
import path from 'path';

export const TEST_ACCOUNTS = {
  owner:  { email: 'test-owner@varuflow-e2e.com',  password: 'E2ETest2026!' },
  admin:  { email: 'test-admin@varuflow-e2e.com',  password: 'E2ETest2026!' },
  member: { email: 'test-member@varuflow-e2e.com', password: 'E2ETest2026!' },
} as const;

export type AccountRole = keyof typeof TEST_ACCOUNTS;

export const AUTH_STATE = {
  owner:  path.resolve(__dirname, '../.auth/owner.json'),
  admin:  path.resolve(__dirname, '../.auth/admin.json'),
  member: path.resolve(__dirname, '../.auth/member.json'),
};

const API_BASE = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

// Uses the test-runner APIRequestContext (no CORS) to get a local-auth JWT
async function getLocalToken(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  // Try login first
  const res = await request.post(`${API_BASE}/api/local-auth/login`, {
    data: { email, password },
  });
  if (res.ok()) {
    const body = await res.json();
    return body.access_token as string;
  }

  // Sign up + verify in DB, then retry (first run only)
  await request.post(`${API_BASE}/api/local-auth/signup`, { data: { email, password } });
  // Force-verify via the dev admin endpoint
  await request.post(`${API_BASE}/api/local-auth/dev-verify`, { data: { email } }).catch(() => {});
  const retry = await request.post(`${API_BASE}/api/local-auth/login`, { data: { email, password } });
  if (retry.ok()) return (await retry.json()).access_token as string;

  throw new Error(`Could not authenticate E2E user ${email} — run: docker exec varuflow-main-postgres-1 psql -U postgres -d varuflow -c "UPDATE auth_users SET is_email_verified=true WHERE email='${email}'"`)
}

export async function loginAs(
  page: Page,
  role: AccountRole = 'owner',
  request?: APIRequestContext,
) {
  const { email, password } = TEST_ACCOUNTS[role];
  const isDev = process.env.PLAYWRIGHT_ENV === 'local' || !process.env.NEXT_PUBLIC_SUPABASE_URL;

  if (isDev && request) {
    const token = await getLocalToken(request, email, password);
    await page.goto('/en/dashboard');
    await page.evaluate((t) => {
      localStorage.setItem('vf-auth-token', t);
      localStorage.setItem('vf-auth-token-local', t);
    }, token);
    await page.reload();
    await page.waitForURL(/dashboard/, { timeout: 15_000 });
    return;
  }

  // Supabase UI flow (prod/staging)
  await page.goto('/auth/login');
  await page.waitForLoadState('domcontentloaded');
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(en\/|ar\/)?dashboard|onboarding/, { timeout: 15_000 });
}

export const test = base.extend<{
  authedPage:  Page;
  adminPage:   Page;
  memberPage:  Page;
}>({
  authedPage: async ({ page, request }, use) => {
    await loginAs(page, 'owner', request);
    await use(page);
  },

  adminPage: async ({ page, request }, use) => {
    await loginAs(page, 'admin', request);
    await use(page);
  },

  memberPage: async ({ page, request }, use) => {
    await loginAs(page, 'member', request);
    await use(page);
  },
});

export { expect };
