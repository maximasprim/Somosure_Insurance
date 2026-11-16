"""The weekly-report importer's rules: parsing, cleaning, matching, export. No database needed."""

from datetime import date, datetime
from decimal import Decimal

from app.services.sales_import import claims as claims_mod
from app.services.sales_import import cleaners as c
from app.services.sales_import.export import build_cleaned_workbook
from app.services.sales_import import posting_rules as pr
from app.services.sales_import.manual_rules import build_manual_entry, default_expiry
from app.services.sales_import.matching import canonical_underwriter, match_provider_name, names_overlap, phone_key
from app.services.sales_import.parser import BlockTotals, WorkbookError, parse_workbook
from app.services.sales_import.period import apply_period, in_period, parse_period
from app.services.sales_import.pipeline import resolve_workbook
from app.services.sales_import.reconcile import reconcile
from app.services.sales_import.sync import CLAIM_TRACKED, SALES_TRACKED, apply_overrides, best_sales_match, plan_sync
from tests.sales_import_fixtures import build_workbook


def _resolved(**kwargs):
    pw = parse_workbook(build_workbook(**kwargs))
    return pw, resolve_workbook(pw)


# ---- cleaners ------------------------------------------------------------------------------


def test_text_dates_tolerate_the_typos_seen_in_the_real_sheets():
    assert c.parse_text_date("13/01/2026") == date(2026, 1, 13)
    assert c.parse_text_date("3/1/2026") == date(2026, 1, 3)
    assert c.parse_text_date("13.01.2026") == date(2026, 1, 13)
    assert c.parse_text_date("O5/06/2026") == date(2026, 6, 5)  # letter O for zero
    assert c.parse_text_date("13/01//2026") == date(2026, 1, 13)
    assert c.parse_text_date("31/03/202") is None  # a year typo is not a date
    assert c.parse_text_date("-") is None


def test_true_dates_with_day_12_or_less_are_read_as_day_month_swapped_unless_the_row_says_otherwise():
    # Excel stored 6 Jan as 1 June. The paid date and the one-year span both confirm the swap.
    resolved = c.resolve_policy_dates(datetime(2026, 6, 1), datetime(2027, 5, 1), "07/01/2026", (2026, 1))
    assert (resolved.start, resolved.expiry, resolved.paid) == (date(2026, 1, 6), date(2027, 1, 5), date(2026, 1, 7))
    assert any(f.code == "date_day_month_swapped" for f in resolved.flags)


def test_a_day_first_formatted_date_is_taken_exactly_as_it_is():
    exact = c.ExactDate(2026, 3, 9)
    assert c.date_readings(exact) == [c.DateReading(date(2026, 3, 9))]
    assert c.day_first_format("dd/mm/yyyy") and c.day_first_format("d-mmm-yyyy")
    assert not c.day_first_format("mm/dd/yyyy") and not c.day_first_format("m/d/yyyy")


def test_year_typos_get_a_suggested_fix_but_are_not_changed():
    resolved = c.resolve_policy_dates("14/03/2027", "13/03/2027", "14/03/2026")
    flag = next(f for f in resolved.flags if f.code == "expiry_before_start")
    assert "14/03/2026" in flag.message
    assert resolved.start == date(2027, 3, 14)  # untouched


def test_policy_numbers_cover_type_plates_phones():
    assert c.clean_policy_number(102577000060.0) == ("102577000060", None)
    assert c.clean_policy_number("HDO/0700/52395/2026 (COMP)") == ("HDO/0700/52395/2026", "COMP")
    assert c.clean_policy_number("N/A") == (None, None)
    assert c.clean_plate("kdr 904v") == ("KDR904V", True)
    assert c.clean_plate("KDN 45OT") == ("KDN450T", True)  # O typed for 0
    assert c.clean_phone(721559694.0) == "+254721559694"
    assert c.clean_phone("0721 559 694") == "+254721559694"
    assert c.clean_phone("254 721 800510") == "+254721800510"


def test_the_reg_column_also_carries_the_product_for_non_motor_policies():
    assert c.classify_asset("PI")[0] == "professional_indemnity"
    assert c.classify_asset("Credit Life")[0] == "credit_life"
    assert c.classify_asset("KDR 904V") == ("motor", "KDR904V", None)
    assert c.classify_asset("something odd")[0] == "other"


