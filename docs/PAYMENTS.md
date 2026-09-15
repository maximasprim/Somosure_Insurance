# Payments - Phase 3

## Why a mock M-Pesa provider, not a stub that just returns "success"

No Safaricom Daraja credentials exist yet. Rather than short-circuiting the
payment flow with a function that returns `{status: "success"}`,
`MockMpesaProvider` simulates the actual two-step shape a real integration
has:

1. `initiate()` - like a real STK push, returns `pending` immediately.
   Nothing is marked successful at this point, mock or not.
2. A signed callback (`build_simulated_callback` / the dev-only
   `POST /api/v1/payments/{checkout_id}/simulate-completion` endpoint)
   is posted to the **same webhook route** (`POST /api/v1/webhooks/mpesa`)
   a real Daraja callback would hit, and goes through the same
   `verify_webhook()` signature check.

This means the signature-verification code path is exercised for real in
dev/demo, not skipped - swapping in `DarajaMpesaProvider` later changes only
which class implements `verify_webhook`, not the route or the service logic
that calls it.

## The rule this enforces (spec §13)

> Never rely solely on frontend payment confirmation. The backend must
> independently verify transactions.

Concretely: `PaymentStep.tsx` on the frontend never sets a payment to
"successful" itself - it only calls `initiate`, then (in dev) triggers the
simulate-completion endpoint, then polls `GET /payments/{id}/status`. The
actual status transition happens exclusively inside
`handle_mpesa_webhook`, gated on `verify_webhook().is_valid`.

## Idempotency

A webhook can be delivered more than once. `handle_mpesa_webhook` checks
`payment.status == "successful"` before doing anything and returns early -
a duplicate callback cannot double-issue a policy.

## What happens on a successful payment

`handle_mpesa_webhook` calls `policy_service.issue_policy` directly once a
payment verifies as successful. This is the one automatic issuance path in
the system today; Phase 6's automation engine (event → rule → action) will
generalize this into a configurable rule rather than a hardcoded call, but
the underlying `issue_policy` function doesn't change.

## Adding a real payment provider

Same pattern as `docs/PROVIDER_ADAPTERS.md`: implement
`PaymentProviderAdapter`, register it in `app/payments/registry.py`, and
never invent response fields not present in the real provider's
documentation.
