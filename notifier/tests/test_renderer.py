"""Snapshot-style renderer tests — assert key phrases appear in output."""

from pathlib import Path

import pandas as pd
import pytest

from src.grouper import group_by_manager
from src.findings import load_findings
from src.regional import group_by_regional_manager
from src.renderer import render_html, render_regional_html, render_regional_text, render_text

FIXTURE = Path(__file__).parent / "fixtures" / "sample_summary.csv"
FINDINGS_FIXTURE = Path(__file__).parent / "fixtures" / "sample_findings.csv"


@pytest.fixture()
def digests():
    df = pd.read_csv(FIXTURE)
    return group_by_manager(df)


@pytest.fixture()
def digests_with_findings():
    df = pd.read_csv(FIXTURE)
    findings_df = load_findings(FINDINGS_FIXTURE.read_bytes())
    return group_by_manager(df, findings_df=findings_df)


@pytest.fixture()
def digest_a(digests):
    return next(d for d in digests if d.manager_email == "manager.a@company.com")


@pytest.fixture()
def digest_b(digests):
    return next(d for d in digests if d.manager_email == "manager.b@company.com")


def test_html_contains_machine_name(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "Elk Grove / Gluer 01" in html


def test_html_contains_total_impact(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "12,500" in html


def test_html_contains_outcome_name(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "OEE" in html


def test_html_contains_lever_reason(digest_a):
    # V2 "Why" card heads with the top lever's reason
    html = render_html(digest_a, "Test Subject")
    assert "Motor Fault" in html


def test_html_streak_phrase_bsp_count_for_downtime_reason(digest_a):
    # Gluer 01's top lever is Downtime Reason, streak=3 — BSP-count wording
    html = render_html(digest_a, "Test Subject")
    assert "Above benchmark in 3 of the last 4 weeks." in html


def test_html_streak_phrase_consecutive_weeks_for_main_kpi(digest_b):
    # Chicago / Flexo 01's top lever is Speed, streak=2 — consecutive-worse-weeks wording
    html = render_html(digest_b, "Test Subject")
    assert "Trending worse for 2 weeks straight — needs attention." in html


def test_html_no_driven_clause_anywhere(digest_a):
    # "driven primarily by" clause removed entirely (V1 and V2 both)
    html = render_html(digest_a, "Test Subject")
    assert "driven primarily by" not in html


def test_html_no_driven_clause_digest_b(digest_b):
    html = render_html(digest_b, "Test Subject")
    assert "driven primarily by" not in html


def test_text_contains_machine_name(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Elk Grove / Gluer 01" in text


def test_text_contains_lever_details(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Motor Fault" in text


def test_html_subject_in_output(digest_a):
    html = render_html(digest_a, "Weekly OEE Insight Digest — 2026-04-21")
    assert "2026-04-21" in html


def test_html_action_present_for_top_lever(digest_a):
    # Card 3 (How to fix) always has action text, even on a lookup miss
    # ("Motor Fault" is not a real reason key, so this exercises the generic fallback)
    html = render_html(digest_a, "Test Subject")
    assert "Review this event with the operator and maintenance" in html


def test_html_action_present_for_real_lookup_key():
    # Speed is a real key in the action lookup — exercises the hit path
    df = pd.read_csv(FIXTURE)
    digests = group_by_manager(df)
    b = next(d for d in digests if d.manager_email == "manager.b@company.com")
    html = render_html(b, "Test Subject")
    assert "Compare actual run speed to the machine" in html


def test_text_streak_phrase_present(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Above benchmark in 3 of the last 4 weeks." in text


# --- Overview section tests ---

def test_html_overview_present(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "kpi-tiles" in html


def test_html_overview_total_sheets(digest_a):
    # Gluer 01 (12,500) + Gluer 02 (7,300) = 19,800
    html = render_html(digest_a, "Test Subject")
    assert "19,800" in html


def test_html_no_machines_impacted_tile(digest_a):
    # "Machines impacted" tile removed in V2
    html = render_html(digest_a, "Test Subject")
    assert "Machines impacted" not in html


def test_html_overview_top_driver(digest_a):
    # Gluer 01's top lever is Downtime Reason (5,100 sheets) — must appear in the Top driver tile
    html = render_html(digest_a, "Test Subject")
    assert "5,100" in html


def test_html_focus_machines_order(digest_a):
    # Gluer 01 (12,500 sheets) must appear before Gluer 02 (7,300 sheets)
    html = render_html(digest_a, "Test Subject")
    pos1 = html.index("Elk Grove / Gluer 01")
    pos2 = html.index("Elk Grove / Gluer 02")
    assert pos1 < pos2


def test_html_no_maintenance_report_when_absent(digest_a):
    # digest_a has no findings/pm attached — Maintenance report section must be suppressed
    html = render_html(digest_a, "Test Subject")
    assert "Maintenance report" not in html


def test_html_where_to_focus_heading(digest_b):
    html = render_html(digest_b, "Test Subject")
    assert "Where to focus this week" in html


def test_text_overview_present(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Sheets lost vs BSP" in text


def test_text_overview_total_sheets(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "19,800" in text


def test_text_overview_top_mover(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Elk Grove / Gluer 01" in text


def test_html_machine_oee_vs_bsp_present(digest_a):
    # Gluer 01: cur_oee=0.6234 → 62.34%, bsp=0.7812 → 78.12%
    html = render_html(digest_a, "Test Subject")
    assert "OEE 62.34% vs BSP 78.12%" in html


def test_html_graphic_care_findings_wording(digests_with_findings):
    digest = next(d for d in digests_with_findings if d.manager_email == "manager.a@company.com")
    html = render_html(digest, "Test Subject")
    assert "Maintenance Findings" not in html
    assert "Graphic Care Findings" in html


def test_html_maintenance_report_shows_missing_wo(digests_with_findings):
    # Maintenance report only renders when findings are attached
    digest = next(d for d in digests_with_findings if d.manager_email == "manager.a@company.com")
    html = render_html(digest, "Test Subject")
    assert "Missing Work Order" in html


def test_html_maintenance_report_plain_english_pm_wording(digests_with_findings):
    digest = next(d for d in digests_with_findings if d.manager_email == "manager.a@company.com")
    html = render_html(digest, "Test Subject")
    assert "1.5" not in html  # no jargon "1.5x allowed days" wording
    assert "significantly overdue" in html
    assert "allowable completion window" in html


def test_text_machine_oee_vs_bsp_present(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "OEE 62.34% vs BSP 78.12%" in text


def test_html_no_scrap_reason_in_output(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "Scrap Reason" not in html


def test_html_no_scrap_reason_digest_b(digest_b):
    html = render_html(digest_b, "Test Subject")
    assert "Scrap Reason" not in html


# --- Regional digest rendering ---

@pytest.fixture()
def regional_digest_x():
    df = pd.read_csv(FIXTURE)
    digests = group_by_regional_manager(df)
    return next(d for d in digests if d.regional_manager_email == "regional.x@company.com")


def test_regional_html_department_headings_present(regional_digest_x):
    html = render_regional_html(regional_digest_x, "Test Regional Subject")
    assert "Gluer" in html
    assert "Sheetfed Printing" in html


def test_regional_html_top_three_cap(regional_digest_x):
    html = render_regional_html(regional_digest_x, "Test Regional Subject")
    # Gluer has 4 impacted machines; the smallest (Dallas Gluer 02, 6,000) is capped out
    assert "Elk Grove / Gluer 01" in html
    assert "Dallas / Gluer 01" in html
    assert "Elk Grove / Gluer 02" in html
    assert "Dallas / Gluer 02" not in html


def test_regional_html_plant_rollup_present(regional_digest_x):
    html = render_regional_html(regional_digest_x, "Test Regional Subject")
    assert "Elk Grove" in html
    assert "Dallas" in html
    assert "Chicago" in html


def test_regional_html_no_maintenance_line_when_absent(regional_digest_x):
    html = render_regional_html(regional_digest_x, "Test Regional Subject")
    assert "Maintenance across the region" not in html


def test_regional_text_contains_department_and_plant(regional_digest_x):
    text = render_regional_text(regional_digest_x, "Test Regional Subject")
    assert "GLUER" in text
    assert "Elk Grove" in text
