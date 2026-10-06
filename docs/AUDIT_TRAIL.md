# Audit trail

A permanent record of **who did what, when, to which record, and why**.

## What is recorded

| Kind | What it captures | Written |
|---|---|---|
| **change** | Every record created, edited or deleted, with the before and after value of each field that changed | Inside the same database transaction as the change - a change can never exist without its audit entry, and a rolled-back change leaves none |
| **request** | Every request that changes data, plus sensitive reads (opening an uploaded document, exports), with the outcome and status code - **including refused (403) and failed attempts** | After the response |
| **event** | Named events: sign-ins, documents opened, audit exports, a provider deleted with everything depending on it | After the response |

Every entry carries: time (UTC, to the millisecond), who (name, email, role, or "customer / not signed in" / "system"),
what (a readable summary), the record it concerns (type, id, reference/name), the customer it relates to, the reason when
one was given, IP address, device, and a request id that ties the entries of one action together.

## Who is "who"
* **Staff / customers** - taken from the login token; name and email are looked up and stored on the entry, so the trail
  still reads correctly if the account is later renamed or removed.
* **Guests** (not signed in) - recorded as a guest, with IP and device.
* **Webhooks** (M-Pesa, WhatsApp) - recorded as the system.
* **Scripts / background work** - recorded as "System".

## Where the reason comes from
In order: the `X-Audit-Reason` request header, then a `reason`, `rejection_reason`, `cancellation_reason`,
`override_reason`, `notes`, `note` or `comment` field in the request body. This means every place staff already type a
note or a required override reason (approve / reject / change a decision, claims, tickets...) is captured with no change.
Only the reason text is kept - **request bodies are never stored**.
Added a "Reason for this change" box on the financing settings screen; any other screen can pass one with
`api.patch(path, body, { reason })`.

## What is never stored
Passwords, password hashes, tokens, API keys, OTPs, signatures and credentials are replaced by `[redacted]` (the entry
still shows *that* a password changed). Login attempts keep the email tried, never the password. Long values are cut at
300 characters.

## Tamper resistance
* The table is **append-only at the database level**: triggers refuse UPDATE, DELETE and TRUNCATE.
* There is no API to edit or delete an entry.
* No foreign keys, so entries outlive users and customers.
* Reading and exporting is limited to **super_admin** and **management**, and exporting is itself recorded.

A database superuser can still drop the triggers - for stronger guarantees, ship the table to storage the app cannot
write to (see "Next steps").

## Where to see it
* **Admin → Administration → Audit trail**: filter by type, person, record, date, text, "only refused / failed
  attempts"; expand any row for the before/after table, IP, device and request id; export to CSV.
* **History panels** on the application, financing and customer screens show that record's trail.
* API: `GET /api/v1/admin/audit` (filters: `kind`, `exclude_kind`, `actor`, `actor_user_id`, `entity_type`, `entity_id`,
  `customer_id`, `action`, `q`, `date_from`, `date_to`, `failed_only`, `limit`, `offset`), `/facets`, `/export.csv`, `/{id}`.

## Settings (`backend/.env`)
* `AUDIT_ENABLED=true` - master switch.
* `AUDIT_EXCLUDED_TABLES=` - extra tables to leave out of change capture (comma separated).
* `AUDIT_LOG_READS=false` - also record every admin *read* (very detailed; document opens and exports are always recorded).
* `AUDIT_LOG_GUEST_REQUESTS=true` - record public requests that change data.

## Limits to be aware of
* History tables that already record what happened (`*_events`, lead activities, communications, notifications, raw
  gateway payloads) and per-quote line items are skipped to keep the trail readable. The record they belong to is still
  audited. Edit `DEFAULT_EXCLUDED_TABLES` in `app/audit/capture.py` to change this.
* Bulk SQL that bypasses the ORM is not itemised. The only place the app does this (deleting a provider and its
  dependants) records one event with the exact counts removed.
* The request's IP comes from `X-Forwarded-For` when present, so it is only as trustworthy as your proxy.
* Entries are never purged. Plan storage (or archiving) accordingly.
* Auditing is designed never to break a request: if writing an entry fails, the failure is logged and the request goes on.

## Next steps worth considering
Daily export of the table to write-once storage; alerts on repeated failed logins or bulk deletes; a required-reason
prompt on more screens (rate cards, staff access changes).
