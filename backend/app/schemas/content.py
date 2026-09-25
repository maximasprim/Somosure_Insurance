import uuid
from datetime import datetime

from pydantic import BaseModel


class ContentOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    body: str
    category_id: uuid.UUID | None
    is_published: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentCreate(BaseModel):
    slug: str
    title: str
    body: str
    category_id: str | None = None
    is_published: bool = False


class ContentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    is_published: bool | None = None


class FaqOut(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    category_id: uuid.UUID | None
    display_order: int
    is_published: bool

    model_config = {"from_attributes": True}


class FaqCreate(BaseModel):
    question: str
    answer: str
    category_id: str | None = None
    display_order: int = 0
    is_published: bool = True


class FaqUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category_id: str | None = None
    display_order: int | None = None
    is_published: bool | None = None


class ContentCategoryOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str

    model_config = {"from_attributes": True}