def test_underwriter_spellings():
    assert c.resolve_underwriter("MORNACH")[0] == "MONARCH"
    assert c.resolve_underwriter("directline")[0] == "DIRECT LINE"
    assert c.resolve_underwriter("CIC General Insurance Company")[0] == "CIC"
    assert c.resolve_underwriter("MONARCH")[1] == []
    name, flags = c.resolve_underwriter("Brand New Insurer")
    assert name == "BRAND NEW INSURER" and flags[0].code == "underwriter_unknown"
    assert c.resolve_underwriter("MORNACH", {"MORNACH": "SOMETHING ELSE"})[0] == "SOMETHING ELSE"  # saved alias wins


def test_staff_and_branch_are_split_whichever_way_round_they_were_typed():
    assert c.split_staff_branch("JOSPHINE -HQ") == ("JOSPHINE", "HQ")
    assert c.split_staff_branch("HQ-JOSPHINE") == ("JOSPHINE", "HQ")
    assert c.split_staff_branch("JOSSY EMBAKASI") == ("JOSSY", "EMBAKASI")
    assert c.split_staff_branch("Lagat Ng Rd") == ("Lagat", "NGONG ROAD")
    assert c.split_staff_branch("HQ") == (None, "HQ")
    assert c.split_staff_branch("Jesse") == ("Jesse", None)
    assert c.split_staff_branch("KATE - NGNG RD")[1] == "NGONG ROAD"


def test_misspelled_staff_names_are_merged_into_the_common_spelling():
    raws = ["JOSPHINE-HQ"] * 5 + ["JOSEPHINE-HQ", "SCOLA-KAJIADO", "SCHOLA-KAJIADO", "SCOLA - KAJIADO"]
    resolver = c.StaffResolver(raws)
    assert resolver.resolve("JOSEPHINE-HQ")[:2] == ("Josphine", "HQ")
    assert resolver.resolve("SCHOLA-KAJIADO")[:2] == ("Scola", "KAJIADO")
    assert "JOSEPHINE HQ" in resolver.resolved
    assert c.StaffResolver(raws, {"JOSEPHINE HQ": ("Josephine", "HQ")}).resolve("JOSEPHINE-HQ")[:2] == ("Josephine", "HQ")


# ---- parser --------------------------------------------------------------------------------


def test_parser_reads_blocks_headers_formulas_and_skips_what_is_not_data():
    pw, rw = _resolved()
    assert [s.name for s in pw.sheets] == ["2026 Sales", "Claims 2026", "IPF REPORT 2026"]
    assert pw.ignored_sheets == ["Notes"]
    assert len(rw.sales) == 3 and len(rw.claims) == 1 and len(rw.ipf) == 2

    jan = rw.sales[0]
    assert (jan["period_year"], jan["period_month"]) == (2026, 1)
    assert (jan["start_date"], jan["expiry_date"], jan["date_paid"]) == (date(2026, 1, 6), date(2027, 1, 5), date(2026, 1, 7))
    assert jan["underwriter"] == "MONARCH" and jan["underwriter_raw"] == "MORNACH"
    assert jan["reg_no"] == "KDR904V" and jan["product_line"] == "motor"
    assert jan["policy_number"] == "123456"
    assert jan["branch"] == "HQ" and jan["staff_name"] in {"Josphine", "Josephine"}
    assert jan["business_type"] == "renewal"
    # formulas with no saved result are worked out
    assert (jan["commission"], jan["wht"], jan["net_revenue"]) == (Decimal("5000.00"), Decimal("500.00"), Decimal("4500.00"))

    second = rw.sales[1]
    assert second["product_line"] == "professional_indemnity" and second["reg_no"] is None
    assert (second["policy_number"], second["cover_type"]) == ("HDO/1/2026", "COMP")
    assert second["underwriter"] == "DIRECT LINE"
    assert second["commission"] == Decimal("4000.00")
    # "JOSPHINE -HQ" and "HQ-JOSEPHINE" are one person: the same spelling is used for both
    assert second["staff_name"] == jan["staff_name"] and second["branch"] == "HQ"

    feb = rw.sales[2]
    assert feb["period_month"] == 2  # the month name was on the first data row, header had none
    assert feb["start_date"] == date(2026, 2, 3) and feb["expiry_date"] == date(2027, 2, 2)
    assert (feb["staff_name"], feb["branch"]) == ("Wilson", "RUIRU")
    assert any("leftover" in n for n in pw.notes)


