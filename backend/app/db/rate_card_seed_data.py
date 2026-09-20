"""Static rate-card data for the two brokers whose published rate cards
have been supplied so far: AMACO (Africa Merchant Assurance Co Ltd) and
Pioneer Insurance Kenya. Consumed by app/db/seed.py.

This is real, sourced pricing data, not fabricated placeholders - each
vehicle class records exactly which document it came from
(`source_document`) and how confidently it was transcribed
(`data_confidence`). See docs/RATE_CARDS.md for the canonical class-code
list, the assumptions made while transcribing each document, and how to
add a new broker's rate card here (or, preferably, through the
/api/v1/admin/rate-cards API instead of editing this file).

Only the `motor` product category is populated - both source documents
were motor rating guides. Nothing about the schema is motor-specific
(see app/models/rate_card.py); a medical, life, or travel rate card for
either broker - or a new broker entirely - slots in as more rows here or
through the admin API, with no code changes.
"""

AMACO_SOURCE = "AMACO Rating Guide - 2026 Revised Motor Rates (circulated 2 Jul 2026)"
PIONEER_SOURCE = (
    "Pioneer Insurance Kenya rate sheet (RATES_2025.pdf) - table columns did not "
    "extract cleanly from the source file; figures below are a best-effort "
    "reconstruction and are marked needs_review. Verify against the original "
    "document before quoting a live customer against them."
)

PROVIDERS = [
    {
        "key": "amaco",
        "name": "AMACO (Africa Merchant Assurance Co Ltd)",
        "provider_type": "insurer",
    },
    {
        "key": "pioneer insurance kenya",
        "name": "Pioneer Insurance Kenya",
        "provider_type": "insurer",
    },
]


def _psv_capacity_tpo_tiers(annual_by_capacity: dict[int, float], tier_order_start: int) -> list[dict]:
    """AMACO's PSV Third Party Only schedule prices annual premium per
    exact seating capacity (7 through 51 seats), not a handful of bands -
    see docs page 16. Each capacity gets its own exact-match tier
    (min_value == max_value) rather than being approximated by a formula,
    so every figure here is the document's own number.
    """
    tiers = []
    for order, (capacity, annual_premium) in enumerate(sorted(annual_by_capacity.items()), start=tier_order_start):
        tiers.append(
            {
                "cover_type": "tpo",
                "band_unit": "passengers",
                "min_value": capacity,
                "max_value": capacity,
                "flat_amount": annual_premium,
                "min_premium": annual_premium,
                "label": f"{capacity} passengers (annual)",
                "tier_order": order,
            }
        )
    return tiers


_PSV_TPO_ANNUAL_BY_CAPACITY = {
    7: 70025, 8: 72904, 9: 75873, 10: 78755, 11: 79822, 12: 84602, 13: 87483,
    14: 88357, 15: 93332, 16: 96215, 17: 99185, 18: 102062, 19: 104943, 20: 107915,
    21: 110793, 22: 113676, 23: 116642, 24: 119523, 25: 122493, 26: 124329, 27: 127166,
    28: 132944, 29: 133826, 30: 144503, 31: 150283, 32: 155652, 33: 156132, 34: 167623,
    35: 173403, 36: 195335, 37: 199292, 38: 210977, 39: 214902, 40: 216323, 41: 216259,
    42: 219521, 43: 222785, 44: 226115, 45: 229377, 46: 232643, 47: 235907, 48: 239172,
    49: 242436, 50: 245761, 51: 247300,
}

