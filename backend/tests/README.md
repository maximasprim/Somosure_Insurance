# Test suite

Integration tests against a REAL PostgreSQL database - not SQLite, not
mocked sessions. Several models use Postgres-specific UUID/JSON column
types that don't translate to SQLite, and more importantly, running
against the real engine is what actually catches real bugs (see below).

## Setup

```bash
createdb somosure_test
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/somosure_test"
export DATABASE_URL="$TEST_DATABASE_URL"   # some app code reads this directly
export JWT_SECRET_KEY="test-secret"
pip install -r requirements-dev.txt
pytest tests/ -v
```

CI (`.github/workflows/ci.yml`) runs this automatically against a real
Postgres service container on every push/PR.

## What's covered

- `test_auth.py` - registration (incl. the linked Customer record),
  duplicate email handling, login success/failure, token refresh
- `test_quotes.py` - the quote engine, guest customer/lead creation,
  repeat-guest lead advancement, and the aggregator multi-insurer
  fan-out (verifies one call genuinely returns distinctly-priced quotes
  tagged with different underlying insurers)
- `test_journey.py` - the full customer journey in one test: quote →
  application → document upload → submit → underwriting approval →
  M-Pesa payment → signed webhook verification → automatic policy
  issuance → automation-engine-driven sticker generation. Also covers
  webhook signature rejection and duplicate-webhook idempotency.
- `test_rbac.py` - role-gated endpoints actually block unauthorized
  roles and allow authorized ones; unauthenticated requests are rejected
  rather than silently allowed
- `test_financing.py` - eligibility math checked against the spec's own
  worked example, installment schedule generation (including rounding),
  and rejection paths (amount ceiling, invalid term)

## What this suite already found and fixed

Written and run for the first time during this build, this suite caught
three real, previously-undetected bugs - the kind that only surface when
code actually executes, not when it's read or import-checked:

1. **`passlib==1.7.4` is incompatible with `bcrypt>=4.1`** (which removed
   an attribute passlib's version probe reads) - this broke password
   hashing entirely, not just a warning. Fixed by pinning `bcrypt==4.0.1`.
2. **`app/models/asset.py` (Vehicle, InsuredAsset) was never imported by
   the running app**, only by Alembic's `env.py` - so `Base.metadata`
   was incomplete for anyone not going through a migration (e.g. a fresh
   `create_all()`, or this test suite). Fixed by adding `app/models/__init__.py`
   that imports every model module, and having `app/main.py` import it.
3. **A systemic UUID-serialization bug across ~20 endpoints** - every
   response schema with `id: str` (and other UUID foreign keys typed as
   `str`) combined with `from_attributes=True` crashed with a
   `ResponseValidationError` the moment a route returned a raw ORM object
   directly, because Pydantic v2 doesn't auto-coerce a `UUID` object into
   a `str`-typed field. Fixed by changing every such field to `uuid.UUID`
   across `auth.py`, `application.py`, `admin.py`, `automation.py`,
   `crm.py`, `financing.py`, `payment.py`, and `me.py` schemas - this
   affected user registration, provider/product CRUD, application
   creation, automation rule management, financing applications,
   customer profile, and support tickets.

## What's not covered yet

CRM lead pipeline endpoints, sticker workflow transitions, automation
rule CRUD, admin reports, and the provider adapter registry itself
(beyond what's exercised indirectly through the quote/journey tests)
don't have dedicated test files yet - the highest-value flows were
prioritized first given the scope of what needed covering.
