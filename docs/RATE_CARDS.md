# Configurable rate cards (AMACO, Pioneer Insurance Kenya, and future brokers)

## Why this exists

Real insurer/broker API access (see `PROVIDER_LANDSCAPE.md`) isn't in
place yet for anyone. But a rate card - a PDF rating guide an insurer
circulates to its agents - is real, current pricing, even without an
API behind it. This system lets an admin type one of those rate cards
into the database, per broker, so the quote engine computes a real
premium from real numbers instead of either (a) waiting for an API that
doesn't exist yet, or (b) showing another `MockProvider` placeholder.

Two brokers are seeded today, from documents supplied directly:

- **AMACO** (Africa Merchant Assurance Co Ltd) - "Rating Guide, 2026
  Revised Motor Rates", circulated 2 Jul 2026. Well-structured, clearly
  legible - seeded with `data_confidence="verified"`.
- **Pioneer Insurance Kenya** - a rate sheet whose table columns did not
  extract cleanly from the source file. Every Pioneer class is seeded
  with `data_confidence="needs_review"`, and both the admin UI and the
  customer-facing quote card surface that flag. **Verify Pioneer's
  numbers against the original document before relying on them for a
  real customer.**

Only the `motor` product category is populated, because that's what both
source documents cover. Nothing in the schema is motor-specific - a
medical, life, or travel rate card (for either of these two brokers, or
a brand new one) slots in as more rows, not a schema change.

## How it fits into the existing architecture

- `app/models/rate_card.py` - the schema: `RateCardVehicleClass` (one
  insurable risk class for one provider), `RateCardTier` (a priced band
  within a class), `RateCardExtension` (an optional add-on like PVT or
  Excess Protector), `RateCardExcess` (a disclosed deductible).
- `app/services/rate_card_engine.py` - pure pricing logic: resolves a
  canonical vehicle-class code from the quote form's answers, picks the
  matching tier, applies requested extensions, and adds Kenya's standard
  motor insurance levies (PHCF 0.25%, IRA Training Levy 0.20%, Kshs. 40
  stamp duty).
- `app/providers/rate_card_adapter.py` - `RateCardAdapter`, a normal
  `InsuranceProviderAdapter` like every other provider integration.
  `get_quote()` is real (computed from a real rate card, `is_mock=False`);
  every stage after the quote (application, payment, policy issuance,
  claims) is routed to manual staff follow-up, the same honest pattern
  the codebase already uses for a provider with no live API for that
  stage (see the claims staff-assisted fallback).
- `app/providers/registry.py` - maps the provider's name (lower-cased)
  to `RateCardAdapter`, exactly like every other named insurer.
- `app/api/v1/admin_rate_cards.py` - CRUD for everything above, plus a
  `/preview` endpoint that prices a draft answer set immediately so an
  admin can sanity-check a tier edit without running a full quote
  request.
