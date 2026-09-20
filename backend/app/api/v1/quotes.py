from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.provider import InsuranceProvider
from app.schemas.quote import NormalizedQuoteOut, QuoteRequestCreate, QuoteRequestOut
from app.services.quote_service import request_quotes

router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@router.post("", response_model=QuoteRequestOut)
async def create_quote_request(payload: QuoteRequestCreate, db: AsyncSession = Depends(get_db)):
    quote_request, quotes, any_failure = await request_quotes(
        db, payload.category, payload.answers, payload.customer_id
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
