"""Resolve a lever/reason to plant-facing action guidance — pure, no I/O.

Reads the static `Reason_Category_Action_Lookup.xlsx` reference file (shipped
with the package under `data/`, not fetched from SharePoint — this table
doesn't change week to week the way MachineWeekSummary/Findings/PM do).

Loaded once via lru_cache. Any failure to load or resolve degrades to a
generic action rather than raising — `build_machine()` is shared by both the
plant-manager and regional groupers, so an exception here would break both
digests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "data" / "Reason_Category_Action_Lookup.xlsx"
_SHEET_NAME = "Reason Lookup"

_COL_KEY = "Lever / Reason"
_COL_CATEGORY = "Category"
_COL_ACTION = "How the Plant Team Can Help"

# Prefix of the lookup's own "not yet mapped" placeholder (532 of 2006 rows).
# Its trailing clause ("...then refine this row's category and action") is
# aimed at whoever maintains the lookup, not the plant manager reading the
# email, so it is swapped for plant-facing wording instead of rendered as-is.
_SENTINEL_PREFIX = "Reason not yet mapped to a specific theme"
_GENERIC_ACTION = (
    "Review this event with the operator and maintenance to confirm "
    "the root cause before the next run."
)

_unmapped_count = 0
_lookup_count = 0


@dataclass
class ActionGuidance:
    category: str
    action: str
    is_generic: bool


_GENERIC_GUIDANCE = ActionGuidance(category="", action=_GENERIC_ACTION, is_generic=True)


@lru_cache(maxsize=1)
def load_action_lookup(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """Load the lookup as {key.lower(): (category, action)}. Cached after first call."""
    p = path or _DEFAULT_PATH
    try:
        df = pd.read_excel(p, sheet_name=_SHEET_NAME, engine="openpyxl")
    except Exception:
        log.exception("Failed to load action lookup from %s — all actions will be generic", p)
        return {}

    df = df.rename(columns=lambda c: str(c).strip())
    missing = {_COL_KEY, _COL_CATEGORY, _COL_ACTION} - set(df.columns)
    if missing:
        log.error("Action lookup %s missing columns: %s", p, missing)
        return {}

    table: dict[str, tuple[str, str]] = {}
    for _, row in df.iterrows():
        key = str(row[_COL_KEY]).strip()
        if not key:
            continue
        table[key.lower()] = (str(row[_COL_CATEGORY]).strip(), str(row[_COL_ACTION]).strip())
    return table


def lookup_action(reason_key: str | None, fallback_key: str) -> ActionGuidance:
    """Resolve action guidance for a lever.

    `reason_key` is Lever_N_Reasons (may be None/blank); `fallback_key` is
    Lever_N_Name, used when there is no specific reason (e.g. Speed, Avg MR
    Time). Exact match first, then case-insensitive.
    """
    global _unmapped_count, _lookup_count
    _lookup_count += 1

    key = (reason_key or fallback_key or "").strip()
    table = load_action_lookup()
    entry = table.get(key.lower())

    if entry is None:
        _unmapped_count += 1
        log.debug("No action lookup match for key %r", key)
        return _GENERIC_GUIDANCE

    category, action = entry
    if action.startswith(_SENTINEL_PREFIX):
        _unmapped_count += 1
        return ActionGuidance(category=category, action=_GENERIC_ACTION, is_generic=True)

    return ActionGuidance(category=category, action=action, is_generic=False)


def log_unmapped_summary() -> None:
    """Log how many lookups fell back to the generic action this run."""
    if _lookup_count:
        log.info("%d of %d lever actions had no mapped guidance (generic fallback used)",
                  _unmapped_count, _lookup_count)


def reset_unmapped_counter() -> None:
    """Reset run-scoped counters — call at the start of each notifier run/test."""
    global _unmapped_count, _lookup_count
    _unmapped_count = 0
    _lookup_count = 0
