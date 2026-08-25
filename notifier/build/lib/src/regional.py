"""Group MachineWeekSummary rows by Regional_Manager_Email into RegionalDigest objects.

Regional managers own several plants and/or departments. Their digest is a
high-level synopsis — region KPI tiles, a plant roll-up, and per-department
top-N tables — not the per-machine lever detail plant managers get.

Pure module: no I/O. Reuses grouper.build_machine() so a machine is built
identically whether it ends up in a plant digest or a regional digest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from .grouper import (
    MachineSummary,
    MoverRow,
    _OVERVIEW_LEVER_LABELS,
    _nan_to_none,
    build_machine,
)

log = logging.getLogger(__name__)

_COL_RM_EMAIL = "Regional_Manager_Email"
_COL_RM_NAME = "Regional_Manager_Name"
_COL_PLANT = "Plant"
_COL_DEPT = "Department"
_COL_PERIOD = "Period_Start"
_COL_TOTAL = "Total_Sheet_Impact"
_COL_PLANT_WC = "Plant - WC"

_DEFAULT_TOP_N = 3


@dataclass
class PlantRollup:
    plant: str
    sheets: float
    machines_impacted: int
    worst_machine: str | None
    worst_machine_sheets: float | None


@dataclass
class DepartmentSection:
    department: str
    sheets: float
    machines_impacted: int
    plants_count: int
    top_machines: list[MoverRow] = field(default_factory=list)


@dataclass
class RegionalDigest:
    regional_manager_email: str
    regional_manager_name: str | None
    period_start: str
    total_sheets: float
    plants_covered: int
    machines_impacted: int
    top_driver_name: str | None
    top_driver_sheets: float | None
    maint_open: int
    maint_priority10: int
    maint_overdue_pm: int
    plant_rollups: list[PlantRollup] = field(default_factory=list)
    departments: list[DepartmentSection] = field(default_factory=list)

    @property
    def has_maintenance(self) -> bool:
        return self.maint_open > 0 or self.maint_priority10 > 0 or self.maint_overdue_pm > 0


def _plant_rollup(plant: str, machines: list[MachineSummary]) -> PlantRollup:
    sheets = sum(m.total_sheet_impact for m in machines)
    impacted = [m for m in machines if m.total_sheet_impact > 0]
    worst = max(impacted, key=lambda m: m.total_sheet_impact, default=None)
    return PlantRollup(
        plant=plant,
        sheets=sheets,
        machines_impacted=len(impacted),
        worst_machine=worst.plant_wc if worst else None,
        worst_machine_sheets=worst.total_sheet_impact if worst else None,
    )


def _department_section(
    department: str, entries: list[tuple[MachineSummary, str]], top_n: int
) -> DepartmentSection:
    machines = [m for m, _ in entries]
    sheets = sum(m.total_sheet_impact for m in machines)
    impacted = [m for m in machines if m.total_sheet_impact > 0]
    plants = {plant for _, plant in entries}

    top_sorted = sorted(impacted, key=lambda m: m.total_sheet_impact, reverse=True)[:top_n]
    top_machines = [
        MoverRow(
            plant_wc=m.plant_wc,
            total_sheet_impact=m.total_sheet_impact,
            top_lever=_OVERVIEW_LEVER_LABELS.get(m.levers[0].name, m.levers[0].name) if m.levers else None,
            cur_oee=m.outcome_1_cur_actual,
            bsp_oee=m.outcome_1_bsp_benchmark,
        )
        for m in top_sorted
    ]

    return DepartmentSection(
        department=department,
        sheets=sheets,
        machines_impacted=len(impacted),
        plants_count=len(plants),
        top_machines=top_machines,
    )


def group_by_regional_manager(
    df: pd.DataFrame,
    findings_df: pd.DataFrame | None = None,
    pm_df: pd.DataFrame | None = None,
    top_n: int = _DEFAULT_TOP_N,
) -> list[RegionalDigest]:
    """Return one RegionalDigest per unique Regional_Manager_Email, ordered by total sheets DESC.

    Returns [] (with a log message, not an exception) when Regional_Manager_Email
    is absent from the CSV — lets the notifier keep working against a
    MachineWeekSummary.csv produced before the Qlik reload that added it.
    """
    if _COL_RM_EMAIL not in df.columns:
        log.info(
            "CSV has no '%s' column — skipping regional digests "
            "(Qlik app may need reloading with the latest script)",
            _COL_RM_EMAIL,
        )
        return []

    required = {_COL_TOTAL, _COL_PLANT_WC, _COL_PERIOD, _COL_PLANT, _COL_DEPT}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV is missing required columns for regional digests: {sorted(missing)}\n"
            f"Columns present: {sorted(df.columns.tolist())}"
        )

    digests: list[RegionalDigest] = []

    for email, group in df.groupby(_COL_RM_EMAIL, sort=False):
        if pd.isna(email) or str(email).strip() == "":
            log.warning("Skipping %d rows with no Regional_Manager_Email", len(group))
            continue

        rm_name = None
        if _COL_RM_NAME in group.columns:
            rm_name = _nan_to_none(group[_COL_RM_NAME].iloc[0])
        period = str(group[_COL_PERIOD].iloc[0])

        machines = [build_machine(row, findings_df, pm_df) for _, row in group.iterrows()]
        plants_by_row = group[_COL_PLANT].astype(str).tolist()

        total_sheets = sum(m.total_sheet_impact for m in machines)
        impacted = [m for m in machines if m.total_sheet_impact > 0]

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

        maint_open = sum(m.findings.total_open for m in machines if m.findings)
        maint_p10 = sum(m.findings.high_priority_count for m in machines if m.findings)
        maint_pm = sum(m.pm_summary.total_overdue for m in machines if m.pm_summary)

        plant_groups: dict[str, list[MachineSummary]] = {}
        for m, plant_val in zip(machines, plants_by_row):
            plant_groups.setdefault(plant_val, []).append(m)
        plant_rollups = sorted(
            (_plant_rollup(plant, ms) for plant, ms in plant_groups.items()),
            key=lambda p: p.sheets,
            reverse=True,
        )

        dept_groups: dict[str, list[tuple[MachineSummary, str]]] = {}
        for m, plant_val in zip(machines, plants_by_row):
            dept_groups.setdefault(m.department, []).append((m, plant_val))
        departments = sorted(
            (_department_section(dept, entries, top_n) for dept, entries in dept_groups.items()),
            key=lambda d: d.sheets,
            reverse=True,
        )

        digests.append(
            RegionalDigest(
                regional_manager_email=str(email),
                regional_manager_name=str(rm_name) if rm_name else None,
                period_start=period,
                total_sheets=total_sheets,
                plants_covered=len(plant_groups),
                machines_impacted=len(impacted),
                top_driver_name=top_driver_name,
                top_driver_sheets=top_driver_sheets,
                maint_open=maint_open,
                maint_priority10=maint_p10,
                maint_overdue_pm=maint_pm,
                plant_rollups=plant_rollups,
                departments=departments,
            )
        )

    digests.sort(key=lambda d: d.total_sheets, reverse=True)
    log.info("Grouped %d machines into %d regional digests", len(df), len(digests))
    return digests
