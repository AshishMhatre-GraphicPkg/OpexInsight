# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

A Python email notifier that sends Monday-morning OEE Insight digests to
plant managers **and** high-level region synopses to regional managers. It
reads `MachineWeekSummary.csv` from SharePoint (written by Qlik Section 49),
checks freshness, fetches Maintenance Findings and PM Compliance data,
groups rows by `Manager_Email` (plant digests) and by `Regional_Manager_Email`
(regional digests), renders Jinja2 templates on the company brand theme
(Green `#006548` / Light Green `#76BC21` / Black `#3D3935`), and sends via
Microsoft Graph API.

`PlantManagers.xlsx` — the source of `Manager_Email` / `Regional_Manager_Email`
— is read by **Qlik** (Section 7B of `InsightOpexv1.qvs`), not by this
notifier. Its grain is one row per **Plant + Department**; see the "Routing"
section below.

---

## Commands

```bash
# Install (editable, with dev extras)
pip install -e ".[dev]"

# Dry run — renders per-manager HTML to out/preview/ and per-region HTML to
# out/preview/regional/, without sending
python main.py --dry-run

# Live send — plant digests + regional digests
python main.py

# Preview with real SharePoint data — no mail sent, HTML saved to
# out/test_preview/ (plant) and out/test_preview/regional/ (regional)
python test_without_mail.py --ignore-freshness

# Run tests
pytest tests/

# Run a single test file
pytest tests/test_grouper.py
pytest tests/test_regional.py
```

---

## Architecture

```
main.py                  # Orchestrator: fetch → freshness → findings → PM → routing check → group → render → send
test_without_mail.py     # Fetch real SharePoint data, render previews to out/test_preview/ — no mail sent
src/
  fetch.py               # Graph API: fetch_csv (with mtime), fetch_findings_csv, fetch_pm_xlsx
  freshness.py           # StaleDataError raised if CSV mtime > freshness_max_hours
  grouper.py             # build_machine(row, ...) → MachineSummary; group_by_manager(df, ...) → list[ManagerDigest]
  regional.py            # group_by_regional_manager(df, ...) → list[RegionalDigest]; reuses grouper.build_machine
  routing_check.py       # find_routing_mismatches(df) → list[str], from Routing_Match_Level
  findings.py            # Pure: load_findings(), build_summary_for_machine() → FindingsSummary | None
  pm_compliance.py       # Pure: load_pm_compliance(), build_pm_summary_for_machine() → PMSummary | None
  actions.py             # Pure: load_action_lookup(), lookup_action() → ActionGuidance (see "Manager digest V2" below)
  data/Reason_Category_Action_Lookup.xlsx  # Static reference table actions.py loads (shipped as package data)
  renderer.py            # Jinja2 wrappers: render_html/text, render_regional_html/text, render_admin_alert
  mailer.py              # Graph API: _post_with_retry (3 attempts, exp backoff), send_mail, send_admin_alert
  logging_setup.py       # configure() called once at startup
templates/
  _theme.j2               # Brand color/type tokens + shared Jinja macros. Imported by email.html.j2 (V2) via
                           # {% import '_theme.j2' as t %}; regional.html.j2 still hardcodes hex inline (not yet migrated).
  email.html.j2            # Per-manager HTML digest — V2: top-3-by-impact machines as Who/Why/How cards, rest
                            # rolled into one line, maintenance shown as plant-wide totals. See "Manager digest V2" below.
  email.txt.j2              # Plain-text mirror of email.html.j2
  regional.html.j2, regional.txt.j2  # Per-region synopsis: KPI tiles, plant roll-up, top-3-per-department tables (V1 design, unchanged)
  admin_alert.html.j2
  archive/                # Frozen pre-redesign templates kept for reference/rollback — see archive/README.md
tests/
  fixtures/sample_summary.csv            # 6 machines / 4 plant managers / 2 regional managers (see below)
  fixtures/sample_findings.csv           # 7 rows, 3 machines — Open/Missing WO/overdue/corroborated mix
  fixtures/sample_pm_compliance.xlsx     # Sheet1 blank; Sheet2: 7 rows, 3 machines, mixed Urgency
  test_grouper.py         # Unit tests for grouper (no network)
  test_regional.py        # Unit tests for regional grouping + routing mismatch detection (no network)
  test_findings.py        # Unit tests for findings module (no network)
  test_pm_compliance.py   # Unit tests for pm_compliance module (no network)
  test_actions.py         # Unit tests for the action lookup module (no network)
  test_renderer.py        # Assertion-style template tests, plant + regional (no network, no snapshots)
  test_freshness.py
config.yaml   # sharepoint_site_id, sharepoint_file_path, sharepoint_findings_path, sharepoint_pm_path,
              # sender_upn, admin_email, email_subject_prefix, regional_subject_prefix, regional_top_n
.env          # AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (gitignored)
```

