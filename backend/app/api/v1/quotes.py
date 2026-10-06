from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.provider import InsuranceProvider
from app.schemas.quote import NormalizedQuoteOut, QuoteRequestCreate, QuoteRequestOut
from app.services.document_requirements import requirements_payload
from app.services.product_catalog import is_coming_soon, normalize_category
from app.services.quote_availability import get_category_availability
from app.services.quote_service import request_quotes

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@router.post("", response_model=QuoteRequestOut)
async def create_quote_request(payload: QuoteRequestCreate, db: AsyncSession = Depends(get_db)):
    # Retired products (home, business) are served as their replacement
    # (property), so old links and stale browser tabs keep working.
    category = normalize_category(payload.category)
    if is_coming_soon(category):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Online quotes for {category} insurance are coming soon - please talk to one of our agents.",
        )
    quote_request, quotes, any_failure = await request_quotes(
        db, category, payload.answers, payload.customer_id
    )

    provider_names: dict[str, str] = {}
    if quotes:
        providers = (
            await db.scalars(
                select(InsuranceProvider).where(
                    InsuranceProvider.id.in_([q.provider_id for q in quotes])
                )
            )
        ).all()
        provider_names = {str(p.id): p.name for p in providers}

    return QuoteRequestOut(
        reference=quote_request.reference,
        category=quote_request.category,
        status=quote_request.status,
        customer_id=str(quote_request.customer_id) if quote_request.customer_id else None,
        note="Some insurers were temporarily unavailable; showing available quotations." if any_failure else None,
        quotes=[
            NormalizedQuoteOut(
                id=str(q.id),
                provider_id=str(q.provider_id),
                provider_name=(
                    f"{q.underlying_provider_name} (via {provider_names.get(str(q.provider_id), 'Unknown')})"
                    if q.underlying_provider_name
                    else provider_names.get(str(q.provider_id), "Unknown")
                ),
                underlying_provider_name=q.underlying_provider_name,
                premium=q.premium,
                taxes=q.taxes,
                fees=q.fees,
                total=q.total,
                currency=q.currency,
                coverage=q.coverage,
                exclusions=q.exclusions,
                deductibles=q.deductibles,
                payment_options=q.payment_options,
                provider_metadata=q.provider_metadata,
                is_mock=q.is_mock,
                valid_until=q.valid_until,
            )
            for q in quotes
        ],
    )


@router.get("/availability")
async def category_availability(db: AsyncSession = Depends(get_db)):
    """Which product categories can be quoted online right now. The quote
    pages use this to show a "coming soon - talk to an agent" screen for a
    category with no live pricing, instead of the quote form."""
    return {"categories": await get_category_availability(db)}


@router.get("/document-requirements")
async def document_requirements(category: str = "motor", corporate: bool = False):
    """The documents a customer should have ready as softcopies - shown
    right after quotes are generated, before they start an application."""
    return requirements_payload(normalize_category(category), corporate)
