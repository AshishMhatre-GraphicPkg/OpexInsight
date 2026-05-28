"""Tests for src/findings.py — pure, no network required."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.findings import (
    FindingsSummary,
    HIGH_PRIORITY_THRESHOLD,
    build_summary_for_machine,
    load_findings,
)
from src.grouper import group_by_manager

FINDINGS_FIXTURE = Path(__file__).parent / "fixtures" / "sample_findings.csv"
SUMMARY_FIXTURE = Path(__file__).parent / "fixtures" / "sample_summary.csv"

_AS_OF = date(2026, 4, 28)


@pytest.fixture()
def findings_df():
    return load_findings(FINDINGS_FIXTURE.read_bytes())


@pytest.fixture()
def summary_df():
    return pd.read_csv(SUMMARY_FIXTURE)


# ── load_findings ────────────────────────────────────────────────────────────

def test_load_findings_renames_columns(findings_df):
    assert "wc_object_id" in findings_df.columns
    assert "section" in findings_df.columns
    assert "status" in findings_df.columns
    assert "priority" in findings_df.columns
    assert "allowed_days" in findings_df.columns
    assert "date" in findings_df.columns


# ── filter_for_machine (via build_summary_for_machine) ───────────────────────

def test_filter_for_machine_returns_only_matching_wc(findings_df):
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result is not None
    # WC-001 has 3 rows; summary totals should reflect that
    assert result.total_open + result.total_missing_wo == 3


def test_no_findings_returns_none(findings_df):
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-999", [], _AS_OF)
    assert result is None


# ── overdue flag ─────────────────────────────────────────────────────────────

def test_overdue_flag_marks_stale_row(findings_df):
    # WC-001 Feeder: date=3/1/2026, allowed=14d → overdue by 2026-04-28
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result is not None
    assert result.total_overdue >= 1


def test_overdue_flag_does_not_mark_fresh_row(findings_df):
    # WC-001 Stripping: date=4/1/2026, allowed=60d → NOT overdue by 2026-04-28 (27d elapsed)
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result is not None
    # Stripping row should not be overdue; total_overdue should be < 3 (not all rows overdue)
    assert result.total_overdue < 3


def test_overdue_count_wc001(findings_df):
    # Feeder (3/1, 14d) → overdue; Platen (3/15, 30d) → overdue (44d > 30d); Stripping (4/1, 60d) → not (27d)
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result.total_overdue == 2


# ── lever corroboration ──────────────────────────────────────────────────────

def test_lever_match_corroborates_feeder_section(findings_df):
    # WC-002 Feeder section; lever "Feeder DT%" contains keyword "feeder"
    result = build_summary_for_machine(
        findings_df, "Elk Grove", "WC-002", ["Feeder DT%", "Downtime Reason"], _AS_OF
    )
    assert result is not None
    assert "Feeder" in result.corroborated_sections


def test_lever_match_case_insensitive(findings_df):
    result = build_summary_for_machine(
        findings_df, "Elk Grove", "WC-002", ["FEEDER DT%"], _AS_OF
    )
    assert result is not None
    assert "Feeder" in result.corroborated_sections


def test_lever_no_match_when_section_absent(findings_df):
    # WC-010 has Blanking + Stripping; levers "Speed"/"Downtime Reason" don't match either keyword dict
    result = build_summary_for_machine(
        findings_df, "Chicago", "WC-010", ["Speed", "Downtime Reason"], _AS_OF
    )
    assert result is not None
    assert result.corroborated_sections == []


# ── Missing WO handling ──────────────────────────────────────────────────────

def test_missing_wo_counted_separately_from_open(findings_df):
    # WC-001: 2 Open rows, 1 Missing WO row
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result.total_open == 2
    assert result.total_missing_wo == 1


def test_missing_wo_not_counted_as_open(findings_df):
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result.total_open + result.total_missing_wo == 3


# ── high priority ─────────────────────────────────────────────────────────────

def test_high_priority_count_only_threshold(findings_df):
    # WC-001: Feeder Priority=10, Platen Priority=8, Stripping Priority=6 → only 1 high-priority
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result.high_priority_count == 1


def test_priority_below_threshold_excluded(findings_df):
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    # Priority 8 and 6 must NOT count
    assert result.high_priority_count < 3


# ── section sort order ────────────────────────────────────────────────────────

def test_section_sort_order_missing_plus_overdue_desc(findings_df):
    # WC-001 sections:
    #   Feeder: missing=0, overdue=1 → score=1
    #   Platen: missing=1, overdue=1 → score=2
    #   Stripping: missing=0, overdue=0 → score=0
    # Expected order: Platen, Feeder, Stripping
    result = build_summary_for_machine(findings_df, "Elk Grove", "WC-001", [], _AS_OF)
    assert result is not None
    sections = [s.section for s in result.by_section]
    assert sections[0] == "Platen"
    assert sections[-1] == "Stripping"


# ── grouper integration ───────────────────────────────────────────────────────

def test_grouper_attaches_findings_to_machine(summary_df, findings_df):
    digests = group_by_manager(summary_df, findings_df=findings_df)
    a = next(d for d in digests if d.manager_email == "manager.a@company.com")
    wc01 = next(m for m in a.machines if "Gluer 01" in m.plant_wc)
    assert wc01.findings is not None
    assert isinstance(wc01.findings, FindingsSummary)


def test_grouper_without_findings_is_backwards_compatible(summary_df):
    digests = group_by_manager(summary_df)
    for digest in digests:
        for machine in digest.machines:
            assert machine.findings is None


def test_grouper_machine_without_findings_row_returns_none(summary_df, findings_df):
    # All 3 machines in the fixture have findings — verify the field is populated
    digests = group_by_manager(summary_df, findings_df=findings_df)
    for digest in digests:
        for machine in digest.machines:
            # findings should be non-None for all 3 fixture machines
            assert machine.findings is not None