**`tests/fixtures/sample_summary.csv` layout:** Elk Grove (Gluer, 2 machines)
and Chicago (Sheetfed Printing, 1 machine) route to `manager.a@company.com`
/ `manager.b@company.com` as before. Dallas (Gluer, 2 machines) and Denver
(Web Cutting, 1 machine) were added for regional-digest coverage, routing
to `manager.c@company.com` / `manager.d@company.com`. All six machines
share regional manager `regional.x@company.com` (Elk Grove, Chicago,
Dallas) except Denver, which is `regional.y@company.com` — giving the
Gluer department 4 impacted machines under regional.x (to exercise the
top-3-per-department cap) and one single-plant, single-department region
(regional.y) as a minimal case. Dallas's first row carries
`Routing_Match_Level = 'Plant'` to exercise the fallback-detection tests;
every other row is `'Department'`. Dallas/Denver machines intentionally
have no Findings.csv / PM rows — `test_findings.py` only asserts findings
presence for the original 3 machines.

### Data flow

```
SharePoint
  MachineWeekSummary.csv ──► fetch_csv ──► freshness check ──┬─► find_routing_mismatches ──► admin alert (non-fatal)
                                                              ├─► group_by_manager ─────────► ManagerDigest[]
                                                              └─► group_by_regional_manager ─► RegionalDigest[]
  Findings.csv ────────────► fetch_findings_csv ──► load_findings ──► findings_df ────────────────┤ (both groupers)
  PMComplianceDump.xlsx ───► fetch_pm_xlsx ──► load_pm_compliance ──► pm_df ───────────────────────┘ (both groupers)
                                                                                     │
                                                           build_machine() — shared by both groupers, calls:
                                                           build_summary_for_machine (findings, per machine)
                                                           build_pm_summary_for_machine (PM, per machine)
                                                                                     │
                                                           MachineSummary.findings: FindingsSummary | None
                                                           MachineSummary.pm_summary: PMSummary | None
                                                                                     │
                                                render_html/text ──► Graph /sendMail (plant, with CC)
                                                render_regional_html/text ──► Graph /sendMail (regional, no CC)
```

Findings, PM, and routing-fallback issues each send an admin alert but do **not** abort the run — plant digests render without the missing blocks, and regional digests still send even if some Plant+Department pairs fell back to plant-level routing.

### Routing columns (`grouper.py` / `regional.py` / `routing_check.py`)

Stamped onto every row by Qlik Section 49 from `PlantManagers.xlsx` (via
Section 7B), resolved at Plant+Department grain with a Plant-only fallback:

| Column | Notes |
|---|---|
| `Manager_Email`, `CC_List` | Plant manager routing — unchanged consumer (`group_by_manager`) |
| `Regional_Manager_Email`, `Regional_Manager_Name` | Regional manager routing — consumed by `group_by_regional_manager` |
| `Routing_Match_Level` | `'Department'` \| `'Plant'` \| `'None'` — which map resolved the row. Consumed by `find_routing_mismatches()`, not rendered in either email. |

### RegionalDigest schema (`regional.py`)

```python
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
    top_machines: list[MoverRow]   # grouper.MoverRow, capped to top_n (default 3), sheets DESC

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
    plant_rollups: list[PlantRollup]        # sheets DESC
    departments: list[DepartmentSection]    # sheets DESC

    @property
    def has_maintenance(self) -> bool: ...
```

