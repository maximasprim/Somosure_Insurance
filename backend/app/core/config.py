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

    cors_origins: str = "http://localhost:3000,https://somosure-insuarance-ltd.vercel.app"

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

    # Who is alerted when someone applies to become a partner (comma-separated).
    # Emails go out through the SMTP account below, texts through the SMS
    # provider; with neither configured the alert is only logged and the
    # application still appears in Admin -> Partner applications.
    partner_alert_emails: str = ""
    partner_alert_phones: str = ""

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
    
    # ---- M-Pesa (Safaricom Daraja "M-Pesa Express" / STK push) -------------
    # mock    - the built-in simulator. Allowed outside production only (or when
    #           ALLOW_MOCK_PAYMENTS=true for a deliberate demo): the simulator's
    #           signing secret is public in the repo, so it must never confirm
    #           real policies on a live server.
    # daraja  - real M-Pesa. Needs the MPESA_* values below. Try it with
    #           MPESA_ENV=sandbox first (developer.safaricom.co.ke), then production.
    mpesa_mode: str = "mock"
    mpesa_env: str = "sandbox"  # sandbox | production
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""  # Paybill number, or the Till number for buy-goods
    mpesa_passkey: str = ""  # the Lipa Na M-Pesa Online passkey
    mpesa_transaction_type: str = "CustomerPayBillOnline"  # or CustomerBuyGoodsOnline for a Till
    # Public https address of THIS backend (e.g. https://somosure-backend.onrender.com).
    # Safaricom posts payment results to <this>/api/v1/webhooks/pay/<MPESA_CALLBACK_SECRET>.
    mpesa_callback_base_url: str = ""
    # A long random string that is part of the callback address. Daraja callbacks
    # carry no signature, so this secret in the URL (plus an independent
    # confirmation call to Safaricom) is what stops anyone forging a payment.
    mpesa_callback_secret: str = ""
    allow_mock_payments: bool = False

    # ---- Background jobs (renewal reminders, abandoned-quote recovery, ...) ----
    # In-process scheduler. Safe with several server instances: a database lock
    # lets only one run each job at a time. NOTE: on a host that puts the service
    # to sleep when idle (e.g. Render's free plan) it can't run while asleep - use
    # the CRON_SECRET endpoint below from an always-on pinger as well/instead.
    scheduler_enabled: bool = False
    scheduler_tick_seconds: int = 60
    # Lets an external scheduler (cron-job.org, a Render Cron Job, GitHub Actions)
    # trigger the jobs: POST /api/v1/internal/cron/run with header
    # "X-Cron-Secret: <value>". Empty = that endpoint is switched off.
    cron_secret: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache means .env is read once per process - restart on change.
    return Settings()
