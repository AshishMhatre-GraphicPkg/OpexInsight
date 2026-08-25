"""Group MachineWeekSummary rows by Manager_Email into ManagerDigest objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

from . import actions

from . import feedback as feedback_mod

if TYPE_CHECKING:
    from .findings import FindingsSummary
    from .pm_compliance import PMSummary
    from .feedback import AckLinks, LastAck

log = logging.getLogger(__name__)

# V2 manager digest: number of top-impact machines that get a full 3-card
# (Who/Why/How) treatment; the rest are rolled into a compact "also impacted" list.
FOCUS_MACHINE_COUNT = 3

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
_COL_RM_EMAIL = "Regional_Manager_Email"
_COL_RM_NAME = "Regional_Manager_Name"
_COL_MATCH_LEVEL = "Routing_Match_Level"

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
    "Blanket Washes per 10K", "Feeder Trips per 10K",
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


# Streak_4wk on a Downtime Reason lever is a count of weeks (of the last 4)
# whose rate exceeded BSP (InsightOpexv1.qvs Section 41B). On every other
# lever, Streak is a run of consecutive weeks each worse than the week before
# (InsightOpexv1.qvs:1828-1868, Peek()-based) — not a comparison to BSP and not
# capped to a fixed window. The two are different measurements; the wording
# below says only what each one actually supports.
_BSP_COUNT_STREAK_LEVERS = {"Downtime Reason"}


def _streak_phrase(name: str, streak: int, direction: str) -> str:
    if name in _BSP_COUNT_STREAK_LEVERS:
        verb = "Above" if direction == "above BSP" else "Below"
        if streak <= 0:
            return f"First week {verb.lower()} benchmark in the last 4."
        if streak >= 4:
            return f"{verb} benchmark in all 4 of the last 4 weeks."
        return f"{verb} benchmark in {streak} of the last 4 weeks."

    verb = "Below" if direction == "below BSP" else "Above"
    if streak <= 0:
        return f"{verb} benchmark this week — watch next week."
    if streak == 1:
        return "Trending worse — first week worse than last."
    if streak >= 4:
        return "Trending worse for 4+ weeks straight — needs attention."
    return f"Trending worse for {streak} weeks straight — needs attention."


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
    streak_phrase: str = ""
    action: str = ""
    action_is_generic: bool = False
    action_pairs: list[actions.FactorAction] = field(default_factory=list)


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
    plant: str | None = None
    wc_object_id: str | None = None


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
    maint_missing_wo: int = 0

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
    ack: AckLinks | None = None
    last_ack: LastAck | None = None

    @property
    def focus_machines(self) -> list[MachineSummary]:
        """Top FOCUS_MACHINE_COUNT impacted machines — get the full 3-card treatment.

        `machines` is already sorted Total_Sheet_Impact DESC (group_by_manager),
        so this is a slice, not a re-sort or re-selection.
        """
        return [m for m in self.machines if m.total_sheet_impact > 0][:FOCUS_MACHINE_COUNT]

    @property
    def other_machines(self) -> list[MachineSummary]:
        """Remaining impacted machines beyond the focus set — name + sheets only."""
        return [m for m in self.machines if m.total_sheet_impact > 0][FOCUS_MACHINE_COUNT:]


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
    maint_missing_wo = sum(m.findings.total_missing_wo for m in machines if m.findings)

    return OverviewSummary(
        total_sheets=total_sheets,
        machines_impacted=machines_impacted,
        top_driver_name=top_driver_name,
        top_driver_sheets=top_driver_sheets,
        top_movers=top_movers,
        maint_open=maint_open,
        maint_priority10=maint_p10,
        maint_overdue_pm=maint_pm,
        maint_missing_wo=maint_missing_wo,
    )


def _nan_to_none(val):
    if pd.isna(val):
        return None
    return val


def _unique_join(values: list[str], max_items: int = 3) -> str:
    """Summarise a digest's plant/department values for the feedback token:
    the single value if all machines agree, a joined list of up to
    max_items, or "Multiple" beyond that. A manager who covers several
    plants/departments therefore gets a stable-but-summarised token, not one
    per machine — the acknowledgement loop is digest-level, not per-machine.
    """
    uniq: list[str] = []
    for v in values:
        if v and v not in uniq:
            uniq.append(v)
    if not uniq:
        return ""
    if len(uniq) <= max_items:
        return " / ".join(uniq)
    return "Multiple"


def _build_levers(row: pd.Series) -> list[LeverSummary]:
    department = str(row.get(_COL_DEPT, "") or "")
    levers = []
    for i in (1, 2, 3, 4, 5):
        name = _nan_to_none(row.get(f"Lever_{i}_Name"))
        if name is None:
            break
        lever_name = str(name).strip()
        reasons = _nan_to_none(row.get(f"Lever_{i}_Reasons"))
        streak = int(row.get(f"Lever_{i}_Streak", 0) or 0)
        direction = _streak_direction(lever_name)
        parent_outcome = str(row.get(f"Lever_{i}_Parent_Outcome", "") or "")
        guidance = actions.lookup_action(lever_name, department, parent_outcome)
        levers.append(
            LeverSummary(
                name=lever_name,
                reasons=reasons,
                sheets=float(row.get(f"Lever_{i}_Sheets", 0) or 0),
                gap_pct=float(row.get(f"Lever_{i}_Gap_Pct", 0) or 0),
                streak=streak,
                parent_outcome=parent_outcome,
                cur_actual=_format_kpi_value(lever_name, row.get(f"Lever_{i}_Cur_Actual")),
                bsp_benchmark=_format_kpi_value(lever_name, row.get(f"Lever_{i}_BSP_Benchmark")),
                streak_direction=direction,
                streak_phrase=_streak_phrase(lever_name, streak, direction),
                action=guidance.action,
                action_is_generic=guidance.is_generic,
                action_pairs=guidance.pairs,
            )
        )
    return levers


def build_machine(
    row: pd.Series,
    findings_df: pd.DataFrame | None = None,
    pm_df: pd.DataFrame | None = None,
) -> MachineSummary:
    """Build a single MachineSummary from one MachineWeekSummary.csv row.

    Shared by group_by_manager() and regional.group_by_regional_manager() so
    both digest types build machines identically.
    """
    levers = _build_levers(row)
    plant = str(row.get("Plant", ""))
    wc_id = str(row.get("WC Object ID", ""))

    machine_findings = None
    if findings_df is not None:
        from .findings import build_summary_for_machine
        machine_findings = build_summary_for_machine(
            findings_df, plant, wc_id, [lv.name for lv in levers]
        )

    machine_pm = None
    if pm_df is not None:
        from .pm_compliance import build_pm_summary_for_machine
        machine_pm = build_pm_summary_for_machine(pm_df, wc_id)

    driver_parent = _nan_to_none(row.get(_COL_DRIVER_PARENT))
    driver_sheets_raw = row.get(_COL_DRIVER_SHEETS)
    cur_actual_raw = _nan_to_none(row.get(_COL_OUTCOME1_CUR))
    bsp_raw = _nan_to_none(row.get(_COL_OUTCOME1_BSP))
    return MachineSummary(
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
        plant=plant or None,
        wc_object_id=wc_id or None,
    )


def group_by_manager(
    df: pd.DataFrame,
    findings_df: pd.DataFrame | None = None,
    pm_df: pd.DataFrame | None = None,
    feedback_cfg: dict | None = None,
    responses_df: pd.DataFrame | None = None,
) -> list[ManagerDigest]:
    """Return one ManagerDigest per unique Manager_Email, ordered by Total_Sheet_Impact DESC.

    findings_df: optional pre-parsed Findings.csv DataFrame from findings.load_findings().
    When supplied, attaches a FindingsSummary to each MachineSummary.

    feedback_cfg / responses_df: optional acknowledgement-loop config and
    parsed responses (feedback.load_responses()). When feedback_cfg is
    absent/disabled, ManagerDigest.ack and .last_ack stay None and the
    templates omit the block entirely.
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

        machines = [build_machine(row, findings_df, pm_df) for _, row in group.iterrows()]
        ack_plant = _unique_join([m.plant for m in machines if m.plant])
        ack_dept = _unique_join([m.department for m in machines if m.department])
        ack_manager_label = feedback_mod.manager_label_from_email(str(email))

        digests.append(
            ManagerDigest(
                manager_email=str(email),
                cc_list=str(cc) if cc else None,
                period_start=period,
                machines=machines,
                overview=_build_overview(machines),
                ack=feedback_mod.build_ack_links(feedback_cfg, ack_plant, ack_dept, period, ack_manager_label),
                last_ack=feedback_mod.last_ack_for(responses_df, ack_plant, ack_dept, ack_manager_label, period),
            )
        )

    log.info("Grouped %d machines into %d manager digests", len(df), len(digests))
    return digests