def test_claims_get_a_dated_timeline_and_the_reported_date_is_settled_by_it():
    _, rw = _resolved()
    claim = rw.claims[0]
    assert claim["date_reported"] == date(2026, 5, 3)  # the cell said 5 March; the narrative says 3 May
    assert [m["event"] for m in claim["milestones"]] == ["reported", "documents_submitted", "release_letter"]
    assert claim["outcome"] == "closed" and claim["contact"] == "+254721559694" and claim["reg_no"] == "KDR904V"


def test_ipf_dates_follow_the_order_of_the_rows():
    _, rw = _resolved()
    assert [r["date_paid"] for r in rw.ipf] == [date(2026, 2, 3), date(2026, 2, 23)]


def test_an_unreadable_file_is_refused_with_a_clear_message():
    try:
        parse_workbook(b"this is not a workbook")
    except WorkbookError as exc:
        assert "Excel" in str(exc)
    else:
        raise AssertionError("expected WorkbookError")


def test_commission_cap_and_missing_data_are_flagged():
    _, rw = _resolved()
    codes = {f["code"] for row in rw.sales for f in row["flags"]}
    assert "date_day_month_swapped" in codes
    assert rw.sales[0]["issue_level"] in {"info", "none", "warning"}


# ---- reconciliation ------------------------------------------------------------------------


def test_reconciliation_flags_a_sheet_total_that_does_not_cover_its_rows():
    pw, _ = _resolved()
    jan = next(b for b in pw.blocks if b.month == 1)
    jan.total_row, jan.sheet_premium, jan.sheet_commission = 5, Decimal("70000"), Decimal("5000")  # commission total stops a row short
    result = {r["month"]: r for r in reconcile(pw.blocks, pw.sales)}
    assert result[1]["status"] == "mismatch"
    assert set(result[1]["difference"]) == {"commission"}
    assert result[2]["status"] == "no_total"


# ---- keys, matching, sync ------------------------------------------------------------------


def test_keys_are_stable_and_a_filled_in_policy_number_is_still_recognised():
    a = c.row_keys("MONARCH", None, "KDR904V", date(2026, 1, 6), Decimal("50000"), "JOHN DOE", 2026)
    b = c.row_keys("MONARCH", "HDO/1", "KDR904V", date(2026, 1, 6), Decimal("50000"), "JOHN DOE", 2026)
    assert a[0] != b[0] and a[1] == b[1]  # primary key changes with the number, fallback does not
    assert c.row_keys("MONARCH", "HDO/1", None, None, None, "X", 2026)[0] != c.row_keys("MONARCH", "HDO/1", None, None, None, "X", 2025)[0]


def _existing(rows):
    return [dict(r, id=f"id-{i}", status="active") for i, r in enumerate(rows)]


def test_sync_new_unchanged_changed_missing_and_moved_rows():
    _, rw = _resolved()
    rows = rw.sales
    existing = _existing(rows)
    years = {2026}

    same = plan_sync(rows, existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years, use_fallback=True)
    assert (len(same.inserts), len(same.updated), len(same.unchanged), len(same.missing_ids)) == (0, 0, 3, 0)

    edited = [dict(r) for r in rows]
    edited[0]["premium"] = Decimal("51000.00")
    plan = plan_sync(edited, existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years, use_fallback=True)
    assert len(plan.updated) == 1 and plan.updated[0].diffs == [{"field": "premium", "old": "50000.00", "new": "51000.00"}]

    plan = plan_sync(rows[:2], existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years, use_fallback=True)
    assert plan.missing_ids == ["id-2"]
    plan = plan_sync(rows[:2], existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years={2025}, use_fallback=True)
    assert plan.missing_ids == []  # a year that was not uploaded is never judged

    came_back = [dict(e) for e in existing]
    came_back[2]["status"] = "missing_from_sheet"
    plan = plan_sync(rows, came_back, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years, use_fallback=True)
    assert len(plan.restored) == 1

    # policy number typed into a row that had none: same row, not a new one plus a missing one
    filled = [dict(r) for r in rows]
    filled[2]["policy_number"] = "NEW/123"
    filled[2]["natural_key"], _ = c.row_keys(filled[2]["underwriter"], "NEW/123", filled[2]["reg_no"], filled[2]["start_date"],
                                              filled[2]["premium"], filled[2]["client_name"], 2026)
    plan = plan_sync(filled, existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years, use_fallback=True)
    assert (len(plan.inserts), len(plan.missing_ids), len(plan.updated)) == (0, 0, 1)


