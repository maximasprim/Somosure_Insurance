"""Static rate-card data for the brokers whose published rate cards have
been supplied so far: AMACO (Africa Merchant Assurance Co Ltd), Pioneer
Insurance Kenya, and CIC General Insurance Ltd. Consumed by app/db/seed.py.

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
    "Pioneer Insurance Kenya rate sheet (RATES_2025.pdf), re-transcribed from a cleaner text extraction "
    "than the original pass - most figures below are now a direct read of the source table and marked "
    "verified. Genuinely ambiguous parts of the source (see individual class notes, e.g. Own Goods TPO "
    "tonnage bands, fleet-specific commercial numbers) are still marked needs_review - verify those "
    "specific figures against the original document before quoting a live customer against them."
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
    {
        "key": "cic",
        "name": "CIC General Insurance Ltd",
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
# See PIONEER_SOURCE above. Re-transcribed from a cleaner extraction of
# the same RATES_2025.pdf than the first pass - most classes are now a
# direct read of the source and marked verified; genuinely ambiguous
# figures (mostly where the PDF's own layout doesn't make the tonnage/
# fleet breakdown explicit) keep data_confidence="needs_review" and say
# exactly what's uncertain in their notes.
PIONEER_CLASSES = [
    {
        "code": "motor_private",
        "label": "Motor Private & Double Cabins",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "data_confidence": "verified",
        "notes": "Comprehensive minimum premium Kshs. 37,500 (single unit) / Kshs. 30,000 (fleet). Fleet TPO is "
        "Kshs. 6,500 flat (single unit 7,500) - see motor_private_fleet_individual for the fleet class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 500000, "max_value": 999999,
             "rate_percent": 6.0, "min_premium": 37500, "label": "500,000-999,999 (Basic)", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000000, "max_value": 1499999,
             "rate_percent": 5.0, "min_premium": 37500, "label": "1,000,000-1,499,999, incl. EP & PVT", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1500000, "max_value": 2499999,
             "rate_percent": 4.0, "min_premium": 37500, "label": "1,500,000-2,499,999, incl. EP & PVT", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 2500000, "max_value": None,
             "rate_percent": 3.25, "min_premium": 37500, "label": "2,500,000 and above, incl. EP & PVT "
             "(source document does not give a distinct rate for this band; top listed rate reused)", "tier_order": 4},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Single unit", "tier_order": 1},
        ],
    },
    {
        "code": "motor_private_fleet_individual",
        "label": "Motor Private Fleet",
        "data_confidence": "verified",
        "notes": "Source document gives a fleet minimum premium and fleet TPO rate but no distinct fleet "
        "comprehensive %; the Motor Private comprehensive bands are reused here.",
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
        "code": "motor_commercial_hybrid",
        "label": "Motor Commercial Hybrid Cover (Own Goods & General Cartage)",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "data_confidence": "needs_review",
        "notes": "Comprehensive: 3% min Kshs. 37,500 for General Cartage, 2.5% min Kshs. 37,500 for Own Goods "
        "(the source lists both rates together without a fully explicit per-category label - Own Goods is "
        "priced here as the cheaper of the two since that matches every other broker's own-goods-vs-cartage "
        "ordering; verify against the original document). Fleet and zero-mileage vehicles share the same "
        "Kshs. 7,500 flat TPO rate as a single unit. Farm & Warehouses TPO Kshs. 7,500, Construction TPO "
        "Kshs. 10,000 - see farm_warehouses and construction classes. Fleet (3+): Own Damage Excess Protector "
        "inclusive up to 3 tonnes; PVT free up to Kshs. 5M for 4-15 tonnes, else 0.25% min Kshs. 2,500 - not "
        "applied automatically, no fleet-specific premium figures were given.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 2.5, "min_premium": 37500,
             "label": "Own Goods (best-effort read of the source table - verify)", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Single, fleet & zero-mileage vehicles", "tier_order": 1},
        ],
    },
    {
        "code": "farm_warehouses",
        "label": "Special Type - Farm & Warehouses",
        "data_confidence": "verified",
        "notes": "Own Damage Excess Protector 0.5% of sum insured, min Kshs. 5,000 - not a separate comprehensive "
        "% rate is given in the source; only the TPO figure below is priced.",
        "tiers": [
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500, "tier_order": 1},
        ],
    },
    {
        "code": "construction",
        "label": "Special Type - Construction",
        "data_confidence": "verified",
        "notes": "PVT free up to Kshs. 5M, above 5M: 0.25% min Kshs. 2,500 - not a separate comprehensive % rate "
        "is given in the source; only the TPO figure below is priced.",
        "tiers": [
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 10000, "min_premium": 10000, "tier_order": 1},
        ],
    },
    {
        "code": "motorcycle_corporate_delivery",
        "label": "Motor Cycle (Corporate & Delivery)",
        "data_confidence": "verified",
        "notes": "No excess protector or PLL offered for this class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 5000,
             "label": "3%, min Kshs. 5,000", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 3000, "min_premium": 3000, "tier_order": 1},
        ],
    },
    {
        "code": "tuktuk_corporate_delivery",
        "label": "Tuk Tuk (Corporate & Delivery)",
        "data_confidence": "verified",
        "notes": "No excess protector or PLL offered for this class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 10000,
             "label": "3%, min Kshs. 10,000", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 5000, "min_premium": 5000, "tier_order": 1},
        ],
    },
    {
        "code": "psv_taxi",
        "label": "Uber / Online Platform Taxis",
        "data_confidence": "verified",
        "notes": "Comprehensive only - source document states no TPO cover is offered for this class and no "
        "excess protector is available. PLL Kshs. 500 per head; PVT free up to Kshs. 5,000,000 sum insured, "
        "above that 0.25% min Kshs. 2,500 - see PIONEER_PROVIDER_EXTENSIONS for the standard PLL/PVT rows "
        "(this class's PVT free-up-to-5M threshold is not applied automatically).",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 6.0, "min_premium": 40000,
             "label": "6% min. 40,000", "tier_order": 1},
        ],
    },
    {
        "code": "psv_tour_vehicle",
        "label": "Chauffeur Driven Tour Vans (TSV)",
        "data_confidence": "verified",
        "notes": "Comprehensive only - source document states no TPO cover is offered for this class.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 40000,
             "label": "5% inclusive of EP & PVT, min. 40,000", "tier_order": 1},
        ],
    },
    {
        "code": "school_bus",
        "label": "School Buses / Vans",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "data_confidence": "verified",
        "notes": "Comprehensive inclusive of Own Damage Excess Protector (0.5% min Kshs. 5,000) and PVT (free up "
        "to Kshs. 5M, above that 0.25% min Kshs. 2,500) - not broken out separately. Free PLL for students only; "
        "PLL for hire to non-affiliated groups is Kshs. 500 per head, added on top of the TPO figures below.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 3.0, "min_premium": 50000,
             "label": "3% inclusive of EP & PVT", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 0, "max_value": 14,
             "flat_amount": 7500, "min_premium": 7500, "label": "Up to 14 passengers (plus Kshs. 250/person PLL)",
             "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 14.01, "max_value": 25,
             "flat_amount": 12500, "min_premium": 12500, "label": "15-25 passengers (plus Kshs. 250/person PLL)",
             "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "passengers", "min_value": 25.01, "max_value": None,
             "flat_amount": 18000, "min_premium": 18000, "label": "Over 25 passengers (plus Kshs. 250/person PLL)",
             "tier_order": 3},
        ],
    },
    {
        "code": "asset_zero_mileage",
        "label": "Asset (zero-mileage, max 3 years)",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 3,
        "comprehensive_ineligible_action": "decline",
        "data_confidence": "verified",
        "notes": "No Third Party Only cover offered for this class. Max age at entry 3 years - tighter than the "
        "standard 15-year limit - so a vehicle outside this age band is declined rather than downgraded to TPO, "
        "since TPO isn't offered here at all.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.5, "min_premium": 40000,
             "label": "4.5% inclusive of EP & PVT, min. 40,000", "tier_order": 1},
        ],
    },
]

PIONEER_PROVIDER_EXTENSIONS = [
    {"code": "excess_protector", "label": "Excess Protector", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 5000, "notes": "Motor Private rate. Several special-type and "
     "commercial classes use 0.5% min Kshs. 5,000 instead - see that class's notes."},
    {"code": "pvt", "label": "Political Violence & Terrorism (PVT)", "basis": "percent_of_sum_insured",
     "rate_percent": 0.25, "min_amount": 2500, "notes": "Charged above the free-up-to-Kshs.-5,000,000 "
     "threshold that applies on several classes (Uber, Construction, School Bus) - the threshold itself "
     "isn't applied automatically."},
    {"code": "courtesy_car", "label": "Courtesy Car",
     "basis": "flat", "flat_amount": 4500, "min_amount": 4500,
     "notes": "Kshs. 4,500 for a 10-day limit (30,000 benefit) on sums insured 2,500,000-4,999,999; "
     "Kshs. 7,500 for a 20-day limit (60,000 benefit) on sums insured 5,000,000 and above."},
    {"code": "pll", "label": "Passenger Legal Liability", "basis": "per_person", "flat_amount": 500,
     "notes": "Kshs. 500 per head for hire to non-affiliated groups; Kshs. 250 per seat for affiliated groups "
     "and for school bus students."},
]

# --- CIC General Insurance Ltd ------------------------------------------
# Two source documents, both effective 1 July 2026: CIC's own printed
# Motor Private and Motor Commercial rate cards. Both are clean, official
# CIC documents (unlike Pioneer's below) - every number here is
# transcribed directly and marked "verified" unless a note says
# otherwise.
#
# Two things in these documents the engine cannot enforce yet, so they're
# recorded in `notes` instead of being applied automatically:
#   1. Fleet performance-based loading by 3-year loss ratio (both private
#      corporate and commercial fleet business) - the engine has no loss
#      ratio input, so the loading schedule is documented, not applied.
#   2. CIC's own Single vs Fleet split for comprehensive commercial rates
#      and for TPO on Motor Private - represented as a "subtype" tier
#      where doing so doesn't collide with a tonnage band already needed
#      for that same class/cover_type (a class's tiers for one cover_type
#      must share one band_unit - see _select_tier), and documented in
#      notes everywhere it doesn't fit as a tier.
CIC_SOURCE_PRIVATE = "CIC Motor Private Rates, effective 1 July 2026 (New_Motor_Private_Terms_01_07_2026.pdf)"
CIC_SOURCE_COMMERCIAL = "CIC Motor Commercial Rates, effective 1 July 2026 (New_Motor_Commercial_Terms_01_07_2026.pdf)"

CIC_CLASSES = [
    {
        "code": "motor_private",
        "label": "Motor Private - Individual",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Comprehensive minimum premium Kshs. 37,500 (Note 5). Agreed Value Basis applies to vehicles "
        "under 8 years old, subject to valuation at inception and each renewal on CIC's valuer panel (Note 3). "
        "Fleet (3+ vehicles, one owner) pays a lower Third Party rate (Kshs. 6,500 flat vs 7,500 single-unit) - "
        "the comprehensive percentage bands are the same for single-unit and fleet.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 0, "max_value": 1000000,
             "rate_percent": 6.0, "min_premium": 37500, "label": "Up to 1,000,000", "tier_order": 1},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1000001, "max_value": 1500000,
             "rate_percent": 5.0, "min_premium": 37500, "label": ">1,000,000 - 1,500,000", "tier_order": 2},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 1500001, "max_value": 2500000,
             "rate_percent": 4.0, "min_premium": 37500, "label": ">1,500,000 - 2,500,000", "tier_order": 3},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 2500001, "max_value": 5000000,
             "rate_percent": 3.5, "min_premium": 37500, "label": ">2,500,000 - 5,000,000", "tier_order": 4},
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "min_value": 5000001, "max_value": None,
             "rate_percent": 3.0, "min_premium": 37500, "label": "Above 5,000,000", "tier_order": 5},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Single unit (fleet of 3+ pays Kshs. 6,500 flat - see notes)", "tier_order": 1},
        ],
        "excesses": [
            {"peril": "third_party_property_damage", "basis": "flat", "flat_amount": 7500,
             "label": "Third Party Property Damage - Kshs. 7,500"},
            {"peril": "young_driver_under_21", "basis": "flat", "flat_amount": 5000,
             "label": "Young driver (under 21) - Kshs. 5,000 over and above normal excess"},
            {"peril": "novice_driver", "basis": "flat", "flat_amount": 5000,
             "label": "Novice driver (under 1 year's experience) - Kshs. 5,000 over and above normal excess"},
            {"peril": "own_damage", "basis": "percent_of_sum_insured", "rate_percent": 2.5, "min_amount": 20000,
             "label": "Own Damage & Partial Theft - 2.5% of sum insured, min Kshs. 20,000, max Kshs. 100,000"},
            {"peril": "theft_with_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 10.0, "min_amount": 20000,
             "label": "Theft, with anti-theft device - 10% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_without_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 20.0, "min_amount": 20000,
             "label": "Theft, without anti-theft device - 20% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_with_tracking", "basis": "percent_of_sum_insured", "rate_percent": 2.5, "min_amount": 20000,
             "label": "Theft, with tracking device - 2.5% of sum insured, min Kshs. 20,000"},
        ],
        "free_benefits": [
            {"code": "towing_recovery", "label": "Towing and recovery", "limit_amount": 30000,
             "limit_label": "Up to Kshs. 30,000", "top_up_note": "Kshs. 1,000 for every additional Kshs. 10,000 cover",
             "cover_type": "comprehensive"},
            {"code": "passenger_legal_liability", "label": "Third party passenger legal liability",
             "limit_amount": 3000000, "limit_label": "Kshs. 3,000,000 per person and Kshs. 20,000,000 per event",
             "top_up_note": "Kshs. 1,000 for every additional Kshs. 1,000,000 cover", "cover_type": "comprehensive"},
        ],
        "extensions": [
            {"code": "courtesy_car", "label": "Loss of use (courtesy car)", "basis": "flat", "flat_amount": 3000,
             "min_amount": None, "limit_amount": 30000,
             "limit_label": "Max Kshs. 30,000, applicable 3 days after full claim documentation"},
            {"code": "forced_atm_withdrawal", "label": "Forced ATM withdrawal following a carjacking", "basis": "flat",
             "flat_amount": 4000, "limit_amount": 40000, "limit_label": "Max Kshs. 40,000"},
            {"code": "out_of_station_accommodation", "label": "Out-of-station accommodation after an admissible claim",
             "basis": "flat", "flat_amount": 2000, "limit_amount": 20000,
             "limit_label": "Max Kshs. 20,000, within 50 KM of workstation/home"},
            {"code": "personal_effects", "label": "Personal effects after an admissible claim", "basis": "flat",
             "flat_amount": 2000, "limit_amount": 20000, "limit_label": "Max Kshs. 20,000"},
            {"code": "loss_of_keys", "label": "Loss of keys after an admissible claim", "basis": "flat",
             "flat_amount": 2000, "limit_amount": 20000, "limit_label": "Max Kshs. 20,000"},
            {"code": "spare_wheel", "label": "Theft / loss of spare wheel", "basis": "flat", "flat_amount": 3000,
             "limit_amount": 30000, "limit_label": "Max Kshs. 30,000"},
            {"code": "accessories_theft", "label": "Theft of accessories (jack, spanners)", "basis": "flat",
             "flat_amount": 1500, "limit_amount": 15000, "limit_label": "Max Kshs. 15,000"},
            {"code": "excess_protector_own_damage", "label": "Excess protector - Own Damage only",
             "basis": "percent_of_sum_insured", "rate_percent": 0.25, "min_amount": 5000,
             "limit_label": "Waives the Own Damage excess"},
            {"code": "excess_protector_theft_and_own_damage", "label": "Excess protector - Theft & Own Damage",
             "basis": "percent_of_sum_insured", "rate_percent": 1.0, "min_amount": 10000,
             "limit_label": "Waives the Theft and Own Damage excess"},
        ],
    },
    {
        "code": "motor_private_corporate",
        "label": "Motor Private - Corporate",
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Vehicles owned by registered organisations. Comprehensive and Third Party rates are the same "
        "for fleet and non-fleet corporate business. Performance-based loading by 3-year loss ratio (not applied "
        "by this system - apply manually): up to 50% loss ratio = 4% (charge basic rate), 51-60% = 4.5%, "
        "61-70% = 5.0%, 71-80% = 6.0%, 81-90% = 6.5%, above 91% = 7.0%.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.0, "min_premium": 37500,
             "label": "Flat rate (Fleet & Non-Fleet), before performance-based loading", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 6500, "min_premium": 6500,
             "label": "Flat rate (Fleet & Non-Fleet)", "tier_order": 1},
        ],
        "excesses": [
            {"peril": "third_party_property_damage", "basis": "flat", "flat_amount": 7500,
             "label": "Third Party Property Damage - Kshs. 7,500"},
            {"peril": "young_driver_under_21", "basis": "flat", "flat_amount": 5000,
             "label": "Young driver (under 21) - Kshs. 5,000 over and above normal excess"},
            {"peril": "novice_driver", "basis": "flat", "flat_amount": 5000,
             "label": "Novice driver (under 1 year's experience) - Kshs. 5,000 over and above normal excess"},
            {"peril": "own_damage", "basis": "percent_of_sum_insured", "rate_percent": 2.5, "min_amount": 20000,
             "label": "Own Damage & Partial Theft - 2.5% of sum insured, min Kshs. 20,000, max Kshs. 100,000"},
            {"peril": "theft_with_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 10.0, "min_amount": 20000,
             "label": "Theft, with anti-theft device - 10% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_without_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 20.0, "min_amount": 20000,
             "label": "Theft, without anti-theft device - 20% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_with_tracking", "basis": "percent_of_sum_insured", "rate_percent": 2.5, "min_amount": 20000,
             "label": "Theft, with tracking device - 2.5% of sum insured, min Kshs. 20,000"},
        ],
        "free_benefits": [
            {"code": "towing_recovery", "label": "Towing and recovery", "limit_amount": 30000,
             "limit_label": "Up to Kshs. 30,000", "top_up_note": "Kshs. 1,000 for every additional Kshs. 10,000 cover",
             "cover_type": "comprehensive"},
            {"code": "passenger_legal_liability", "label": "Third party passenger legal liability",
             "limit_amount": 3000000, "limit_label": "Kshs. 3,000,000 per person and Kshs. 20,000,000 per event",
             "top_up_note": "Kshs. 1,000 for every additional Kshs. 1,000,000 cover", "cover_type": "comprehensive"},
        ],
        "extensions": [
            {"code": "courtesy_car", "label": "Loss of use (courtesy car)", "basis": "flat", "flat_amount": 3000,
             "limit_amount": 30000, "limit_label": "Max Kshs. 30,000, applicable 3 days after full claim documentation"},
            {"code": "political_violence", "label": "Political violence and terrorism", "basis": "percent_of_sum_insured",
             "rate_percent": 0.25, "min_amount": 2500},
            {"code": "excess_protector_own_damage", "label": "Excess protector - Own Damage only",
             "basis": "percent_of_sum_insured", "rate_percent": 0.25, "min_amount": 5000},
            {"code": "excess_protector_theft_and_own_damage", "label": "Excess protector - Theft & Own Damage",
             "basis": "percent_of_sum_insured", "rate_percent": 1.0, "min_amount": 10000},
        ],
    },
    {
        "code": "motor_commercial_own_goods",
        "label": "Motor Commercial - Own Goods",
        "source_document": CIC_SOURCE_COMMERCIAL,
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Comprehensive minimum premium Kshs. 50,000. Fleet comprehensive rate is 4.75% (performance-"
        "based; loss-ratio loading schedule below), single-unit is 5% - the lower fleet % is not applied by this "
        "system. Fleet Third Party rates: up to 3 tonnes Kshs. 7,000, 3-8 tonnes Kshs. 11,000, over 8 tonnes "
        "Kshs. 16,000 (single-unit figures are used as the priced tiers below). Performance-based loading by "
        "3-year loss ratio: up to 50% = charge basic rate, 51-60% = +5.0%, 61-70% = +7.5%, 71-80% = +10.0%, "
        "81-90% = +12.5%, above 91% = +15%. Non-fleet = 2 vehicles or fewer; fleet = 3+ (individual) or 10+ "
        "(registered organisation).",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 5.0, "min_premium": 50000,
             "label": "Single unit, before performance-based loading", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 0, "max_value": 3,
             "flat_amount": 7500, "min_premium": 7500, "label": "Up to 3 tonnes", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 3.01, "max_value": 8,
             "flat_amount": 12000, "min_premium": 12000, "label": "3 - 8 tonnes", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 8.01, "max_value": None,
             "flat_amount": 18000, "min_premium": 18000, "label": "Over 8 tonnes", "tier_order": 3},
        ],
        "excesses": [
            {"peril": "third_party_property_damage", "basis": "flat", "flat_amount": 10000,
             "label": "Third Party Property Damage - Kshs. 10,000"},
            {"peril": "young_driver_under_21", "basis": "flat", "flat_amount": 7500,
             "label": "Young driver (under 21) - Kshs. 7,500 over and above normal excess"},
            {"peril": "novice_driver", "basis": "flat", "flat_amount": 7500,
             "label": "Novice driver (under 2 years' experience) - Kshs. 7,500 over and above normal excess"},
            {"peril": "own_damage", "basis": "percent_of_sum_insured", "rate_percent": 5.0, "min_amount": 20000,
             "label": "Own Damage - 5% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_with_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 10.0, "min_amount": 20000,
             "label": "Theft, with anti-theft device - 10% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_without_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 20.0, "min_amount": 20000,
             "label": "Theft, without anti-theft device - 20% of sum insured, min Kshs. 20,000"},
            {"peril": "theft_with_tracking", "basis": "percent_of_sum_insured", "rate_percent": 5.0, "min_amount": 20000,
             "label": "Theft, with tracking device - 5% of sum insured, min Kshs. 20,000"},
        ],
    },
    {
        "code": "motor_commercial_general_cartage",
        "label": "Motor Commercial - General Cartage / Institutional Cartage",
        "source_document": CIC_SOURCE_COMMERCIAL,
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Comprehensive minimum premium Kshs. 100,000. Fleet comprehensive rate is 6.75% (performance-"
        "based), single-unit is 7% - the lower fleet % is not applied by this system. Fleet Third Party rates: "
        "up to 3 tonnes Kshs. 12,000, 3-8 tonnes Kshs. 15,000, 8-20 tonnes Kshs. 17,000, 20-30 tonnes "
        "Kshs. 20,000, over 30 tonnes Kshs. 22,500 (single-unit figures are used as the priced tiers below). "
        "Over 30 tonnes: Kshs. 25,000 plus Kshs. 500 for every additional tonne (base figure priced below; the "
        "per-tonne addition is not applied automatically). Performance-based loading by 3-year loss ratio: up to "
        "50% = charge basic rate, 51-60% = +5.0%, 61-70% = +7.5%, 71-80% = +10.0%, 81-90% = +12.5%, above 91% = "
        "+15%. Institutional vehicles: comprehensive 4% (performance-based), Third Party Only flat Kshs. 7,500 - "
        "not separately priced here; use this class's comprehensive tier and see notes for TPO.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 7.0, "min_premium": 100000,
             "label": "Single unit, before performance-based loading", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 0, "max_value": 3,
             "flat_amount": 15000, "min_premium": 15000, "label": "Up to 3 tonnes", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 3.01, "max_value": 8,
             "flat_amount": 17000, "min_premium": 17000, "label": "Over 3 - 8 tonnes", "tier_order": 2},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 8.01, "max_value": 20,
             "flat_amount": 20000, "min_premium": 20000, "label": "8 - 20 tonnes", "tier_order": 3},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 20.01, "max_value": 30,
             "flat_amount": 25000, "min_premium": 25000, "label": "20 - 30 tonnes", "tier_order": 4},
            {"cover_type": "tpo", "band_unit": "tonnes", "min_value": 30.01, "max_value": None,
             "flat_amount": 25000, "min_premium": 25000,
             "label": "Over 30 tonnes (base; plus Kshs. 500/extra tonne - see notes)", "tier_order": 5},
        ],
        "excesses": [
            {"peril": "third_party_property_damage", "basis": "flat", "flat_amount": 20000,
             "label": "Third Party Property Damage, up to 20 tonnes - Kshs. 20,000"},
            {"peril": "third_party_property_damage", "basis": "flat", "flat_amount": 30000,
             "label": "Third Party Property Damage, over 20 tonnes - Kshs. 30,000"},
            {"peril": "young_driver_under_21", "basis": "flat", "flat_amount": 10000,
             "label": "Young driver (under 21) - Kshs. 10,000 over and above normal excess"},
            {"peril": "novice_driver", "basis": "flat", "flat_amount": 10000,
             "label": "Novice driver (under 2 years' experience) - Kshs. 10,000 over and above normal excess"},
            {"peril": "own_damage", "basis": "percent_of_sum_insured", "rate_percent": 5.0, "min_amount": 30000,
             "label": "Own Damage - 5% of sum insured, min Kshs. 30,000"},
            {"peril": "theft_with_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 10.0, "min_amount": 30000,
             "label": "Theft, with anti-theft device - 10% of sum insured, min Kshs. 30,000"},
            {"peril": "theft_without_antitheft", "basis": "percent_of_sum_insured", "rate_percent": 20.0, "min_amount": 30000,
             "label": "Theft, without anti-theft device - 20% of sum insured, min Kshs. 30,000"},
            {"peril": "theft_with_tracking", "basis": "percent_of_sum_insured", "rate_percent": 5.0, "min_amount": 30000,
             "label": "Theft, with tracking device - 5% of sum insured, min Kshs. 30,000"},
        ],
    },
    {
        "code": "motor_commercial_prime_mover",
        "label": "Motor Commercial - Prime Mover",
        "source_document": CIC_SOURCE_COMMERCIAL,
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Uses the General Cartage comprehensive rate (7% single / 6.75% fleet, min premium Kshs. "
        "100,000) - CIC's rate card gives Prime Mover its own Third Party figure only. Fleet Third Party rate "
        "Kshs. 18,000 (single-unit figure priced below).",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 7.0, "min_premium": 100000,
             "label": "Single unit, before performance-based loading (General Cartage rate)", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 20000, "min_premium": 20000,
             "label": "Prime mover", "tier_order": 1},
        ],
    },
    {
        "code": "motor_commercial_institutional",
        "label": "Motor Commercial - Institutional Vehicles",
        "source_document": CIC_SOURCE_COMMERCIAL,
        "min_sum_insured": 500000,
        "max_vehicle_age_years": 15,
        "comprehensive_ineligible_action": "downgrade_to_tpo",
        "notes": "Performance-based loading by 3-year loss ratio applies (see motor_commercial_general_cartage "
        "notes) - not applied automatically.",
        "tiers": [
            {"cover_type": "comprehensive", "band_unit": "sum_insured", "rate_percent": 4.0, "min_premium": 50000,
             "label": "Flat rate, before performance-based loading", "tier_order": 1},
            {"cover_type": "tpo", "band_unit": "none", "flat_amount": 7500, "min_premium": 7500,
             "label": "Flat rate", "tier_order": 1},
        ],
    },
]

# Shared across every CIC motor commercial class above (windscreen through
# authorized repair limit are identical figures in both CIC source
# documents; only towing differs, so towing is set per-class instead).
CIC_PROVIDER_FREE_BENEFITS = [
    {"code": "windscreen", "label": "Windscreen", "limit_amount": 30000, "limit_label": "Up to Kshs. 30,000",
     "top_up_note": "Kshs. 1,000 for every additional Kshs. 10,000 cover", "cover_type": "comprehensive"},
    {"code": "entertainment_system", "label": "Vehicle entertainment system", "limit_amount": 30000,
     "limit_label": "Up to Kshs. 30,000", "top_up_note": "Kshs. 1,000 for every additional Kshs. 10,000 cover",
     "cover_type": "comprehensive"},
    {"code": "third_party_property_damage", "label": "Third party property damage", "limit_amount": 5000000,
     "limit_label": "Up to Kshs. 5,000,000", "top_up_note": "Kshs. 1,000 for every additional Kshs. 1,000,000 cover",
     "cover_type": "comprehensive"},
    {"code": "third_party_bodily_injury", "label": "Third party bodily injury / death", "limit_amount": 3000000,
     "limit_label": "Kshs. 3,000,000 per person, unlimited per event",
     "top_up_note": "Kshs. 1,000 for every additional Kshs. 1,000,000 cover", "cover_type": "comprehensive"},
    {"code": "emergency_medical", "label": "Emergency medical expenses (vehicle occupants)", "limit_amount": 30000,
     "limit_label": "Up to Kshs. 30,000, on reimbursement basis",
     "top_up_note": "Kshs. 250 for every additional Kshs. 10,000 cover", "cover_type": "comprehensive"},
    {"code": "riot_strike", "label": "Riot and strike", "limit_label": "Applicable", "cover_type": "comprehensive"},
    {"code": "authorized_repair_limit", "label": "Authorized repair limit", "limit_amount": 50000,
     "limit_label": "Up to Kshs. 50,000", "cover_type": "comprehensive"},
]

# Commercial-only extras (private has its own class-scoped list above -
# political violence and excess protector rates differ between the two).
_CIC_COMMERCIAL_EXTENSIONS = [
    {"code": "political_violence", "label": "Political violence and terrorism", "basis": "percent_of_sum_insured",
     "rate_percent": 0.45, "min_amount": 2500,
     "notes": "Non-fleet rate. Fleet: 0.3% of sum insured, min Kshs. 2,500 (not applied automatically)."},
    {"code": "excess_protector_own_damage", "label": "Excess protector - Own Damage", "basis": "percent_of_sum_insured",
     "rate_percent": 0.5, "min_amount": 5000},
]
for _cic_class in CIC_CLASSES:
    if _cic_class["code"] in ("motor_commercial_own_goods", "motor_commercial_general_cartage", "motor_commercial_prime_mover"):
        _cic_class.setdefault("extensions", []).extend(_CIC_COMMERCIAL_EXTENSIONS)
        _cic_class.setdefault("free_benefits", []).append(
            {"code": "towing_recovery", "label": "Towing and recovery", "limit_amount": 50000,
             "limit_label": "Up to Kshs. 50,000", "top_up_note": "Kshs. 1,000 for every additional Kshs. 10,000 cover",
             "cover_type": "comprehensive"}
        )