# Each entry: code, label, min_sum_insured, max_vehicle_age_years, notes, tiers[], extensions[]
AMACO_CLASSES = [
    {
        "code": "motor_private",
        "label": "Motor Private (070)",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "notes": "Mandatory valuation before onboarding.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 0, "max_value": 500000,
             "rate_percent": 6.0, "min_premium": 30000, "label": "Up to 500,000", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 500001, "max_value": 999999,
             "rate_percent": 4.0, "min_premium": 30000, "label": "500,001 - 999,999", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": 2500000,
             "rate_percent": 3.5, "min_premium": 30000, "label": "1.0M - 2.5M", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 2500001, "max_value": 4999999,
             "rate_percent": 3.0, "min_premium": 30000, "label": "2,500,001 - 4,999,999", "tier_order": 4},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 5000000, "max_value": None,
             "rate_percent": 2.5, "min_premium": 30000, "label": "5 Million and above", "tier_order": 5},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Third Party Only", "tier_order": 1},
        ],
    },
    {
        "code": "motor_private_fleet_individual",
        "label": "Motor Private Fleet - Individual (3+ units) (070)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.5, "min_premium": 25000,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7000, "min_premium": 7000, "tier_order": 1},
        ],
    },
    {
        "code": "motor_private_fleet_corporate",
        "label": "Motor Private Fleet - Corporate (5+ units) (070)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.25, "min_premium": 25000,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7000, "min_premium": 7000, "tier_order": 1},
        ],
    },
    {
        "code": "motor_commercial_own_goods",
        "label": "Motor Commercial - strictly carriage of own goods (080)",
        "min_sum_insured": 500000,
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 500000, "max_value": 999999,
             "rate_percent": 6.0, "min_premium": 35500, "label": "500,000-999,999", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": 1500000,
             "rate_percent": 5.0, "min_premium": 35500, "label": "1M-1.5M", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1500001, "max_value": 3000000,
             "rate_percent": 4.5, "min_premium": 67500, "label": ">1.5M-3M", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 3000001, "max_value": None,
             "rate_percent": 4.0, "min_premium": 120000, "label": ">3M and above", "tier_order": 4},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 0, "max_value": 3,
             "flat_amount": 5500, "min_premium": 5500, "label": "0-3 tonnes", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 3.01, "max_value": 8,
             "flat_amount": 8000, "min_premium": 8000, "label": "3-8 tonnes", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 8.01, "max_value": 15,
             "flat_amount": 10000, "min_premium": 10000, "label": "9-15 tonnes", "tier_order": 3},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 15.01, "max_value": None,
             "flat_amount": 12000, "min_premium": 12000, "label": "15 tonnes and above", "tier_order": 4},
        ],
    },
    {
        "code": "motor_commercial_own_goods_fleet",
        "label": "Motor Commercial Fleet - own goods (6+ units) (080)",
        "notes": "TPO: apply the motor_commercial_own_goods tonnage schedule.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.0, "min_premium": 35500,
             "label": "Flat rate", "tier_order": 1},
        ],
    },
    {
        "code": "motor_commercial_general_cartage",
        "label": "Motor Commercial general cartage / hire & reward - pickups, lorries, canters, merchant commercial (087)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 0, "max_value": 1000000,
             "rate_percent": 6.5, "min_premium": 40000, "label": "Up to 1M", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000001, "max_value": None,
             "rate_percent": 5.5, "min_premium": 40000, "label": "Above 1M", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "prime_mover", "flat_amount": 7500,
             "min_premium": 7500, "label": "Prime mover", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "trailer", "flat_amount": 10000,
             "min_premium": 10000, "label": "Trailer", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "fleet", "flat_amount": 15000,
             "min_premium": 15000, "label": "Fleet (truck & trailer)", "tier_order": 3},
        ],
    },
    {
        "code": "motor_commercial_prime_mover_tanker",
        "label": "Prime movers / Tankers, excluding fuel tankers (087)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": None,
             "rate_percent": 5.0, "min_premium": 50000, "label": "1M and above", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "prime_mover", "flat_amount": 7500,
             "min_premium": 7500, "label": "Prime mover", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "trailer", "flat_amount": 10000,
             "min_premium": 10000, "label": "Trailer", "tier_order": 2},
        ],
    },
    {
        "code": "merchant_commercial_hybrid",
        "label": "Merchant Commercial Hybrid (182)",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "notes": "Does not apply to vehicles under the Private tax class (e.g. Probox, Wish, Sienta, Succeed, Noah, Voxy, Ractis). "
        "Zero-mileage vehicle warranty up to 5 years. Excess protector reinstatement applicable only once.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "zero_mileage", "rate_percent": 4.0,
             "min_premium": 45000, "label": "Zero mileage units (0-5 years), all-inclusive", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "non_zero_mileage", "rate_percent": 4.5,
             "min_premium": 45000, "label": "Others (6-15 years), all-inclusive", "tier_order": 2},
        ],
    },
    {
        "code": "institution_corporate_bus",
        "label": "Institution/Corporate Buses and passenger vans (180)",
        "notes": "PLL @ Kshs. 500 per person loaded separately (see extensions).",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 35500,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 0, "max_value": 15,
             "flat_amount": 8000, "min_premium": 8000, "label": "0-15 passengers", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 15.01, "max_value": 25,
             "flat_amount": 10000, "min_premium": 10000, "label": "15-25 passengers", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 25.01, "max_value": None,
             "flat_amount": 15000, "min_premium": 15000, "label": "Above 25 passengers", "tier_order": 3},
        ],
    },
    {
        "code": "school_bus",
        "label": "School Buses",
        "notes": "Comprehensive rate inclusive of excess protector and PVT. Free PLL for students, teachers & school staff. "
        "Free theft cover for alternator/starter, limit Kshs. 200,000 on reimbursement, 10% excess (min Kshs. 30,000).",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 30000,
             "label": "Flat rate, inclusive of excess protector & PVT", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 0, "max_value": 14,
             "flat_amount": 7500, "min_premium": 7500, "label": "0-14 passengers", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 14.01, "max_value": 28,
             "flat_amount": 8500, "min_premium": 8500, "label": "15-28 passengers", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 28.01, "max_value": None,
             "flat_amount": 10000, "min_premium": 10000, "label": "29 passengers and above", "tier_order": 3},
        ],
    },
    {
        "code": "ambulance_fire",
        "label": "Motor Commercial - Ambulance & Fire Engines (180)",
        "min_sum_insured": 3000000,
        "notes": "Minimum sum insured for special types (ambulances & fire fighters) is Kshs. 3,000,000.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 35500,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 10000, "min_premium": 10000, "tier_order": 1},
        ],
    },
    {
        "code": "motor_commercial_asset",
        "label": "Motor Commercial - Asset (088)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "zero_mileage", "rate_percent": 4.5,
             "min_premium": 40000, "label": "Zero mileage units (new), incl. excess protector & PVT", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "non_zero_mileage", "rate_percent": 4.0,
             "min_premium": 40000, "label": "Others (non-zero mileage), excess protector & PVT optional", "tier_order": 2},
        ],
    },
    {
        "code": "motorcycle_own_use",
        "label": "Motor Cycles - own use only, strictly corporate owned & registered (071)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 7500,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 5000, "min_premium": 5000, "tier_order": 1},
        ],
    },
    {
        "code": "tractor_special_type",
        "label": "Tractors and special types (graders, caterpillars, bulldozers) (081)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "special_type", "rate_percent": 3.5,
             "min_premium": 35500, "label": "Special types (caterpillars, graders, bulldozers etc.)", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "subtype", "subtype_key": "tractor", "rate_percent": 2.5,
             "min_premium": 25000, "label": "Tractors, inclusive of excess protector", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "special_type", "flat_amount": 5500,
             "min_premium": 5500, "label": "Special types", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "tractor", "flat_amount": 5000,
             "min_premium": 5000, "label": "Tractor", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "trailer", "flat_amount": 5000,
             "min_premium": 5000, "label": "Trailer", "tier_order": 3},
        ],
    },
    {
        "code": "driving_school",
        "label": "Motor Commercial Driving Schools",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 35500,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "saloon", "flat_amount": 7500,
             "min_premium": 7500, "label": "Saloons", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "upto_7_tons", "flat_amount": 10000,
             "min_premium": 10000, "label": "Up to 7 tons", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "subtype", "subtype_key": "above_7_tons", "flat_amount": 15000,
             "min_premium": 15000, "label": "Above 7 tons", "tier_order": 3},
        ],
    },
    {
        "code": "motor_trade",
        "label": "Motor Commercial - Motor Trade (Road Risk)",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 35500,
             "label": "Flat rate", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500, "tier_order": 1},
        ],
    },
    {
        "code": "psv_taxi",
        "label": "PSV Taxi - Yellow line / Chauffeur driven / Online",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 6.0, "min_premium": 37500,
             "label": "6% of value, min premium 37,500 (plus PLL, excess protector - see extensions)", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 0, "max_value": 7,
             "flat_amount": 7500, "min_premium": 7500, "label": "Up to 7 passengers (plus PLL per person)", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 7.01, "max_value": 18,
             "flat_amount": 8500, "min_premium": 8500, "label": "8-18 passengers (plus PLL per person)", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 18.01, "max_value": 24,
             "flat_amount": 12500, "min_premium": 12500, "label": "19-24 passengers (plus PLL per person)", "tier_order": 3},
        ],
        "extensions": [
            {"code": "excess_protector", "label": "Excess Protector", "basis": "percent_of_sum_insured",
             "rate_percent": 1.5, "min_amount": 15000},
        ],
    },
    {
        "code": "psv_tour_vehicle",
        "label": "Tour Vehicles - Vans",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.5, "min_premium": 50000,
             "label": "4.5% of value, min premium 50,000, inclusive of excess protector (plus PLL - see extensions)",
             "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 25, "max_value": 41,
             "flat_amount": 15000, "min_premium": 15000, "label": "25-41 passengers (plus PLL per person)", "tier_order": 1},
        ],
    },
    {
        "code": "psv_matatu_bus",
        "label": "PSV Matatu / Bus",
        "notes": "AMACO's PSV Third Party Only schedule (rating guide p.16) prices by exact seating capacity, "
        "7 through 51 seats, add Kshs. 40 stamp duty on all new policies.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.0, "min_premium": 40000,
             "label": "4% of value, min premium 40,000, plus third-party premium per schedule", "tier_order": 1},
            *_psv_capacity_tpo_tiers(_PSV_TPO_ANNUAL_BY_CAPACITY, tier_order_start=1),
        ],
    },
    {
        "code": "psv_tuktuk",
        "label": "PSV Tuktuk",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.0, "min_premium": 20000,
             "label": "4% min 20,000, for a maximum of 6 passengers (plus PLL - see extensions)", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 3000, "min_premium": 3000,
             "label": "Flat gross premium (plus PLL per passenger)", "tier_order": 1},
        ],
    },
]

