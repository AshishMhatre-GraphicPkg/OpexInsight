from pathlib import Path

import pandas as pd
import pytest

from src.grouper import group_by_manager

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
    # First machine (Elk Grove / Gluer 01) should have 3 levers
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert len(wc01.levers) == 3
    assert wc01.levers[0].name == "Downtime Reason"
    assert wc01.levers[0].reasons == "Motor Fault"
    assert wc01.levers[0].streak == 3


def test_machine_with_one_lever_stops_at_none(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    # Second machine (Gluer 02) has Lever_3 cols empty in CSV
    wc02 = next(m for m in a.machines if "Gluer 02" in m.plant_wc)
    assert len(wc02.levers) == 2


def test_outcome_2_none_when_absent(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc02 = next(m for m in a.machines if "Gluer 02" in m.plant_wc)
    assert wc02.outcome_2 is None


def test_machines_sorted_by_impact_desc(df):
    digests = group_by_manager(df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    impacts = [m.total_sheet_impact for m in a.machines]
    assert impacts == sorted(impacts, reverse=True)


def test_missing_manager_email_column_raises():
    bad_df = pd.DataFrame({"Plant": ["X"]})
    with pytest.raises(ValueError, match="Manager_Email"):
        group_by_manager(bad_df)
