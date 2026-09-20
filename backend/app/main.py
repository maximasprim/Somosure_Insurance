import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.models  # noqa: F401 - guarantees every model is registered on
# Base.metadata regardless of which routes happen to import which model
# classes directly (see app/models/__init__.py for why this matters).
from app.api.v1 import admin, admin_claims, admin_content, admin_rate_cards, applications, auth, automation, claims, content, contact, financing, leads, me, partners, payments, policies, quotes, reports, search, stickers, whatsapp
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security_headers import SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO)
settings = get_settings()

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1)

app = FastAPI(
    title="Somosure Insurance Platform API",
    description="Foundation phase: auth, providers/quotes with mock adapter. "
    "See /docs for the live schema.",
    version="0.1.0-phase1",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quotes.router)
app.include_router(applications.router)
app.include_router(policies.router)
app.include_router(admin.router)
app.include_router(admin_rate_cards.router)
app.include_router(payments.router)
app.include_router(payments.webhook_router)
app.include_router(me.router)
app.include_router(leads.router)
app.include_router(automation.router)
app.include_router(stickers.router)
app.include_router(financing.router)
app.include_router(financing.admin_router)
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


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
