# Affiliate program

Pay people who refer customers. When someone they referred **actually gets insured** (a policy is issued), the referrer
earns a commission at a rate set by management in **Admin → Sales & CRM → Affiliates**.

It is built on the existing referral feature and changes nothing about it: single-use referral codes, the
"Refer a friend" card and the registration code box all work as before.

## Ships OFF
The program starts **off, with a 0% default rate**. Nobody earns anything until management sets a rate and switches it on
(Affiliates → Rates & settings). Referrals are still recorded while it is off.

## How someone earns
1. A customer shares a code (an ordinary single-use referral code), or - if enrolled as an **affiliate** - a personal
   **link** (`https://your-site/?ref=AFFXXXXXX`) that works for everyone they share it with, any number of times.
2. The new customer is linked to the referrer: at registration (code box, pre-filled from the link), **or when a guest
   simply asks for a quote** after opening the link. The link is remembered in the browser for 30 days, so a customer who
   comes back later still counts. (Most customers never register, so this matters.)
3. When that customer's policy is issued, a commission is recorded as **pending**.
4. A person approves it, then marks it paid with the payout reference (e.g. the M-Pesa code). Or rejects / reverses it
   with a reason. Every step is on the audit trail (who, when, why).

Rules that protect the program:
* A customer can be credited to **one** referrer, once, and only **before they've bought anything**. Existing customers
  can't be "referred".
* Nobody can earn from their own code. A used single-use code can't be taken over by someone else.
* One commission per policy at most. The rate is **copied onto the commission**, so changing rates later never changes
  what was already earned.
* A paused affiliate earns nothing new. A policy removed with its provider keeps its commissions (the link is cleared).

## What management can configure
**Program settings**
* On/off; the **default rate** (a % of premium, or a fixed KES per policy).
* An optional **rate for existing customers** - used when the person referring already has a policy with us that is
  currently active (not cancelled, not expired). Leave it blank and existing customers earn the default rate like everyone else.
* Which policies earn: only the customer's **first** policy, or **every** policy for N months after they were referred.
* A **minimum premium** and a **cap per policy** (both optional).
* Approve commissions **automatically** or review each one (recommended).
* Whether customers may **enrol themselves** as affiliates (otherwise only staff can).

**Special rates** - change what particular people earn:
* for one **person** (e.g. a partner who gets 10% instead of the default 5%),
* for one **product** (e.g. a flat KES 700 on medical),
* for a **kind of referrer** - existing customers, or people who aren't customers yet,
* for any mix of those, and/or only between **two dates** (a promotion).

The most specific rate wins: that person + product → that person → product + kind of referrer → product → kind of
referrer → a rate for everyone → the program's own rates (the existing-customer rate if it applies, otherwise the default).
Equally specific? The newest wins. The **Try it** box shows exactly what a person would earn on a given policy, and
whether they count as an existing customer.

Commission is worked out on the policy's **premium** (before taxes and fees).

## Discounts for existing customers (instead of, or as well as, commission)
An **existing customer** (someone with a policy that is currently active) who refers someone that buys insurance can be
rewarded with a **discount on their own insurance** rather than cash. Under **Rates & settings → "When an existing
customer refers someone who buys insurance, reward them with…"** choose *Commission* (the default - nothing changes),
*A discount instead of commission*, or *Both*. People who aren't customers always earn commission.

* The discount is a **% of premium** (before taxes and fees) or a **fixed KES amount**, with an optional ceiling and a
  validity period (e.g. 365 days). It is granted as a **credit** when the referred customer's policy is issued - the same
  rules as commission apply (first policy only or every policy for N months, minimum premium, paused affiliates).
* **A credit does nothing until staff apply it.** In **Affiliates → Discounts** staff pick, case by case, which of the
  customer's applications it goes on (the list shows what each would take off, and why some can't take it), may choose a
  smaller amount, and must give a reason. Staff can also give a credit directly (e.g. a goodwill gesture), cancel one, or
  release an applied one before any payment is made.
* **It reduces what the customer pays.** The amount is worked out on the server: paying in full takes it off the total;
  a payment plan takes it off the **first payment** (which never drops below KES 1). The payment page shows the customer
  the discounted amount and a note that it was applied. An application with no discount is paid exactly as before.
* Customers see their credits on their dashboard ("Your insurance discounts").
* Credits can't be applied to an application that is already paid, rejected, already discounted, or being paid through
  **Bidii Credit financing** (financed premiums aren't reduced yet). A credit can only go on that customer's own application.

## Roles
* **super_admin, management** - change settings, rates, enrol/pause affiliates, and handle commissions.
* **finance_officer** - view everything and approve / pay / reject / reverse commissions, but not change rates.

## Where things are
Admin: `/admin/affiliates` (Commissions · Rates & settings · Affiliates). Customer: the "Your referral earnings" card on
the dashboard (hidden until the program is on or the customer has earnings).
API: `/api/v1/admin/affiliate-program/*`, `/api/v1/me/affiliate`. Database: migrations `0022`, `0023` and `0024` (run them before starting the new code - the application table gains columns).

## Things to know
* **Payouts are recorded, not sent.** "Mark paid" records that you paid (with the reference); the money itself is sent
  outside the platform (M-Pesa). Automatic M-Pesa payouts (B2C) could be added later.
* A policy counts when it is **issued**. In the normal flow that happens after the premium is paid; a policy staff issue
  by hand (e.g. zero-deposit financing) also earns, so approving commissions is the moment to check the premium really was paid.
* Commissions are not clawed back automatically if a policy is later cancelled - use **Reverse** with a reason.
* A discount is a rebate the platform applies at checkout; it doesn't change what an insurer charges. Check that giving
  customers a discount like this is acceptable under your insurer agreements and insurance regulations.
* Referrals made before this feature are kept; commissions are only created for policies issued **after** the program is on.
