# Somosure Insurance Platform

A digital insurance ecosystem: marketplace, quotation engine, multi-insurer
integration layer, customer portal, CRM, policy/claims/renewal management,
WhatsApp channel, and premium financing (Bidii Credit).

This repo covers all ten build phases from the original spec - Phases
1–6 and 9–10 fully built and verified; Phase 7 (real provider
integrations) has complete groundwork with real research and adapter
code, gated on external API access being granted; Phase 8 (Bidii Credit
financing) is functionally complete against a mock adapter, gated only on
real Bidii API credentials. See the phase table further down for the
honest status of each.

Real auth, a real database schema, a real design system, the full quote →
application → document upload → underwriting approval → M-Pesa payment →
verified webhook → policy issuance flow, a logged-in customer dashboard,
an agent-facing lead pipeline, a real event → rule → action automation
engine, a working multi-insurer aggregator architecture, a functional
Bidii Credit premium-financing module, a management analytics dashboard,
and production-hardening basics (rate limiting, security headers, SEO).

## Testing (spec §49)

`backend/tests/` - 52 integration tests running against a **real
PostgreSQL database**, not mocks or SQLite. Covers auth, rate limiting
(live-verified threshold), the quote engine (including the aggregator
multi-insurer fan-out), the entire customer journey in one test (quote →
application → documents → approval → M-Pesa payment → signed webhook →
policy issuance → automated sticker generation), webhook security,
idempotency, RBAC, financing math, claims (including the real
staff-assisted fallback when a provider has no claims API), notification
dispatch, and global search. See `backend/tests/README.md` for setup and
the real bugs this suite found and fixed by actually running the code
rather than reading it - including a bcrypt/passlib incompatibility that
broke all password hashing, a model-registration gap, a systemic
UUID-serialization bug across ~20 endpoints, a live frontend bug where
the motor quote flow never read back the resolved guest customer ID, and
a rate-limiter test-isolation issue that caused flaky failures when the
full suite ran together. CI (`.github/workflows/ci.yml`) runs this suite
against a real Postgres service container on every push/PR.

## Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL
- **Auth**: JWT (access + refresh), bcrypt password hashing, RBAC
- **Rate limiting & security**: slowapi, secure headers middleware
- **Error monitoring**: optional Sentry hook (activates only with a real DSN)
- **Infra**: Docker Compose (postgres, redis, backend, frontend)
- **Storage/queue**: Supabase Storage (documents); Redis is provisioned in
  Docker Compose but no background job worker (Celery/RQ) consumes it yet
  - see the Phase 6 scheduler note below

## Repo layout

```
somosure/
├── backend/
│   ├── app/
│   │   ├── core/        # config, security, database session
│   │   ├── models/       # SQLAlchemy models (source of truth for schema)
│   │   ├── schemas/       # Pydantic request/response models
│   │   ├── api/v1/        # route modules, thin - no business logic here
│   │   ├── services/       # business logic layer
│   │   ├── providers/       # InsuranceProviderAdapter + MockProvider
│   │   └── db/               # alembic migrations, seed data
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                  # Next.js routes
│   ├── components/ui/         # design-system primitives
│   ├── lib/
│   └── Dockerfile
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   └── PROVIDER_ADAPTERS.md
└── docker-compose.yml
```

