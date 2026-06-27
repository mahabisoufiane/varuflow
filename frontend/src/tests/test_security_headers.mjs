// node --test runner. See package.json scripts for siblings (test:seo, …).
//
// Guardrails: any edit to src/lib/security-headers.mjs that removes a
// documented allow-list or a non-regressable directive must fail this file.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildCsp,
  buildSecurityHeaders,
  CSP_ALLOW_STRIPE,
  CSP_ALLOW_CRISP,
  CSP_ALLOW_FONTS,
} from "../lib/security-headers.mjs";

const SAMPLE_ENV = {
  apiUrl:      "https://api.varuflow.com",
  supabaseUrl: "https://xyz.supabase.co",
  sentryDsn:   "https://abc123@o456.ingest.sentry.io/789",
};

// ---- Golden string ---------------------------------------------------------
// If you intentionally change the CSP, update this string in the same commit.
const EXPECTED_CSP =
  "default-src 'self'; " +
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://client.crisp.chat; " +
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://client.crisp.chat; " +
  "font-src 'self' data: https://fonts.gstatic.com https://client.crisp.chat; " +
  "img-src 'self' data: blob: https:; " +
  "connect-src 'self' https://api.varuflow.com https://xyz.supabase.co https://o456.ingest.sentry.io " +
    "https://client.crisp.chat wss://client.relay.crisp.chat https://api.stripe.com; " +
  "frame-src https://js.stripe.com https://hooks.stripe.com https://client.crisp.chat; " +
  "frame-ancestors 'none'; " +
  "base-uri 'self'; " +
  "form-action 'self'; " +
  "object-src 'none'";

test("buildCsp: golden-string match for reference env", () => {
  assert.equal(buildCsp(SAMPLE_ENV), EXPECTED_CSP);
});

// ---- Allow-list presence ---------------------------------------------------
test("buildCsp: Stripe hosts present in the right directives", () => {
  const csp = buildCsp(SAMPLE_ENV);
  assert.match(csp, new RegExp(`script-src[^;]*${CSP_ALLOW_STRIPE.script}`));
  assert.match(csp, new RegExp(`connect-src[^;]*${CSP_ALLOW_STRIPE.connect}`));
  for (const host of CSP_ALLOW_STRIPE.frame) {
    assert.match(csp, new RegExp(`frame-src[^;]*${host}`));
  }
});

test("buildCsp: Crisp hosts present in the right directives", () => {
  const csp = buildCsp(SAMPLE_ENV);
  assert.match(csp, new RegExp(`script-src[^;]*${CSP_ALLOW_CRISP.script}`));
  assert.match(csp, new RegExp(`style-src[^;]*${CSP_ALLOW_CRISP.style}`));
  assert.match(csp, new RegExp(`font-src[^;]*${CSP_ALLOW_CRISP.font}`));
  assert.match(csp, new RegExp(`frame-src[^;]*${CSP_ALLOW_CRISP.frame}`));
  assert.ok(csp.includes(CSP_ALLOW_CRISP.connect));
  assert.ok(csp.includes(CSP_ALLOW_CRISP.ws));
});

test("buildCsp: Google Fonts hosts present in style-src and font-src", () => {
  const csp = buildCsp(SAMPLE_ENV);
  assert.match(csp, new RegExp(`style-src[^;]*${CSP_ALLOW_FONTS.style}`));
  assert.match(csp, new RegExp(`font-src[^;]*${CSP_ALLOW_FONTS.font}`));
});

test("buildCsp: Supabase + API + Sentry hosts reach connect-src", () => {
  const csp = buildCsp(SAMPLE_ENV);
  assert.ok(csp.includes(SAMPLE_ENV.apiUrl));
  assert.ok(csp.includes(SAMPLE_ENV.supabaseUrl));
  // DSN origin (not raw DSN with public key) must be used.
  assert.ok(csp.includes("https://o456.ingest.sentry.io"));
  assert.ok(!csp.includes("abc123@")); // no secrets leaked through
});

// ---- Non-regressable directives -------------------------------------------
test("buildCsp: non-regressable hardening directives", () => {
  const csp = buildCsp(SAMPLE_ENV);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.match(csp, /object-src 'none'/);
  assert.match(csp, /base-uri 'self'/);
  assert.match(csp, /form-action 'self'/);
  assert.match(csp, /default-src 'self'/);
});

// ---- Graceful degradation --------------------------------------------------
test("buildCsp: malformed Sentry DSN does not throw or inject garbage", () => {
  const csp = buildCsp({ ...SAMPLE_ENV, sentryDsn: "not-a-url" });
  assert.ok(!csp.includes("not-a-url"));
  assert.ok(!csp.includes("undefined"));
  assert.ok(!/connect-src  /.test(csp)); // no double-space from empty slot
});

test("buildCsp: all-empty env still produces a valid restrictive policy", () => {
  const csp = buildCsp({});
  assert.match(csp, /^default-src 'self'/);
  assert.match(csp, /connect-src 'self'/);
  assert.match(csp, /frame-ancestors 'none'/);
});

// ---- Header array shape ----------------------------------------------------
test("buildSecurityHeaders: returns exactly five headers (guard against silent removal)", () => {
  const headers = buildSecurityHeaders(SAMPLE_ENV);
  assert.equal(headers.length, 5);
});

test("buildSecurityHeaders: each header has the expected fixed value", () => {
  const headers = buildSecurityHeaders(SAMPLE_ENV);
  const asMap = Object.fromEntries(headers.map(h => [h.key, h.value]));
  assert.equal(asMap["X-Frame-Options"],        "DENY");
  assert.equal(asMap["X-Content-Type-Options"], "nosniff");
  assert.equal(asMap["Referrer-Policy"],        "strict-origin-when-cross-origin");
  assert.equal(asMap["Permissions-Policy"],     "camera=(), microphone=(), geolocation=()");
  assert.equal(asMap["Content-Security-Policy"], buildCsp(SAMPLE_ENV));
});
