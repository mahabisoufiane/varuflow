// ---------------------------------------------------------------------------
// Shared security-headers module for the Next.js frontend.
//
// This file is imported by `next.config.mjs` at build time and exercised by
// `frontend/src/tests/test_security_headers.mjs` so a careless edit to any
// allow-list can be caught by CI before it ships.
//
// Design constraints (see docs/operations/security-hardening.md):
//   * buildCsp()/buildSecurityHeaders() must be PURE — no reads from
//     process.env, no side effects. The caller passes env in.
//   * The emitted CSP must be byte-identical to the policy shipped inline in
//     next.config.mjs prior to this refactor. A golden-string test asserts
//     this invariant.
//   * Every third-party host lives in one of the CSP_ALLOW_* constants so it
//     is trivially grep-able and individually justifiable.
// ---------------------------------------------------------------------------

/** Stripe Checkout + Elements + webhook-confirmation endpoint. */
export const CSP_ALLOW_STRIPE = Object.freeze({
  script: "https://js.stripe.com",
  frame:  ["https://js.stripe.com", "https://hooks.stripe.com"],
  connect: "https://api.stripe.com",
});

/** Crisp live-chat widget (script + websocket + font). */
export const CSP_ALLOW_CRISP = Object.freeze({
  script:  "https://client.crisp.chat",
  style:   "https://client.crisp.chat",
  font:    "https://client.crisp.chat",
  frame:   "https://client.crisp.chat",
  connect: "https://client.crisp.chat",
  ws:      "wss://client.relay.crisp.chat",
});

/** Google Fonts (CSS on googleapis, WOFF2 on gstatic). */
export const CSP_ALLOW_FONTS = Object.freeze({
  style: "https://fonts.googleapis.com",
  font:  "https://fonts.gstatic.com",
});

/**
 * Build the full Content-Security-Policy header value.
 *
 * @param {{
 *   apiUrl?: string,
 *   supabaseUrl?: string,
 *   sentryDsn?: string,
 * }} env - already-validated env vars. Missing values are omitted from the
 *          corresponding directives (never injected as empty strings).
 * @returns {string} CSP header value, directives separated by "; ".
 */
export function buildCsp(env = {}) {
  const apiUrl      = env.apiUrl      || "";
  const supabaseUrl = env.supabaseUrl || "";
  const sentryDsn   = env.sentryDsn   || "";

  // Extract the Sentry ingest host so we don't have to whitelist a wildcard.
  // A malformed DSN degrades gracefully — we simply skip Sentry in connect-src
  // rather than throw at build time.
  let sentryHost = "";
  try {
    if (sentryDsn) sentryHost = new URL(sentryDsn).origin;
  } catch { /* ignore malformed DSN */ }

  const connectSrc = [
    "'self'",
    apiUrl,
    supabaseUrl,
    sentryHost,
    CSP_ALLOW_CRISP.connect,
    CSP_ALLOW_CRISP.ws,
    CSP_ALLOW_STRIPE.connect,
  ].filter(Boolean).join(" ");

  // Next.js App Router uses inline scripts for hydration bootstrap.
  // 'strict-dynamic' causes CSP3 browsers to ignore 'unsafe-inline' for
  // scripts, trusting only nonce-propagated scripts. We keep 'unsafe-inline'
  // as a CSP2 fallback for older browsers. 'unsafe-eval' is removed — Next.js
  // 16 does not require it in production builds.
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline' 'strict-dynamic' ${CSP_ALLOW_STRIPE.script} ${CSP_ALLOW_CRISP.script}`,
    `style-src 'self' 'unsafe-inline' ${CSP_ALLOW_FONTS.style} ${CSP_ALLOW_CRISP.style}`,
    `font-src 'self' data: ${CSP_ALLOW_FONTS.font} ${CSP_ALLOW_CRISP.font}`,
    "img-src 'self' data: blob: https:",
    `connect-src ${connectSrc}`,
    `frame-src ${CSP_ALLOW_STRIPE.frame.join(" ")} ${CSP_ALLOW_CRISP.frame}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

/**
 * Build the full array of security headers Next.js emits on every route.
 * @param {object} env - see buildCsp().
 * @returns {Array<{ key: string, value: string }>}
 */
export function buildSecurityHeaders(env = {}) {
  return [
    { key: "X-Frame-Options",         value: "DENY" },
    { key: "X-Content-Type-Options",  value: "nosniff" },
    { key: "Referrer-Policy",         value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy",      value: "camera=(), microphone=(), geolocation=()" },
    { key: "Content-Security-Policy", value: buildCsp(env) },
  ];
}