AMACO_PROVIDER_EXTENSIONS = [
    # vehicle_class_id left as None by the seed loader -> applies to any AMACO
    # class unless that class defines its own row for the same code.
    {"code": "pvt", "label": "Political Violence & Terrorism (PVT) - Private", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 2500, "notes": "Motor Private rate. Motor Commercial: 0.45% (min 2,500); Fleet: 0.3% (min 2,500)."},
    {"code": "excess_protector", "label": "Excess Protector - Private", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 5000, "notes": "Motor Private rate. Motor Commercial: 0.5% (min 5,000)."},
    {"code": "courtesy_car", "label": "Loss of Use (Courtesy Car)", "basis": "flat", "flat_amount": 5000,
     "min_amount": 5000, "notes": "Benefit paid at Kshs. 3,000/day for 15 days, excluding first 3 days, private "
     "vehicles above sum insured Kshs. 1,000,000, max limit Kshs. 45,000."},
    {"code": "pll", "label": "Passenger Legal Liability", "basis": "per_person", "flat_amount": 500,
     "min_amount": 0, "notes": "Kshs. 500 per person; Kshs. 250 per person for school buses used exclusively for students."},
    {"code": "comesa_yellow_card_commercial", "label": "COMESA Yellow Card Cover - Commercial", "basis": "flat",
     "flat_amount": 20000, "min_amount": 20000},
    {"code": "comesa_yellow_card_private", "label": "COMESA Yellow Card Cover - Private", "basis": "flat",
     "flat_amount": 12500, "min_amount": 12500},
]

