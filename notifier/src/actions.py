"""Resolve a lever/department to plant-facing action guidance — pure, no I/O.

Reads the static `Reason_Category_Action_Lookup.xlsx` reference file (shipped
with the package under `data/`, not fetched from SharePoint — this table
doesn't change week to week the way MachineWeekSummary/Findings/PM does).

The lookup covers the 8 main levers (Speed, Downtime %, Scrap Loss, Avg MR
Time, Avg Blanket Wash Time, Avg Feeder Trip Time, Blanket Washes per 10K,
Feeder Trips per 10K), each carrying up to 3 Common Contributing Factor /
Typical Actions pairs, scoped to a specific Department. A Downtime Reason
sub-lever (e.g. "0002-Paperboard") has no row of its own — it resolves via
its parent outcome ("Downtime %") instead, whose row carries the lookup's
generic "review with maintenance" guidance.

Loaded once via lru_cache. Any failure to load or resolve degrades to a
generic action rather than raising — `build_machine()` is shared by both the
plant-manager and regional groupers, so an exception here would break both
digests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "data" / "Reason_Category_Action_Lookup.xlsx"
_SHEET_NAME = "Reason Lookup"

_COL_KEY = "Lever / Reason"
_COL_DEPARTMENT = "Department"
_COL_CATEGORY = "Category"
_COL_FACTOR = ["Common Contributing Factor 1", "Common Contributing Factor 2", "Common Contributing Factor 3"]
_COL_ACTION = ["Typical Actions 1", "Typical Actions 2", "Typical Actions 3"]

# A Downtime Reason sub-lever (Lever_N_Name == "Downtime Reason") has no row
# of its own in the lookup — it resolves via its parent outcome instead.
_DOWNTIME_REASON_NAME = "downtime reason"
_DOWNTIME_PARENT_DEFAULT = "Downtime %"

# Prefix of the (legacy) lookup's own "not yet mapped" placeholder. Kept as a
# guard in case a future row reintroduces this sentinel; inert against the
# current 8-row file.
_SENTINEL_PREFIX = "Reason not yet mapped to a specific theme"
_GENERIC_ACTION = (
    "Review this event with the operator and maintenance to confirm "
    "the root cause before the next run."
)

_unmapped_count = 0
_lookup_count = 0


@dataclass
class FactorAction:
    factor: str
    action: str


@dataclass
class ActionGuidance:
    category: str
    action: str
    is_generic: bool
    pairs: list[FactorAction] = field(default_factory=list)


_GENERIC_GUIDANCE = ActionGuidance(category="", action=_GENERIC_ACTION, is_generic=True, pairs=[])


def _clean(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip()


@lru_cache(maxsize=1)
def load_action_lookup(path: Path | None = None) -> dict[tuple[str, str], tuple[str, list[FactorAction]]]:
    """Load the lookup as {(department.lower(), lever.lower()): (category, pairs)}.

    A pair is dropped only when both its factor and its action are blank
    (a row may legitimately have a blank factor with a non-blank action,
    e.g. the Downtime % row's single generic-review action). Cached after
    first call.
    """
    p = path or _DEFAULT_PATH
    try:
        df = pd.read_excel(p, sheet_name=_SHEET_NAME, engine="openpyxl")
    except Exception:
        log.exception("Failed to load action lookup from %s — all actions will be generic", p)
        return {}

    df = df.rename(columns=lambda c: str(c).strip())
    required = {_COL_KEY, _COL_DEPARTMENT, _COL_CATEGORY, *_COL_FACTOR, *_COL_ACTION}
    missing = required - set(df.columns)
    if missing:
        log.error("Action lookup %s missing columns: %s", p, missing)
        return {}

    table: dict[tuple[str, str], tuple[str, list[FactorAction]]] = {}
    for _, row in df.iterrows():
        lever = _clean(row[_COL_KEY])
        department = _clean(row[_COL_DEPARTMENT])
        if not lever or not department:
            continue

        pairs: list[FactorAction] = []
        for factor_col, action_col in zip(_COL_FACTOR, _COL_ACTION):
            factor = _clean(row[factor_col])
            action = _clean(row[action_col])
            if not factor and not action:
                continue
            pairs.append(FactorAction(factor=factor, action=action))

        table[(department.lower(), lever.lower())] = (_clean(row[_COL_CATEGORY]), pairs)
    return table


def lookup_action(lever_name: str, department: str | None, parent_outcome: str | None = None) -> ActionGuidance:
    """Resolve action guidance for a lever.

    `lever_name` is Lever_N_Name. `department` is the machine's Department —
    matching is strict: a lever/department combination not in the lookup
    falls back to the generic action, even if the same lever matches under a
    different department. `parent_outcome` is Lever_N_Parent_Outcome, used
    only when `lever_name` is a Downtime Reason sub-lever, which has no row
    of its own.
    """
    global _unmapped_count, _lookup_count
    _lookup_count += 1

    name = (lever_name or "").strip()
    if name.lower() == _DOWNTIME_REASON_NAME:
        name = (parent_outcome or "").strip() or _DOWNTIME_PARENT_DEFAULT
    dept = (department or "").strip()

    table = load_action_lookup()
    entry = table.get((dept.lower(), name.lower()))

    if entry is None:
        _unmapped_count += 1
        log.debug("No action lookup match for lever %r / department %r", name, dept)
        return _GENERIC_GUIDANCE

    category, pairs = entry
    if not pairs:
        _unmapped_count += 1
        return ActionGuidance(category=category, action=_GENERIC_ACTION, is_generic=True, pairs=[])

    first_action = next((p.action for p in pairs if p.action), _GENERIC_ACTION)
    return ActionGuidance(category=category, action=first_action, is_generic=False, pairs=pairs)


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
