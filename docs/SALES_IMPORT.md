# Sales import (weekly report workbook)

Keeps the system in step with the weekly report workbook - the one with the `2026 Sales`, `2025 sales`,
`Claims 2026`, `IPF REPORT 2026` ... sheets. The sheet stays the place staff record sales; the system
follows it. Upload the **whole workbook** each time; only what changed is applied.

Admin menu: **Sales import** (roles: super_admin, management, finance_officer).

## How a week works

1. **Import tab -> choose the workbook -> Check file.** Nothing is saved. The screen shows what would be added,
   changed or left out, the problems found, and whether each month's TOTAL row agrees with its rows.
2. **Import now.** Rows are added/updated in one go, with one audit event for the import and the full list of
   changed fields kept on the import batch.
3. Fix whatever the report flagged **in the sheet** (or download the cleaned workbook, below) and upload again.
   Uploading the same file twice changes nothing.

## What the importer understands

* Year sheets (`2026 Sales`, `2025 sales`, any `YYYY ... sales`), `Claims YYYY`, `IPF REPORT YYYY`. A new year's
  sheet is picked up by name. Other sheets are ignored (and listed).
* Month blocks: a header row, rows, a SUM row. Header spelling can vary; the month name can be on the header row,
  on a line above it, or on the first data row; a block with no month at all is the month after the previous one;
  a sheet that opens in November/December and later reaches January starts in the previous year.
* Columns that come and go (phone, new-business/renewal, cover type); unknown extra columns are kept, not lost.
* Commission, tax and net-revenue formulas, including when the file has no saved results.
* The REG NO column also carrying a product (PI, WIBA, MEDICAL, BID BOND, CREDIT LIFE, ...). These become a
  `product_line`; number plates become `motor`.

## Dates

Excel in a month-first locale stored many day/month dates the wrong way round (6 Jan became 1 June) - but only
when the day was 12 or less; the rest stayed text (`13/01/2026`). For each row the importer looks at the start,
expiry and paid dates together, and the month block, and picks the reading that makes a sensible one-year policy
paid around its start date. Corrected cells are noted on the row. When the row cannot confirm the order it says so
(`dates_unverified`). It never changes a date it cannot justify, and never guesses a missing one.

Cells formatted **day-first or with a month name** (`dd/mm/yyyy`, `13-Jan-2026`) are trusted exactly as they are.
The cleaned workbook uses `dd/mm/yyyy`, which is what stops the swap from happening again.

Obvious slips (expiry before start, a year typed wrongly) are flagged with a suggested fix, never silently changed.
See "Suggested fixes" below.

## Choosing the period

On the Import tab, **Import from** (and optionally **Up to**) limit the import to a range of months, e.g. from
January 2025. The choice is remembered for next time. Only months inside the period are read, checked and
compared - the counts, the problems list and the month-total check all describe just that period - and rows
before it that are already in the system are left exactly as they are (never updated, never marked missing),
even though they are in the file. Claims and IPF lines follow their own dates. With no period chosen the whole
workbook is imported. The period applies to both "Check file" and "Import now"; change it and the check is
cleared so the numbers you confirm are the ones that will be imported.

## Suggested fixes

**Suggested fixes tab.** Where a date looks like a year typo, the importer works out the one correction that makes
a one-year policy starting near the payment date and lists it with the row's dates beside it. Tick the ones you
agree with and press Accept (or Accept one at a time). Only the value the importer suggested is accepted - a
value typed by hand is refused. Each acceptance is recorded in the audit trail (old value, new value, who).

An accepted fix is remembered as an override: while the sheet still holds the old value, uploading it again does
not undo the fix and does not report a change. The moment the cell in the sheet changes - corrected there, or
changed to something else - the sheet wins again and the override is dropped. So to undo a fix, change that date
in the sheet. The cleaned workbook contains the accepted fixes.

## How a row is recognised next week

Insurer + policy number + sheet year. A row with no policy number is recognised by insurer + plate + start date +
premium + client. A row that later gains a policy number, or moves to another sheet, is matched on the second key,
so it is updated rather than duplicated. Two rows with the same policy number in one year are kept as two rows.

* **Changed in the sheet** -> the ledger row is updated.
* **Gone from the sheet** -> marked *Not in sheet* (never deleted); active again if it returns. Only years whose
  sheet is in the upload are judged, so uploading just 2026 never touches 2025.

## Names

