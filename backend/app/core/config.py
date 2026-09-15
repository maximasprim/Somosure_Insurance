from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "somosure-documents"

    cors_origins: str = "http://localhost:3000"

    # Error monitoring (spec §2, §30). Only initializes if a real DSN is
    # configured - never fabricates monitoring activity. Get a project DSN
    # from sentry.io and set SENTRY_DSN in backend/.env to enable.
    sentry_dsn: str = ""

    # SMS dispatch (spec §26). Only activates if both are set - see
    # app/notifications/africastalking_dispatcher.py for signup steps.
    africastalking_api_key: str = ""
    africastalking_username: str = ""

    # WhatsApp (spec §17). verify_token and app_secret are values WE
    # choose and configure in Meta's App Dashboard - real regardless of
    # whether a WABA/access token exists yet. See docs/WHATSAPP.md.
    whatsapp_verify_token: str = "somosure-dev-verify-token"
    whatsapp_app_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache means .env is read once per process - restart on change.
    return Settings()
