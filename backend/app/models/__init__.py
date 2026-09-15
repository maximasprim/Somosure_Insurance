"""Importing app.models (directly or transitively) guarantees every model
is registered on Base.metadata.

Without this, a model that no route/service ever imports directly (e.g.
Vehicle/InsuredAsset - nothing references the ORM class itself today, only
the vehicle_id/insured_asset_id foreign key columns on Application) never
gets registered, and anything that relies on Base.metadata being complete
- Base.metadata.create_all() for a quick dev setup, introspection, the
test suite - silently fails or produces an incomplete schema. Alembic's
env.py already imported every module explicitly for this exact reason;
this file makes that guarantee hold for every other entry point too, not
just migrations.
"""

from app.models import (  # noqa: F401
    application,
    asset,
    automation,
    claim,
    content,
    crm,
    customer,
    financing,
    notification,
    partner,
    payment,
    policy,
    provider,
    quote,
    referral,
    renewal,
    sticker,
    support,
    user,
    whatsapp,
)
