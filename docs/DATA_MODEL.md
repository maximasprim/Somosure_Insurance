# Data Model - Phase 1

Tables actually created by migration `0001_initial_foundation`. The rest of
the spec §31 table list (policies, payments, claims, renewals, stickers,
financing, leads, communications, content, automation, audit_logs, ...) is
designed conceptually in the roadmap but not yet migrated - adding them
alongside their first real feature keeps the schema honest about what's
actually wired up.

```mermaid
erDiagram
    ROLES ||--o{ USER_ROLES : has
    USERS ||--o{ USER_ROLES : has
    USERS ||--o| CUSTOMERS : "may become"
    CUSTOMERS ||--o{ CUSTOMER_CONTACTS : has
    CUSTOMERS ||--o{ QUOTE_REQUESTS : makes

    INSURANCE_PROVIDERS ||--o{ INSURANCE_PRODUCTS : offers
    INSURANCE_PRODUCTS ||--o{ INSURANCE_PRODUCT_PLANS : has

    QUOTE_REQUESTS ||--o{ QUOTES : "fans out to"
    INSURANCE_PROVIDERS ||--o{ QUOTES : returns
    INSURANCE_PRODUCTS ||--o{ QUOTES : "quoted against"
    QUOTES ||--o{ QUOTE_ITEMS : "itemized as"

    USERS {
        uuid id PK
        string email UK
        string hashed_password
        bool is_active
    }
    CUSTOMERS {
        uuid id PK
        uuid user_id FK "nullable - guest quote flow"
        string phone
        string lead_source
    }
    INSURANCE_PROVIDERS {
        uuid id PK
        string name
        string integration_mode "mock | rest | soap | manual | csv_import"
        string status "active | inactive | maintenance | manual_only"
        string credentials_secret_ref "reference only, never a value"
    }
    QUOTE_REQUESTS {
        uuid id PK
        string reference UK "SOM-2026-000123"
        string category
        string status
    }
    QUOTES {
        uuid id PK
        uuid quote_request_id FK
        uuid provider_id FK
        numeric total
        bool is_mock
        string status
    }
```

## Notes

- `credentials_secret_ref` on `insurance_providers` stores a *name*, not a
  value - the actual secret is resolved from the environment/secret manager
  at call time and never leaves the backend process (spec §23, §30).
- `quotes.is_mock` is `true` for every row until a real adapter replaces
  `MockProvider` for that insurer - this flag should propagate to every API
  response and UI surface that shows a quote.
- `quote_requests.reference` uses the `SOM-YYYY-NNNNNN` format from spec §6.