Insurers, staff and branches are typed freehand (`MORNACH`, `DIRECTLINE`, `JOSPHINE -HQ`, `HQ-JOSPHINE`...). The
importer matches them itself and saves each match as an **unconfirmed** alias. **Names tab**: confirm or correct
each once; **Apply to the ledger** re-resolves every row. A saved alias always wins over the importer's guess.

## Cleaned workbook

**Import tab -> Download cleaned workbook.** Same layout and columns A-N as the current sheet (plus optional
COVER TYPE and PHONE NO), real day-first dates, names written one way, TOTAL rows recalculated over every row, and
a **Review** sheet listing rows that still need attention. The importer reads it back unchanged.

## Where the data lives

New tables (migration `0032`): `import_batches`, `sales_entries`, `legacy_claims`, `ipf_remittances`,
`import_aliases`; migration `0033` adds `sales_entries.overrides` (accepted fixes and phone numbers added by staff);
migration `0034` adds `customer_id` (and renewal follow-up columns) to the ledger; migration `0035` adds the ids of the posted
records and the underwriter-to-provider links; migration `0036` marks where a ledger row came from (workbook or typed in the
system). Run all five before using the screens. No existing table is altered. They sit **beside** policies/applications/quotes on purpose: a sale in the workbook has no quote
or application behind it, and inventing them would distort conversion figures and could fire renewal/sticker
automations on old business. Where a ledger row's policy number matches a policy in the app, `policy_id` links them.
Claims are linked to the sale with the same plate that was running when the claim was reported.

## Posting into the system (Sales import -> Post to system)

Importing fills the ledger. **Posting** turns each ledger row into the records the rest of the system already uses,
so the Policies, Payments, Customers, search and dashboard pages simply contain them:

    Customer -> Quote request -> Quote -> Application -> Policy -> Payment (+ a policy history entry)

Every policy came from a quote and was paid for; the manual records never captured those steps, so they are
reconstructed from what the sheet says and marked as coming from the workbook (policy source `workbook`, references
starting `WBQ-`, `WBA-`, `WBP-`). Records are dated by the sale (the date paid), so an import never creates a spike on the
day it ran. The payment is recorded as method `offline`, status successful. Nothing here uses the platform's issuing
flow: no sticker is generated, no message or automation fires, no affiliate or loan-officer commission opens.

**Underwriters.** The sheet's insurers are linked to the providers already in the system (`MONARCH` ->
"Monarch Insurance Company"); obvious matches are linked automatically, the rest are chosen on the tab, or created as new
providers - created *inactive* so they never receive quote requests. Fixing a link re-points everything already posted.

**What is appended, and what waits.** A row is posted with whatever it has, and flagged for the rest:

| Missing | What happens |
|---|---|
| Phone | Customer saved with a blank phone; flagged. A number added later (Sales -> Customers, or in the sheet) fills it in. |
| Policy number | A placeholder (`WB-2026-...`) is used and flagged; the real number replaces it when the sheet has it. A number already in use gets the year added (renewals reuse numbers). |
| One of start / expiry | The other date plus or minus a year is used and flagged as assumed. |
| Date paid | The sale month is used for the payment date; flagged. |
| Premium, or both dates, or an unlinked underwriter | The row waits (listed with the reason) - a policy and payment cannot exist without them. It stays in the ledger and in All sales. |

**Customers.** Matched to existing customers first (policy, phone, plate with a similar name); otherwise created - one
per phone number, or per name where there is no phone (flagged "matched by name only", because two people can share a
name). Created customers carry lead source `workbook` and no marketing consent.

**Staying in step.** Premium, dates, commission, underwriter, policy number and payment amount/date are the sheet's: each
import carries later changes into the posted records. A cancelled or under-review status, claims, documents and notes
belong to the app and are never overwritten, and policies not created by posting are never touched.

**Renewal reminders.** The platform's automatic reminders skip workbook policies until you set
`WORKBOOK_RENEWAL_REMINDERS=true` in the backend environment (they would otherwise message customers who have never used
the platform). Sales -> Renewals lists everything due either way.

**Undo.** *Post to system -> Undo* (super admin) removes only what posting created, never anything made by the platform or
staff; the ledger stays, ready to post again.

**Conversion.** Posted policies each have a (reconstructed) quote, so the quote-to-policy conversion on the dashboard
includes them. Quotes that were given but never converted were never recorded in the manual era, so the workbook cohort
can only ever show converted ones and the overall rate will read higher than the platform alone.

## Recording a sale in the system (Sales -> Record a sale)