- `app/db/rate_card_seed_data.py` + `app/db/seed.py::seed_rate_cards()` -
  the actual AMACO/Pioneer numbers, loaded once and never overwritten on
  a re-seed (an admin's edits always win).

## Canonical vehicle-class codes

The same code means the same kind of risk across every provider, so the
quote engine asks every rate-card provider for e.g. `motor_private` and
gets back each one's own number for it. Currently seeded:

| Code | What it covers |
|---|---|
| `motor_private` | Private car |
| `motor_private_fleet_individual` | Private fleet, 3+ vehicles, individual owner |
| `motor_private_fleet_corporate` | Private fleet, 5+ vehicles, corporate owner |
| `motor_commercial_own_goods` | Commercial, strictly carriage of own goods |
| `motor_commercial_own_goods_fleet` | Same, fleet of 6+ |
| `motor_commercial_general_cartage` | Hire & reward - pickups, lorries, canters |
| `motor_commercial_prime_mover_tanker` | Prime movers / tankers (excl. fuel tankers) |
| `merchant_commercial_hybrid` | Merchant Commercial Hybrid class |
| `institution_corporate_bus` | Institution/corporate bus or passenger van |
| `school_bus` | School bus |
| `ambulance_fire` | Ambulance / fire engine |
| `motor_commercial_asset` | Commercial asset (plant & machinery) |
| `motorcycle_own_use` | Motorcycle, corporate-owned, own use |
| `tractor_special_type` | Tractor / grader / caterpillar / bulldozer |
| `driving_school` | Driving school vehicle |
| `motor_trade` | Motor trade (road risk) |
| `psv_taxi` | PSV taxi - yellow line / chauffeur driven / online |
| `psv_tour_vehicle` | Tour van |
| `psv_matatu_bus` | PSV matatu or bus |
| `psv_tuktuk` | PSV tuktuk |

## How the quote form reaches a class

`app/services/rate_card_engine.py::resolve_vehicle_class_code()`:

1. If the answers include an explicit `vehicle_class`, use it directly -
   this is what the frontend's "Specific vehicle class" dropdown
   (`MotorQuoteForm.tsx`) sends once a customer needs a class that plain
   usage can't express (a school bus, a driving-school car, ...).
2. Otherwise, fall back from `usage` (`private` / `commercial` / `psv`)
   and, for PSV, `psv_type` (`taxi_yellow`, `taxi_chauffeur`,
   `taxi_online`, `tour_van`, `matatu`, `bus`, `tuktuk`).

A tier within that class is then picked by whichever value the tier's
`band_unit` calls for - `value` (sum insured), `tonnage`, or
`seating_capacity`, all optional fields on the motor quote form. If the
matching field is missing, or every configured band is a mismatch for
the response given, the engine doesn't fail the quote - it uses the
nearest/lowest configured band and records why in the quote's
`coverage.assumptions` list, so nothing is silently guessed without a
paper trail.

## Assumptions made while transcribing each document

Recorded on the class itself (`notes` field) where they matter, but
worth stating once here too:

- **Cover type mapping**: only `comprehensive` and `tpo` are modeled.
  "Third Party, Fire & Theft" is priced as Third Party Only - neither
  source document gives it a separate loading, and the quote says so
  (`coverage.assumptions`).
- **Kenyan motor levies** (PHCF 0.25%, Training Levy 0.20%, Kshs. 40
  stamp duty) are industry-standard, not from either rate card
  specifically - applied uniformly by the engine, not per-tier data.
- **AMACO's PSV Third Party Only schedule** (rating guide, p.16) prices
  by *exact* seating capacity, 7 through 51 seats - each capacity is
  seeded as its own tier with `min_value == max_value` rather than
  approximated by a formula, so every number traces back to the
  document's own figure.
- **Loss-ratio-based renewal loading, COMESA cover, and short-term
  proration tables** (both documents have these) are **not** modeled
  yet - they apply at renewal/binding time, which this phase doesn't
  automate for these two providers regardless (see "What still requires
  a human" below). Add them as new `RateCardExtension`/tier rows if
  you need them priced at quote time.
- **Pioneer's numbers are lower-confidence across the board** - the
  source file's table structure didn't survive extraction. Where a
  category was mentioned with no legible numeric rate (plain
  motorcycle/tuktuk comprehensive, for instance), it was left out
  entirely rather than guessed. Treat every Pioneer figure as a
  starting point to verify, not a final rate.

## What still requires a human

Getting a quote number is now automatic for these two brokers. Binding
the actual policy with AMACO or Pioneer is not - neither has given this
platform a live API, so `RateCardAdapter` routes every post-quote step
(application submission, payment confirmation, policy issuance, claims)
to the ordinary staff queues, the same as any provider without live
integration. If/when either broker provides real API access, replace
`RateCardAdapter` with a real adapter for that provider in
`app/providers/registry.py` - the rate-card tables and the quote-time
pricing logic can stay exactly as they are; only binding gets real.

## Adding a new broker's rates

You don't need a code change to add a broker whose rate card you've just
received. Preferred path - through the admin API
(`/api/v1/admin/rate-cards`, `super_admin`/`operations`/`management`/
`underwriter` roles):

1. `POST /providers` with the broker's name - it's created `inactive`.
2. `POST /providers/{id}/classes` for each vehicle class in their rate
   card, with its `tiers` inline (or add tiers afterwards via
   `POST /classes/{id}/tiers`). Use the canonical codes above so the
   existing quote form routes to it automatically; a genuinely new kind
   of risk can use a new code (add it to this table and to
   `MotorQuoteForm.tsx`'s dropdown once it's added).
3. `POST /providers/{id}/extensions` for any add-ons (PVT, Excess
   Protector, etc.) - `vehicle_class_id: null` makes an extension a
   provider-wide default.
4. `POST /providers/{id}/preview` with a sample answers payload to
   sanity-check the numbers.
5. `POST /providers/{id}/activate` once you're satisfied - only then
   does it appear in a real customer's comparison table.

The admin frontend at `/admin/rate-cards` wraps steps 1-5 with actual UI
instead of raw API calls, plus a live preview panel.

If a broker gives you a rate card for a product category other than
motor, the schema already supports it (`product_category` is a plain
string on `RateCardVehicleClass`) - but `resolve_vehicle_class_code()`
in `rate_card_engine.py` only knows how to resolve *motor* classes today.
A medical/life/travel rate card needs its own resolver function and its
own quote-form fields before it can be priced automatically the same
way; until then, `RateCardAdapter.get_quote()` correctly raises "no
rates for this category yet" for anything other than motor, rather than
guessing.
