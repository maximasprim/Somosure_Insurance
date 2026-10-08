"""Force-deleting a provider: destroys every record that transitively
depends on it, in dependency order, so nothing is left dangling.

This is deliberately kept separate from the ordinary, safe provider
deletion path (see api/v1/admin.py::delete_provider), which refuses to
touch a provider that has any quote or policy history. This module is
what backs the explicit "yes, destroy everything" action - it should
only ever run when an admin has confirmed by typing the provider's name,
never as a side effect of anything else.

The dependency chain, leaf-to-root (what gets deleted, in this order):

    payment_transactions        -> payments
    sticker_events               -> stickers
    renewal_events                -> renewals
    claim_documents, claim_events -> claims
    financing_installments        -> financing_agreements
    financing_documents, financing_events -> financing_applications
    referrals.policy_id is NULLED, not deleted (see note below)
    policy_documents, policy_events -> policies
    application_documents, application_events -> applications
    quote_items                   -> quotes
    rate_card tiers/excesses      -> rate_card_vehicle_classes
    rate_card extensions/free_benefits, rate_card_vehicle_classes,
    insurance_product_plans       -> insurance_products
    insurance_products, insurance_product_plans, and finally the
    provider itself

A Referral's policy_id is nullable and a referral is really a record of
the REFERRING relationship between two customers, not something that
belongs to the policy - so referrals are kept, with policy_id cleared,
rather than deleted outright.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.models.affiliate import AffiliateCommission
from app.models.application import Application, ApplicationDocument, ApplicationEvent
from app.models.claim import Claim, ClaimDocument, ClaimEvent
from app.models.financing import (
    FinancingAgreement,
    FinancingApplication,
    FinancingDocument,
    FinancingEvent,
    FinancingInstallment,
)
from app.models.payment import Payment, PaymentTransaction
from app.models.policy import Policy, PolicyDocument, PolicyEvent
from app.models.provider import InsuranceProduct, InsuranceProductPlan, InsuranceProvider
from app.models.quote import Quote, QuoteItem
from app.models.rate_card import RateCardExcess, RateCardExtension, RateCardFreeBenefit, RateCardTier, RateCardVehicleClass
from app.models.referral import Referral
from app.models.renewal import Renewal, RenewalEvent
from app.models.sticker import Sticker, StickerEvent


@dataclass
class DeletionCounts:
    """How many rows were removed from each table - returned to the admin
    so a destructive action isn't a black box, and useful in an audit log
    entry if one is added later."""

    payments: int = 0
    payment_transactions: int = 0
    stickers: int = 0
    renewals: int = 0
    claims: int = 0
    financing_applications: int = 0
    financing_agreements: int = 0
    referrals_unlinked: int = 0
    affiliate_commissions_unlinked: int = 0
    policies: int = 0
    applications: int = 0
    quotes: int = 0
    vehicle_classes: int = 0
    extensions: int = 0
    free_benefits: int = 0
    products: int = 0
    other: dict = field(default_factory=dict)


async def force_delete_provider(db: AsyncSession, provider_id: str) -> DeletionCounts:
    """Deletes `provider_id` and everything that depends on it, however
    much quote/policy/payment/claim/financing/sticker history exists.
    Caller (the API layer) is responsible for making sure this was
    explicitly confirmed - this function does not ask twice.
    """
    counts = DeletionCounts()

    quote_ids = select(Quote.id).where(Quote.provider_id == provider_id).scalar_subquery()
    application_ids = select(Application.id).where(Application.quote_id.in_(quote_ids)).scalar_subquery()
    policy_ids = select(Policy.id).where(Policy.provider_id == provider_id).scalar_subquery()
    claim_ids = select(Claim.id).where(Claim.policy_id.in_(policy_ids)).scalar_subquery()
    sticker_ids = select(Sticker.id).where(Sticker.policy_id.in_(policy_ids)).scalar_subquery()
    renewal_ids = select(Renewal.id).where(Renewal.policy_id.in_(policy_ids)).scalar_subquery()
    financing_app_ids = select(FinancingApplication.id).where(FinancingApplication.quote_id.in_(quote_ids)).scalar_subquery()
    financing_agreement_ids = (
        select(FinancingAgreement.id).where(FinancingAgreement.application_id.in_(financing_app_ids)).scalar_subquery()
    )
    payment_ids = (
        select(Payment.id)
        .where(Payment.application_id.in_(application_ids) | Payment.policy_id.in_(policy_ids))
        .scalar_subquery()
    )

    # 1. Payments (children first, self-referencing root+legs together)
    await db.execute(delete(PaymentTransaction).where(PaymentTransaction.payment_id.in_(payment_ids)))
    result = await db.execute(delete(Payment).where(Payment.id.in_(payment_ids)))
    counts.payments = result.rowcount or 0

    # 2. Stickers
    await db.execute(delete(StickerEvent).where(StickerEvent.sticker_id.in_(sticker_ids)))
    result = await db.execute(delete(Sticker).where(Sticker.id.in_(sticker_ids)))
    counts.stickers = result.rowcount or 0

    # 3. Renewals
    await db.execute(delete(RenewalEvent).where(RenewalEvent.renewal_id.in_(renewal_ids)))
    result = await db.execute(delete(Renewal).where(Renewal.id.in_(renewal_ids)))
    counts.renewals = result.rowcount or 0

    # 4. Claims
    await db.execute(delete(ClaimDocument).where(ClaimDocument.claim_id.in_(claim_ids)))
    await db.execute(delete(ClaimEvent).where(ClaimEvent.claim_id.in_(claim_ids)))
    result = await db.execute(delete(Claim).where(Claim.id.in_(claim_ids)))
    counts.claims = result.rowcount or 0

    # 5. Financing (agreement -> installments, then application -> agreement/docs/events)
    await db.execute(delete(FinancingInstallment).where(FinancingInstallment.agreement_id.in_(financing_agreement_ids)))
    result = await db.execute(delete(FinancingAgreement).where(FinancingAgreement.id.in_(financing_agreement_ids)))
    counts.financing_agreements = result.rowcount or 0
    await db.execute(delete(FinancingDocument).where(FinancingDocument.financing_application_id.in_(financing_app_ids)))
    await db.execute(delete(FinancingEvent).where(FinancingEvent.financing_application_id.in_(financing_app_ids)))
    result = await db.execute(delete(FinancingApplication).where(FinancingApplication.id.in_(financing_app_ids)))
    counts.financing_applications = result.rowcount or 0

    # 6. Referrals that point at a policy being removed - unlink, don't delete
    # (a referral is a record of one customer referring another; the
    # reward/relationship it represents outlives any one policy).
    result = await db.execute(update(Referral).where(Referral.policy_id.in_(policy_ids)).values(policy_id=None))
    counts.referrals_unlinked = result.rowcount or 0

    # Commissions are financial records (money earned or paid) - kept, with
    # only the link to the removed policy cleared.
    result = await db.execute(
        update(AffiliateCommission).where(AffiliateCommission.policy_id.in_(policy_ids)).values(policy_id=None)
    )
    counts.affiliate_commissions_unlinked = result.rowcount or 0

    # 7. Policies
    await db.execute(delete(PolicyDocument).where(PolicyDocument.policy_id.in_(policy_ids)))
    await db.execute(delete(PolicyEvent).where(PolicyEvent.policy_id.in_(policy_ids)))
    result = await db.execute(delete(Policy).where(Policy.id.in_(policy_ids)))
    counts.policies = result.rowcount or 0

    # 8. Applications
    await db.execute(delete(ApplicationDocument).where(ApplicationDocument.application_id.in_(application_ids)))
    await db.execute(delete(ApplicationEvent).where(ApplicationEvent.application_id.in_(application_ids)))
    result = await db.execute(delete(Application).where(Application.id.in_(application_ids)))
    counts.applications = result.rowcount or 0

    # 9. Quotes
    await db.execute(delete(QuoteItem).where(QuoteItem.quote_id.in_(quote_ids)))
    result = await db.execute(delete(Quote).where(Quote.provider_id == provider_id))
    counts.quotes = result.rowcount or 0

    # 10. This provider's own configuration - products, plans, and every
    # rate-card table (unconditional: these are pure config, not
    # transactional history, so they're always removed regardless of
    # whether step 1-9 found anything).
    product_ids = select(InsuranceProduct.id).where(InsuranceProduct.provider_id == provider_id).scalar_subquery()
    await db.execute(delete(InsuranceProductPlan).where(InsuranceProductPlan.product_id.in_(product_ids)))
    result = await db.execute(delete(InsuranceProduct).where(InsuranceProduct.provider_id == provider_id))
    counts.products = result.rowcount or 0

    class_ids = select(RateCardVehicleClass.id).where(RateCardVehicleClass.provider_id == provider_id).scalar_subquery()
    await db.execute(delete(RateCardTier).where(RateCardTier.vehicle_class_id.in_(class_ids)))
    await db.execute(delete(RateCardExcess).where(RateCardExcess.vehicle_class_id.in_(class_ids)))
    result = await db.execute(delete(RateCardVehicleClass).where(RateCardVehicleClass.provider_id == provider_id))
    counts.vehicle_classes = result.rowcount or 0
    result = await db.execute(delete(RateCardExtension).where(RateCardExtension.provider_id == provider_id))
    counts.extensions = result.rowcount or 0
    result = await db.execute(delete(RateCardFreeBenefit).where(RateCardFreeBenefit.provider_id == provider_id))
    counts.free_benefits = result.rowcount or 0

    # 11. The provider itself.
    provider = await db.get(InsuranceProvider, provider_id)
    if provider:
        await db.delete(provider)

    await db.commit()
    # The bulk deletes above bypass the ORM, so they aren't individually
    # captured - record exactly what was removed as one audit event.
    record_event(
        "provider.deleted_with_dependents",
        entity_type="insurance_providers",
        entity_id=provider_id,
        summary="Deleted an insurance provider and everything depending on it",
        removed=asdict(counts),
    )
    return counts
