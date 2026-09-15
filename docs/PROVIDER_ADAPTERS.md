# Adding a real insurer integration

This repo ships with `MockProvider` (single-insurer demo data),
`MockAggregatorProvider` (multi-insurer demo data), and nine real, named
adapter skeletons for actual Kenyan companies (see below) - each of the
real ones raises `NotImplementedError` until real API access exists.
Every mock value is flagged `is_mock: True` - in the database row, the API
response, and the UI - and none of it should ever be shown to a customer
as a real premium or policy.

## Real integrations added so far

Nine real, named adapters exist under `app/providers/` (Lami Technologies,
mTek Services, Turaco, Britam, Jubilee Insurance, APA Insurance, CIC
Insurance Group, ICEA Lion, Old Mutual Kenya) - see
`docs/PROVIDER_LANDSCAPE.md` for the research behind each one and
`docs/API_ACCESS_REQUEST_TEMPLATE.md` for outreach. Every one of them
currently raises `NotImplementedError` on every method; none fabricate
data. This section describes what changes once real access is granted to
any of them.

## The aggregator architecture (built, not just planned)

Lami, mTek, and Turaco aren't ordinary single-insurer providers - the
entire value of integrating with them is that ONE API call returns quotes
from MANY underlying insurers (Lami reportedly bridges ~25). The codebase
reflects this directly:

- `InsuranceProviderAdapter.get_quotes_bulk()` (in `app/providers/base.py`)
  is what the quote engine actually calls for every provider. Its default
  implementation just wraps `get_quote()` in a single-item list - so a
  direct insurer adapter (Britam, MockProvider, ...) needs zero changes.
  An aggregator overrides `get_quotes_bulk()` to fan out internally and
  return one `NormalizedQuote` per underlying insurer.
- `NormalizedQuote.underlying_provider_name` carries the real insurer's
  name (e.g. "Britam") even though the DB row the quote is stored against
  is "Lami Technologies" - persisted on `Quote.underlying_provider_name`
  (migration `0008`), and surfaced in the API response as e.g.
  `"Britam (via Lami Technologies)"`.
- `MockAggregatorProvider` proves this actually works today: it's a
  seeded, **active** demo provider (`Demo Aggregator (mock)`,
  `provider_type: aggregator`) whose `get_quotes_bulk()` returns three
  distinctly-priced quotes tagged with three different demo underwriter
  names, all from one call - functionally verified, not just asserted.

When Lami's real API arrives, `LamiAdapter.get_quotes_bulk()` is the only
method that needs a real implementation. The quote engine, the `Quote`
table, the API response shape, and the frontend comparison UI all already
handle the "one provider row, many underlying insurers" case correctly.

## Adding a real insurer integration

1. Add credentials to `backend/.env` (never commit real values) -
   e.g. `BRITAM_API_BASE_URL`, `BRITAM_API_KEY`.
2. Implement the real logic in that company's existing adapter file (e.g.
   `app/providers/britam_adapter.py` already exists as a
   `PendingIntegrationAdapter` skeleton - replace it with a class
   implementing `InsuranceProviderAdapter` directly, calling the real
   endpoints and mapping responses into `NormalizedQuote`, `PolicyResult`,
   etc.). Do not invent endpoints or response fields that aren't in the
   supplied documentation - where a method isn't supported by the
   provider's API, raise `NotImplementedError` with a clear message rather
   than fabricating a result. If the company is an aggregator (Lami, mTek,
   Turaco), implement `get_quotes_bulk()` for real - see "The aggregator
   architecture" above - not just `get_quote()`.
3. It's already registered in `app/providers/registry.py`'s
   `_REAL_ADAPTERS` dict - no change needed there unless the company name
   in the database doesn't match the dict key.
4. In the admin provider management screen, set that `InsuranceProvider`
   row's `integration_mode` to `rest` (or `soap`) and
   `credentials_secret_ref` to the name of the secret - never paste a key
   into the database or the frontend. Leave `status: inactive` until
   testing is done.
5. Write adapter tests against recorded/sandboxed responses from the
   provider, not against production, before flipping `status` to `active`.

## Failure handling contract

An adapter method should raise on failure rather than return a fabricated
result - `quote_service.request_quotes` already catches per-provider
exceptions and excludes that provider from the comparison rather than
failing the whole request (spec §46). Adapters should not swallow errors
themselves.
