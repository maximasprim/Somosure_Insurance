# WhatsApp Integration - research and what's actually built

Researched September 2026. Sources: Meta's own developer documentation
(developers.facebook.com), and independent 2026 guides (Unipile, Message
Central).

## The real access model

WhatsApp Cloud API is Meta's own official API - **on-premise access was
deprecated in October 2025, so Cloud API is now the only option.** Two
paths to use it:

1. **Direct with Meta** - create a Meta Business Manager account
   (verification takes 1-3 business days), register a business phone
   number, get outbound message templates pre-approved, and build your
   own webhook infrastructure. Genuinely self-serve, like Africa's
   Talking - no partnership conversation required, just paperwork and
   engineering time.
2. **Through a BSP** (Business Solution Provider - e.g. Twilio, 360dialog,
   Message Central) - managed infrastructure and a shared inbox UI, live
   in as little as 48 hours, at the cost of a middleman fee on top of
   Meta's own per-message pricing.

Either way, three real constraints apply once this goes live:

- **Template approval**: any message a business *initiates* (not a reply)
  must use a pre-approved template. This matters directly for this
  platform's automation rules - a renewal reminder or "policy activated"
  notification sent via WhatsApp would need an approved template, not a
  freeform message.
- **24-hour customer service window**: once a customer messages in, the
  business can reply freely for 24 hours; outside that window, only
  approved templates go out. This shapes the conversation service design
  below.
- **Signal protocol encryption** end-to-end; Cloud API itself communicates
  over Graph API (sending) and webhooks (receiving), both HTTPS/TLS.

## What's built here vs. what needs real credentials

The **webhook verification and signature-checking mechanism is fully,
genuinely implemented** - not mocked - because both pieces only require
values *we* choose (a verify token, an app secret placeholder), not
Meta's approval:

- `GET /api/v1/webhooks/whatsapp` implements Meta's actual verification
  challenge exactly as specified: Meta calls this with
  `hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`, and the
  endpoint must echo back `hub.challenge` only if the token matches what
  we configured. This is real, working code - point Meta's App Dashboard
  at this URL once a real app exists and it will pass verification.
- `POST /api/v1/webhooks/whatsapp` implements Meta's real signature
  scheme - an `X-Hub-Signature-256` HMAC-SHA256 header computed from the
  app secret - exactly the same "verify before trusting" pattern used for
  the M-Pesa webhook (see `docs/PAYMENTS.md`).

**What's NOT real**: actually sending a message via Graph API
(`WhatsAppAdapter.send_text_message` / `send_template_message`) requires
a real WABA (WhatsApp Business Account) ID and access token - these raise
`NotImplementedError` until a real Meta Business Manager account and
approved templates exist, per the same rule as every insurer adapter
(spec §51 - never fabricate a message that didn't send).

## What's built beyond the webhook

- `WhatsAppConversation` / `WhatsAppMessage` models - every inbound
  message is logged, matched to a `Customer` by phone number (creating a
  guest customer if none exists, same pattern as the quote engine's guest
  resolution), and mirrored into the existing `Communication` table so
  it shows up in CRM history alongside SMS/email.
- A minimal conversation state machine reflecting spec §17's use cases
  (quote request, check status, claim report, agent handoff) - see
  `app/services/whatsapp_service.py`. This is a keyword-routing skeleton,
  not an NLP system; a real deployment would likely want proper intent
  classification, which is out of scope here.

## Outreach

Since Cloud API is self-serve, there's no separate "request access"
email needed the way there is for Lami or the direct insurers - the next
concrete step is registering a Meta Business Manager account and a
business phone number, which is a business/ops task rather than a
technical-access request.
