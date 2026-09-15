# Kenya Insurance API Landscape - Phase 7 groundwork

Researched September 2026. Sources linked inline; re-verify before relying
on anything here for a real integration decision - company partnerships
and API offerings change.

## The core finding

None of Kenya's major underwriters publish a self-serve public developer
API portal (no public "developer.britam.com" or equivalent was found for
any of them). This is normal for the region: African insurance carriers
are described industry-wide as running on "rigid systems that do not allow
for integration with external partners," which is exactly why aggregator
insurtechs like Lami exist in the first place. Two paths exist for
Somosure to connect to real insurers:

**Path A - direct integration with an underwriter.** Requires a signed
agency/broker agreement with that insurer first; the insurer then shares
its technical integration spec privately (not published). This is a
business development conversation, not a developer-signup form.

**Path B - integrate once with an aggregator that already bridges many
insurers.** A single API contract gets you multiple underwriters at once.
This is very likely the faster path to real quotes from real insurers.

## Direct underwriters (Path A) - request access individually

| Company | Kenyan market position | What's known |
|---|---|---|
| **Britam** | One of the "big three" alongside Jubilee/CIC; ~4M microinsurance customers (2024) | Partners with M-TIBA, Telkom, Airtel, Little Cab via bespoke integrations - "Britam Connect" embedded-insurance branding exists, no public API docs found |
| **Jubilee Insurance** | Historically #1 by market share | Launched **J-Force** (2025) - a "paperless web and mobile platform for policy issuance, customer engagement and transaction processing" for its agents; no public API found |
| **APA Insurance** | Top-5 by government tender wins | No public API found |
| **CIC Insurance Group** | Top-3, strong in agricultural/climate microinsurance | No public API found |
| **ICEA Lion** | Major player, strong claims ratios | No public API found |
| **Old Mutual Kenya** (formerly UAP) | Major player | No public API found |
| **Sanlam Kenya** (Sanlam Allianz) | Major player, formerly Pan Africa Life | No public API found |
| **GA Insurance** | Mid-tier, integrates via mTek | No public API found directly; reachable via mTek (see below) |

Sources: [Kenya Digital Insurance Platforms Market Report](https://www.kenresearch.com/industry-reports/kenya-digital-insurance-platforms-market), [Britam InsurTech Award deck](https://www.slideshare.net/slideshow/britam-general-insurance-limited-kenya/252234311), [Wikipedia: List of insurance companies in Kenya](https://en.wikipedia.org/wiki/List_of_insurance_companies_in_Kenya).

## Aggregators (Path B) - one integration, multiple insurers

| Platform | HQ | What they offer |
|---|---|---|
| **Lami Technologies** | Nairobi | Insurance-as-a-service API; connects to **~25 insurance companies**; existing enterprise customers include Stanbic Bank Kenya and Jumia. Products: motor, medical, and other tailored covers, quote-to-policy-document in seconds via API. **This is the single most promising integration target** - one contract, broad underwriter coverage. |
| **mTek Services** (acquired by **bolttech**, Dec 2025) | Nairobi | Partners directly with GA Insurance, Sanlam, and Britam; B2B integration offering for banks/MFIs. Now part of bolttech's global embedded-insurance stack, so terms may have changed post-acquisition. |
| **Turaco** | Nairobi (+ Uganda, Ghana, Nigeria) | API-driven embedded insurance, focused on low-premium health/life/accident products for MNO and fintech partners (e.g. M-KOPA); less likely to fit Somosure's broader product range but worth a conversation given the API-first posture. |

Sources: [TechCrunch - Lami raises $1.8M](https://techcrunch.com/2021/05/04/kenyas-lami-raises-1-8m-to-scale-api-insurance-platform-across-africa/), [Lami CEO interview](https://www.builtinafrica.io/blog-post/jihan-abass-lami), [bolttech acquires mTek](https://bolttech.io/news/mtek-becomes-part-of-bolttech/), [Turaco/M-KOPA milestone](https://techcabal.com/2025/03/18/turaco-m-kopa-insurance-partnersh/).

## What this repo does with this research

Every company above has a corresponding adapter file under
`app/providers/` (e.g. `lami_adapter.py`, `britam_adapter.py`) and a seeded
`InsuranceProvider` row (`status: inactive`, no `api_base_url` or
credentials). Each adapter:

- Implements the full `InsuranceProviderAdapter` interface so it's ready
  to receive real logic
- Raises `NotImplementedError` on every method with a message naming
  exactly what's missing (base URL, auth scheme, endpoint paths, field
  mappings) - never a fabricated response
- Carries a docstring citing what's publicly known about that company's
  integration model (from the table above), so whoever picks up the real
  integration later isn't starting from zero

This is exactly the "build interfaces/mocks until real provider API
documentation and credentials are supplied" rule from spec §51 - applied
to real, named candidates instead of hypothetical ones, since you asked
for the outreach targets to be real.

## Suggested outreach order

1. **Lami** first - broadest underwriter coverage in one integration,
   Kenya-based, and their own marketing already targets exactly this kind
   of B2B2C integration.
2. **mTek/bolttech** as a second aggregator option, especially if GA
   Insurance or Sanlam products matter for Somosure's lineup.
3. **Direct insurer conversations** (Britam, Jubilee, APA, CIC, ICEA Lion)
   in parallel if a direct agency relationship is wanted regardless of
   aggregator coverage - these take longer since there's no self-serve
   developer signup, but Somosure's existing broker/agency relationships
   (if any) may already open this door faster than a cold approach.

A ready-to-send outreach message is in `docs/API_ACCESS_REQUEST_TEMPLATE.md`.