For moving off the manual records at your own pace. The form has the same columns as a row of the weekly sheet; only the
client, insurer, registration or product, start date, date paid and premium are required, and anything else left out is
flagged for review rather than refused. It works out what the sheet works out: expiry one year after the start, commission
at the insurer's usual rate (editable), withholding tax at 10% of commission, net revenue.

On Record, the sale is posted at once as a real customer, quote, application, policy and payment (the same engine as the
import), added to the ledger with staff, branch and month, counted in sales, reports and renewals, and included in the
cleaned weekly report the system exports. So the sheet can be produced from the system.

* **The same person twice.** Typing a name or phone suggests customers already in the system; pick one and the sale goes on
  their record. A phone number that matches exactly one customer is used automatically.
* **The same sale twice.** If the policy number is already in the system, or the insurer + registration + start + premium +
  client match an existing row, you are warned and must confirm that it is a different sale.
* **If the sheet has it too.** A sale recorded here and later typed in the sheet gets the same keys as the sheet row, so the
  import merges the two into one. A sale recorded here is never reported as "missing from the sheet".
* **Mistakes.** *Void* (admin and management) removes the policy, payment and quote created for it, and the customer if it was
  created for that sale. A workbook row is corrected in the sheet, not voided here. A policy with a claim or other activity added in
  the app cannot be voided automatically.
* **Who:** super admin, management, operations, sales agents and finance can record; only admin, management and operations can void.
  Not yet possible: editing a recorded sale (void it and record it again).

## How the rest of the system uses the ledger

Before rows are posted (and for rows that cannot be), the pages that need a full picture read the platform and the ledger
together (`services/sales_import/unified.py`). Posted rows are real policies and are found by every existing page.