`group_by_regional_manager(df, findings_df=None, pm_df=None, top_n=3)` builds
each machine via the same `grouper.build_machine()` plant digests use, then
rolls up by `Plant` and by `Department`. Returns `[]` (with a log message,
not an exception) when `Regional_Manager_Email` is absent from the CSV — a
CSV from before the Qlik reload that added it still lets plant digests send.
Maintenance is a single rolled-up count (open findings, priority-10 count,
overdue PMs) — no per-machine maintenance detail, unlike the plant digest's
full Maintenance Report table.

### MachineWeekSummary.csv schema (`grouper.py`)

One row per machine. Join key for findings is `Plant` + `WC Object ID`. Join key for PM compliance is `WC Object ID` only (see Plant format mismatch note below).

| Column | Notes |
|---|---|
| `Plant`, `WC Object ID` | Join keys for findings lookup |
| `Manager_Email`, `CC_List` | Routing; CC_List is semicolon-separated |
| `Plant - WC`, `Department`, `Period_Start` | Identity / display |
| `Total_Sheet_Impact` | OEE row's `Sheet_Impact` only — primary sort key (DESC). Levers ladder into OEE so summing all rows would double-count. |
| `Outcome_1_Name`, `Outcome_1_Sheets` | Single Outcome KPI (always OEE) — `Outcome_2_*` columns removed |
| `Lever_{1..5}_{Name,Reasons,Sheets,Gap_Pct,Streak,Parent_Outcome,Cur_Actual,BSP_Benchmark}` | Up to 5 levers after sub-reason swap (see below) |
| `Driver_Parent_Name` | `'Downtime %'` if it appeared in the original top-3 OEE levers; empty otherwise (Scrap Rate no longer triggers this) |
| `Driver_Parent_Sheets` | Sheet_Impact of the dominant driver parent; empty when `Driver_Parent_Name` is empty |

`_build_levers()` iterates `i in (1, 2, 3, 4, 5)` and stops at the first `Lever_N_Name` that is NaN — levers must be contiguous. Machines can have 2–5 levers depending on the sub-reason swap.

### Findings.csv schema (`findings.py`)

Daily-refreshed file at `sharepoint_findings_path`. `load_findings()` renames `G.*` prefixed columns to clean internal names.

| Raw column | Internal name | Notes |
|---|---|---|
| `Plant` | `plant` | Plant number — joins to MachineWeekSummary `Plant` |
| `G.WCobjectID` | `wc_object_id` | Joins to `WC Object ID` |
| `G.Section` | `section` | Machine section (Feeder, Platen, Stripping, Blanking, …) |
| `G.Priority` | `priority` | 1–10; `HIGH_PRIORITY_THRESHOLD = 10` |
| `GC Work Order Status` | `status` | `"Open"` or `"Missing WO"` |
| `GC Allowed Days` | `allowed_days` | Numeric; overdue when `elapsed_days > allowed_days` |
| `Expected Findings Date` | `date` | Parsed via `pd.to_datetime` |

### `FindingsSummary` dataclass (per machine)

```python
@dataclass
class SectionStat:
    section: str
    open_count: int
    missing_wo_count: int
    overdue_count: int
    max_priority: int
    is_corroborated: bool          # section keyword matches an active lever name

@dataclass
class FindingsSummary:
    total_open: int
    total_missing_wo: int
    total_overdue: int
    high_priority_count: int       # Priority >= HIGH_PRIORITY_THRESHOLD (10)
    corroborated_sections: list[str]
    by_section: list[SectionStat]  # sorted: (missing_wo + overdue) DESC, max_priority DESC
```

`build_summary_for_machine` returns `None` when no findings rows match — template omits the block entirely.

### PMComplianceDump.xlsx schema (`pm_compliance.py`)

Read from **Sheet2** only (`sheet_name=1`). `load_pm_compliance()` validates required columns and coerces types; no column renaming (names are used as-is).

