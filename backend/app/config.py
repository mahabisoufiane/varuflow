from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/varuflow"
    CORS_ORIGINS: str = "http://localhost:3000"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    RESEND_API_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    FORTNOX_CLIENT_ID: str = ""
    FORTNOX_CLIENT_SECRET: str = ""
    FORTNOX_REDIRECT_URI: str = "https://varuflow-production.up.railway.app/api/integrations/fortnox/callback"
    OPENAI_API_KEY: str = ""
    PORTAL_JWT_SECRET: str = "portal-secret-change-in-production-32chars"
    PORTAL_BASE_URL: str = "https://varuflow.se"
    FRONTEND_URL: str = "https://varuflow.se"
    SENTRY_DSN: str = ""
    ENV: str = "development"
    DEBUG: bool = True

    # ── Standalone local auth ──────────────────────────────────────────────────
    # Strong random secret used to sign local JWT access tokens.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    AUTH_JWT_SECRET: str = "change-me-in-production-use-a-64-char-random-hex-string"

    # SMTP settings for auth emails (verification, password reset)
    SMTP_HOST: str = ""          # e.g. smtp.mailgun.org | smtp.sendgrid.net
    SMTP_PORT: int = 587         # 587 = STARTTLS, 465 = TLS, 25 = plain
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@varuflow.se"


settings = Settings()
