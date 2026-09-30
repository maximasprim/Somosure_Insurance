import uuid

from pydantic import BaseModel


class ProviderCreate(BaseModel):
    name: str
    provider_type: str = "insurer"
    integration_mode: str = "mock"
    status: str = "inactive"
    supports_quote: bool = False
    supports_policy: bool = False
    supports_payment: bool = False
    supports_documents: bool = False
    supports_claims: bool = False
    supports_renewal: bool = False
    supports_webhooks: bool = False


class ProviderUpdate(BaseModel):
    """Every field is optional - PATCH sends only what changed
    (`exclude_unset`), so this covers full-record editing, not just the
    status toggle the original UI had."""

    name: str | None = None
    provider_type: str | None = None
    status: str | None = None
    integration_mode: str | None = None
    supports_quote: bool | None = None
    supports_policy: bool | None = None
    supports_payment: bool | None = None
    supports_documents: bool | None = None
    supports_claims: bool | None = None
    supports_renewal: bool | None = None
    supports_webhooks: bool | None = None


class ProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    integration_mode: str
    status: str
    supports_quote: bool
    supports_policy: bool
    supports_payment: bool
    supports_documents: bool
    supports_claims: bool
    supports_renewal: bool
    supports_webhooks: bool

    model_config = {"from_attributes": True}
    # Deliberately excludes api_base_url and credentials_secret_ref -
    # never surface integration internals to any client, admin included,
    # through a generic serializer (spec §23).


class ProductCreate(BaseModel):
    provider_id: str
    category: str
    subtype: str | None = None
    name: str
    description: str | None = None
    required_fields: dict = {}
    required_documents: dict = {}


class ProductOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    category: str
    subtype: str | None
    name: str
    is_active: bool

    model_config = {"from_attributes": True}