| Column | Notes |
|---|---|
| `WC Object ID` | Join key — matched against MachineWeekSummary `WC Object ID` |
| `Core PM` | PM category (e.g. "Lubrication", "Inspection") |
| `Urgency` | Integer; only `Urgency = 1` rows are counted (3+ weeks past Allowed Days) |
| `Plant` | Present in file but **not used** in the join — see Plant format mismatch note |

**Plant format mismatch:** `PMComplianceDump.xlsx` stores Plant as a short int (`8`); `MachineWeekSummary.csv` uses zero-padded strings (`0008`). Plant is excluded from the join entirely — `WC Object ID` is unique across plants and is sufficient.

### `PMSummary` dataclass (per machine)

```python
@dataclass
class PMCoreSummary:
    core_pm: str
    overdue_count: int        # count of Urgency=1 rows for this Core PM

@dataclass
class PMSummary:
    total_overdue: int        # sum across all Core PMs
    by_core_pm: list[PMCoreSummary]   # sorted overdue_count DESC
```

`build_pm_summary_for_machine` returns `None` when no Urgency=1 rows match — template omits the block entirely.

### Section → Lever corroboration (`SECTION_TO_LEVER_KEYWORDS` in `findings.py`)

Maps `G.Section` values to keywords searched (case-insensitive) in lever names. Currently seeded with four sections; extend once the full `G.Section` value list is confirmed — no schema change needed.

```python
SECTION_TO_LEVER_KEYWORDS = {
    "Feeder":    ["feeder"],
    "Platen":    ["platen", "die cut"],
    "Stripping": ["stripping", "strip"],
    "Blanking":  ["blanking", "blank"],
}
```

### Key design decisions

