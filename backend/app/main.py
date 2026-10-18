import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.models  # noqa: F401 - guarantees every model is registered on
# Base.metadata regardless of which routes happen to import which model
# classes directly (see app/models/__init__.py for why this matters).
from app.api.v1 import admin, admin_affiliates, admin_audit, admin_claims, admin_content, admin_customers, admin_ops, admin_rate_cards, admin_users, applications, auth, automation, claims, content, contact, financing, leads, me, partners, payments, policies, quotes, reports, search, stickers, whatsapp
from app.api.v1 import admin_ipf, admin_partner_applications, admin_pricing, affiliate_me, internal_cron, partner_applications
from app.audit.capture import install as install_audit_capture
from app.audit.middleware import AuditMiddleware
from app.core.config import get_settings
from app.core.guest_access import GUEST_HEADER
from app.core.rate_limit import limiter
from app.core.security_headers import SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO)
settings = get_settings()

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Starts the in-process background scheduler when SCHEDULER_ENABLED=true."""
    task = None
    if settings.scheduler_enabled:
        from app.services.scheduler import scheduler_loop

        task = asyncio.create_task(scheduler_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="Somosure Insurance Platform API",
    description="Foundation phase: auth, providers/quotes with mock adapter. "
    "See /docs for the live schema.",
    version="0.1.0-phase1",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)

# Audit trail: record who did what (see docs/AUDIT_TRAIL.md). Change capture
# hooks the database session; the middleware records each data-changing or
# sensitive request with its outcome and the stated reason.
install_audit_capture()
app.add_middleware(AuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # The browser may read this response header: it carries the guest access
    # token issued when an application is created (see app/core/guest_access.py).
    expose_headers=[GUEST_HEADER],
)

app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(applications.router)
app.include_router(policies.router)
app.include_router(admin.router)
app.include_router(admin_audit.router)
app.include_router(admin_affiliates.router)
app.include_router(affiliate_me.router)
app.include_router(partner_applications.router)
app.include_router(admin_partner_applications.router)
app.include_router(admin_users.router)
app.include_router(admin_users.roles_router)
app.include_router(admin_customers.router)
app.include_router(admin_ops.policies_router)
app.include_router(admin_ops.payments_router)
app.include_router(admin_ops.renewals_router)
app.include_router(admin_ops.support_router)
app.include_router(admin_ops.tasks_router)
app.include_router(admin_rate_cards.router)
app.include_router(payments.router)
app.include_router(payments.webhook_router)
app.include_router(me.router)
app.include_router(leads.router)
app.include_router(automation.router)
app.include_router(stickers.router)
app.include_router(financing.router)
app.include_router(financing.admin_router)
app.include_router(admin_ipf.router)
app.include_router(admin_ipf.officers_router)
app.include_router(admin_pricing.tiers_router)
app.include_router(admin_pricing.anniversary_config_router)
app.include_router(admin_pricing.anniversary_plan_router)
app.include_router(reports.router)
app.include_router(claims.router)
app.include_router(admin_claims.router)
app.include_router(search.router)
app.include_router(content.router)
app.include_router(content.faq_router)
app.include_router(admin_content.router)
app.include_router(partners.router)
app.include_router(whatsapp.router)
app.include_router(whatsapp.admin_router)
app.include_router(contact.router)
app.include_router(internal_cron.router)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
