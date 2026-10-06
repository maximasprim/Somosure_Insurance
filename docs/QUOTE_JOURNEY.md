# Smoother quote journey (Oct 2026)

What was added, where it lives, and how to switch parts off.

| Feature | Backend | Frontend |
|---|---|---|
| Make -> Model dropdowns (all African-market makes, "Other" escape hatch) | - | `lib/vehicleData.ts`, `components/quote/MotorQuoteForm.tsx` |
| "Have these ready" document card after quotes | `GET /api/v1/quotes/document-requirements`, `app/services/document_requirements.py` | `components/quote/DocumentChecklistCard.tsx` |
| Upload screening (real file type, corrupt/blank/dark/tiny, wrong document, duplicate file) | `app/services/document_validation.py`, `document_intake.py` | `DocumentUploadStep.tsx`, `lib/api.ts` (`uploadFile`) |
| Never ask for a document twice (financing reuses insurance docs; logged-in customers reuse ID/KRA PIN) | `app/services/document_reuse_service.py`, `.../documents/prepare` + `.../documents/checklist` | `DocumentUploadStep.tsx`, `FinancingDocumentsStep.tsx` |
| Premium-quote document generated automatically for Bidii Credit | `app/services/simple_pdf.py` | - |
| Financing figures re-price immediately (existing loan, loan age as you type, company) | extra context fields on `/financing/eligibility` | `FinancingOption.tsx` |
| Choosing financing hides M-Pesa unless a deposit is due | - | `PaymentStep.tsx` |
| "Coming soon - talk to an agent" for products with no live pricing | `GET /api/v1/quotes/availability`, `contact` takes `product_interest` | `ComingSoonCard.tsx`, `GenericQuoteFlow.tsx` |
| "Under review" watches the application and moves on when approved | `GET /api/v1/applications/{id}/status` | `ApprovalWaitStep.tsx` |
| Staff see screening notes / where a reused file came from | `validation_notes` on documents | admin application + financing detail pages |
| Save-and-resume (quotes, documents, waiting for approval; never payment) | - | `lib/quoteSession.ts`, `ResumeQuoteCard.tsx` |
| Same person, different phone format = one customer (lookup only, stored numbers untouched) | `app/core/phone.py` | - |
| No-deposit financing approval creates a staff task to issue the policy | `_flag_zero_deposit_approval` in `financing_service.py` | - |
| Optional company-applicant deposit/rate (blank = standard) | migration `0020`, `corporate_*` settings, `is_corporate` on eligibility | admin financing settings page, `FinancingOption.tsx` |

## Settings (backend `.env`)
- `DOCUMENT_VALIDATION=strict|lenient|off` - strict refuses junk, lenient keeps it flagged `needs_review`, off = old behaviour.
- `ALLOW_DEMO_QUOTE_CATEGORIES=false` - set `true` on staging to let the demo insurers' quotes through for every category.

- `NEXT_PUBLIC_WHATSAPP_NUMBER` (frontend `.env.local`) - the number the "talk to an agent" links open.

## Database
Migrations `0019_document_screening` and `0020_corporate_financing_terms` only add nullable columns, so existing data and behaviour are unchanged. Run `alembic -c app/db/alembic.ini upgrade head`.

## What the screening can and cannot prove
Always: real PDF/JPEG/PNG from the file's bytes, not corrupt, not tiny, not password-protected, <=10 pages.
Images: readable size, not blank, not near-black, blur flagged for review.
PDFs with a text layer (online NTSA logbook, iTax KRA PIN): content must look like the claimed document.
Photos and scanned PDFs only get content-checked if the Tesseract OCR binary is installed on the server (the Dockerfile
now installs it); otherwise they pass the quality checks and are stored as "not machine-verified" for staff to review.
OCR on a phone photo is unreliable, so a photo is only REFUSED when its text positively looks like a different document
(an ID in the logbook slot). If OCR simply can't confirm it, the photo is kept and flagged `needs_review`.
The checks run in a worker thread, so a slow upload never blocks other requests.
