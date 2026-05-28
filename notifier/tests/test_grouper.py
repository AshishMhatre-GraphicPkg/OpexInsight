from pathlib import Path

import pandas as pd
import pytest

from src.grouper import group_by_manager, MoverRow

FIXTURE = Path(__file__).parent / "fixtures" / "sample_summary.csv"


@pytest.fixture()
def df():
    return pd.read_csv(FIXTURE)


def test_two_managers(df):
    digests = group_by_manager(df)
    emails = {d.manager_email for d in digests}
    assert emails == {"manager.a@company.com", "manager.b@company.com"}


def test_manager_a_has_two_machines(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    assert len(a.machines) == 2


def test_manager_b_has_one_machine(df):
    digests = group_by_manager(df)
    b = next(d for d in digests if d.manager_email == "manager.b@company.com")
    assert len(b.machines) == 1


def test_cc_list_carried(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    assert a.cc_list == "supervisor.a@company.com"


def test_manager_b_no_cc(df):
    digests = group_by_manager(df)
    b = next(d for d in digests if d.manager_email == "manager.b@company.com")
    assert b.cc_list is None


def test_levers_parsed(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    # First machine (Elk Grove / Gluer 01) should have 2 levers (Scrap Reason removed)
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert len(wc01.levers) == 2
    assert wc01.levers[0].name == "Downtime Reason"
    assert wc01.levers[0].reasons == "Motor Fault"
    assert wc01.levers[0].streak == 3


def test_machine_with_two_levers_stops_at_none(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    # Gluer 02 has only 2 levers; Lever_3 cols are empty — loop must stop
    wc02 = next(m for m in a.machines if "Gluer 02" in m.plant_wc)
    assert len(wc02.levers) == 2


def test_machines_sorted_by_impact_desc(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    impacts = [m.total_sheet_impact for m in a.machines]
    assert impacts == sorted(impacts, reverse=True)


def test_missing_manager_email_column_raises():
    bad_df = pd.DataFrame({"Plant": ["X"]})
    with pytest.raises(ValueError, match="Manager_Email"):
        group_by_manager(bad_df)


def test_lower_is_better_lever_formats_as_pct_and_above_bsp(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    lvr = wc01.levers[0]  # Downtime Reason — lower-is-better, percent
    assert lvr.cur_actual == "32.00%"
    assert lvr.bsp_benchmark == "14.00%"
    assert lvr.streak_direction == "above BSP"


def test_lower_is_better_raw_numeric_lever(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    lvr = wc01.levers[1]  # Avg MR Time — lower-is-better, time in hours → minutes
    assert "%" not in lvr.cur_actual
    assert "%" not in lvr.bsp_benchmark
    assert lvr.streak_direction == "above BSP"


def test_raw_numeric_lever_no_percent(df):
    digests = group_by_manager(df)
    b = next(d for d in digests if d.manager_email == "manager.b@company.com")
    wc10 = b.machines[0]  # Chicago / Flexo 01 — Speed lever is raw integer
    speed_lever = next(l for l in wc10.levers if l.name.strip() == "Speed")
    assert "%" not in speed_lever.cur_actual
    assert "%" not in speed_lever.bsp_benchmark
    assert "." not in speed_lever.cur_actual
    assert "." not in speed_lever.bsp_benchmark
    assert speed_lever.streak_direction == "below BSP"


def test_missing_cur_actual_returns_empty_string(df):
    # Gluer 02 has no Lever_3 — loop stops at NaN name, no error
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc02 = next(m for m in a.machines if "Gluer 02" in m.plant_wc)
    assert len(wc02.levers) == 2  # Lever_3 absent, so only 2


def test_driver_parent_populated_when_downtime_present(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert wc01.driver_parent == "Downtime %"
    assert wc01.driver_parent_sheets == 5100.0


def test_driver_parent_none_when_neither_present(df):
    # Gluer 02 has only OEE-parent levers (Speed, Setup Frequency)
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc02 = next(m for m in a.machines if "Gluer 02" in m.plant_wc)
    assert wc02.driver_parent is None
    assert wc02.driver_parent_sheets is None


def test_outcome_oee_columns_populated(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert wc01.outcome_1_cur_actual == pytest.approx(0.6234)
    assert wc01.outcome_1_bsp_benchmark == pytest.approx(0.7812)


def test_overview_top_lever_downtime_reason_relabeled(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    # Gluer 01's top lever is Downtime Reason (5,100 sheets) — overview should show "Downtime"
    mover = next(r for r in a.overview.top_movers if "Gluer 01" in r.plant_wc)
    assert mover.top_lever == "Downtime"
    # But the underlying LeverSummary name is unchanged
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert wc01.levers[0].name == "Downtime Reason"


def test_overview_mover_oee_columns(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    mover = next(r for r in a.overview.top_movers if "Gluer 01" in r.plant_wc)
    assert mover.cur_oee == pytest.approx(0.6234)
    assert mover.bsp_oee == pytest.approx(0.7812)


def test_avg_mr_time_lever_formats_as_minutes(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    lvr = wc01.levers[1]  # Avg MR Time: 0.45 hr → 27 Mins, 0.333 hr → 20 Mins
    assert lvr.name == "Avg MR Time"
    assert lvr.cur_actual.endswith(" Mins")
    assert "." not in lvr.cur_actual.replace(" Mins", "")
    assert lvr.bsp_benchmark.endswith(" Mins")
    assert "." not in lvr.bsp_benchmark.replace(" Mins", "")
    assert lvr.cur_actual == "27 Mins"
    assert lvr.bsp_benchmark == "20 Mins"


def test_speed_lever_formats_as_integer(df):
    digests = group_by_manager(df)
    b = next(d for d in digests if d.manager_email == "manager.b@company.com")
    wc10 = b.machines[0]
    speed_lever = next(l for l in wc10.levers if l.name.strip() == "Speed")
    assert speed_lever.cur_actual == "45,000"
    assert speed_lever.bsp_benchmark == "52,000"