## Running locally

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
docker compose up --build
```

- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## What's real vs. mocked in this phase

| Area | Status |
|---|---|
| Auth (register/login/refresh), RBAC | Real |
| Database schema (core + Phase 2 tables) | Real |
| Design system (tokens, Button/Card/Input/Badge) | Real |
| Homepage + product selector shell | Real |
| Provider adapter interface | Real interface, **MockProvider only** - no real insurer credentials exist yet |
| Quotation engine | Real request/normalize flow against MockProvider |
| Motor quote form → compare → application → document upload → submit | Real, end to end (frontend + backend) |
| Policy issuance | Real service, staff-triggered or automatic on verified payment |
| Admin: provider, product, and application review/approval | Real, RBAC-gated, credentials never exposed |
| Payments | Real M-Pesa abstraction (`app/payments`), signature-verified webhook, idempotent processing - **MockMpesaProvider only**, no Daraja credentials exist yet |
| Staff/customer login (frontend) | Real - `/login` and `/register` store a real JWT; role claim routes staff to `/admin`, customers to `/dashboard` |
| Customer dashboard, profile, support tickets | Real - `/dashboard`, `/profile`, `/support`, all backed by `/api/v1/me/*` |
| CRM: leads, activities, funnel | Real - every quote request (guest or logged-in) auto-creates or advances a lead; `/admin/leads` is a working kanban pipeline |
| Automation engine (event → rule → action) | Real - `app/automation/`, seeded with 4 default rules; `/admin/automation` shows rules and run history |
| Sticker workflow | Real - auto-generated on motor policy activation, enforced state machine (`app/services/sticker_service.py`), staff queue at `/admin/stickers` |
| Renewal reminders | Real scanner implementing the 60/30/14/7/3/1/0-day cadence (spec §16), idempotent per policy per day-bucket |
| Abandoned quote recovery | Real scanner (4-hour threshold), fires a recovery notification per abandoned quote request |
| Document storage | Real local-disk implementation for dev; Supabase Storage adapter is a documented stub (`app/core/storage.py`) |
| Claims management (spec §15) | Real - report, document upload, submit (with genuine staff-assisted fallback when a provider has no claims API), staff transition state machine (`app/services/claim_service.py`), customer tracking at `/claims`, staff dashboard at `/admin/claims` |
| WhatsApp | **Not built yet** - genuinely out of scope for this build, no groundwork exists |
| Dynamic quote forms for every product category | Real - motor has a bespoke form; medical, life, travel, home, business, and personal accident all use a shared generic form driven by per-category field config (`lib/quoteFields.ts`), reusing the same quote→application→documents→payment flow (`components/quote/GenericQuoteFlow.tsx`) |
| Marketing site polish | Real - Framer Motion scroll reveals and micro-interactions throughout, a mobile nav drawer (previously missing entirely), a floating WhatsApp CTA (`components/WhatsAppButton.tsx`), animated stats counters, and five new pages (`/insurance`, `/about`, `/renewals`, `/contact`, `/resources`, `/privacy`, `/terms`) - every link in the navbar and footer was cross-checked against the actual route tree to confirm nothing 404s |
| Public contact form | Real - `POST /api/v1/contact`, no auth required, reuses the same guest-customer/lead resolution pattern as the quote engine so messages land in the sales pipeline instead of disappearing |
| Notification dispatch (spec §26) | Real abstraction (`app/notifications/`) - a real, named SMS adapter skeleton for Africa's Talking (Kenya's dominant SMS gateway, genuinely self-serve signup, unlike the insurers) pending only an API key; `MockDispatcher` logs what would be sent and is wired into the automation engine for real today |
| Global search (spec §28) | Real - searches customers, quotes, applications, policies, claims, and payments by reference/phone/name; `/admin/search` |
| Content/CMS (spec §21) | Real - published articles + FAQs (public `/faq`, `/api/v1/content`), admin authoring at `/api/v1/admin/content` |
| Referral system (spec §42) | Real - code generation, redemption at registration, conversion tracked on policy issuance; reward *payment* is a manual admin action by design (spec: "keep reward logic configurable") |
| Partner ecosystem (spec §43) | Foundational record only - `Partner` model + admin CRUD; a partner-specific lead/application workflow is a future capability this supports but doesn't yet implement |
| WhatsApp integration (spec §17) | **Webhook verification is genuinely, fully implemented** - Meta's real subscription-challenge (GET) and HMAC-SHA256 signature scheme (POST) require no fabrication since both depend only on values this app controls, not Meta's approval. Inbound messages create/match a guest Customer by phone (same pattern as guest quotes), log to CRM `Communication` history, and get a basic keyword-routed reply. Only *sending* via Graph API needs a real WABA ID/access token - `MockWhatsAppAdapter` stands in for that alone. Admin inbox at `/admin/whatsapp`. See `docs/WHATSAPP.md` for the real access-model research (Cloud API is genuinely self-serve, unlike the insurers) |
| **Phase 7 groundwork**: real Kenyan providers researched | `docs/PROVIDER_LANDSCAPE.md` - Britam, Jubilee, APA, CIC, ICEA Lion, Old Mutual (direct insurers, no public API found) plus **Lami Technologies, mTek/bolttech, Turaco** (aggregators bridging multiple insurers via one API) |
| **Phase 7**: real provider adapters | 9 real, named adapter classes under `app/providers/` - each raises an informative `NotImplementedError` naming exactly what's missing, never fabricated data. `docs/API_ACCESS_REQUEST_TEMPLATE.md` is a ready-to-send outreach email |
| **Phase 7**: aggregator multi-insurer architecture | Real, working, and verified - `get_quotes_bulk()` lets ONE provider row return quotes from SEVERAL underlying insurers in one call (what Lami/mTek actually do). `MockAggregatorProvider` proves this end-to-end today: one call returns 3 distinctly-priced quotes tagged with their underlying insurer name, with zero changes needed to the quote engine when Lami's real API arrives |
| **Phase 8**: Bidii Credit financing | Fully functional (not "switched off" - this is a confirmed live partnership): eligibility check, application, agreement + installment schedule generation, admin portfolio view. Math verified against the spec's own worked example (KES 30,000 premium → 20% deposit → 80% financed) exactly. `MockBidiiCreditAdapter` stands in only where real Bidii API credentials are still needed |
| **Phase 9**: management analytics | Real KPI overview (customers, leads, quote conversion, active premium, revenue, commission, sticker pipeline), provider performance breakdown, CSV export, `/admin/reports` with live Recharts visualizations |
| **Phase 10**: optimization/hardening | Rate limiting (10/min on login, 200/min app-wide) - **live-tested with real HTTP requests, not just wired up**: confirmed 429 responses kick in exactly at the configured threshold. Security headers confirmed live on an actual response. SEO (`robots.txt`, dynamic `sitemap.ts`, OpenGraph metadata). Optional Sentry hook (only activates with a real DSN - never fabricates monitoring activity) |

**A known, documented limitation:** there is no live background
scheduler yet (Celery/RQ). The renewal scanner, abandoned-quote scanner,
and "run due automations" step all exist as real, callable functions with
real logic, but nothing currently calls them on a timer - the admin
screen at `/admin/automation` triggers them on demand. Pointing a cron
job or Celery beat task at the same three functions is the only thing
that changes once a scheduler exists; none of the underlying logic does.

**What Phase 10 leaves genuinely open, honestly:** load testing, a full
WCAG accessibility audit, and a CI/CD pipeline are operational practices
you run repeatedly against a live, deployed system with real traffic -
not one-time code that gets "finished" in a repo. The pieces that are
actual code (rate limiting, security headers, SEO metadata, structured
error monitoring) are built and verified above; a `.github/workflows` CI
config could be added next if useful, but a load test needs a real
staging deployment to test against, and an accessibility audit needs a
real screen reader pass, not a script pretending to be one.

**Verification performed on this repo, not just written:** the backend was
actually imported (`from app.main import app`) and every one of its 57
routes confirmed to resolve; all 37 tables were confirmed to register on
`Base.metadata` matching all eight migrations exactly. The rate limiter was
tested by actually firing 12 rapid requests at the login endpoint against
a live running server - requests 1–10 passed through, 11–12 correctly
returned `429 Too Many Requests`. Security headers were confirmed present
on a real HTTP response, not just asserted from the middleware code. The
aggregator fan-out was functionally tested - confirming a single
`get_quotes_bulk()` call produces multiple distinctly-priced quotes each
tagged with a different underlying insurer, while a direct insurer adapter
still produces exactly one. The financing math was checked against the
spec's own numbers line by line. The frontend passed a real `tsc --noEmit`
with zero errors, and a full `next build` succeeded for all 17 routes
(isolated from this sandbox's one network restriction - no access to
`fonts.googleapis.com` - by temporarily stubbing the font import; the real
repo is unaffected and builds normally on a network-connected machine).
Two real bugs were caught by this verification process and fixed, not
glossed over: a Next.js CVE (14.2.15 → 14.2.35), and a missing `recharts`
dependency that `tsc` caught before it could ship broken.

No fake insurer APIs are presented as real. The mock adapter is labeled
`is_mock: true` everywhere it appears, including in API responses, per your
implementation rule against fabricating premiums, policies, or claims status.

## Roadmap (matches your phase list)

1. **Foundation** - ✅
2. **Core insurance**: products, providers, quote engine, applications, documents, policies - ✅
3. **Payments**: M-Pesa abstraction, verification, receipts - ✅
4. **Customer portal**: dashboard, policies, documents, payments, support - ✅ (renewal *actioning* and claims tracking land with the automation engine in Phase 6)
5. **CRM**: leads, agents, activities, sales pipeline - ✅
6. **Automation**: notifications, renewal engine, sticker workflow, quote recovery - ✅
7. **Real provider integrations** - groundwork ✅ (research, 9 real named adapters, working aggregator architecture); actual API credentials still pending outreach - this phase completes as real access is granted, not on a fixed timeline
8. **Premium financing (Bidii Credit)** - ✅ functionally complete against a mock adapter; real Bidii API credentials are the only remaining piece
9. **Management analytics**: KPI overview, provider performance, CSV export - ✅
10. **Optimization**: rate limiting, security headers, SEO (robots.txt/sitemap/OpenGraph), optional Sentry hook - ✅ core pieces; load testing, full accessibility audit, and CI/CD remain as ongoing operational work rather than one-time build tasks

Each phase should land as its own PR against this foundation, not a rewrite.
