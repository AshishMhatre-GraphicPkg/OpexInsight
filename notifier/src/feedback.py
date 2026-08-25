"""Digest acknowledgement loop — pure, no I/O.

A manager's response is captured by a Microsoft Form whose pre-filled URL
carries a plain-text reference token identifying exactly which digest the
click came from. Forms writes responses to an Excel workbook on the same
SharePoint site the notifier already reads with `Sites.Read.All` — no new
Azure permission, no hosting, no inbound HTTP surface. See
notifier/CLAUDE.md for the Form setup runbook.

Token format: "<plant>|<department>|<period_start>|<manager label>", e.g.
"Elk Grove|Gluer|2026-04-20|Manager A" — human-readable in the Excel
Reference column, and also the exact key used to match a response back to
"last week's digest" for a given manager. A digest can span more than one
plant/department (a manager covering several); in that case the plant/
department fields are a joined summary (see grouper._unique_join), which
means the token for a given manager is stable week to week only as long as
their machine set doesn't change shape — documented, not a hidden gotcha.

`manager label` is NOT a real display name — MachineWeekSummary.csv only
carries Manager_Email (Regional_Manager_Name exists for regional digests,
but there is no Manager_Name equivalent for plant digests). It is derived
from the email's local part via manager_label_from_email() as a readable
stand-in (e.g. "manager.a@company.com" -> "Manager A"). Wiring a real name
through would mean stamping Manager_Name onto MachineWeekSummary.csv in
InsightOpexv1.qvs Section 49, mirroring how Regional_Manager_Name already
works — not done here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from urllib.parse import quote

import pandas as pd

_TOKEN_SEP = "|"
_TOKEN_FIELDS = ("plant", "department", "period_start", "manager_label")


@dataclass
class AckLinks:
    yes_url: str
    no_url: str
    yes_label: str
    no_label: str


@dataclass
class LastAck:
    answered: bool
    answer: str | None  # "Yes" | "No" | None
    submitted_at: str | None
    phrase: str


def manager_label_from_email(email: str) -> str:
    """Best-effort readable label from an email's local part, e.g.
    "manager.a@company.com" -> "Manager A". Not a real display name — see
    module docstring."""
    local = (email or "").split("@", 1)[0]
    words = [w for w in re.split(r"[._\-+]+", local) if w]
    return " ".join(w.capitalize() for w in words) if words else (email or "")


def _clean(value: str) -> str:
    """Strip and neutralise the token separator so a stray '|' in a plant/
    department name can't corrupt the field count on parse."""
    return str(value or "").strip().replace(_TOKEN_SEP, "/")


def encode_token(plant: str, department: str, period_start: str, manager_label: str) -> str:
    return _TOKEN_SEP.join(
        _clean(v) for v in (plant, department, period_start, manager_label)
    )


def parse_token(token: str) -> tuple[str, str, str, str] | None:
    """Return (plant, department, period_start, manager_label), or None if
    the token is malformed."""
    if not isinstance(token, str):
        return None
    parts = token.strip().split(_TOKEN_SEP)
    if len(parts) != 4:
        return None
    plant, department, period_start, manager_label = parts
    if not period_start:
        return None
    return plant, department, period_start, manager_label


def build_ack_links(
    fb_cfg: dict | None,
    plant: str,
    department: str,
    period_start: str,
    manager_label: str,
) -> AckLinks | None:
    """Build the Yes/No pre-filled Form URLs for one digest, or None when the
    feedback loop is unconfigured/disabled — callers and templates then omit
    the block entirely, so the feature is off by default."""
    if not fb_cfg or not fb_cfg.get("enabled"):
        return None
    form_url = fb_cfg.get("form_url")
    param_answer = fb_cfg.get("param_answer")
    param_token = fb_cfg.get("param_token")
    answer_yes = fb_cfg.get("answer_yes")
    answer_no = fb_cfg.get("answer_no")
    if not all([form_url, param_answer, param_token, answer_yes, answer_no]):
        return None

    token = encode_token(plant, department, period_start, manager_label)
    sep = "&" if "?" in form_url else "?"

    def _url(answer: str) -> str:
        # Forms' pre-fill format wraps a Choice question's value in literal
        # double quotes (a JSON string), unlike a plain Text question — the
        # "Reference" token below is a Text question and stays unquoted.
        # Confirmed against a real "Get pre-filled link" export.
        return (
            f'{form_url}{sep}{param_answer}={quote(chr(34) + answer + chr(34))}'
            f"&{param_token}={quote(token)}"
        )

    return AckLinks(
        yes_url=_url(answer_yes),
        no_url=_url(answer_no),
        yes_label=fb_cfg.get("yes_button_label", "Yes"),
        no_label=fb_cfg.get("no_button_label", "No"),
    )


