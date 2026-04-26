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
    assert "12.5" in html


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


def test_html_outcome_2_absent_when_none(digest_b):
    # manager B machine has no Outcome_2
    html = render_html(digest_b, "Test Subject")
    assert "and <strong>None" not in html


def test_text_contains_machine_name(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Elk Grove / Gluer 01" in text


def test_text_contains_lever_details(digest_a):
    text = render_text(digest_a, "Test Subject")
    assert "Motor Fault" in text


def test_html_subject_in_output(digest_a):
    html = render_html(digest_a, "Weekly OEE Insight Digest — 2026-04-21")
    assert "2026-04-21" in html
