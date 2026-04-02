from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/varuflow"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""
    RESEND_API_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    FORTNOX_CLIENT_ID: str = ""
    FORTNOX_CLIENT_SECRET: str = ""
    FORTNOX_REDIRECT_URI: str = "http://localhost:8000/api/integrations/fortnox/callback"
    OPENAI_API_KEY: str = ""
    ENV: str = "development"
    DEBUG: bool = True


settings = Settings()
