"""Snapshot-style renderer tests — assert key phrases appear in output."""

from pathlib import Path

import pandas as pd
import pytest

from src.grouper import group_by_manager
from src.renderer import render_html, render_text

FIXTURE = Path(__file__).parent / "fixtures" / "sample_summary.csv"


@pytest.fixture()
def digests():
    df = pd.read_csv(FIXTURE)
    return group_by_manager(df)


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
    assert "12500" in html


def test_html_contains_outcome_name(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "OEE" in html


def test_html_contains_lever_reason(digest_a):
    html = render_html(digest_a, "Test Subject")
    assert "Motor Fault" in html


def test_html_streak_highlighted(digest_a):
    html = render_html(digest_a, "Test Subject")
    # Lever 1 on machine 1 has streak=3 — should render streak info
    assert "3/4" in html


def test_html_no_streak_when_zero(digest_b):
    # Chicago / Flexo 01 lever 1 (Speed) has streak=2, lever 2 has streak=0
    html = render_html(digest_b, "Test Subject")
    assert "2/4" in html


def test_html_single_outcome_narrative(digest_b):
    # Only OEE outcome — no "and <strong>" secondary outcome rendered
    html = render_html(digest_b, "Test Subject")
    assert "driven primarily by <strong>OEE</strong>" in html
    assert "and <strong>" not in html


def test_text_contains_machine_name(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Elk Grove / Gluer 01" in text


def test_text_contains_lever_details(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Motor Fault" in text


def test_html_subject_in_output(digest_a):
    html = render_html(digest_a, "Weekly OEE Insight Digest — 2026-04-21")
    assert "2026-04-21" in html


def test_html_lever_shows_actual_vs_bsp(digest_a):
    html = render_html(digest_a, "Test Subject")
    # Downtime Reason on Gluer 01: actual 32.00% vs BSP 14.00%
    assert "actual 32.00% vs BSP 14.00%" in html


def test_html_streak_uses_above_bsp_for_lower_is_better(digest_a):
    html = render_html(digest_a, "Test Subject")
    # Downtime Reason streak=3 — lower-is-better → "above BSP"
    assert "3/4 weeks above BSP" in html


def test_html_streak_uses_below_bsp_for_higher_is_better(digest_b):
    html = render_html(digest_b, "Test Subject")
    # Speed lever streak=2 — higher-is-better → "below BSP"
    assert "2/4 weeks below BSP" in html


def test_text_lever_shows_actual_vs_bsp(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "actual 32.00% vs BSP 14.00%" in text


def test_text_streak_direction_present(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "above BSP" in text or "below BSP" in text


def test_html_no_actual_vs_bsp_when_empty(digest_a):
    # Verify the conditional renders — no "actual  vs BSP" (double space from empty str)
    html = render_html(digest_a, "Test Subject")
    assert "actual  vs BSP" not in html
