from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.content import Content, ContentCategory, Faq
from app.schemas.content import ContentCategoryOut, ContentOut, FaqOut

router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("", response_model=list[ContentOut])
async def list_content(db: AsyncSession = Depends(get_db), category: str | None = None):
    stmt = select(Content).where(Content.is_published.is_(True))
    if category:
        cat = await db.scalar(select(ContentCategory).where(ContentCategory.slug == category))
        if cat:
            stmt = stmt.where(Content.category_id == cat.id)
    return (await db.scalars(stmt)).all()


@router.get("/categories", response_model=list[ContentCategoryOut])
async def list_categories(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(ContentCategory))).all()


@router.get("/{slug}", response_model=ContentOut)
async def get_content(slug: str, db: AsyncSession = Depends(get_db)):
    content = await db.scalar(select(Content).where(Content.slug == slug, Content.is_published.is_(True)))
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    return content


faq_router = APIRouter(prefix="/api/v1/faqs", tags=["content"])


@faq_router.get("", response_model=list[FaqOut])
async def list_faqs(db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(select(Faq).where(Faq.is_published.is_(True)).order_by(Faq.display_order))
    ).all()