def test_two_rows_with_the_same_policy_number_are_told_apart_by_content_not_order():
    _, rw = _resolved()
    one, two = dict(rw.sales[0]), dict(rw.sales[1])
    for r in (one, two):
        r["policy_number"] = "SAME/1"
        r["underwriter"] = "MONARCH"
    keys_a = c.row_keys(one["underwriter"], "SAME/1", one["reg_no"], one["start_date"], one["premium"], one["client_name"], 2026)
    keys_b = c.row_keys(two["underwriter"], "SAME/1", two["reg_no"], two["start_date"], two["premium"], two["client_name"], 2026)
    assert keys_a[0] == keys_b[0] and keys_a[1] != keys_b[1]


def test_a_claim_is_attached_to_the_policy_running_when_it_was_reported():
    sales = [
        {"id": "old", "reg_no": "KDR904V", "underwriter": "MONARCH", "start_date": date(2025, 1, 6), "expiry_date": date(2026, 1, 5)},
        {"id": "current", "reg_no": "KDR904V", "underwriter": "MONARCH", "start_date": date(2026, 1, 6), "expiry_date": date(2027, 1, 5)},
    ]
    claim = {"reg_no": "KDR904V", "underwriter": "MONARCH", "date_reported": date(2026, 5, 3)}
    assert best_sales_match(claim, sales) == "current"
    assert best_sales_match({"reg_no": "ZZZ999Z", "underwriter": "MONARCH"}, sales) is None
    assert best_sales_match({"reg_no": None}, sales) is None


def test_claim_narrative_timeline():
    text = "Claim reported and documents submitted on 29/05/2026. Repair Authority issued on 6/2/2026. Repairs done on 27th /02/2026."
    events = [(m["event"], m["date"]) for m in claims_mod.extract_milestones(text)]
    assert ("reported", "2026-05-29") in events and ("documents_submitted", "2026-05-29") in events
    assert ("repair_authority", "2026-02-06") in events and ("repairs_done", "2026-02-27") in events
    assert claims_mod.normalize_outcome("Closed, client unresponsive") == "closed_unresponsive"
    assert claims_mod.normalize_outcome(None) == "open"


# ---- cleaned workbook: what we export, we can import again unchanged ------------------------


def test_the_cleaned_workbook_round_trips_through_the_importer():
    pw, rw = _resolved()
    exported = build_cleaned_workbook(rw.sales, rw.claims, rw.ipf, rw.issues)
    pw2 = parse_workbook(exported)
    rw2 = resolve_workbook(pw2)

    assert [r["natural_key"] for r in rw2.sales] and {r["natural_key"] for r in rw2.sales} == {r["natural_key"] for r in rw.sales}
    assert {r["natural_key"] for r in rw2.claims} == {r["natural_key"] for r in rw.claims}
    assert {r["natural_key"] for r in rw2.ipf} == {r["natural_key"] for r in rw.ipf}
    by_key = {r["natural_key"]: r for r in rw2.sales}
    for original in rw.sales:
        again = by_key[original["natural_key"]]
        for field in ("client_name", "underwriter", "reg_no", "start_date", "expiry_date", "date_paid", "staff_name", "branch",
                      "policy_number", "cover_type", "premium", "commission", "wht", "net_revenue", "period_year", "period_month"):
            assert original[field] == again[field], field
    # dates are exported day-first, so the next import does not second-guess them
    assert "date_day_month_swapped" not in rw2.issue_counts
    assert pw2.ignored_sheets in ([], ["Review"])  # the Review sheet (if any) is never read as data


# ---- suggested fixes ---------------------------------------------------------------------------


def test_a_year_typo_carries_a_structured_fix_a_person_can_accept():
    resolved = c.resolve_policy_dates("14/03/2027", "13/03/2027", "14/03/2026")
    flag = next(f for f in resolved.flags if f.code == "expiry_before_start")
    assert flag.fix == {"field": "start_date", "value": "2026-03-14", "label": "start date"}
    assert flag.as_dict()["fix"]["value"] == "2026-03-14"
    # nothing is suggested when no single-year change makes sense
    assert c.suggest_date_fix(date(2026, 3, 5), date(2026, 3, 6), date(2026, 3, 5))["field"] == "expiry_date"  # a year short
    assert c.suggest_date_fix(date(2026, 3, 5), date(2026, 9, 10), date(2026, 3, 5)) is None  # no one-year change fits


