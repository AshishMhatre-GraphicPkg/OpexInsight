"""Digest acknowledgement loop — pure, no I/O.

A manager's response is captured by a Microsoft Form whose pre-filled URL
carries a plain-text reference token identifying exactly which digest (kind +
week + recipient) the click came from. Forms writes responses to an Excel
workbook on the same SharePoint site the notifier already reads with
`Sites.Read.All` — no new Azure permission, no hosting, no inbound HTTP
surface. See notifier/CLAUDE.md for the Form setup runbook.

Token format: "<kind>|<period_start>|<email>", e.g. "P|2026-04-20|a@x.com".
`kind` is "P" (plant digest) or "R" (regional digest) — the prefix exists so
a person who is both a plant and a regional manager never collides across
the two digest types for the same week.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from urllib.parse import quote

import pandas as pd

_TOKEN_SEP = "|"
_VALID_KINDS = {"P", "R"}


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


def encode_token(kind: str, period_start: str, email: str) -> str:
    if kind not in _VALID_KINDS:
        raise ValueError(f"Unknown feedback kind: {kind!r}")
    return f"{kind}{_TOKEN_SEP}{period_start}{_TOKEN_SEP}{email}"


def parse_token(token: str) -> tuple[str, str, str] | None:
    """Return (kind, period_start, email), or None if the token is malformed."""
    if not isinstance(token, str):
        return None
    parts = token.strip().split(_TOKEN_SEP, maxsplit=2)
    if len(parts) != 3:
        return None
    kind, period_start, email = parts
    if kind not in _VALID_KINDS or not period_start or not email:
        return None
    return kind, period_start, email


def build_ack_links(
    fb_cfg: dict | None,
    kind: str,
    period_start: str,
    email: str,
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

    token = encode_token(kind, period_start, email)
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
        yes_label=fb_cfg.get("yes_button_label", "Yes — we'll action this"),
        no_label=fb_cfg.get("no_button_label", "No — not relevant"),
    )


_RESPONSE_COLUMNS = ["token", "kind", "period_start", "email", "answer", "comment", "submitted_at"]


def load_responses(content: bytes, fb_cfg: dict) -> pd.DataFrame:
    """Parse the Forms results workbook into a normalised DataFrame with columns
    token, kind, period_start, email, answer, comment, submitted_at.
    Rows whose token doesn't parse are dropped (malformed data never crashes
    the run, it's just excluded)."""
    sheet = fb_cfg.get("responses_sheet", 0)
    df = pd.read_excel(BytesIO(content), sheet_name=sheet, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    col_token = fb_cfg.get("col_token", "Reference (do not edit)")
    col_answer = fb_cfg.get("col_answer", "Will your plant action these insights this week?")
    col_comment = fb_cfg.get("col_comment", "Anything we should know? (optional)")
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
        kind, period_start, email = parsed
        raw_answer = row.get(col_answer)
        answer = "Yes" if str(raw_answer).strip() == answer_yes else "No"
        rows.append(
            {
                "token": str(row[col_token]),
                "kind": kind,
                "period_start": period_start,
                "email": email,
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
    kind: str,
    email: str,
    period_start: str,
) -> LastAck | None:
    """Look up whether `email` acknowledged the PRIOR week's digest of this
    kind. Returns None when the feedback loop wasn't live that week
    (responses_df is None) so templates render nothing rather than a
    misleading "no response" on the very first run."""
    if responses_df is None:
        return None

    prior = _prior_period(period_start)
    if prior is None:
        return None

    matches = responses_df[
        (responses_df["kind"] == kind)
        & (responses_df["email"] == email)
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
    distinct (kind, email) responses recorded for the current period."""
    if responses_df is None or responses_df.empty:
        return 0, 0
    this_week = responses_df[responses_df["period_start"] == period_start]
    responded = this_week[["kind", "email"]].drop_duplicates().shape[0]
    return responded, 0
