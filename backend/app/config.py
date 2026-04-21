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
    # `SUPABASE_SERVICE_KEY` is the canonical name used throughout the codebase.
    # `SUPABASE_SERVICE_ROLE_KEY` is accepted as an alias because the Railway
    # deployment was provisioned under that name — resolved at startup below.
    SUPABASE_URL:              str = ""
    SUPABASE_SERVICE_KEY:      str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET:       str = ""
    SUPABASE_ANON_KEY:         str = ""

    # ── Third-party services ──────────────────────────────────────────────────
    RESEND_API_KEY:       str = ""
    STRIPE_SECRET_KEY:    str = ""
    STRIPE_WEBHOOK_SECRET:str = ""
    STRIPE_PRO_PRICE_ID:  str = ""
    FORTNOX_CLIENT_ID:    str = ""
    FORTNOX_CLIENT_SECRET:str = ""
    FORTNOX_REDIRECT_URI: str = "https://varuflow-production.up.railway.app/api/integrations/fortnox/callback"
    OPENAI_API_KEY:        str = ""
    SENTRY_DSN:            str = ""

    # ── URLs ──────────────────────────────────────────────────────────────────
    PORTAL_BASE_URL: str = "https://varuflow.vercel.app"
    FRONTEND_URL:    str = "https://varuflow.vercel.app"

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

    # ── Proxy trust ───────────────────────────────────────────────────────────
    # Set to True on Railway/Render where X-Forwarded-For is injected by a
    # trusted load balancer. When False the rate limiter uses request.client.host.
    TRUST_PROXY: bool = True

    # ── Country / i18n defaults ──────────────────────────────────────────────
    # Resolved country for a request falls back to this code when no header,
    # subdomain, or org-level country is available.
    DEFAULT_COUNTRY: str = "SE"

    # ── Security hardening toggles ───────────────────────────────────────────
    # Deprecated toggles kept for one release so Railway doesn't hard-fail if
    # the variables are still set. They have NO effect — JWT signature
    # verification is now always enforced in production (ENV != development),
    # and production startup always validates that secrets are non-placeholder.
    ENFORCE_JWT_SIGNATURE:    bool = True   # kept for back-compat, ignored
    ENFORCE_SECRET_VALIDATION: bool = True   # kept for back-compat, ignored


settings = Settings()

# Accept SUPABASE_SERVICE_ROLE_KEY as an alias for SUPABASE_SERVICE_KEY so
# existing Railway deployments (provisioned with the _ROLE_ name) continue
# to work without a breaking rename. The canonical field is SERVICE_KEY.
if not settings.SUPABASE_SERVICE_KEY and settings.SUPABASE_SERVICE_ROLE_KEY:
    settings.SUPABASE_SERVICE_KEY = settings.SUPABASE_SERVICE_ROLE_KEY


def validate_production_config() -> None:
    """Crash the process if dangerous defaults are still set in production.

    Called once from main.py lifespan BEFORE the app starts serving requests.
    Prints a clear message so Railway logs immediately surface the problem.
    """
    if settings.ENV == "development":
        # Local dev — all defaults are fine
        return

    errors: list[str] = []

    # ── Required secrets in production — no opt-out ─────────────────────────
    if settings.PORTAL_JWT_SECRET in _DANGEROUS_SECRETS or not settings.PORTAL_JWT_SECRET:
        errors.append(
            "PORTAL_JWT_SECRET is empty or the default placeholder. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    elif len(settings.PORTAL_JWT_SECRET) < 32:
        errors.append("PORTAL_JWT_SECRET must be at least 32 characters.")

    if settings.AUTH_JWT_SECRET in _DANGEROUS_SECRETS or not settings.AUTH_JWT_SECRET:
        errors.append(
            "AUTH_JWT_SECRET is empty or the default placeholder. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    elif len(settings.AUTH_JWT_SECRET) < 32:
        errors.append("AUTH_JWT_SECRET must be at least 32 characters.")

    if not settings.SUPABASE_JWT_SECRET:
        errors.append(
            "SUPABASE_JWT_SECRET is empty. Required to verify Supabase JWT "
            "signatures in production."
        )
    elif len(settings.SUPABASE_JWT_SECRET) < 32:
        errors.append("SUPABASE_JWT_SECRET must be at least 32 characters.")

    if not settings.CORS_ORIGINS or settings.CORS_ORIGINS.strip() == "*":
        errors.append(
            "CORS_ORIGINS must be an explicit comma-separated list of origins. "
            "Wildcard '*' is never permitted in production."
        )

    # DEBUG must be off in production
    if settings.DEBUG:
        errors.append(
            "DEBUG=True in production exposes stack traces. "
            "Set DEBUG=False in Railway Variables."
        )

    if errors:
        for msg in errors:
            log.critical("SECURITY CONFIG ERROR: %s", msg)
        sys.exit(
            "\n\n🚨  VARUFLOW REFUSED TO START — unsafe production configuration:\n"
            + "\n".join(f"  • {e}" for e in errors)
            + "\n\nFix the above in Railway → Variables, then redeploy.\n"
        )
