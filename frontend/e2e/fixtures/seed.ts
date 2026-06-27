/**
 * E2E Seed Script
 * ---------------
 * Creates all test data required by the Playwright suite.
 * Run once before the test suite; call cleanup() afterwards.
 *
 * Usage:
 *   node --loader ts-node/esm e2e/fixtures/seed.ts
 *   Or via playwright/global-setup.ts (recommended).
 */

const API_BASE  = process.env.PLAYWRIGHT_API_URL  || 'https://varuflow-production.up.railway.app';
const ADMIN_KEY = process.env.ADMIN_API_KEY        || '';

// ──────────────────────────────────────────────────────────────────────────────
// Seed data definitions
// ──────────────────────────────────────────────────────────────────────────────
export const SEED = {
  org: {
    name: 'Varuflow E2E Org',
    country: 'SE',
    currency: 'SEK',
  },
  users: {
    owner:  { email: 'test-owner@varuflow-e2e.com',  role: 'OWNER',  password: 'E2ETest2026!' },
    admin:  { email: 'test-admin@varuflow-e2e.com',  role: 'ADMIN',  password: 'E2ETest2026!' },
    member: { email: 'test-member@varuflow-e2e.com', role: 'MEMBER', password: 'E2ETest2026!' },
  },
  products: [
    { name: 'E2E Widget A',    sku: 'E2E-001', price: 199.00, cost: 100.00, stock: 50 },
    { name: 'E2E Widget B',    sku: 'E2E-002', price: 299.00, cost: 150.00, stock: 20 },
    { name: 'E2E Low Stock',   sku: 'E2E-003', price:  49.00, cost:  25.00, stock:  3 },
    { name: 'E2E Service Fee', sku: 'E2E-004', price: 500.00, cost:   0.00, stock:  0 },
    { name: 'E2E Bundle',      sku: 'E2E-005', price: 999.00, cost: 600.00, stock: 10 },
  ],
  customers: [
    { company_name: 'E2E Customer Alpha', email: 'alpha@e2e.test', phone: '+4670123456' },
    { company_name: 'E2E Customer Beta',  email: 'beta@e2e.test',  phone: '+4670123457' },
    { company_name: 'E2E VIP Account',    email: 'vip@e2e.test',   phone: '+4670123458', tags: ['VIP'] },
  ],
  invoices: [
    { status: 'DRAFT', customer_index: 0 },
    { status: 'SENT',  customer_index: 1 },
    { status: 'PAID',  customer_index: 2 },
  ],
};

// ──────────────────────────────────────────────────────────────────────────────
// Helper — authenticated admin fetch
// ──────────────────────────────────────────────────────────────────────────────
async function adminFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type':  'application/json',
      'X-Admin-Token': ADMIN_KEY,
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error(`adminFetch ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

// ──────────────────────────────────────────────────────────────────────────────
// Exported seed / cleanup functions (called from global-setup / global-teardown)
// ──────────────────────────────────────────────────────────────────────────────

export async function seedTestData() {
  console.log('[seed] Creating E2E test data…');
  // NOTE: actual calls depend on backend admin API; adjust paths as needed.
  // The structure below is a reference implementation.
  try {
    await adminFetch('/api/admin/e2e/seed', {
      method: 'POST',
      body: JSON.stringify(SEED),
    });
    console.log('[seed] ✓ Test data created.');
  } catch (err) {
    console.warn('[seed] Seed endpoint not available — tests will use pre-existing data.', err);
  }
}

export async function cleanupTestData() {
  console.log('[seed] Cleaning up E2E test data…');
  try {
    await adminFetch('/api/admin/e2e/cleanup', { method: 'DELETE' });
    console.log('[seed] ✓ Test data removed.');
  } catch (err) {
    console.warn('[seed] Cleanup endpoint not available — manual cleanup may be needed.', err);
  }
}
