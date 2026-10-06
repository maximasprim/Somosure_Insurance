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

    cors_origins: str = "http://localhost:3000", "https://somosure-insuarance-ltd.vercel.app"

    # Used to build links inside emails/SMS sent to users (password reset,
    # etc.) - the frontend origin, not the API's own.
    frontend_base_url: str = "http://localhost:3000", "https://somosure-insuarance-ltd.vercel.app"

    # Real email delivery via a standard SMTP account (a work email
    # inbox, not a dedicated transactional-email service) - see
    # .env.example for setup notes. Left blank, email falls back to
    # MockDispatcher (logs instead of sending).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Somosure"
    smtp_use_tls: bool = True

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

    # Upload screening for application/financing documents (see
    # app/services/document_validation.py).
    #   strict  - junk (wrong file type, blank/corrupt file, a PDF that
    #             clearly isn't the claimed document) is refused with a
    #             clear message. Recommended for production.
    #   lenient - nothing is refused; suspicious files are stored flagged
    #             "needs_review" with the reason, for staff to see.
    #   off     - no screening at all (original behaviour).
    document_validation: str = "strict"

    # Audit trail (see docs/AUDIT_TRAIL.md).
    audit_enabled: bool = True
    # Extra comma-separated table names to leave out of change capture
    # (on top of the built-in list in app/audit/capture.py).
    audit_excluded_tables: str = ""
    # Also record every admin READ request (very detailed, grows fast).
    # Document downloads and exports are always recorded regardless.
    audit_log_reads: bool = False
    # Record public/guest requests that change data (quote requests, uploads...).
    audit_log_guest_requests: bool = True

    # Quote categories with no live (non-demo) pricing are shown to
    # customers as "coming soon" with an agent hand-off. Set true in a
    # demo/staging environment to let the mock insurers' demo quotes
    # through for every category instead.
    allow_demo_quote_categories: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache means .env is read once per process - restart on change.
    return Settings()