# --- Pioneer Insurance Kenya --------------------------------------------
# See PIONEER_SOURCE above: the source PDF's table columns didn't extract
# cleanly, so every class below is marked needs_review. Only classes with
# a clearly legible numeric rate were included - where a category was
# mentioned but no usable number could be read (e.g. plain motorcycle,
# tuktuk comprehensive rates), it was left out rather than guessed.
PIONEER_CLASSES = [
    {
        "code": "motor_private",
        "label": "Motor Private & Double Cabins",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 500000, "max_value": 999999,
             "rate_percent": 6.0, "min_premium": 37500, "label": "500,000-999,999 (Basic)", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": 1499999,
             "rate_percent": 5.0, "min_premium": 37500, "label": "1,000,000-1,499,999, incl. EP & PVT", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1500000, "max_value": 2499999,
             "rate_percent": 4.0, "min_premium": 37500, "label": "1,500,000-2,499,999, incl. EP & PVT", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 2500000, "max_value": None,
             "rate_percent": 3.25, "min_premium": 37500, "label": "2,500,000 and above, incl. EP & PVT "
             "(source document did not give a distinct rate for this band; top listed rate reused)", "tier_order": 4},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Single unit", "tier_order": 1},
        ],
    },
    {
        "code": "motor_private_fleet_individual",
        "label": "Motor Private Fleet",
        "notes": "Source document gives a fleet minimum premium but no distinct fleet %; the Motor Private "
        "comprehensive bands are reused here.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 500000, "max_value": 999999,
             "rate_percent": 6.0, "min_premium": 30000, "label": "500,000-999,999", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": 1499999,
             "rate_percent": 5.0, "min_premium": 30000, "label": "1,000,000-1,499,999", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1500000, "max_value": 2499999,
             "rate_percent": 4.0, "min_premium": 30000, "label": "1,500,000-2,499,999", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 2500000, "max_value": None,
             "rate_percent": 3.25, "min_premium": 30000, "label": "2,500,000 and above", "tier_order": 4},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 6500, "min_premium": 6500,
             "label": "Fleet", "tier_order": 1},
        ],
    },
    {
        "code": "psv_taxi",
        "label": "Uber / Online Platform Taxis",
        "notes": "Comprehensive only - source document states no TPO cover is offered for this class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 6.0, "min_premium": 40000,
             "label": "6% min. 40,000", "tier_order": 1},
        ],
    },
    {
        "code": "psv_tour_vehicle",
        "label": "Chauffeur Driven Tour Vans (TSV)",
        "notes": "Comprehensive only - source document states no TPO cover is offered for this class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 40000,
             "label": "5% inclusive of EP & PVT, min. 40,000", "tier_order": 1},
        ],
    },
    {
        "code": "school_bus",
        "label": "School Buses / Vans",
        "notes": "Rate and minimum premium reconstructed from a garbled part of the source table; verify before use. "
        "Free PLL for students only.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 50000,
             "label": "3% inclusive of EP & PVT", "tier_order": 1},
        ],
    },
]

PIONEER_PROVIDER_EXTENSIONS = [
    {"code": "excess_protector", "label": "Excess Protector", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 5000},
    {"code": "pvt", "label": "Political Violence & Terrorism (PVT)", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 2500},
    {"code": "courtesy_car", "label": "Courtesy Car",
     "basis": "flat", "flat_amount": 4500, "min_amount": 4500,
     "notes": "Kshs. 4,500 for a 10-day limit (30,000 benefit) on sums insured 2.5M-4.99M; "
     "Kshs. 7,500 for a 20-day limit (60,000 benefit) on sums insured 5M and above."},
    {"code": "pll", "label": "Passenger Legal Liability", "basis": "per_person", "flat_amount": 500,
     "notes": "Kshs. 500 per head for hire to non-affiliated groups; Kshs. 250 per seat for affiliated groups."},
]
