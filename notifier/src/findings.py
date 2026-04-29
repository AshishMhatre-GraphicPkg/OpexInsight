"""Parse and summarise Findings.csv per machine — pure, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

HIGH_PRIORITY_THRESHOLD = 10

# Maps G.Section values to keywords found in lever names.
# Extend this dict once the full G.Section value list is known.
SECTION_TO_LEVER_KEYWORDS: dict[str, list[str]] = {
    "Feeder":    ["feeder"],
    "Platen":    ["platen", "die cut"],
    "Stripping": ["stripping", "strip"],
    "Blanking":  ["blanking", "blank"],
}

_STATUS_MISSING_WO = "Missing WO"
_STATUS_OPEN = "Open"

# Raw CSV column → internal name
_RENAMES = {
    "Plant":                         "plant",
    "G.WCobjectID":                  "wc_object_id",
    "G.Section":                     "section",
    "G.Priority":                    "priority",
    "G.WorkOrder":                   "work_order",
    "GC Allowed Days":               "allowed_days",
    "Expected Findings Date":        "date",
    "GC Work Order Status":          "status",
}


@dataclass
class SectionStat:
    section: str
    open_count: int
    missing_wo_count: int
    overdue_count: int
    max_priority: int
    is_corroborated: bool


@dataclass
class FindingsSummary:
    total_open: int
    total_missing_wo: int
    total_overdue: int
    high_priority_count: int
    corroborated_sections: list[str]
    by_section: list[SectionStat] = field(default_factory=list)


def load_findings(csv_bytes: bytes) -> pd.DataFrame:
    """Parse Findings.csv bytes and return a normalised DataFrame."""
    df = pd.read_csv(pd.io.common.BytesIO(csv_bytes))
    df = df.rename(columns={k: v for k, v in _RENAMES.items() if k in df.columns})
    if "plant" in df.columns:
        df["plant"] = df["plant"].astype(str)
    if "wc_object_id" in df.columns:
        df["wc_object_id"] = df["wc_object_id"].astype(str)
    if "priority" in df.columns:
        df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(0).astype(int)
    if "allowed_days" in df.columns:
        df["allowed_days"] = pd.to_numeric(df["allowed_days"], errors="coerce").fillna(0)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "status" in df.columns:
        df["status"] = df["status"].fillna("").astype(str).str.strip()
    return df


def _flag_overdue(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    df = df.copy()
    as_of_ts = pd.Timestamp(as_of)
    elapsed = (as_of_ts - df["date"]).dt.days
    df["is_overdue"] = elapsed > df["allowed_days"]
    return df


def _is_section_corroborated(section: str, lever_names: list[str]) -> bool:
    keywords = SECTION_TO_LEVER_KEYWORDS.get(section, [])
    if not keywords:
        return False
    for lever in lever_names:
        lever_lower = lever.lower()
        for kw in keywords:
            if kw in lever_lower:
                return True
    return False


def _match_to_levers(df: pd.DataFrame, lever_names: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["is_corroborated"] = df["section"].apply(
        lambda s: _is_section_corroborated(str(s), lever_names)
    )
    return df


def build_summary_for_machine(
    df_all: pd.DataFrame,
    plant: str,
    wc_object_id: str,
    lever_names: list[str],
    as_of: date | None = None,
) -> FindingsSummary | None:
    """Return a FindingsSummary for one machine, or None if no findings exist."""
    if as_of is None:
        as_of = date.today()

    mask = (df_all["plant"] == str(plant)) & (df_all["wc_object_id"] == str(wc_object_id))
    df = df_all[mask].copy()
    if df.empty:
        return None

    df = _flag_overdue(df, as_of)
    df = _match_to_levers(df, lever_names)

    is_open = df["status"] == _STATUS_OPEN
    is_missing = df["status"] == _STATUS_MISSING_WO

    total_open = int(is_open.sum())
    total_missing_wo = int(is_missing.sum())
    total_overdue = int(df["is_overdue"].sum())
    high_priority_count = int((df["priority"] >= HIGH_PRIORITY_THRESHOLD).sum())

    by_section: list[SectionStat] = []
    for section, grp in df.groupby("section", sort=False):
        s_open = int((grp["status"] == _STATUS_OPEN).sum())
        s_missing = int((grp["status"] == _STATUS_MISSING_WO).sum())
        s_overdue = int(grp["is_overdue"].sum())
        s_max_priority = int(grp["priority"].max())
        s_corroborated = bool(grp["is_corroborated"].any())
        by_section.append(
            SectionStat(
                section=str(section),
                open_count=s_open,
                missing_wo_count=s_missing,
                overdue_count=s_overdue,
                max_priority=s_max_priority,
                is_corroborated=s_corroborated,
            )
        )

    # Sort: (missing_wo + overdue) DESC, max_priority DESC
    by_section.sort(key=lambda s: (s.missing_wo_count + s.overdue_count, s.max_priority), reverse=True)

    corroborated_sections = [s.section for s in by_section if s.is_corroborated]

    return FindingsSummary(
        total_open=total_open,
        total_missing_wo=total_missing_wo,
        total_overdue=total_overdue,
        high_priority_count=high_priority_count,
        corroborated_sections=corroborated_sections,
        by_section=by_section,
    )
