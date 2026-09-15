import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.content import Content, Faq
from app.schemas.content import ContentCreate, ContentOut, ContentUpdate, FaqCreate, FaqOut

router = APIRouter(
    prefix="/api/v1/admin/content",
    tags=["content"],
    dependencies=[Depends(require_roles("super_admin", "management", "marketing"))],
)


@router.get("", response_model=list[ContentOut])
async def list_all_content(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Content))).all()


@router.post("", response_model=ContentOut)
async def create_content(payload: ContentCreate, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    existing = await db.scalar(select(Content).where(Content.slug == payload.slug))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A content item with this slug already exists")

    content = Content(id=uuid.uuid4(), author_user_id=claims.get("sub"), **payload.model_dump())
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


@router.patch("/{content_id}", response_model=ContentOut)
async def update_content(content_id: str, payload: ContentUpdate, db: AsyncSession = Depends(get_db)):
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)
    return content


@router.post("/faqs", response_model=FaqOut)
async def create_faq(payload: FaqCreate, db: AsyncSession = Depends(get_db)):
    faq = Faq(id=uuid.uuid4(), **payload.model_dump())
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq
