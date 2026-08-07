from pathlib import Path

import pandas as pd
import pytest

from src.regional import group_by_regional_manager
from src.routing_check import find_routing_mismatches

FIXTURE = Path(__file__).parent / "fixtures" / "sample_summary.csv"


@pytest.fixture()
def df():
    return pd.read_csv(FIXTURE)


@pytest.fixture()
def digests(df):
    return group_by_regional_manager(df)


@pytest.fixture()
def digest_x(digests):
    return next(d for d in digests if d.regional_manager_email == "regional.x@company.com")


@pytest.fixture()
def digest_y(digests):
    return next(d for d in digests if d.regional_manager_email == "regional.y@company.com")


def test_two_regional_managers(digests):
    emails = {d.regional_manager_email for d in digests}
    assert emails == {"regional.x@company.com", "regional.y@company.com"}


def test_returns_empty_when_column_absent():
    bad_df = pd.DataFrame({"Plant": ["X"], "Plant - WC": ["X - Y"], "Period_Start": ["2026-01-01"],
                            "Total_Sheet_Impact": [1], "Department": ["Gluer"]})
    assert group_by_regional_manager(bad_df) == []


def test_blank_regional_email_skipped(df):
    df = df.copy()
    df.loc[df["Plant"] == "Denver", "Regional_Manager_Email"] = ""
    digests = group_by_regional_manager(df)
    emails = {d.regional_manager_email for d in digests}
    assert "regional.y@company.com" not in emails


def test_regional_manager_name_carried(digest_x):
    assert digest_x.regional_manager_name == "Regional Manager X"


def test_region_total_sheets(digest_x):
    # 12500 + 7300 + 9100 + 8000 + 6000
    assert digest_x.total_sheets == pytest.approx(42900)


def test_region_plants_covered(digest_x):
    assert digest_x.plants_covered == 3  # Elk Grove, Chicago, Dallas


def test_region_machines_impacted(digest_x):
    assert digest_x.machines_impacted == 5


def test_region_top_driver(digest_x):
    # Speed is the first lever on Gluer 02 (4000), Flexo 01 (4500), Dallas Gluer 02 (2500) = 11000
    assert digest_x.top_driver_name == "Speed"
    assert digest_x.top_driver_sheets == pytest.approx(11000)


def test_digests_sorted_by_total_sheets_desc(digests):
    totals = [d.total_sheets for d in digests]
    assert totals == sorted(totals, reverse=True)


# --- Plant roll-up ---

def test_plant_rollup_sums_match_machines(digest_x):
    total_from_rollups = sum(p.sheets for p in digest_x.plant_rollups)
    assert total_from_rollups == pytest.approx(digest_x.total_sheets)


def test_plant_rollup_sorted_desc(digest_x):
    sheets = [p.sheets for p in digest_x.plant_rollups]
    assert sheets == sorted(sheets, reverse=True)


def test_plant_rollup_worst_machine(digest_x):
    elk_grove = next(p for p in digest_x.plant_rollups if p.plant == "Elk Grove")
    assert elk_grove.worst_machine == "Elk Grove / Gluer 01"
    assert elk_grove.worst_machine_sheets == pytest.approx(12500)
    assert elk_grove.machines_impacted == 2


# --- Department sections ---

def test_department_sums_match_machines(digest_x):
    total_from_depts = sum(d.sheets for d in digest_x.departments)
    assert total_from_depts == pytest.approx(digest_x.total_sheets)


def test_department_sorted_desc(digest_x):
    sheets = [d.sheets for d in digest_x.departments]
    assert sheets == sorted(sheets, reverse=True)


def test_gluer_department_has_four_machines_capped_to_top_three(digest_x):
    gluer = next(d for d in digest_x.departments if d.department == "Gluer")
    assert gluer.machines_impacted == 4
    assert len(gluer.top_machines) == 3
    top_sheets = [m.total_sheet_impact for m in gluer.top_machines]
    assert top_sheets == [12500, 8000, 7300]  # 6000 (Dallas Gluer 02) excluded by the cap


def test_department_plants_count(digest_x):
    gluer = next(d for d in digest_x.departments if d.department == "Gluer")
    assert gluer.plants_count == 2  # Elk Grove, Dallas


def test_custom_top_n(df):
    digests = group_by_regional_manager(df, top_n=1)
    x = next(d for d in digests if d.regional_manager_email == "regional.x@company.com")
    gluer = next(d for d in x.departments if d.department == "Gluer")
    assert len(gluer.top_machines) == 1
    assert gluer.top_machines[0].total_sheet_impact == 12500


# --- Single-plant region (Denver) ---

def test_single_plant_region(digest_y):
    assert digest_y.plants_covered == 1
    assert digest_y.machines_impacted == 1
    assert digest_y.total_sheets == pytest.approx(15000)
    assert digest_y.top_driver_name == "Downtime %"
    assert digest_y.top_driver_sheets == pytest.approx(9000)


def test_no_maintenance_by_default(digest_x):
    assert digest_x.has_maintenance is False
    assert digest_x.maint_open == 0


# --- Routing mismatch detection ---

def test_find_routing_mismatches_flags_plant_fallback(df):
    mismatches = find_routing_mismatches(df)
    assert len(mismatches) == 1
    assert "Dallas" in mismatches[0]
    assert "Gluer" in mismatches[0]


def test_find_routing_mismatches_empty_when_column_absent():
    bad_df = pd.DataFrame({"Plant": ["X"], "Department": ["Y"]})
    assert find_routing_mismatches(bad_df) == []


def test_find_routing_mismatches_empty_when_all_matched(df):
    df = df.copy()
    df["Routing_Match_Level"] = "Department"
    assert find_routing_mismatches(df) == []
