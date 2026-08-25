"""Tests for src/feedback.py — pure, no network required."""

from io import BytesIO

import openpyxl
import pandas as pd
import pytest

from src.feedback import (
    AckLinks,
    LastAck,
    ack_stats,
    build_ack_links,
    encode_token,
    last_ack_for,
    load_responses,
    parse_token,
)

FB_CFG = {
    "enabled": True,
    "form_url": "https://forms.office.com/Pages/ResponsePage.aspx?id=ABC123",
    "param_answer": "r1",
    "param_token": "r2",
    "answer_yes": "Yes — we will action this",
    "answer_no": "No — not relevant this week",
    "col_token": "Reference (do not edit)",
    "col_answer": "Will your plant action these insights this week?",
    "col_comment": "Anything we should know? (optional)",
    "col_submitted": "Completion time",
}


def _workbook(rows: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    headers = [FB_CFG["col_token"], FB_CFG["col_answer"], FB_CFG["col_comment"], FB_CFG["col_submitted"]]
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── token round-trip ─────────────────────────────────────────────────────────

def test_encode_parse_round_trip():
    token = encode_token("P", "2026-04-20", "manager.a@graphicpkg.com")
    assert parse_token(token) == ("P", "2026-04-20", "manager.a@graphicpkg.com")


def test_encode_parse_round_trip_special_chars_in_email():
    token = encode_token("R", "2026-04-20", "first.last+ack@graphicpkg.com")
    assert parse_token(token) == ("R", "2026-04-20", "first.last+ack@graphicpkg.com")


def test_encode_invalid_kind_raises():
    with pytest.raises(ValueError):
        encode_token("X", "2026-04-20", "a@x.com")


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "P|2026-04-20",  # missing email
        "Q|2026-04-20|a@x.com",  # invalid kind
        "P||a@x.com",  # empty period
        42,
    ],
)
def test_parse_token_malformed_returns_none(bad):
    assert parse_token(bad) is None


# ── build_ack_links ───────────────────────────────────────────────────────────

def test_build_ack_links_none_when_no_config():
    assert build_ack_links(None, "P", "2026-04-20", "a@x.com") is None


def test_build_ack_links_none_when_disabled():
    cfg = {**FB_CFG, "enabled": False}
    assert build_ack_links(cfg, "P", "2026-04-20", "a@x.com") is None


def test_build_ack_links_none_when_form_url_blank():
    cfg = {**FB_CFG, "form_url": ""}
    assert build_ack_links(cfg, "P", "2026-04-20", "a@x.com") is None


def test_build_ack_links_encodes_token_and_pipe():
    links = build_ack_links(FB_CFG, "P", "2026-04-20", "manager.a@graphicpkg.com")
    assert isinstance(links, AckLinks)
    token = encode_token("P", "2026-04-20", "manager.a@graphicpkg.com")
    from urllib.parse import quote
    assert quote(token) in links.yes_url
    assert quote(token) in links.no_url
    assert "%7C" in links.yes_url  # URL-encoded '|'


def test_build_ack_links_yes_no_answers_differ():
    links = build_ack_links(FB_CFG, "P", "2026-04-20", "a@x.com")
    assert links.yes_url != links.no_url
    from urllib.parse import quote
    # Choice-question pre-fill values are wrapped in literal double quotes
    # (Forms' JSON-string pre-fill format) — confirmed against a real
    # "Get pre-filled link" export.
    assert quote(f'"{FB_CFG["answer_yes"]}"') in links.yes_url
    assert quote(f'"{FB_CFG["answer_no"]}"') in links.no_url


def test_build_ack_links_answer_value_is_quoted_for_choice_question():
    links = build_ack_links(FB_CFG, "P", "2026-04-20", "a@x.com")
    assert "%22Yes" in links.yes_url
    assert 'this%22&' in links.yes_url


def test_build_ack_links_appends_with_ampersand_when_query_present():
    cfg = {**FB_CFG, "form_url": FB_CFG["form_url"] + "?x=1"}
    links = build_ack_links(cfg, "P", "2026-04-20", "a@x.com")
    assert "?x=1&r1=" in links.yes_url


# ── load_responses ───────────────────────────────────────────────────────────

