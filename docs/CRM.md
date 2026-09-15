# CRM - Phase 5

## Every quote request becomes a lead, guest or not

`quote_service.resolve_customer` tries three things in order:

1. A real `customer_id` (logged-in customer) - used directly.
2. A guest match by phone number against an existing `Customer` row.
3. A brand-new guest `Customer`, created from whatever the quote form
   collected (motor's `owner_name` / `owner_phone`).

If none of that yields a phone number, the quote proceeds fully anonymous
and no lead is created - this only happens for a request with no contact
info at all, which the current motor form always collects.

`quote_service.record_lead` then either advances an existing open lead
(one not already `won`/`lost`) or creates a new one at stage `quote`,
logging a `LeadActivity` either way. This is the "new lead notification"
half of spec §19 - the pipeline is always populated without an agent doing
anything, though the *notification* itself (email/Slack ping to an agent)
is a Phase 6 automation-engine action, not built here.

## Why this mattered for correctness, not just features

Before this phase, the frontend's guest quote flow used a placeholder
`customer_id` UUID that didn't correspond to a real `Customer` row - since
`applications.customer_id` is a NOT NULL foreign key, that placeholder
would have failed with a foreign-key violation the first time someone ran
the flow against a real Postgres database rather than importing the app in
isolation. Building the CRM's lead-from-quote logic forced fixing that
gap properly instead of patching around it.

## What's deliberately manual for now

- **Lead assignment** (`assigned_agent_id`) is a plain PATCH - round-robin
  or rule-based auto-assignment is a Phase 6 automation-engine concern.
- **Cross-sell suggestions** (spec §19 - "customer bought motor, suggest
  personal accident") aren't built; they need real customer behavior data
  to be meaningful, not just the pipeline skeleton.
- **Communications** table exists in the schema (migration `0005`) but
  nothing writes to it yet - it's there for Phase 6's WhatsApp integration
  to log into immediately without another migration.
