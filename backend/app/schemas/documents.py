import uuid

from pydantic import BaseModel


class ChecklistItemOut(BaseModel):
    type: str
    label: str
    description: str
    tips: list[str] = []
    state: str  # provided | missing | auto
    source: str | None = None  # uploaded | insurance_application | earlier_application | generated
    optional: bool = False  # can be left out; the application can still be submitted


class DocumentChecklistOut(BaseModel):
    items: list[ChecklistItemOut]
    missing: list[str]  # required document types still needed from the customer
    optional_missing: list[str] = []  # optional ones not provided yet (the valuation report)
    complete: bool  # nothing REQUIRED is missing


class ApplicationStatusOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str

    model_config = {"from_attributes": True}
