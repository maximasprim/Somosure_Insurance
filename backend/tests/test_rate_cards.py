"""Integration tests for the rate-card engine: seeding AMACO and Pioneer
Insurance Kenya's real rate cards (app/db/rate_card_seed_data.py) and
pricing a quote against them end to end, through the same
POST /api/v1/quotes endpoint a real customer hits.
"""

from decimal import Decimal


async def _seed_rate_cards(db_session):
    from app.db.seed import seed_rate_cards

    await seed_rate_cards(db_session)
    await db_session.commit()


async def test_amaco_motor_private_comprehensive_matches_the_rate_card(client, db_session):
    """Sum insured 800,000 falls in AMACO's 500,001-999,999 band (4.0%,
    min premium 30,000) -> 800,000 * 4% = 32,000, which clears the floor,
    so base premium is exactly 32,000 - not the 30,000 floor."""
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={
            "category": "motor",
            "answers": {
                "value": 800000,
                "usage": "private",
                "cover_type": "comprehensive",
                "owner_phone": "0700000001",
                "owner_name": "Rate Card Test",
            },
        },
    )
    assert res.status_code == 200
    quotes = res.json()["quotes"]

    amaco_quotes = [q for q in quotes if q["provider_metadata"].get("quote_basis") == "published_rate_card"]
    amaco_quote = next(q for q in amaco_quotes if Decimal(q["premium"]) == Decimal("32000.00"))
    assert amaco_quote["is_mock"] is False
    # PHCF 0.25% + Training Levy 0.20% of the 32,000 premium, plus Kshs 40 stamp duty
    assert Decimal(amaco_quote["taxes"]) == Decimal("80.00") + Decimal("64.00")
    assert Decimal(amaco_quote["fees"]) == Decimal("40.00")
    assert Decimal(amaco_quote["total"]) == Decimal("32184.00")


async def test_amaco_motor_private_below_first_band_hits_the_minimum_premium(client, db_session):
    """Sum insured 400,000 falls in AMACO's lowest band (0-500,000 at 6%)
    - 400,000 * 6% = 24,000, floored to the 30,000 minimum premium."""
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={
            "category": "motor",
            "answers": {
                "value": 400000,
                "usage": "private",
                "cover_type": "comprehensive",
                "owner_phone": "0700000002",
                "owner_name": "Rate Card Test 2",
            },
        },
    )
    quotes = res.json()["quotes"]
    amaco_quote = next(
        q for q in quotes
        if q["provider_metadata"].get("source_document", "").startswith("AMACO")
    )
    assert Decimal(amaco_quote["premium"]) == Decimal("30000.00")


async def test_amaco_motor_private_tpo_is_a_flat_fee(client, db_session):
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={
            "category": "motor",
            "answers": {
                "value": 800000,
                "usage": "private",
                "cover_type": "third_party",
                "owner_phone": "0700000003",
                "owner_name": "Rate Card Test 3",
            },
        },
    )
    quotes = res.json()["quotes"]
    amaco_quote = next(
        q for q in quotes
        if q["provider_metadata"].get("source_document", "").startswith("AMACO")
    )
    assert Decimal(amaco_quote["premium"]) == Decimal("7500.00")
    assert Decimal(amaco_quote["total"]) == Decimal("7573.75")


async def test_pioneer_quote_is_flagged_needs_review(client, db_session):
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={
            "category": "motor",
            "answers": {
                "value": 800000,
                "usage": "private",
                "cover_type": "comprehensive",
                "owner_phone": "0700000004",
                "owner_name": "Rate Card Test 4",
            },
        },
    )
    quotes = res.json()["quotes"]
    pioneer_quote = next(
        q for q in quotes
        if q["provider_metadata"].get("data_confidence") == "needs_review"
    )
    assert "not yet been verified" in pioneer_quote["coverage"]["data_confidence_notice"]


async def test_unconfigured_product_category_fails_this_provider_only_not_the_whole_request(client, db_session):
    """Neither rate card has medical rates yet - the medical quote request
    should still succeed overall (spec §46: one provider failing never
    breaks the whole comparison), just without a rate-card quote in it."""
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={"category": "medical", "answers": {"owner_phone": "0700000005", "owner_name": "Rate Card Test 5"}},
    )
    assert res.status_code == 200
    quotes = res.json()["quotes"]
    assert not any(q["provider_metadata"].get("quote_basis") == "published_rate_card" for q in quotes)


async def test_vehicle_class_override_reaches_school_bus_pricing(client, db_session):
    await _seed_rate_cards(db_session)

    res = await client.post(
        "/api/v1/quotes",
        json={
            "category": "motor",
            "answers": {
                "value": 2000000,
                "usage": "commercial",
                "vehicle_class": "school_bus",
                "cover_type": "comprehensive",
                "owner_phone": "0700000006",
                "owner_name": "Rate Card Test 6",
            },
        },
    )
    quotes = res.json()["quotes"]
    amaco_quote = next(
        q for q in quotes
        if q["provider_metadata"].get("source_document", "").startswith("AMACO")
    )
    # 2,000,000 * 3% = 60,000, above the 30,000 floor
    assert Decimal(amaco_quote["premium"]) == Decimal("60000.00")
    assert "School Bus" in amaco_quote["coverage"]["summary"]
