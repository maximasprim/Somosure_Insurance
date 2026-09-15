"""Shared fixtures for the integration test suite.

These tests run against a REAL PostgreSQL database (not SQLite, not
mocks) - several models use Postgres-specific UUID/JSON column types that
don't translate to SQLite, and more importantly, running against the real
engine is what actually proves the schema and queries work, not just that
the Python compiles. Point TEST_DATABASE_URL at a throwaway database
before running pytest; see tests/README.md for setup.

The engine is created fresh per test (function-scoped), not once per
session - an async engine is bound to whatever event loop is active when
it's created, and pytest-asyncio gives each test its own loop by default.
A session-scoped engine intermittently fails with asyncpg errors like
"another operation is in progress" once a later test's loop differs from
the one the engine was created on. Recreating tables per test costs a
little time but avoids an entire class of flaky failures.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/somosure_test"
)


@pytest.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory):
    from app.core.rate_limit import limiter

    # The rate limiter's default storage is in-memory and shared across the
    # whole pytest process (not per-test) - without resetting it, enough
    # tests calling /login in sequence within the same process eventually
    # trip the real 10/minute login limit, causing failures that have
    # nothing to do with the test itself. Reset before each test so rate
    # limiting is exercised deliberately (test_rate_limit.py) rather than
    # leaking between unrelated tests.
    limiter.reset()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_providers(db_session):
    """Three single-insurer demo providers + one demo aggregator (fanning
    out to 3 underlying insurers) - mirrors app/db/seed.py's demo data so
    quote-engine tests don't depend on the full seed script (which also
    creates roles etc. against a different session)."""
    import uuid

    from app.models.provider import InsuranceProvider

    providers = []
    for name in ["Demo Insurer A", "Demo Insurer B", "Demo Insurer C"]:
        p = InsuranceProvider(
            id=uuid.uuid4(), name=name, provider_type="insurer", integration_mode="mock",
            status="active", supports_quote=True, integration_version="mock-0.1",
        )
        db_session.add(p)
        providers.append(p)

    aggregator = InsuranceProvider(
        id=uuid.uuid4(), name="Demo Aggregator (mock)", provider_type="aggregator", integration_mode="mock",
        status="active", supports_quote=True, integration_version="mock-0.1",
    )
    db_session.add(aggregator)
    providers.append(aggregator)

    await db_session.commit()
    return providers


@pytest.fixture
async def seeded_automation_rules(db_session):
    """Mirrors app/db/seed.py's DEFAULT_RULES so automation-dependent
    tests don't need to run the full seed script."""
    import uuid

    from app.models.automation import AutomationRule

    rules = [
        AutomationRule(
            id=uuid.uuid4(), name="Generate sticker on motor policy activation",
            trigger_event="policy.activated", conditions={"category": "motor"},
            action_type="generate_sticker", action_config={}, delay_seconds=0, is_active=True,
        ),
        AutomationRule(
            id=uuid.uuid4(), name="Notify customer their policy is active",
            trigger_event="policy.activated", conditions={},
            action_type="send_notification",
            action_config={"channel": "sms", "subject": "Policy activated", "body_template": "Your policy {policy_number} is now active."},
            delay_seconds=0, is_active=True,
        ),
        AutomationRule(
            id=uuid.uuid4(), name="Send renewal reminder",
            trigger_event="renewal.reminder_due", conditions={},
            action_type="send_notification",
            action_config={"channel": "sms", "subject": "Renewal reminder", "body_template": "Policy {policy_number} due in {days_remaining} days."},
            delay_seconds=0, is_active=True,
        ),
        AutomationRule(
            id=uuid.uuid4(), name="Recover abandoned quote",
            trigger_event="quote.abandoned", conditions={},
            action_type="send_notification",
            action_config={"channel": "sms", "subject": "Complete your quote", "body_template": "Quote {quote_reference} is waiting."},
            delay_seconds=0, is_active=True,
        ),
    ]
    for r in rules:
        db_session.add(r)
    await db_session.commit()
    return rules