def test_an_accepted_fix_holds_while_the_sheet_is_unchanged_and_yields_when_the_sheet_changes():
    _, rw = _resolved(include_year_typo=True)
    typo = next(r for r in rw.sales if r["client_name"] == "ANN WANJIRU")
    assert typo["issue_level"] == "error"
    overrides = {"start_date": {"value": "2026-03-14", "sheet": "2027-03-14"}}

    row, kept = apply_overrides(typo, overrides)  # the sheet still says 14/03/2027
    assert row["start_date"] == date(2026, 3, 14) and kept == overrides
    assert {f["code"] for f in row["flags"]} >= {"fix_applied"} and "expiry_before_start" not in {f["code"] for f in row["flags"]}
    assert row["issue_level"] == "info"

    corrected = dict(typo, start_date=date(2026, 3, 14))  # the sheet was fixed
    row, kept = apply_overrides(corrected, overrides)
    assert kept == {} and row["start_date"] == date(2026, 3, 14)

    changed = dict(typo, start_date=date(2026, 3, 20))  # the sheet was changed to something else: the sheet wins
    row, kept = apply_overrides(changed, overrides)
    assert kept == {} and row["start_date"] == date(2026, 3, 20)


def test_a_re_upload_of_the_uncorrected_sheet_keeps_an_accepted_fix_without_reporting_a_change():
    _, rw = _resolved(include_year_typo=True)
    existing = _existing(rw.sales)
    typo = next(e for e in existing if e["client_name"] == "ANN WANJIRU")
    typo["overrides"] = {"start_date": {"value": "2026-03-14", "sheet": "2027-03-14"}}
    typo["start_date"] = date(2026, 3, 14)
    plan = plan_sync(rw.sales, existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years={2026}, use_fallback=True, overrides=True)
    assert len(plan.updated) == 0 and len(plan.unchanged) == len(rw.sales)
    kept = next(m for m in plan.matched if m.id == typo["id"])
    assert kept.values["start_date"] == date(2026, 3, 14) and kept.values["overrides"]


# ---- choosing the period -----------------------------------------------------------------------