- **`fetch.py` and `mailer.py` each acquire their own MSAL token** — no shared token object; each module is self-contained.
- **`findings.py` and `pm_compliance.py` are pure** — no I/O. Both follow the same contract: `load_X(bytes)` → DataFrame; `build_X_for_machine(df, …)` → dataclass or `None`. Tests call both directly with no network.
- **`grouper.py` is pure** — `findings_df=None` and `pm_df=None` make both optional; existing callers are unchanged. `MachineSummary` carries `outcome_1` / `outcome_1_sheets` (always OEE) and the new `driver_parent` / `driver_parent_sheets` fields (both `None` when Downtime % did not appear in the top-3 OEE levers for that machine).
- **Sub-lever swap rule** — Qlik Section 49 replaces each `Downtime %` occurrence in the top-3 OEE lever pool with up to 2 Downtime Reason sub-reasons before writing `MachineWeekSummary.csv`. Scrap Loss has no sub-reasons and passes through the swap unchanged. Python reads the already-swapped rows — there is no swap logic in Python. `Lever_N_Parent_Outcome` on a sub-reason row holds `'Downtime %'`. `Driver_Parent_Name` / `Driver_Parent_Sheets` are the email headline source — not derived from levers in Python.
- **Summary clause** — `email.html.j2` and `email.txt.j2` render "driven primarily by **\<driver_parent\>** (X sheets)" when `m.driver_parent` is non-null; the clause is omitted entirely otherwise. `Driver_Parent_Name` is only set when `Downtime %` drove the week.
- **Findings and PM failures are non-fatal** — each catches exceptions, sends an admin alert, and continues the digest without that block. Pattern reuses `send_admin_alert` at `mailer.py:85`.
- **PM join uses `WC Object ID` only** — Plant is excluded because PMComplianceDump stores it as a short int (`8`) while MachineWeekSummary uses zero-padded strings (`0008`). `WC Object ID` is unique across plants.
- **PM block placement** — in the V1 manager template (archived), an amber table rendered immediately below the Findings block within each per-machine card, suppressed when `pm_summary is None`. In V2, per-machine PM/findings detail is gone from the manager digest — `pm_summary` / `findings` still populate on every `MachineSummary` (used for the plant-wide maintenance totals and for the Card 3 corroboration note) but are no longer rendered per machine. `regional.py`'s regional digest never rendered per-machine PM detail either way.
- **KPI value formatting (`_format_kpi_value` in `grouper.py`)** — formats `cur_actual` / `bsp_benchmark` strings at grouping time. Rules in priority order: (1) `_PERCENT_LEVERS` → `XX.XX%`; (2) `_TIME_HOURS_LEVERS` (Avg MR Time, Avg Blanket Wash Time, Avg Feeder Trip Time) → multiply by 60, integer, e.g. `"27 Mins"`; (3) `Speed` → integer with comma separator, e.g. `"45,000"`; (4) default → `XX.XX`. Templates render the pre-formatted strings directly — no unit logic in Jinja2.
- **Renderer uses a module-level `_env`** — Jinja2 environment is created once at import time.
- **Admin alerts are best-effort** — `send_admin_alert` swallows exceptions so a broken credential does not mask the original error.
- **`--dry-run` writes to `out/preview/<email>.html`** (plant) and `out/preview/regional/<email>.html` (regional) — safe to run against production config.
- **`test_without_mail.py`** — fetches all three SharePoint sources, renders plant previews to `out/test_preview/` and regional previews to `out/test_preview/regional/`, logs findings/PM attachment counts and any routing fallbacks, writes a clickable `_index.html` covering both report types.
- **`build_machine()` is the single per-row builder** — extracted from `group_by_manager`'s loop so `regional.py` builds `MachineSummary` objects identically; a machine's data never diverges between the plant digest and the regional roll-up that includes it.
- **Regional digests are a synopsis, not a drill-down** — no per-machine lever bullets, no findings/PM detail per machine. Region KPI tiles → plant roll-up table → per-department top-3 tables (`regional_top_n` in `config.yaml`, default 3) → one maintenance summary line. Detail lives in the plant manager's email; the regional footer says so.
- **Routing fallback is logged, not silently accepted** — `Routing_Match_Level` on every row tells Python whether Qlik resolved that Plant+Department pair or fell back to a plant-only match. `find_routing_mismatches()` turns any non-`'Department'` rows into one admin alert per run (deduplicated by Plant+Department) so a missing workbook row gets fixed instead of persisting unnoticed. The machine still gets emailed either way — this is visibility, not a blocker.
- **Regional emails never CC** — plant digests CC via `CC_List`; regional digests always pass `cc_list=None` to `send_mail`.
- **Brand theme lives in `templates/_theme.j2`** — Jinja `{% set %}` color/font tokens plus shared macros. `email.html.j2` (the V2 manager digest) imports it (`{% import '_theme.j2' as t %}`) and uses its macros/tokens for inline styles; `regional.html.j2` and the archived V1 templates still hardcode the same hex values inline rather than importing it — a pre-existing gap this redesign did not close outside the manager template. Palette: Green `#006548` (primary), Light Green `#76BC21` (accent), Black `#3D3935` (ink). Streak/warning emphasis uses amber (`#8A5A00` / `#FFF8E8` / `#E0A800`), not red — red directly against the brand green is the hardest color pairing for red-green color vision deficiency, and reads as "error" rather than "trend to watch." Emphasis never rests on color alone (bold weight + explicit text always accompanies a color cue).
- **Every visual style is inlined, `<style>` is enhancement-only** — Outlook desktop (Word rendering engine) drops most box-model CSS and `border-radius`; Outlook.com ignores `<style>` blocks entirely. Every template carries the same values as inline `style=` attributes on every element that matters, with a `<head><style>` block layered on top purely for `@media` mobile stacking and clients that honor it.

### Manager digest V2 (`email.html.j2` / `email.txt.j2`)

Redesigned to cut data fatigue — one page for most managers, never more than
two. V1 (3 KPI tiles, a 5-column movers table, a 4-column maintenance table,
and a per-machine card with up to 5 lever bullets + full findings/PM detail)
is archived at `templates/archive/manager_v1.{html,txt}.j2`; see
`templates/archive/README.md` to roll back. **No calculation, threshold,
ranking, or machine/lever-selection logic changed** — `grouper.py` still
computes everything; V2 only changes how much of it the template shows.

