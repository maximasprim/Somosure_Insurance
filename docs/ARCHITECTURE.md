# Architecture - Phase 1

## Layers (backend)

```
API routes (app/api/v1)      - thin, no business logic
    ↓
Services (app/services)      - business logic, transactions
    ↓
Provider adapters (app/providers)  - normalize each insurer's API shape
    ↓
Models (app/models)          - SQLAlchemy, source of truth for schema
```

Routes never talk to the database or a provider directly - they call a
service, which is the only thing allowed to open a transaction or call a
provider adapter. This is what makes it possible to add real insurer
integrations later without touching route code (spec §32).

## Provider abstraction (spec §5, §33)

Every insurer/broker is represented by an `InsuranceProvider` row plus an
`InsuranceProviderAdapter` implementation. The registry
(`app/providers/registry.py`) resolves a provider row to its adapter at
runtime based on `integration_mode`. Today only `MockProvider` exists;
`BritamAdapter`, `JubileeAdapter`, etc. get added to `_REAL_ADAPTERS` once
real API documentation and credentials are supplied - nothing else in the
codebase changes.

Every adapter method returns a normalized dataclass (`NormalizedQuote`,
`PolicyResult`, `ClaimStatusResult`, ...) so a `Quote` row always has the
same shape regardless of which insurer produced it.

## Provider failure isolation (spec §46)

`quote_service.request_quotes` fans a quote request out to every active
provider concurrently and never lets one provider's exception break the
others - a failed provider is logged, the request is flagged
`partial_failure`, and the customer still sees quotes from everyone who
responded, with a plain-language note.

## Auth & RBAC

JWT access tokens (short-lived) carry the user's role name as a claim;
refresh tokens are longer-lived and only usable at `/api/v1/auth/refresh`.
`require_roles(...)` in `app/core/security.py` is a dependency factory -
any route can restrict itself to specific roles without duplicating logic.
Roles are seeded from the fixed list in spec §24; fine-grained permissions
(`permissions` / `role_permissions` tables) exist in the schema for Phase 2
when route-level permission checks (not just role checks) are needed.

## What's deliberately not here yet

Payments, WhatsApp, CRM, renewals engine, sticker workflow, financing, and
admin analytics are real modules with their own state machines - building
them now, before the foundation is reviewed, would mean guessing at
interfaces the foundation should define. They're scoped in the README
roadmap instead.
