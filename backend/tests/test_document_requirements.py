"""Which documents are asked for, by category and cover type (document_requirements.py)."""

from app.services.document_requirements import (
    insurance_documents,
    quote_cover_type,
    requirements_payload,
)


def _types(category, cover=None):
    return [d.type for d in insurance_documents(category, cover)]


def test_comprehensive_motor_cover_also_asks_for_a_valuation_report():
    assert _types("motor", "comprehensive") == ["national_id", "logbook", "valuation_report", "kra_pin"]
    assert _types("motor", "Comprehensive") == ["national_id", "logbook", "valuation_report", "kra_pin"]


def test_other_motor_cover_and_other_products_do_not():
    for cover in ("tpo", "third_party", "third_party_fire_theft", None):
        assert "valuation_report" not in _types("motor", cover)
    assert "valuation_report" not in _types("medical", "comprehensive")
    assert "valuation_report" not in _types("property", "comprehensive")


def test_the_requirements_payload_follows_the_cover_type():
    with_cover = requirements_payload("motor", False, "comprehensive")
    assert "valuation_report" in [d["type"] for d in with_cover["insurance"]]
    assert "valuation_report" not in [d["type"] for d in requirements_payload("motor")["insurance"]]
    # Financing asks for what it always did.
    assert "valuation_report" not in [d["type"] for d in with_cover["financing"]["documents"]]


def test_what_a_quote_was_priced_as_wins_over_what_was_asked_for():
    # A car too old for comprehensive is quoted third-party even when comprehensive was chosen.
    assert quote_cover_type({"cover_type": "tpo"}, {"cover_type": "comprehensive"}) == "tpo"
    assert quote_cover_type({}, {"cover_type": "Comprehensive"}) == "comprehensive"
    assert quote_cover_type(None, None) is None
