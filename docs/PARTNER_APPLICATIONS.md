# Partner applications

How a business becomes a Somosure partner.

## The flow
1. **Apply** - the public page `/partners` ("Become a partner", linked from the footer and the home page) has a short
   form: business name, type (car dealer, vehicle importer, employer, SME, bank, SACCO, agent, corporate), town and
   website (optional), contact person, phone, email, how they'd like to work with us (refer customers / submit applications
   for their customers / both), roughly how many customers they could send a month, which insurance interests them, a
   few words on how they'd work with us, and consent to be contacted. They get a reference number.
2. **Alert** - the team is emailed (and optionally texted) straight away, with the application's details and a link to the queue.
3. **Decide** - **Admin → Sales & CRM → Partner applications** (a badge on the menu shows how many are waiting). Staff
   **approve or decline, always with a reason** (kept on record and on the audit trail).
4. **Approve** - creates the **Partner** record (managed by whoever approved it) so it appears in Admin → Partners. Optionally,
   in the same step, **enrol the contact as an affiliate**: they get a personal referral link and code, and you can give them
   a **special commission rate** and/or an **insurance discount credit**. Decline creates nothing.

Applicants are not told automatically when a decision is made - contact them yourself.

## Settings (`backend/.env`)
* `PARTNER_ALERT_EMAILS` - comma-separated addresses to email on each new application (uses your SMTP settings).
* `PARTNER_ALERT_PHONES` - comma-separated numbers to text (uses your SMS provider; logged only if none is configured).
Leave both blank to skip alerts - applications still appear in the queue.
**WhatsApp alerts are not available**: sending a WhatsApp message to your team needs the WhatsApp Business API's outbound
messaging, which the platform isn't set up for. Email and SMS cover it.

## Protections
* Rate limited (5 a minute per visitor) and a hidden "bot trap" field: bots that fill it in look successful but nothing is stored.
* The same person applying twice (same email or phone) while an application is still waiting does **not** create a second
  one or alert the team again - they get the same reference.
* Applicants must tick a consent box. Server-side validation mirrors the form (valid email/phone, minimum message, known types).
* Approving checks every option **before** creating anything, so a mistake never leaves a half-created partner.
* Only **super_admin** and **management** can see or decide applications.

## How an approved partner gets rewarded
Partners are businesses; affiliates are customers. Enrolling at approval creates (or reuses, matched by phone/email) a
customer record for the contact person and makes them an affiliate. Their **special commission rate** is a normal
affiliate rate rule (see AFFILIATE_PROGRAM.md); their **discount credit** appears under Affiliates → Discounts for staff
to apply. If the affiliate program is switched off, you are warned - nothing is earned until it is switched on.

## Where things are
Public: `/partners`. Admin: `/admin/partner-applications`. API: `POST /api/v1/partner-applications` (public),
`/api/v1/admin/partner-applications/*`. Database: migration `0025`.
