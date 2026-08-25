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
    manager_label_from_email,
    parse_token,
)

FB_CFG = {
    "enabled": True,
    "form_url": "https://forms.office.com/Pages/ResponsePage.aspx?id=ABC123",
    "param_answer": "r1",
    "param_token": "r2",
    "answer_yes": "Yes - we will action this",
    "answer_no": "No - not relevant this week",
    "col_token": "Reference (Do not edit)",
    "col_answer": "Will your plant action these insights this week?",
    "col_comment": "Anything we should know?",
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


# ── manager_label_from_email ────────────────────────────────────────────────

def test_manager_label_basic():
    assert manager_label_from_email("manager.a@graphicpkg.com") == "Manager A"


def test_manager_label_underscores_and_hyphens():
    assert manager_label_from_email("first_last-name@x.com") == "First Last Name"


def test_manager_label_plus_addressing():
    assert manager_label_from_email("ashish.mhatre+test@graphicpkg.com") == "Ashish Mhatre Test"


def test_manager_label_empty_string():
    assert manager_label_from_email("") == ""


def test_manager_label_no_local_words_falls_back_to_email():
    assert manager_label_from_email("@x.com") == "@x.com"


# ── token round-trip ─────────────────────────────────────────────────────────

def test_encode_parse_round_trip():
    token = encode_token("Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert parse_token(token) == ("Elk Grove", "Gluer", "2026-04-20", "Manager A")


def test_encode_parse_round_trip_regional():
    token = encode_token("Region", "All Plants", "2026-04-20", "Ann Lee")
    assert parse_token(token) == ("Region", "All Plants", "2026-04-20", "Ann Lee")


def test_encode_strips_embedded_pipe_so_field_count_stays_four():
    token = encode_token("Elk Grove | Annex", "Gluer", "2026-04-20", "Manager A")
    parsed = parse_token(token)
    assert parsed is not None
    assert len(token.split("|")) == 4


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "Elk Grove|Gluer|2026-04-20",  # missing manager label (only 3 fields)
        42,
    ],
)
def test_parse_token_malformed_returns_none(bad):
    assert parse_token(bad) is None


def test_parse_token_empty_period_returns_none():
    assert parse_token("Elk Grove|Gluer||Manager A") is None


def test_parse_token_empty_department_is_valid():
    # Only period_start is required to be non-empty; plant/department/manager
    # can theoretically be blank (e.g. a digest with no resolvable plant).
    assert parse_token("Elk Grove||2026-04-20|Manager A") == ("Elk Grove", "", "2026-04-20", "Manager A")


# ── build_ack_links ───────────────────────────────────────────────────────────

def test_build_ack_links_none_when_no_config():
    assert build_ack_links(None, "Elk Grove", "Gluer", "2026-04-20", "Manager A") is None


def test_build_ack_links_none_when_disabled():
    cfg = {**FB_CFG, "enabled": False}
    assert build_ack_links(cfg, "Elk Grove", "Gluer", "2026-04-20", "Manager A") is None


def test_build_ack_links_none_when_form_url_blank():
    cfg = {**FB_CFG, "form_url": ""}
    assert build_ack_links(cfg, "Elk Grove", "Gluer", "2026-04-20", "Manager A") is None