_RESPONSE_COLUMNS = ["token", *_TOKEN_FIELDS, "answer", "comment", "submitted_at"]


def load_responses(content: bytes, fb_cfg: dict) -> pd.DataFrame:
    """Parse the Forms results workbook into a normalised DataFrame with
    columns token, plant, department, period_start, manager_label, answer,
    comment, submitted_at. Rows whose token doesn't parse are dropped
    (malformed data never crashes the run, it's just excluded)."""
    sheet = fb_cfg.get("responses_sheet", 0)
    df = pd.read_excel(BytesIO(content), sheet_name=sheet, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    col_token = fb_cfg.get("col_token", "Reference (Do not edit)")
    col_answer = fb_cfg.get("col_answer", "Will your plant action these insights this week?")
    col_comment = fb_cfg.get("col_comment", "Anything we should know?")
    col_submitted = fb_cfg.get("col_submitted", "Completion time")

    missing = {col_token, col_answer} - set(df.columns)
    if missing:
        raise ValueError(f"Feedback responses workbook missing required columns: {missing}")

    answer_yes = fb_cfg.get("answer_yes", "")

    rows = []
    for _, row in df.iterrows():
        parsed = parse_token(row.get(col_token))
        if parsed is None:
            continue
        plant, department, period_start, manager_label = parsed
        raw_answer = row.get(col_answer)
        answer = "Yes" if str(raw_answer).strip() == answer_yes else "No"
        rows.append(
            {
                "token": str(row[col_token]),
                "plant": plant,
                "department": department,
                "period_start": period_start,
                "manager_label": manager_label,
                "answer": answer,
                "comment": row.get(col_comment) if col_comment in df.columns else None,
                "submitted_at": str(row[col_submitted]) if col_submitted in df.columns else None,
            }
        )

    return pd.DataFrame(rows, columns=_RESPONSE_COLUMNS)


def _prior_period(period_start: str) -> str | None:
    try:
        return (pd.to_datetime(period_start) - timedelta(days=7)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def last_ack_for(
    responses_df: pd.DataFrame | None,
    plant: str,
    department: str,
    manager_label: str,
    period_start: str,
) -> LastAck | None:
    """Look up whether this (plant, department, manager) acknowledged the
    PRIOR week's digest. Returns None when the feedback loop wasn't live
    that week (responses_df is None) so templates render nothing rather
    than a misleading "no response" on the very first run.

    Matching is by exact (plant, department, manager_label) string equality
    against a freshly-recomputed token, so it only finds a match if the
    digest's plant/department summary is unchanged from the prior week —
    see module docstring."""
    if responses_df is None:
        return None

    prior = _prior_period(period_start)
    if prior is None:
        return None

    matches = responses_df[
        (responses_df["plant"] == plant)
        & (responses_df["department"] == department)
        & (responses_df["manager_label"] == manager_label)
        & (responses_df["period_start"] == prior)
    ]
    if matches.empty:
        return LastAck(
            answered=False,
            answer=None,
            submitted_at=None,
            phrase="No response recorded for last week's digest.",
        )

    # Most recent submission wins if a manager responded more than once.
    if "submitted_at" in matches.columns and matches["submitted_at"].notna().any():
        matches = matches.sort_values("submitted_at")
    latest = matches.iloc[-1]

    if latest["answer"] == "Yes":
        phrase = "You acknowledged last week's digest and confirmed you'd action it."
    else:
        phrase = "You marked last week's digest as not relevant."

    return LastAck(
        answered=True,
        answer=str(latest["answer"]),
        submitted_at=str(latest["submitted_at"]) if pd.notna(latest.get("submitted_at")) else None,
        phrase=phrase,
    )


def ack_stats(responses_df: pd.DataFrame | None, period_start: str) -> tuple[int, int]:
    """Return (responded, expected) counts for THIS week's period, for a
    single admin log line. `expected` is left as 0 here — callers that know
    the digest count should compute the ratio themselves; this just counts
    distinct tokens recorded for the current period."""
    if responses_df is None or responses_df.empty:
        return 0, 0
    this_week = responses_df[responses_df["period_start"] == period_start]
    responded = this_week["token"].drop_duplicates().shape[0]
    return responded, 0
