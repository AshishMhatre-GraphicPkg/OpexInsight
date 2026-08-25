"""Parse and summarise PMComplianceDump.xlsx per machine — pure, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import pandas as pd

_REQUIRED_COLUMNS = {"WC Object ID", "Core PM", "Urgency"}


@dataclass
class PMCoreSummary:
    core_pm: str
    overdue_count: int


@dataclass
class PMSummary:
    total_overdue: int
    by_core_pm: list[PMCoreSummary] = field(default_factory=list)


def load_pm_compliance(content: bytes) -> pd.DataFrame:
    """Parse Sheet2 of PMComplianceDump.xlsx and return a normalised DataFrame."""
    df = pd.read_excel(BytesIO(content), sheet_name=1, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"PMComplianceDump.xlsx missing required columns: {missing}")

    df["WC Object ID"] = df["WC Object ID"].astype(str).str.strip()
    df["Core PM"] = df["Core PM"].astype(str).str.strip()
    df["Urgency"] = pd.to_numeric(df["Urgency"], errors="coerce").fillna(0).astype(int)

    return df


def build_pm_summary_for_machine(
    df: pd.DataFrame,
    wc_object_id: str,
) -> PMSummary | None:
    """Return a PMSummary for one machine (Urgency=1 rows only), or None if none exist."""
    mask = (df["WC Object ID"] == str(wc_object_id).strip()) & (df["Urgency"] == 1)
    filtered = df[mask]
    if filtered.empty:
        return None

    counts = (
        filtered.groupby("Core PM", sort=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    by_core_pm = [
        PMCoreSummary(core_pm=str(row["Core PM"]), overdue_count=int(row["count"]))
        for _, row in counts.iterrows()
    ]

    return PMSummary(
        total_overdue=int(mask.sum()),
        by_core_pm=by_core_pm,
    )
