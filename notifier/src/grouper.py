"""Group MachineWeekSummary rows by Manager_Email into ManagerDigest objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from .findings import FindingsSummary
    from .pm_compliance import PMSummary

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
_COL_DRIVER_PARENT = "Driver_Parent_Name"
_COL_DRIVER_SHEETS = "Driver_Parent_Sheets"
_COL_OUTCOME1_CUR = "Outcome_1_Cur_Actual"
_COL_OUTCOME1_BSP = "Outcome_1_BSP_Benchmark"

_OVERVIEW_LEVER_LABELS = {"Downtime Reason": "Downtime"}

_LEVER_FIELDS = ("Name", "Reasons", "Sheets", "Gap_Pct", "Streak", "Parent_Outcome", "Cur_Actual", "BSP_Benchmark")

_PERCENT_LEVERS = {
    "OEE",
    "Downtime %", "Scrap Loss",
    "Downtime Reason",
}

_LOWER_IS_BETTER_LEVERS = {
    "Downtime %", "Scrap Loss", "Avg MR Time",
    "Downtime Reason",
    "Avg Blanket Wash Time", "Avg Feeder Trip Time",
}

_TIME_HOURS_LEVERS = {"Avg MR Time", "Avg Blanket Wash Time", "Avg Feeder Trip Time"}


def _format_kpi_value(name: str, val) -> str:
    if val is None or (hasattr(val, "__float__") and pd.isna(val)):
        return ""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)
    if name in _PERCENT_LEVERS:
        return f"{v * 100:.2f}%"
    if name in _TIME_HOURS_LEVERS:
        return f"{v * 60:,.0f} Mins"
    if name == "Speed":
        return f"{v:,.0f}"
    return f"{v:,.2f}"


def _streak_direction(name: str) -> str:
    return "above BSP" if name in _LOWER_IS_BETTER_LEVERS else "below BSP"


@dataclass
class LeverSummary:
    name: str
    reasons: str | None
    sheets: float
    gap_pct: float
    streak: int
    parent_outcome: str
    cur_actual: str
    bsp_benchmark: str
    streak_direction: str


@dataclass
class MachineSummary:
    plant_wc: str
    department: str
    period_start: str
    total_sheet_impact: float
    outcome_1: str | None
    outcome_1_sheets: float | None
    outcome_1_cur_actual: float | None = None
    outcome_1_bsp_benchmark: float | None = None
    driver_parent: str | None = None
    driver_parent_sheets: float | None = None
    levers: list[LeverSummary] = field(default_factory=list)
    findings: FindingsSummary | None = None
    pm_summary: PMSummary | None = None


@dataclass
class MoverRow:
    plant_wc: str
    total_sheet_impact: float
    top_lever: str | None
    cur_oee: float | None = None
    bsp_oee: float | None = None


@dataclass
class OverviewSummary:
    total_sheets: float
    machines_impacted: int
    top_driver_name: str | None
    top_driver_sheets: float | None
    top_movers: list[MoverRow]
    maint_open: int
    maint_priority10: int
    maint_overdue_pm: int

    @property
    def has_maintenance(self) -> bool:
        return self.maint_open > 0 or self.maint_priority10 > 0 or self.maint_overdue_pm > 0


@dataclass
class ManagerDigest:
    manager_email: str
    cc_list: str | None
    period_start: str
    machines: list[MachineSummary] = field(default_factory=list)
    overview: OverviewSummary | None = None


def _build_overview(machines: list) -> OverviewSummary:
    total_sheets = sum(m.total_sheet_impact for m in machines)
    machines_impacted = sum(1 for m in machines if m.total_sheet_impact > 0)

    lever_totals: dict[str, float] = {}
    for m in machines:
        if m.levers:
            lv = m.levers[0]
            lever_totals[lv.name] = lever_totals.get(lv.name, 0.0) + lv.sheets
    if lever_totals:
        top_driver_name = max(lever_totals, key=lambda k: lever_totals[k])
        top_driver_sheets: float | None = lever_totals[top_driver_name]
    else:
        top_driver_name = None
        top_driver_sheets = None

    top_movers = [
        MoverRow(
            plant_wc=m.plant_wc,
            total_sheet_impact=m.total_sheet_impact,
            top_lever=_OVERVIEW_LEVER_LABELS.get(m.levers[0].name, m.levers[0].name) if m.levers else None,
            cur_oee=m.outcome_1_cur_actual,
            bsp_oee=m.outcome_1_bsp_benchmark,
        )
        for m in machines
        if m.total_sheet_impact > 0
    ]

    maint_open = sum(m.findings.total_open for m in machines if m.findings)
    maint_p10 = sum(m.findings.high_priority_count for m in machines if m.findings)
    maint_pm = sum(m.pm_summary.total_overdue for m in machines if m.pm_summary)

    return OverviewSummary(
        total_sheets=total_sheets,
        machines_impacted=machines_impacted,
        top_driver_name=top_driver_name,
        top_driver_sheets=top_driver_sheets,
        top_movers=top_movers,
        maint_open=maint_open,
        maint_priority10=maint_p10,
        maint_overdue_pm=maint_pm,
    )


def _nan_to_none(val):
    if pd.isna(val):
        return None
    return val


def _build_levers(row: pd.Series) -> list[LeverSummary]:
    levers = []
    for i in (1, 2, 3, 4, 5):
        name = _nan_to_none(row.get(f"Lever_{i}_Name"))
        if name is None:
            break
        lever_name = str(name).strip()
        levers.append(
            LeverSummary(
                name=lever_name,
                reasons=_nan_to_none(row.get(f"Lever_{i}_Reasons")),
                sheets=float(row.get(f"Lever_{i}_Sheets", 0) or 0),
                gap_pct=float(row.get(f"Lever_{i}_Gap_Pct", 0) or 0),
                streak=int(row.get(f"Lever_{i}_Streak", 0) or 0),
                parent_outcome=str(row.get(f"Lever_{i}_Parent_Outcome", "") or ""),
                cur_actual=_format_kpi_value(lever_name, row.get(f"Lever_{i}_Cur_Actual")),
                bsp_benchmark=_format_kpi_value(lever_name, row.get(f"Lever_{i}_BSP_Benchmark")),
                streak_direction=_streak_direction(lever_name),
            )
        )
    return levers


def group_by_manager(
    df: pd.DataFrame,
    findings_df: pd.DataFrame | None = None,
    pm_df: pd.DataFrame | None = None,
) -> list[ManagerDigest]:
    """Return one ManagerDigest per unique Manager_Email, ordered by Total_Sheet_Impact DESC.

    findings_df: optional pre-parsed Findings.csv DataFrame from findings.load_findings().
    When supplied, attaches a FindingsSummary to each MachineSummary.
    """
    if _COL_MANAGER not in df.columns:
        raise ValueError(f"CSV missing column '{_COL_MANAGER}'")

    required = {_COL_TOTAL, _COL_PLANT_WC, _COL_PERIOD}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {sorted(missing)}\n"
            f"Columns present: {sorted(df.columns.tolist())}\n"
            "The Qlik app may need to be reloaded with the latest script."
        )

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

            machine_pm = None
            if pm_df is not None:
                from .pm_compliance import build_pm_summary_for_machine
                wc_id = str(row.get("WC Object ID", ""))
                machine_pm = build_pm_summary_for_machine(pm_df, wc_id)

            driver_parent = _nan_to_none(row.get(_COL_DRIVER_PARENT))
            driver_sheets_raw = row.get(_COL_DRIVER_SHEETS)
            cur_actual_raw = _nan_to_none(row.get(_COL_OUTCOME1_CUR))
            bsp_raw = _nan_to_none(row.get(_COL_OUTCOME1_BSP))
            machines.append(
                MachineSummary(
                    plant_wc=str(row[_COL_PLANT_WC]),
                    department=str(row.get(_COL_DEPT, "")),
                    period_start=str(row[_COL_PERIOD]),
                    total_sheet_impact=float(row.get(_COL_TOTAL, 0) or 0),
                    outcome_1=_nan_to_none(row.get(_COL_O1_NAME)),
                    outcome_1_sheets=float(row[_COL_O1_SHEETS]) if _nan_to_none(row.get(_COL_O1_SHEETS)) is not None else None,
                    outcome_1_cur_actual=float(cur_actual_raw) if cur_actual_raw is not None else None,
                    outcome_1_bsp_benchmark=float(bsp_raw) if bsp_raw is not None else None,
                    driver_parent=str(driver_parent) if driver_parent else None,
                    driver_parent_sheets=float(driver_sheets_raw) if _nan_to_none(driver_sheets_raw) is not None else None,
                    levers=levers,
                    findings=machine_findings,
                    pm_summary=machine_pm,
                )
            )

        digests.append(
            ManagerDigest(
                manager_email=str(email),
                cc_list=str(cc) if cc else None,
                period_start=period,
                machines=machines,
                overview=_build_overview(machines),
            )
        )

    log.info("Grouped %d machines into %d manager digests", len(df), len(digests))
    return digests