def test_build_ack_links_encodes_token_and_pipe():
    links = build_ack_links(FB_CFG, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert isinstance(links, AckLinks)
    token = encode_token("Elk Grove", "Gluer", "2026-04-20", "Manager A")
    from urllib.parse import quote
    assert quote(token) in links.yes_url
    assert quote(token) in links.no_url
    assert "%7C" in links.yes_url  # URL-encoded '|'


def test_build_ack_links_default_labels_are_plain_yes_no():
    links = build_ack_links(FB_CFG, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert links.yes_label == "Yes"
    assert links.no_label == "No"


def test_build_ack_links_custom_labels_from_config():
    cfg = {**FB_CFG, "yes_button_label": "Confirm", "no_button_label": "Skip"}
    links = build_ack_links(cfg, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert links.yes_label == "Confirm"
    assert links.no_label == "Skip"


def test_build_ack_links_yes_no_answers_differ():
    links = build_ack_links(FB_CFG, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert links.yes_url != links.no_url
    from urllib.parse import quote
    # Choice-question pre-fill values are wrapped in literal double quotes
    # (Forms' JSON-string pre-fill format) — confirmed against a real
    # "Get pre-filled link" export.
    assert quote(f'"{FB_CFG["answer_yes"]}"') in links.yes_url
    assert quote(f'"{FB_CFG["answer_no"]}"') in links.no_url


def test_build_ack_links_answer_value_is_quoted_for_choice_question():
    links = build_ack_links(FB_CFG, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert "%22Yes" in links.yes_url
    assert 'this%22&' in links.yes_url


def test_build_ack_links_appends_with_ampersand_when_query_present():
    cfg = {**FB_CFG, "form_url": FB_CFG["form_url"] + "?x=1"}
    links = build_ack_links(cfg, "Elk Grove", "Gluer", "2026-04-20", "Manager A")
    assert "?x=1&r1=" in links.yes_url


# ── load_responses ───────────────────────────────────────────────────────────

def test_load_responses_basic():
    token_yes = encode_token("Elk Grove", "Gluer", "2026-04-13", "Manager A")
    token_no = encode_token("Chicago", "Sheetfed Printing", "2026-04-13", "Manager B")
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
    assert df[df["manager_label"] == "Manager B"]["comment"].iloc[0] == "Already fixed last month"
    assert df[df["manager_label"] == "Manager A"]["plant"].iloc[0] == "Elk Grove"


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
    assert last_ack_for(None, "Elk Grove", "Gluer", "Manager A", "2026-04-20") is None


def test_last_ack_for_no_response_recorded():
    df = pd.DataFrame(columns=["token", "plant", "department", "period_start", "manager_label", "answer", "comment", "submitted_at"])
    result = last_ack_for(df, "Elk Grove", "Gluer", "Manager A", "2026-04-20")
    assert isinstance(result, LastAck)
    assert result.answered is False
    assert "No response" in result.phrase


def test_last_ack_for_looks_up_prior_week():
    df = pd.DataFrame(
        [
            {
                "token": "x", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-13",
                "manager_label": "Manager A", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Elk Grove", "Gluer", "Manager A", "2026-04-20")
    assert result.answered is True
    assert result.answer == "Yes"
    assert "acknowledged" in result.phrase


def test_last_ack_for_no_answer_phrase():
    df = pd.DataFrame(
        [
            {
                "token": "x", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-13",
                "manager_label": "Manager A", "answer": "No",
                "comment": "not relevant", "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Elk Grove", "Gluer", "Manager A", "2026-04-20")
    assert result.answered is True
    assert result.answer == "No"
    assert "not relevant" in result.phrase


def test_last_ack_for_ignores_different_plant_department():
    # A regional manager's "Region/All Plants" ack must not satisfy a plant
    # manager's lookup for the same person/week, and vice versa.
    df = pd.DataFrame(
        [
            {
                "token": "x", "plant": "Region", "department": "All Plants", "period_start": "2026-04-13",
                "manager_label": "Shared Person", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Elk Grove", "Gluer", "Shared Person", "2026-04-20")
    assert result.answered is False


def test_last_ack_for_duplicate_submission_takes_latest():
    df = pd.DataFrame(
        [
            {
                "token": "x1", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-13",
                "manager_label": "Manager A", "answer": "No",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
            {
                "token": "x2", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-13",
                "manager_label": "Manager A", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 10:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Elk Grove", "Gluer", "Manager A", "2026-04-20")
    assert result.answer == "Yes"


def test_last_ack_for_month_boundary():
    df = pd.DataFrame(
        [
            {
                "token": "x", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-27",
                "manager_label": "Manager A", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-28 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Elk Grove", "Gluer", "Manager A", "2026-05-04")
    assert result.answered is True


def test_last_ack_for_regional_uses_region_placeholder():
    df = pd.DataFrame(
        [
            {
                "token": "x", "plant": "Region", "department": "All Plants", "period_start": "2026-04-13",
                "manager_label": "Ann Lee", "answer": "Yes",
                "comment": None, "submitted_at": "2026-04-14 08:00:00",
            },
        ]
    )
    result = last_ack_for(df, "Region", "All Plants", "Ann Lee", "2026-04-20")
    assert result.answered is True


# ── ack_stats ─────────────────────────────────────────────────────────────────

def test_ack_stats_none_df():
    assert ack_stats(None, "2026-04-20") == (0, 0)


def test_ack_stats_counts_distinct_tokens_current_week():
    df = pd.DataFrame(
        [
            {"token": "a", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-20",
             "manager_label": "Manager A", "answer": "Yes", "comment": None, "submitted_at": "t1"},
            {"token": "b", "plant": "Chicago", "department": "Sheetfed Printing", "period_start": "2026-04-20",
             "manager_label": "Manager B", "answer": "No", "comment": None, "submitted_at": "t2"},
            {"token": "c", "plant": "Elk Grove", "department": "Gluer", "period_start": "2026-04-13",
             "manager_label": "Manager A", "answer": "Yes", "comment": None, "submitted_at": "t3"},
        ]
    )
    responded, _ = ack_stats(df, "2026-04-20")
    assert responded == 2