| Where | What you see |
|---|---|
| **Reports & analytics** (dashboard) | A new **All sales** section under the platform sections: sales, premium, commission and net revenue compared with the previous period, by month, underwriter, branch, staff, new/renewal and product, plus workbook claims and renewals due. The platform-only figures above it are unchanged and still mean "sold through the platform". |
| **Sales** (`/admin/sales`) | **All sales** - one list, each row marked Platform / Workbook / Platform + workbook. **Renewals** - policies due (and the last 30 days' lapses) from both sources, with phone/WhatsApp links and a follow-up status and note you keep for workbook policies. **Customers** - matching tools and the clients waiting for a phone number. |
| **Customer page** | A "Policies and claims from the weekly report" panel appears when that customer has workbook history (nothing is shown otherwise). |
| **Global search** | Also finds workbook policies by client, policy number, registration or phone. |
| **Import** | After each import, workbook policies are matched to existing customers (see below). |

**Counted once.** A sale is counted one time: a workbook row whose policy number matches a policy in the app stands in
for that policy (it carries staff, branch and commission, which the app does not have); a platform policy with no
workbook row counts as itself. Demo (mock) policies are never counted. "All sales" dates workbook rows by the date
paid, so a row paid in a different month from its sheet block can sit in a different month here than on the Sales
import Summary tab (which follows the sheet's own blocks).

**Customers.** Matching, strongest first: the policy is also a platform policy; the phone number matches exactly one
customer; the number plate belongs to one customer's vehicle **and** the names share a word. Nothing is merged and no
existing customer is changed. Customers are created only when you choose **Check what would be created too** and then
confirm, and only for clients that have a phone number (new customers: lead source "workbook", no marketing
consent). Clients with no phone are listed so a number can be added; a number added in the app is kept on all that
client's rows and gives way to the sheet as soon as the sheet has one. Claims follow the sale they belong to, else
their phone number.

**Renewals.** The platform's own renewal reminders (`renewal_service`) are untouched and still look only at platform
policies. Workbook policies are not reminded automatically - the worklist shows who is due and gives a WhatsApp link
to contact them from your own phone. A workbook policy drops off the list when the same registration has a later
policy in the sheet, or when it is marked renewed or lost.

## Automatic import from Google Sheets (Sales import -> Automation)

Instead of uploading the workbook each week, point the system at the Google Sheet and let it pull the sheet itself.

**Setting it up.** Open the sheet in Google Sheets -> Share -> General access -> *Anyone with the link* -> Viewer. Paste the sheet's
address on the **Automation** tab, choose how often (every day / week / month), the day and the hour (Nairobi time), tick *Import
automatically* and Save. **Run now** pulls it immediately without waiting. Optional: the same *Import from / Up to* period as the Import
tab, and *Also post new rows into the system* (off by default, so nothing is posted until you have looked at it).

**What a run does.** It downloads the whole sheet as a workbook and imports it exactly like an upload (same checks, same period rule,
same "only what changed is applied"). If the sheet is identical to the last import, or would change nothing, the run is logged as *No
changes* and **no version is created**, so the history only holds real changes. Every attempt - imported, no changes, or failed - is
listed under *Recent attempts*.

**When it fails** (sheet made private, Google unreachable, file not a workbook) nothing is changed, the reason is shown in plain words on
the tab, and it is retried every 6 hours up to 3 times before waiting for the normal slot.

**Only a Google Sheet that anyone with the link can view works.** A sheet restricted to named people needs a Google login the system does
not have; the tab says so. Only the sheet's id is taken from the pasted link - the address that is fetched is always built by the system,
so the link box cannot be used to make the server call some other address.

### Running it on a schedule (deployment)

The pull is a background job named `sales_import` that checks every 10 minutes whether one is due (cheap when it is not). It runs when
`SCHEDULER_ENABLED=true`, or when an outside timer calls `POST /api/v1/internal/cron/run` (header `X-Cron-Secret`) - on a host that
sleeps when idle use the second, e.g. every 10 minutes, optionally with `?jobs=sales_import`. If neither is set up the Automation tab
will show a "Next import" time that never arrives - check *Last attempt* after the first scheduled time.
Run `alembic -c app/db/alembic.ini upgrade head` (migration `0037`) before using the tab.

## Versions and reverting (Sales import -> Versions)

Every committed import - by hand, from Google Sheets, or a revert - becomes a numbered **version**, and the exact workbook file is kept
in document storage (the same storage as uploaded documents; each distinct file is stored once). The tab lists them with date, source,
who, what it changed, and **Download** (the original file).

**Revert to this** puts the ledger back to what that version's workbook says. It opens a preview first - how many rows are set back, how
many will be marked *not in sheet*, how many posted policies will be removed - and asks for an optional reason (kept on the version and
in the audit trail). Then:

* rows whose values changed since that version are set back to what it says;
* rows that did not exist in that version are marked *not in sheet* (the ledger never deletes), and the policy, payment, quote and
  application posting made for them are removed again (a policy that staff have since added a claim or renewal to is kept, and counted);
* the revert is recorded as a **new version** - history is never rewritten, so a revert can itself be reverted;
* **automatic import is paused**, because otherwise the next pull would bring today's sheet straight back. Resume it on the Automation
  tab once the Google Sheet matches what you restored.

**Not touched by a revert:** sales recorded by hand in the system, staff follow-up notes, accepted date fixes that still apply, name
aliases and underwriter links, claims and documents added in the app, the platform's own policies, and customers created by posting
(they stay, and are relinked by the next import if needed). Reverting needs super admin or management; finance can view and download.

**Limits.** A revert restores the *ledger and what posting made from it*; it does not restore the Google Sheet itself (use the sheet's own
version history for that). Reverting to a version imported with a period limit restores only that period. Stored workbooks are never
deleted automatically, so storage grows by one file per real change.

Code: `services/sales_import/google_sheet.py` (download), `schedule.py` (when), `auto_import.py` (settings, runs, revert),
`versions.py` (history and stored files); API in `api/v1/admin_sales_import_auto.py`; tests in `tests/test_sales_import_automation.py`.

## Known limits

* Phone numbers are only in the 2023-2024 sheets; without them the renewals list shows "no phone in the sheet".
* Commission is taken as written in the sheet (the sheet uses different rates per insurer, typed per row); rows
  that are zero, over 30% of premium, or unlike the insurer's usual rate are flagged.
* The sheet's own TOTAL rows are never trusted - they are compared with the rows and the difference is reported.
* Dates the sheet gets wrong in a way no other cell on the row can settle stay flagged for a person to fix.

## Code map

`backend/app/services/sales_import/` - `posting.py` + `posting_rules.py` (post into the system, underwriter links, undo), `manual.py` + `manual_rules.py` (record a sale), `unified.py` (all sales, reports, renewals, customers), `matching.py` (phone/name
matching rules), `cleaners.py` (rules), `parser.py` (workbook -> records), `period.py`
(import from / up to), `pipeline.py` (names, keys), `reconcile.py`, `sync.py` (what is new/changed/missing), `service.py` (database), `export.py`
(cleaned workbook), `claims.py` (claim timeline). Tests: `tests/test_sales_import_core.py` (no database),
`tests/test_sales_import_api.py` and `tests/test_sales_sync_api.py` and `tests/test_sales_post_api.py` and `tests/test_sales_record_api.py` (API).
