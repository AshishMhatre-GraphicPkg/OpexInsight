"""Group MachineWeekSummary rows by Manager_Email into ManagerDigest objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .findings import FindingsSummary

log = logging.getLogger(__name__)

# CSV column names (match Qlik STORE output)
_COL_MANAGER = "Manager_Email"
_COL_CC = "CC_List"
_COL_PLANT_WC = "Plant - WC"
_COL_DEPT = "Department"
_COL_PERIOD = "Period_Start"
_COL_TOTAL = "Total_Sheet_Impact"
_COL_O1_NAME = "Outcome_1_Name"
_COL_O1_SHEETS = "Outcome_1_Sheets"
_COL_O2_NAME = "Outcome_2_Name"
_COL_O2_SHEETS = "Outcome_2_Sheets"

_LEVER_FIELDS = ("Name", "Reasons", "Sheets", "Gap_Pct", "Streak", "Parent_Outcome")


@dataclass
class LeverSummary:
    name: str
    reasons: str | None
    sheets: float
    gap_pct: float
    streak: int
    parent_outcome: str


@dataclass
class MachineSummary:
    plant_wc: str
    department: str
    period_start: str
    total_sheet_impact: float
    outcome_1: str | None
    outcome_1_sheets: float | None
    outcome_2: str | None
    outcome_2_sheets: float | None
    levers: list[LeverSummary] = field(default_factory=list)
    findings: FindingsSummary | None = None


@dataclass
class ManagerDigest:
    manager_email: str
    cc_list: str | None
    period_start: str
    machines: list[MachineSummary] = field(default_factory=list)


def _nan_to_none(val):
    if pd.isna(val):
        return None
    return val


def _build_levers(row: pd.Series) -> list[LeverSummary]:
    levers = []
    for i in (1, 2, 3):
        name = _nan_to_none(row.get(f"Lever_{i}_Name"))
        if name is None:
            break
        levers.append(
            LeverSummary(
                name=str(name),
                reasons=_nan_to_none(row.get(f"Lever_{i}_Reasons")),
                sheets=float(row.get(f"Lever_{i}_Sheets", 0) or 0),
                gap_pct=float(row.get(f"Lever_{i}_Gap_Pct", 0) or 0),
                streak=int(row.get(f"Lever_{i}_Streak", 0) or 0),
                parent_outcome=str(row.get(f"Lever_{i}_Parent_Outcome", "") or ""),
            )
        )
    return levers


def group_by_manager(df: pd.DataFrame, findings_df: pd.DataFrame | None = None) -> list[ManagerDigest]:
    """Return one ManagerDigest per unique Manager_Email, ordered by Total_Sheet_Impact DESC.

    findings_df: optional pre-parsed Findings.csv DataFrame from findings.load_findings().
    When supplied, attaches a FindingsSummary to each MachineSummary.
    """
    if _COL_MANAGER not in df.columns:
        raise ValueError(f"CSV missing column '{_COL_MANAGER}'")

    df = df.sort_values(_COL_TOTAL, ascending=False)
    digests: list[ManagerDigest] = []

    for email, group in df.groupby(_COL_MANAGER, sort=False):
        if pd.isna(email) or str(email).strip() == "":
            log.warning("Skipping %d rows with no Manager_Email", len(group))
            continue

        cc = _nan_to_none(group[_COL_CC].iloc[0]) if _COL_CC in group.columns else None
        period = str(group[_COL_PERIOD].iloc[0])

        machines = []
        for _, row in group.iterrows():
            levers = _build_levers(row)
            machine_findings = None
            if findings_df is not None:
                from .findings import build_summary_for_machine
                plant = str(row.get("Plant", ""))
                wc_id = str(row.get("WC Object ID", ""))
                machine_findings = build_summary_for_machine(
                    findings_df, plant, wc_id, [lv.name for lv in levers]
                )
            machines.append(
                MachineSummary(
                    plant_wc=str(row[_COL_PLANT_WC]),
                    department=str(row.get(_COL_DEPT, "")),
                    period_start=str(row[_COL_PERIOD]),
                    total_sheet_impact=float(row.get(_COL_TOTAL, 0) or 0),
                    outcome_1=_nan_to_none(row.get(_COL_O1_NAME)),
                    outcome_1_sheets=float(row[_COL_O1_SHEETS]) if _nan_to_none(row.get(_COL_O1_SHEETS)) is not None else None,
                    outcome_2=_nan_to_none(row.get(_COL_O2_NAME)),
                    outcome_2_sheets=float(row[_COL_O2_SHEETS]) if _nan_to_none(row.get(_COL_O2_SHEETS)) is not None else None,
                    levers=levers,
                    findings=machine_findings,
                )
            )

        digests.append(
            ManagerDigest(
                manager_email=str(email),
                cc_list=str(cc) if cc else None,
                period_start=period,
                machines=machines,
            )
        )

    log.info("Grouped %d machines into %d manager digests", len(df), len(digests))
    return digests
