"""The quote page shows a new total the instant an add-on or excess protector is ticked, using only what the quote
itself publishes (`coverage.pricing_rules`, the options' prices, the premium). These tests make the server prove that
those published figures are enough to reproduce its own totals, for every option and for all of them together - so the
instant figure on screen can never disagree with the confirmed one (frontend/lib/quotePricing.ts does the same sums).
"""

from decimal import ROUND_HALF_UP, Decimal

import pytest

CENT = Decimal("0.01")
ANSWERS = {"value": 800000, "usage": "private", "cover_type": "comprehensive", "owner_phone": "0700000001", "owner_name": "Live Price"}


@pytest.fixture(autouse=True)
def rate_cards_from_the_test_database(session_factory, monkeypatch):
    """The rate-card adapter opens its own database session. Left alone that is the app's global engine - whatever
    DATABASE_URL says (a live database on a developer machine) - so these tests point it at the test database."""
    from app.providers import rate_card_adapter

    monkeypatch.setattr(rate_card_adapter, "AsyncSessionLocal", session_factory)


async def _seed(db_session):
    from app.db.seed import seed_rate_cards

    await seed_rate_cards(db_session)
    await db_session.commit()


async def _rate_card_quotes(client, extensions):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {**ANSWERS, "extensions": extensions}})
    assert res.status_code == 200, res.text
    return [q for q in res.json()["quotes"] if q["provider_metadata"].get("quote_basis") == "published_rate_card"]


def _live(quote, picked):
    """What the page computes: back out what the server priced in, add what is ticked, then levies and flat fees."""
    rules = quote["coverage"]["pricing_rules"]
    premium = Decimal(quote["premium"])
    for option in quote["coverage"].get("optional_extensions", []):
        if option["selected"]:
            premium -= Decimal(option["amount"])
        if option["code"] in picked:
            premium += Decimal(option["amount"])
    taxes = sum(((premium * Decimal(r)).quantize(CENT, rounding=ROUND_HALF_UP) for r in rules["levy_rates"]), Decimal("0"))
    fees = Decimal(rules["flat_fees"])
    return premium, taxes, fees, premium + taxes + fees


async def test_published_rules_reproduce_the_servers_total_for_every_tick(client, db_session):
    await _seed(db_session)
    base = await _rate_card_quotes(client, [])
    assert base, "no rate-card quotes to check"
    for q in base:
        assert q["coverage"]["pricing_rules"] == {"levy_rates": ["0.0025", "0.0020"], "flat_fees": "40.00"}
        assert (Decimal(q["taxes"]), Decimal(q["fees"]), Decimal(q["total"])) == _live(q, set())[1:]  # nothing ticked: matches itself

    options = {o["code"]: o["kind"] for q in base for o in q["coverage"].get("optional_extensions", [])}
    assert options, "the seeded rate cards should offer options"
    assert "excess_protector" in options.values() and "extra" in options.values()

    combos = [{code} for code in options] + [set(options)]  # each on its own, then everything ticked at once
    checked = 0
    for combo in combos:
        priced = {q["provider_id"]: q for q in await _rate_card_quotes(client, sorted(combo))}
        for q in base:
            offered = {o["code"] for o in q["coverage"].get("optional_extensions", [])}
            if not combo & offered:
                continue  # this insurer does not offer anything that was ticked
            server = priced[q["provider_id"]]
            expected = _live(q, combo & offered)
            actual = (Decimal(server["premium"]), Decimal(server["taxes"]), Decimal(server["fees"]), Decimal(server["total"]))
            assert expected == actual, f"{q['provider_name']} with {sorted(combo)}: page would show {expected}, server says {actual}"
            checked += 1
    assert checked >= len(options)


async def test_unticking_what_the_server_priced_in_takes_it_back_out(client, db_session):
    """Start from a quote that already includes extras, untick them, and land exactly on the no-extras price."""
    await _seed(db_session)
    plain = {q["provider_id"]: q for q in await _rate_card_quotes(client, [])}
    every_code = sorted({o["code"] for q in plain.values() for o in q["coverage"].get("optional_extensions", [])})
    loaded = await _rate_card_quotes(client, every_code)
    for q in loaded:
        expected = Decimal(plain[q["provider_id"]]["total"])
        assert _live(q, set())[3] == expected