def test_load_responses_basic():
    token_yes = encode_token("P", "2026-04-13", "manager.a@graphicpkg.com")
    token_no = encode_token("P", "2026-04-13", "manager.b@graphicpkg.com")
    content = _workbook(
        [
            {
                FB_CFG["col_token"]: token_yes,
                FB_CFG["col_answer"]: FB_CFG["answer_yes"],
                FB_CFG["col_comment"]: "",
                FB_CFG["col_submitted"]: "2026-04-14 08:00:00",
            },
            {
                FB_CFG["col_token"]: token_no,
                FB_CFG["col_answer"]: FB_CFG["answer_no"],
                FB_CFG["col_comment"]: "Already fixed last month",
                FB_CFG["col_submitted"]: "2026-04-14 09:00:00",
            },
        ]
    )
    df = load_responses(content, FB_CFG)
    assert len(df) == 2
    assert set(df["answer"]) == {"Yes", "No"}
    assert df[df["email"] == "manager.b@graphicpkg.com"]["comment"].iloc[0] == "Already fixed last month"


def test_load_responses_drops_malformed_tokens():
    content = _workbook(
        [
            {
                FB_CFG["col_token"]: "not-a-real-token",
                FB_CFG["col_answer"]: FB_CFG["answer_yes"],
                FB_CFG["col_comment"]: "",
                FB_CFG["col_submitted"]: "2026-04-14 08:00:00",
            },
        ]
    )
    df = load_responses(content, FB_CFG)
    assert len(df) == 0


def test_load_responses_missing_columns_raises():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Some Other Column"])
    ws.append(["value"])
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="missing required columns"):
        load_responses(buf.getvalue(), FB_CFG)


# ── last_ack_for ──────────────────────────────────────────────────────────────

def test_last_ack_for_none_when_no_responses_df():
    assert last_ack_for(None, "P", "a@x.com", "2026-04-20") is None


def test_last_ack_for_no_response_recorded():
    df = pd.DataFrame(columns=["token", "kind", "period_start", "email", "answer", "comment", "submitted_at"])
    result = last_ack_for(df, "P", "manager.a@graphicpkg.com", "2026-04-20")
    assert isinstance(result, LastAck)
    assert result.answered is False
    assert "No response" in result.phrase


def test_last_ack_for_looks_up_prior_week():
    df = pd.DataFrame(
        [
            {
                "token": "x", "kind": "P", "period_start": "2026-04-13",
                "email": "manager.a@graphicpkg.com", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "P", "manager.a@graphicpkg.com", "2026-04-20")
    assert result.answered is True
    assert result.answer == "Yes"
    assert "acknowledged" in result.phrase


def test_last_ack_for_no_answer_phrase():
    df = pd.DataFrame(
        [
            {
                "token": "x", "kind": "P", "period_start": "2026-04-13",
                "email": "manager.a@graphicpkg.com", "answer": "No",
                "comment": "not relevant", "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "P", "manager.a@graphicpkg.com", "2026-04-20")
    assert result.answered is True
    assert result.answer == "No"
    assert "not relevant" in result.phrase


def test_last_ack_for_ignores_wrong_kind():
    # A regional manager's "R" ack must not satisfy a plant "P" lookup for the same email/week.
    df = pd.DataFrame(
        [
            {
                "token": "x", "kind": "R", "period_start": "2026-04-13",
                "email": "shared@graphicpkg.com", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "P", "shared@graphicpkg.com", "2026-04-20")
    assert result.answered is False


def test_last_ack_for_duplicate_submission_takes_latest():
    df = pd.DataFrame(
        [
            {
                "token": "x1", "kind": "P", "period_start": "2026-04-13",
                "email": "manager.a@graphicpkg.com", "answer": "No",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
            {
                "token": "x2", "kind": "P", "period_start": "2026-04-13",
                "email": "manager.a@graphicpkg.com", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 10:00:00",
            },
        ]
    )
    result = last_ack_for(df, "P", "manager.a@graphicpkg.com", "2026-04-20")
    assert result.answer == "Yes"


def test_last_ack_for_month_boundary():
    df = pd.DataFrame(
        [
            {
                "token": "x", "kind": "P", "period_start": "2026-04-27",
                "email": "manager.a@graphicpkg.com", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-28 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "P", "manager.a@graphicpkg.com", "2026-05-04")
    assert result.answered is True


# ── ack_stats ─────────────────────────────────────────────────────────────────

def test_ack_stats_none_df():
    assert ack_stats(None, "2026-04-20") == (0, 0)


def test_ack_stats_counts_distinct_current_week():
    df = pd.DataFrame(
        [
            {"token": "a", "kind": "P", "period_start": "2026-04-20", "email": "m.a@x.com",
             "answer": "Yes", "comment": None, "submitted_at": "t1"},
            {"token": "b", "kind": "P", "period_start": "2026-04-20", "email": "m.b@x.com",
             "answer": "No", "comment": None, "submitted_at": "t2"},
            {"token": "c", "kind": "P", "period_start": "2026-04-13", "email": "m.c@x.com",
             "answer": "Yes", "comment": None, "submitted_at": "t3"},
        ]
    )
    responded, _ = ack_stats(df, "2026-04-20")
    assert responded == 2