- **Two KPI tiles, not three** — "Machines impacted" was dropped. "Sheets
  lost vs BSP" and "Top driver" remain (`OverviewSummary`, unchanged fields).
- **`ManagerDigest.focus_machines`** (top `FOCUS_MACHINE_COUNT = 3` machines
  by `Total_Sheet_Impact`, already sorted DESC — a slice, not a re-sort) get
  a three-column Who/Why/How-to-Fix card. **`ManagerDigest.other_machines`**
  (the remainder with impact > 0) collapse into one "Also impacted: name
  (sheets), name (sheets)…" line. Only `levers[0]` (the top lever) is shown
  per focus machine — levers 2–5 are still on `MachineSummary.levers` (used
  by `regional.py` and available for a future drill-down) but not rendered.
- **Card 3 (How to Fix) action text comes from `src/actions.py`** —
  `lookup_action(lever.reasons or lever.name, ...)` against
  `src/data/Reason_Category_Action_Lookup.xlsx` ("Reason Lookup" sheet,
  key = `Lever / Reason`, action = `How the Plant Team Can Help`). Loaded
  once via `lru_cache`; any load/lookup failure degrades to a generic
  fallback sentence rather than raising, because `build_machine()` is shared
  with `regional.py` — an exception here must not break the regional digest
  too. ~26% of the lookup's rows carry a "not yet mapped" placeholder; those
  are detected by prefix and swapped for the same generic fallback rather
  than rendered verbatim (the real text is aimed at the lookup's maintainer,
  not the plant manager). `actions.log_unmapped_summary()` logs a per-run
  count of generic-fallback hits so the lookup can be improved over time.
  When a machine's findings are corroborated with its top lever
  (`FindingsSummary.corroborated_sections`, unchanged logic from
  `findings.py`), Card 3 adds an amber note pointing at the open Graphic
  Care finding instead of duplicating a separate findings block.
- **`LeverSummary.streak_phrase`** replaces the old literal `"{{ streak }}/4
  weeks {{ direction }}"` wording, which was wrong for every lever except
  Downtime Reason. `Streak_4wk` means two different things depending on the
  lever (see `InsightOpexv1.qvs:1828-1868` vs Section 41B):
  - **Downtime Reason** — count of the last 4 weeks whose rate exceeded BSP.
    `_streak_phrase` renders "Above/Below benchmark in N of the last 4
    weeks."
  - **Every other lever** (Speed, Downtime %, Scrap Loss, Avg MR Time, Avg
    Blanket Wash Time, Avg Feeder Trip Time) — a `Peek()`-based run of
    *consecutive weeks each worse than the week before*, not a comparison to
    BSP and not capped to a 4-week window. `_streak_phrase` renders
    "Below/Above benchmark this week — watch next week." (streak 0),
    "Trending worse — first week worse than last." (streak 1), or "Trending
    worse for N weeks straight — needs attention." (streak 2+, capped at
    "4+" for display). The calculation (`Streak` value itself) is unchanged;
    only the English describing it was corrected.
- **Maintenance is one plant-wide summary line**, not a per-machine table:
  open Graphic Care Findings, Missing Work Orders (`OverviewSummary.maint_missing_wo`,
  new field, same `FindingsSummary.total_missing_wo` sum other maintenance
  totals already used), and critically-overdue PM procedures, plus one
  plain-English sentence. "Critically overdue" is still `Urgency == 1` from
  `pm_compliance.py` (documented upstream as "3+ weeks past Allowed Days") —
  there is no "1.5× allowed days" rule anywhere in this codebase; the plain
  English describes the real `Urgency` rule, not an invented one. Suppressed
  entirely when `OverviewSummary.has_maintenance` is false.
- **Regional digests (`regional.*.j2`) are unchanged** — same V1 design as
  before. A regional V2 redesign, if wanted, is future work.

### Upgrade path

To replace Jinja2 with LLM prose, swap `src/renderer.py` for an Azure OpenAI call. `ManagerDigest` / `MachineSummary` / `LeverSummary` / `FindingsSummary` / `PMSummary` / `RegionalDigest` / `PlantRollup` / `DepartmentSection` are the stable interface.
