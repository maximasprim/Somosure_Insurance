import uuid

from pydantic import BaseModel


class ChecklistItemOut(BaseModel):
    type: str
    label: str
    description: str
    tips: list[str] = []
    state: str  # provided | missing | auto
    source: str | None = None  # uploaded | insurance_application | earlier_application | generated


class DocumentChecklistOut(BaseModel):
    items: list[ChecklistItemOut]
    missing: list[str]  # document types still needed from the customer
    complete: bool


class ApplicationStatusOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str

    model_config = {"from_attributes": True}