def test_periods_are_year_month_and_validated():
    assert parse_period("2025-01") == (2025, 1) and parse_period("") is None and parse_period(None) is None
    for bad in ("2025", "2025-13", "01/2025", "January 2025"):
        try:
            parse_period(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert in_period(2026, 2, (2026, 2), None) and not in_period(2026, 1, (2026, 2), None)
    assert in_period(2026, 2, None, (2026, 2)) and not in_period(2026, 3, None, (2026, 2))
    assert in_period(2026, None, (2026, 2), None) and not in_period(2025, None, (2026, 2), None)  # year-only rows compare by year


def test_the_period_limits_what_is_read_and_everything_derived_from_it():
    pw = parse_workbook(build_workbook())
    skipped = apply_period(pw, parse_period("2026-02"), None)
    assert skipped == {"sales": 2, "claims": 0, "ipf": 0}  # January's two rows; the claim (May) and IPF lines (Feb) are inside
    assert [b.month for b in pw.blocks] == [2]
    rw = resolve_workbook(pw)
    assert [r["client_name"] for r in rw.sales] == ["PETER KAMAU"]
    assert next(s for s in pw.sheets if s.name == "2026 Sales").rows == 1

    pw = parse_workbook(build_workbook())
    assert apply_period(pw, parse_period("2026-03"), None) == {"sales": 3, "claims": 0, "ipf": 2}
    pw = parse_workbook(build_workbook())
    assert apply_period(pw, None, parse_period("2026-01")) == {"sales": 1, "claims": 1, "ipf": 2}


def test_rows_outside_the_period_are_never_judged_missing():
    _, rw = _resolved()
    existing = _existing(rw.sales)
    inside = lambda e: (e["period_year"], e["period_month"] or 0) >= (2026, 2)
    plan = plan_sync([r for r in rw.sales if inside(r)], existing, tracked=SALES_TRACKED, year_field="sheet_year",
                     uploaded_years={2026}, use_fallback=True, in_scope=inside)
    assert plan.missing_ids == []
    plan = plan_sync([], existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years={2026}, use_fallback=True, in_scope=inside)
    assert len(plan.missing_ids) == 1  # only the February row is inside the period


# ---- matching workbook clients to customers ---------------------------------------------------


def test_phone_numbers_match_whatever_way_they_were_written():
    assert phone_key("0721 559 694") == phone_key("+254721559694") == phone_key("254721559694") == "721559694"
    assert phone_key("12345") is None and phone_key(None) is None


def test_a_plate_match_needs_a_similar_name_too():
    assert names_overlap("JOHN KAMAU", "kamau john mwangi")
    assert not names_overlap("JANE ROE", "JOHN DOE")
    assert not names_overlap("AB CD", "AB CD")  # words under three letters are not evidence


def test_platform_provider_names_are_brought_onto_the_workbook_names():
    known = {"AMACO", "CIC"}
    assert canonical_underwriter("AMACO INSURANCE", known) == "AMACO"
    assert canonical_underwriter("Unknown Co", known) == "UNKNOWN CO"
    assert canonical_underwriter(None, known) == "NOT STATED"


def test_a_phone_added_by_staff_holds_while_the_sheet_has_none_and_yields_when_it_gets_one():
    _, rw = _resolved()
    row = rw.sales[2]
    assert row["phone"] is None
    overrides = {"phone": {"value": "+254733000222", "sheet": None}}
    kept_row, kept = apply_overrides(row, overrides)
    assert kept_row["phone"] == "+254733000222" and kept == overrides
    assert "fix_applied" not in {f["code"] for f in kept_row["flags"]}  # no date note for a phone

    sheet_now_has_one = dict(row, phone="+254799000111")
    row2, kept2 = apply_overrides(sheet_now_has_one, overrides)
    assert kept2 == {} and row2["phone"] == "+254799000111"


# ---- posting into the system's own records ----------------------------------------------------


def _entry(**over):
    base = {
        "natural_key": "k1", "sheet_year": 2026, "period_year": 2026, "period_month": 1, "underwriter": "MONARCH", "phone": None,
        "policy_number": "ABC/1", "premium": Decimal("1000.00"), "start_date": date(2026, 1, 6), "expiry_date": date(2027, 1, 5),
        "date_paid": date(2026, 1, 7), "issue_level": "none", "product_line": "motor",
    }
    return {**base, **over}


def test_a_row_is_only_held_when_the_system_cannot_store_it():
    linked = {"MONARCH"}
    ok = pr.classify(_entry(), linked)
    assert ok.ready and [f["code"] for f in ok.flags] == ["customer_no_phone"]  # appended, with a flag

    assert [c for c, _ in pr.classify(_entry(underwriter="MADISON"), linked).reasons] == ["no_provider_link"]
    assert [c for c, _ in pr.classify(_entry(premium=None), linked).reasons] == ["missing_premium"]
    assert [c for c, _ in pr.classify(_entry(start_date=None, expiry_date=None), linked).reasons] == ["missing_dates"]
    assert [c for c, _ in pr.classify(_entry(underwriter=None), linked).reasons] == ["no_underwriter"]


def test_what_is_missing_is_flagged_but_still_posted():
    flags = {f["code"] for f in pr.classify(_entry(policy_number=None, expiry_date=None, date_paid=None, issue_level="warning", phone="+254711000111"), {"MONARCH"}).flags}
    assert flags == {"policy_number_placeholder", "date_assumed", "payment_date_assumed", "import_issues"}


def test_one_missing_date_is_derived_from_the_other_and_marked_assumed():
    assert pr.derive_dates(date(2026, 3, 14), None) == (date(2026, 3, 14), date(2027, 3, 13), True)
    assert pr.derive_dates(None, date(2027, 3, 13)) == (date(2026, 3, 14), date(2027, 3, 13), True)
    assert pr.derive_dates(date(2026, 3, 14), date(2027, 3, 13)) == (date(2026, 3, 14), date(2027, 3, 13), False)
    assert pr.derive_dates(None, None) == (None, None, False)


def test_policy_numbers_are_never_duplicated_and_placeholders_are_recognisable():
    taken = {"ABC/1"}
    assert pr.unique_policy_number(_entry(policy_number="XYZ/9"), taken) == ("XYZ/9", None)
    assert pr.unique_policy_number(_entry(policy_number="ABC/1"), taken) == ("ABC/1-2026", "policy_number_year_added")
    number, flag = pr.unique_policy_number(_entry(policy_number=None), taken)
    assert flag == "policy_number_placeholder" and pr.is_placeholder(number) and not pr.is_placeholder("HDO/0700/123")
    taken_both = {"ABC/1", "ABC/1-2026"}
    assert pr.unique_policy_number(_entry(policy_number="ABC/1"), taken_both)[0] not in taken_both


def test_sale_dates_statuses_and_categories():
    assert pr.sold_on(_entry()) == date(2026, 1, 7)
    assert pr.sold_on(_entry(date_paid=None)) == date(2026, 1, 6)
    assert pr.sold_on(_entry(date_paid=None, start_date=None)) == date(2026, 1, 1)
    assert pr.policy_status(date(2026, 11, 12), date(2026, 11, 12)) == "active"
    assert pr.policy_status(date(2026, 11, 11), date(2026, 11, 12)) == "expired"
    assert pr.category_for("motor") == "motor" and pr.category_for("credit_life") == "life" and pr.category_for("additions") == "other"


def test_a_sheet_underwriter_is_recognised_as_the_provider_already_in_the_system():
    providers = {"MONARCH INSURANCE COMPANY": "p1", "AMACO": "p2", "CIC GENERAL": "p3"}
    assert match_provider_name("MONARCH", providers) == "p1"
    assert match_provider_name("AMACO INSURANCE", providers) == "p2"
    assert match_provider_name("CIC", providers) == "p3"
    assert match_provider_name("MADISON", providers) is None and match_provider_name(None, providers) is None


# ---- a sale typed into the system -------------------------------------------------------------


def _form(**over):
    base = {
        "client_name": "  peter   kamau ", "phone": None, "reg_or_product": "kdm 813y", "start_date": date(2026, 2, 3), "date_paid": date(2026, 2, 3),
        "staff_name": "WILSON", "branch": "ruiru", "business_type": None, "policy_number": "ABC/999 (COMP)", "premium": Decimal("30000"), "commission": Decimal("3000"),
    }
    return {**base, **over}


def test_a_typed_sale_is_shaped_like_a_sheet_row_with_the_sheets_arithmetic():
    built = build_manual_entry(_form(), underwriter="KENYA ALLIANCE", underwriter_name="Kenya Alliance Insurance")
    e = built.entry
    assert not built.errors
    assert (e["client_name"], e["reg_no"], e["policy_number"], e["cover_type"]) == ("PETER KAMAU", "KDM813Y", "ABC/999", "COMP")
    assert (e["staff_name"], e["branch"], e["period_year"], e["period_month"]) == ("Wilson", "RUIRU", 2026, 2)
    assert e["expiry_date"] == date(2027, 2, 2) == default_expiry(date(2026, 2, 3))
    assert (e["commission"], e["wht"], e["net_revenue"], e["commission_rate"]) == (Decimal("3000.00"), Decimal("300.00"), Decimal("2700.00"), Decimal("0.1000"))
    assert e["origin"] == "manual" and e["sheet_name"] == "Entered in system"


def test_the_same_sale_typed_in_the_sheet_gets_the_same_keys_so_the_import_merges_it():
    e = build_manual_entry(_form(), underwriter="KENYA ALLIANCE", underwriter_name="x").entry
    sheet = c.row_keys("KENYA ALLIANCE", "ABC/999", "KDM813Y", date(2026, 2, 3), Decimal("30000.00"), "PETER KAMAU", 2026)
    assert (e["natural_key"], e["fallback_key"]) == sheet


def test_a_typed_sale_is_validated_with_plain_reasons():
    bad = build_manual_entry(_form(client_name="", premium=Decimal("0"), reg_or_product="", phone="123"), underwriter="X", underwriter_name="X")
    assert bad.entry is None and len(bad.errors) == 4
    backwards = build_manual_entry(_form(expiry_date=date(2026, 1, 1)), underwriter="X", underwriter_name="X")
    assert backwards.errors == ["The expiry date must be after the start date."]
    # tax is a figure the person can override; net follows
    custom = build_manual_entry(_form(wht=Decimal("250")), underwriter="X", underwriter_name="X").entry
    assert (custom["wht"], custom["net_revenue"]) == (Decimal("250.00"), Decimal("2750.00"))
    # a product, not a plate, is fine; commission may be left out
    product = build_manual_entry(_form(reg_or_product="WIBA", commission=None), underwriter="X", underwriter_name="X").entry
    assert product["product_line"] == "wiba" and product["reg_no"] is None and product["commission"] is None and product["wht"] is None
