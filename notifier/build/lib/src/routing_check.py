"""Detect Plant+Department rows that fell back to plant-level manager routing.

Qlik Section 49 stamps a Routing_Match_Level column ('Department' | 'Plant' |
'None') onto every MachineWeekSummary.csv row, based on whether the row's
Plant+Department pair was found in PlantManagers.xlsx. This module surfaces
those fallbacks so an admin alert can point at the workbook rows that need
fixing, instead of the mismatch silently persisting.
"""

from __future__ import annotations

import pandas as pd

_COL_PLANT = "Plant"
_COL_DEPT = "Department"
_COL_MATCH_LEVEL = "Routing_Match_Level"


def find_routing_mismatches(df: pd.DataFrame) -> list[str]:
    """Return one human-readable line per unique Plant+Department pair that
    did not resolve at the Department level.

    Returns [] when Routing_Match_Level is absent (older CSV) or when every
    row matched at the Department level.
    """
    if _COL_MATCH_LEVEL not in df.columns:
        return []

    required = {_COL_PLANT, _COL_DEPT}
    if not required.issubset(df.columns):
        return []

    mismatched = df[df[_COL_MATCH_LEVEL] != "Department"]
    if mismatched.empty:
        return []

    pairs = (
        mismatched[[_COL_PLANT, _COL_DEPT, _COL_MATCH_LEVEL]]
        .drop_duplicates()
        .sort_values([_COL_PLANT, _COL_DEPT])
    )

    lines = []
    for _, row in pairs.iterrows():
        level = row[_COL_MATCH_LEVEL]
        if level == "Plant":
            lines.append(f"Plant {row[_COL_PLANT]} / {row[_COL_DEPT]} — fell back to plant-level routing")
        else:
            lines.append(f"Plant {row[_COL_PLANT]} / {row[_COL_DEPT]} — no manager routing found (Manager_Email is null)")
    return lines
