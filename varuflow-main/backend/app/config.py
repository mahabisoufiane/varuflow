"""Application settings loaded from environment variables / .env file.

All fields default to safe LOCAL-DEV values.
Production secrets are validated at startup in main.py — the app refuses
to boot if dangerous defaults are still present.

Generate strong secrets:
  python -c "import secrets; print(secrets.token_hex(32))"
"""
import sys
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

# Sentinel values that must never reach production
_DANGEROUS_SECRETS: set[str] = {
    "portal-secret-change-in-production-32chars",
    "change-me-in-production-use-a-64-char-random-hex-string",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Core ──────────────────────────────────────────────────────────────────
    # Default to "production" so a misconfigured Railway deploy is STRICT,
    # not permissive. Override to "development" only in local .env files.
    ENV:   str  = "production"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/varuflow"

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "https://varuflow.vercel.app"

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL:         str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET:  str = ""

    # ── Third-party services ──────────────────────────────────────────────────
    RESEND_API_KEY:       str = ""
    STRIPE_SECRET_KEY:         str = ""
    STRIPE_WEBHOOK_SECRET:     str = ""
    STRIPE_STARTER_PRICE_ID:   str = ""   # Starter plan (499 SEK/mo) — falls back to PRO price if blank
    STRIPE_PRO_PRICE_ID:       str = ""   # Professional plan (1490 SEK/mo)
    FORTNOX_CLIENT_ID:    str = ""
    FORTNOX_CLIENT_SECRET:str = ""
    # Must be set per deployment (dev / preprod / prod / per-country).
    # Shape: https://<backend-host>/api/integrations/fortnox/callback
    FORTNOX_REDIRECT_URI: str = ""
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt Fortnox OAuth
    # tokens at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If empty, tokens are stored in plaintext (legacy behaviour — not recommended).
    FORTNOX_ENCRYPTION_KEY: str = ""
    # ── Exchange rates (Item 34) ─────────────────────────────────────────
    # openexchangerates.org app_id. Empty disables the daily rate sweep
    # — existing transactions continue to work at rate = 1 (identity).
    OPEN_EXCHANGE_RATES_API_KEY: str = ""
    # ── PII encryption (Item 28) ─────────────────────────────────────────
    # Fernet key used by app.services.encryption to transparently encrypt
    # sensitive columns (TOTP secrets, customer email/phone/address, etc.)
    # at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If empty, encryption is a no-op — new writes are plaintext and legacy
    # rows stay readable. Recommended in every non-dev environment.
    PII_ENCRYPTION_KEY: str = ""
    # Zero-downtime rotation: set to the previous PII_ENCRYPTION_KEY while
    # rotating. MultiFernet tries each key in order on decrypt, so rows
    # encrypted with the old key remain readable until they are re-written
    # under the new key. Clear this once the backfill is complete. See
    # docs/operations/security-hardening.md for the runbook.
    PII_ENCRYPTION_KEY_PREVIOUS: str = ""
    OPENAI_API_KEY:        str = ""
    SENTRY_DSN:            str = ""

    # Bolagsverket (Swedish Companies Registration Office) company-lookup
    # API. Optional — if empty the lookup endpoint returns a stub payload
    # with ``status: "not_configured"`` so development environments work
    # without sharing production credentials.
    BOLAGSVERKET_API_URL:   str = ""
    BOLAGSVERKET_API_TOKEN: str = ""

    # ── BankID (Swedish e-identification) ────────────────────────────────────
    # Defaults to the official BankID test environment so dev boxes can
    # run the flow without provisioning a real Relying Party certificate.
    # Production must override to https://appapi2.bankid.com/rp/v6.0 and
    # supply a mutually-authenticated client cert from Finansiell ID-
    # Teknik BID AB. See https://www.bankid.com/en/utvecklare for the
    # onboarding + certificate issuance runbook.
    BANKID_API_URL: str = "https://appapi2.test.bankid.com/rp/v6.0"
    # PEM bundle containing the relying-party client cert + private key
    # (in that order). Empty disables BankID — the router then returns
    # 503 so operators get a clear signal instead of a generic 500.
    BANKID_CLIENT_CERT_PATH: str = ""
    # CA bundle for verifying the BankID server. Empty falls back to the
    # bundled certifi roots — acceptable in test, recommended to pin in
    # production to the BankID-provided root.
    BANKID_CA_CERT_PATH: str = ""

    # ── URLs ──────────────────────────────────────────────────────────────────
    PORTAL_BASE_URL: str = "https://varuflow.vercel.app"
    FRONTEND_URL:    str = "https://varuflow.vercel.app"

    # Calendly booking links used in NPS follow-up and retention emails
    CALENDLY_DETRACTOR_URL: str = "https://calendly.com/varuflow/feedback"
    CALENDLY_CSM_URL:       str = "https://calendly.com/varuflow/success"
    CALENDLY_FOUNDER_URL:   str = "https://calendly.com/varuflow/founders"

    # ── JWT secrets ───────────────────────────────────────────────────────────
    # Portal JWT: signs short-lived tokens for B2B customer portal access.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    PORTAL_JWT_SECRET: str = "portal-secret-change-in-production-32chars"

    # Local-auth JWT: signs 15-min access tokens for standalone auth system.
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    AUTH_JWT_SECRET: str = "change-me-in-production-use-a-64-char-random-hex-string"

    # ── SMTP (auth emails) ────────────────────────────────────────────────────
    SMTP_HOST:     str = ""           # e.g. smtp.mailgun.org | smtp.sendgrid.net
    SMTP_PORT:     int = 587          # 587 = STARTTLS | 465 = TLS | 25 = plain
    SMTP_USER:     str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM:     str = "noreply@varuflow.se"
    # ── WhatsApp / SMS (Item 18) ──────────────────────────────────────
    # Provider-agnostic HTTP bridge. The service POSTs a JSON body of
    # ``{to, from, body}`` to WHATSAPP_API_URL with a Bearer token; any
    # gateway that matches that contract (Twilio Content API proxy,
    # Meta Cloud API behind a thin shim, 46elks, etc.) works. Empty
    # URL or token disables the channel — the dunning sweep falls
    # back to email-only, never 500s.
    WHATSAPP_API_URL:    str = ""
    WHATSAPP_API_TOKEN:  str = ""
    WHATSAPP_FROM_NUMBER: str = ""
    # Same contract for SMS. Typically the same provider as WhatsApp
    # but split into its own env vars so operators can enable one
    # channel without the other.
    SMS_API_URL:    str = ""
    SMS_API_TOKEN:  str = ""
    SMS_FROM_NUMBER: str = ""
    # ── nShift / Unifaun shipping gateway ────────────────────────────────────
    # Covers PostNord, DHL, UPS via a single integration.
    # Leave empty to disable real label generation (tracking stored manually).
    NSHIFT_API_KEY: str = ""
    NSHIFT_API_SECRET: str = ""
    NSHIFT_SENDER_ID: str = ""  # nShift sender profile ID

    # ── Storefront Stripe webhook ─────────────────────────────────────────────
    # Separate webhook secret for /api/shop/webhooks/stripe so the storefront
    # and invoice/billing webhooks each verify with their own key.
    STRIPE_STOREFRONT_WEBHOOK_SECRET: str = ""

    # ── Admin API ─────────────────────────────────────────────────────
    # Shared secret for admin-only endpoints (e.g. waitlist list/export).
    # Generate: python -c "import secrets; print(secrets.token_hex(32))"
    # Leave empty to disable all admin endpoints.
    ADMIN_API_KEY: str = ""
    # Zero-downtime rotation: set this to the OLD key during a rollout so
    # in-flight admin scripts keep working while operators distribute the
    # new key, then clear it once the cutover is complete. See
    # SECURITY.md § "Admin key rotation" for the runbook.
    ADMIN_API_KEY_PREVIOUS: str = ""
    # ── Proxy trust ───────────────────────────────────────────────────────────
    # Set to True on Railway/Render where X-Forwarded-For is injected by a
    # trusted load balancer. When False the rate limiter uses request.client.host.
    TRUST_PROXY: bool = True

    # Escape hatch for integration tests and the occasional
    # load-balancer-behind-a-load-balancer deploy where in-process
    # rate limiting should sleep. When True the middleware AND every
    # per_org/per_ip dep-style limiter short-circuit to a no-op. Must
    # never be True in production — startup logs warn if ENV=production
    # and this flag is on.
    RATE_LIMIT_DISABLED: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    # When set, the rate limiter uses Redis for a shared sliding-window counter
    # that works correctly across multiple Railway replicas.
    # Format: redis://[:password@]host[:port][/db]  or  rediss:// for TLS.
    # Leave empty to fall back to the in-memory counter (single-replica only).
    REDIS_URL: str = ""

    # ── Country / i18n defaults ──────────────────────────────────────────────
    # Resolved country for a request falls back to this code when no header,
    # subdomain, or org-level country is available.
    DEFAULT_COUNTRY: str = "SE"

    # ── Security hardening toggles ───────────────────────────────────────────
    # JWT signature enforcement. Defaults to True — production must verify
    # signatures. Override to False in a local .env only if you are running
    # without a Supabase project. Never set False on Railway.
    ENFORCE_JWT_SIGNATURE: bool = True

    # Production startup refuses to boot if placeholder secrets are still
    # present or required secrets are missing.
    ENFORCE_SECRET_VALIDATION: bool = True

    # Defense-in-depth for the dev auth bypass. Even when ENV=development,
    # the unauthenticated dev user is only served if this flag is also True.
    # This prevents a misconfigured Railway deploy (ENV accidentally set to
    # "development") from silently disabling authentication.
    ALLOW_DEV_BYPASS: bool = False

    # When True, all write endpoints return 503. See middleware/readonly.py.
    # Flip via Railway Variables during DB restores / maintenance windows.
    READONLY_MODE: bool = False

    # ── PostHog product analytics ─────────────────────────────────────────────
    # Set POSTHOG_API_KEY on Railway to enable server-side event tracking.
    # POSTHOG_HOST defaults to the EU-hosted endpoint for GDPR compliance.
    # Leave empty to disable analytics entirely (no exceptions raised).
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST:    str = "https://eu.i.posthog.com"


settings = Settings()


def is_production() -> bool:
    """True when running in a production-like environment.

    Accepts "production" or "prod" (case-insensitive) so a Railway deploy
    with ENV=prod behaves identically to ENV=production.
    """
    return settings.ENV.strip().lower() in ("production", "prod")


def validate_production_config() -> None:
    """Crash the process if dangerous defaults are still set in production.

    Called once from main.py lifespan BEFORE the app starts serving requests.
    Prints a clear message so Railway logs immediately surface the problem.
    """
    if not is_production():
        # Local dev — all defaults are fine
        return

    errors: list[str] = []

    # Opt-in enforcement — keeps current Railway deployment working while
    # still giving a single knob to flip for pre-launch hardening.
    if settings.ENFORCE_SECRET_VALIDATION:
        if settings.PORTAL_JWT_SECRET in _DANGEROUS_SECRETS:
            errors.append(
                "PORTAL_JWT_SECRET is still the default placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if settings.AUTH_JWT_SECRET in _DANGEROUS_SECRETS:
            errors.append(
                "AUTH_JWT_SECRET is still the default placeholder. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if not settings.SUPABASE_JWT_SECRET:
            errors.append(
                "SUPABASE_JWT_SECRET is empty. Without it, JWT signature "
                "verification cannot be enabled."
            )
        if settings.ENFORCE_JWT_SIGNATURE and not settings.SUPABASE_JWT_SECRET:
            errors.append(
                "ENFORCE_JWT_SIGNATURE=True but SUPABASE_JWT_SECRET is empty."
            )

    # 3. DEBUG must be off in production
    if settings.DEBUG:
        errors.append(
            "DEBUG=True in production exposes stack traces and enables dev bypass. "
            "Set DEBUG=False in Railway Variables."
        )

    # 4. Fortnox tokens must be encrypted at rest if the integration is in use.
    #    If a customer ever connects Fortnox, their access_token + refresh_token
    #    land in the DB. Without FORTNOX_ENCRYPTION_KEY they are written in
    #    plaintext \u2014 a read-only DB dump would then let an attacker impersonate
    #    the customer against Fortnox's API. Require the key whenever the
    #    OAuth credentials are configured, regardless of whether any org has
    #    connected yet.
    if (settings.ENFORCE_SECRET_VALIDATION
            and (settings.FORTNOX_CLIENT_ID or settings.FORTNOX_CLIENT_SECRET)
            and not settings.FORTNOX_ENCRYPTION_KEY):
        errors.append(
            "Fortnox OAuth is configured but FORTNOX_ENCRYPTION_KEY is empty. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    # 5. CORS must not be wildcarded in production (belt-and-braces \u2014 main.py
    #    already enforces this, but a misconfigured env var should refuse to
    #    boot rather than silently fall back to a permissive default).
    if settings.ENFORCE_SECRET_VALIDATION:
        origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
        if not origins or "*" in origins:
            errors.append(
                "CORS_ORIGINS must be a non-empty, explicit list in production. "
                "Current value: " + repr(settings.CORS_ORIGINS)
            )

    # 6. PII encryption key \u2014 required before any customer data is written.
    #    Without it, columns encrypted by app.services.encryption are stored
    #    in plaintext (TOTP secrets, customer email/phone/address). A read-
    #    only DB dump would expose all PII. Warn loudly; treat as fatal so
    #    operators cannot silently skip it on a fresh deploy.
    if settings.ENFORCE_SECRET_VALIDATION and not settings.PII_ENCRYPTION_KEY:
        errors.append(
            "PII_ENCRYPTION_KEY is empty. Customer PII (email, phone, address) "
            "and TOTP secrets will be stored in plaintext. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )

    # 7. Fortnox redirect URI \u2014 if OAuth credentials are configured the redirect
    #    URI must also be set or the OAuth flow cannot complete.
    if (settings.ENFORCE_SECRET_VALIDATION
            and (settings.FORTNOX_CLIENT_ID or settings.FORTNOX_CLIENT_SECRET)
            and not settings.FORTNOX_REDIRECT_URI):
        errors.append(
            "FORTNOX_CLIENT_ID/SECRET is set but FORTNOX_REDIRECT_URI is empty. "
            "Set it to: https://varuflow-production.up.railway.app/api/integrations/fortnox/callback"
        )

    # 8. RATE_LIMIT_DISABLED must never be True in production \u2014 it silently
    #    removes all rate limits and could be accidentally left over from a
    #    debugging session.
    if settings.RATE_LIMIT_DISABLED:
        errors.append(
            "RATE_LIMIT_DISABLED=True in production disables ALL rate limiting. "
            "Remove this flag from Railway Variables before going live."
        )

    # 9. Sentry DSN \u2014 not a hard crash, but a missing DSN means silent failures
    #    in production. Log a critical warning so it shows up in Railway logs.
    if not settings.SENTRY_DSN:
        log.warning(
            "SENTRY_DSN is not set \u2014 errors in production will not be reported. "
            "Add SENTRY_DSN to Railway Variables for error monitoring."
        )

    if errors:
        for msg in errors:
            log.critical("SECURITY CONFIG ERROR: %s", msg)
        sys.exit(
            "\n\n🚨  VARUFLOW REFUSED TO START — unsafe production configuration:\n"
            + "\n".join(f"  • {e}" for e in errors)
            + "\n\nFix the above in Railway → Variables, then redeploy.\n"
        )
