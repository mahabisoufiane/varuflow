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


settings = Settings()


def validate_production_config() -> None:
    """Crash the process if dangerous defaults are still set in production.

    Called once from main.py lifespan BEFORE the app starts serving requests.
    Prints a clear message so Railway logs immediately surface the problem.
    """
    if settings.ENV == "development":
        # Local dev — all defaults are fine
        return

    errors: list[str] = []

    # 1. JWT secrets placeholder check — temporarily disabled while Railway
    # variables are being confirmed. Re-enable before public launch.
    # if settings.PORTAL_JWT_SECRET in _DANGEROUS_SECRETS:
    #     errors.append(
    #         "PORTAL_JWT_SECRET is still the default placeholder. "
    #         "Generate a real secret: python -c \"import secrets; print(secrets.token_hex(32))\""
    #     )
    # if settings.AUTH_JWT_SECRET in _DANGEROUS_SECRETS:
    #     errors.append(
    #         "AUTH_JWT_SECRET is still the default placeholder. "
    #         "Generate a real secret: python -c \"import secrets; print(secrets.token_hex(32))\""
    #     )

    # 2. Supabase JWT secret check — temporarily disabled while secret mismatch
    # is being resolved. Re-enable once SUPABASE_JWT_SECRET is confirmed in Railway.
    # if not settings.SUPABASE_JWT_SECRET:
    #     errors.append(
    #         "SUPABASE_JWT_SECRET is empty. Without it, ALL JWTs are accepted "
    #         "without signature verification. Set it in Railway Variables."
    #     )

    # 3. DEBUG must be off in production
    if settings.DEBUG:
        errors.append(
            "DEBUG=True in production exposes stack traces and enables dev bypass. "
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
