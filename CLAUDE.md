# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Repo Is

A Qlik Sense load script (`InsightOpexv1.qvs`) that powers the **Folding Carton Actionable Intelligence Platform** — a weekly automated insight engine. It compares each machine's recent performance against its own **Best Shown Performance (BSP)** benchmark, scores the gap by size and trend urgency, and produces a ranked action list stored as a QVD on SharePoint.

There is no build system, no test runner, and no linter. Changes are made directly to the `.qvs` file and executed by reloading the Qlik Sense app.

---

## Repo Structure

Two components share this repo:

| Component | Path | Language | What it does |
|---|---|---|---|
| **Qlik load script** | `InsightOpexv1.qvs` | Qlik script | Computes BSP benchmarks, scores gaps, stores `InsightRecords.qvd` and `MachineWeekSummary.csv` to SharePoint |
| **Email notifier** | `notifier/` | Python 3.11+ | Reads `MachineWeekSummary.csv` and `Findings.csv` from SharePoint, renders per-manager digest emails, sends via Microsoft Graph API |

The interface between them is two CSV files on SharePoint (`OPEXinsights/`):

- **`MachineWeekSummary.csv`** — written by Qlik Section 49 after each Monday reload. One row per machine per week, with top-2 Outcomes and top-3 Levers pre-pivoted. Join key: `Plant` (plant number) + `WC Object ID`.
- **`Findings.csv`** — written by an external maintenance system (daily). One row per open/missing-WO finding. Join key: `Plant` + `G.WCobjectID`.

See `notifier/CLAUDE.md` for the full notifier architecture.

---

## Script Architecture — 6 Tabs / Steps

The script is a single `.qvs` file divided into 6 logical tabs (marked with `///$tab Step N`). Execution is linear top to bottom.

### Step 1 — Variables & Config
- Week boundary variables (`vCurrentWeekStart`, `vLastWeekStart`, `v2WeekStart`, `v4WeekStart`, `v13WeekStart`) computed from `Today()` using `WeekStart()` with `vWeekStartDay = 0` (Monday). **`v2WeekStart = vLastWeekStart` (both set to `-1`) — the current period is 1 week, not 2.** `v4WeekStart` is used only for the Section 41B streak weekly lookback.
- BSP window: `v2YearStart` = rolling 24 months back from today (not a fixed date).
- Thresholds: `vBSP_L1_Min=15`, `vBSP_L2_Min=25`, `vBSP_L3_Min=35`, `vMinCoverage=0.5`.
- Output path `vInsightQVDPath` → SharePoint; fact source `vFactQVD` → QVD library.

### Step 2 — Dimension Tables
Loads `PlantInformation`, `WcAttributes`, `Department_Lookup` (Excel), `CartonExtraDim`, `MaterialConversions`, reason code tables, all board attribute mapping tables (`BoardType_Map`, `Material_Map`, `BoardTypeGroup_Map`, `BoardCaliper_Map`), and `OrderOp_NumberUp_Map` (Order Operation Key → Number Up, from `model Asset Utilization - OrderOpData.qvd`).

**Critical:** `Plant` is removed from `WcAttributes` in-memory to prevent a circular reference. Plant reaches `InsightRecords` only through fact-table enrichment via `ApplyMap('Plant_Map', ...)`.

**`OrderOp_NumberUp_Map` lifecycle:** Defined in Step 2, used in Step 3 (`JobFact_Raw` LOAD) and again in Step 5 (Sections 40–41 reason die-level raws which re-read from QVD). Not dropped until end of Section 41.

### Step 3 — Fact Table Passes (Sections 8–15)

This is the most complex step. `JobFact_Raw` is loaded once (full binary QVD read, no transforms) then re-read via `RESIDENT` passes:

| Table | Grain | Purpose |
|---|---|---|
| `JobFact_Job_BSP_Agg` | Date + WC + Shift + Die | L1 BSP source aggregation |
| `JobFact_Job_BSP` | Same grain, RunHours > 2 filter | L1 BSP qualifying runs (all KPIs) |
| `JobFact_Job_BSP_L2_Agg` | Date + WC + Shift + Die + **PltMatKey** | L2 BSP source (PltMatKey as true GROUP BY, not Max()) |
| `JobFact_Job_BSP_L2` | Same + board attributes resolved | L2 BSP qualifying runs (all KPIs) |
| `JobFact_DownReason_BSP` | Date + WC + Shift + Die + PltMatKey + ReasonKey | Downtime reason BSP source |
| `JobFact_ScrapReason_BSP` | Date + WC + Shift + Die + PltMatKey + ReasonKey | Scrap reason BSP source |
| `JobFact_Scoring_Agg` | Date + WC + Die + Carton + PltMatKey + Shift + Operator + Order | 13-week trend + current period |
| `JobFact_Scoring` | Same + board attributes | Final scoring source |

After `JobFact_Scoring` is loaded, `JobFact_Raw` and all remaining mapping tables are dropped — except `OrderOp_NumberUp_Map` which is kept alive for Section 40–41.

**Mapping tables built in Step 3:**
- `QualifyingRuns_Map` — key: `Date|WC|ShiftCode|Die`, value: 1 — used to filter reason aggs to qualifying runs only.
- `SchedHours_Map`, `TotalQty_Map` — same key, carry job-level denominators to reason grain.

**`L2_ExtraDim` field:** Derived in `JobFact_Job_BSP_L2` (and all reason BSP tables) from Department. Encodes the department-specific extra dimension used to refine the L2 BSP grain:
- `Gluer`, `Window` → `Text("Carton Style")` (carton type drives performance on these machines)
- `Sheetfed Cutting`, `Web Cutting` → `Text(NumberUp)` (number-up layout drives run efficiency)
- All other departments → `''` (empty string — L2 grain unchanged from prior behaviour)

This single column is appended to all L2 BSP mapping keys, so no extra tables are needed.

### Step 4 — BSP Calculation (Sections 17–28)

12 BSP tables are computed (L1/L2/L3 × Main KPI / Setup KPI / Downtime Reason / Scrap Reason). Each follows the same pattern:
1. `BSP_X_Raw` — `FRACTILE()` grouped at the appropriate grain
2. `BSP_X` — filtered to min run count threshold
3. Raw table dropped

- **Main/Downtime/Scrap KPIs:** `P75` for higher-is-better, `P25` for lower-is-better. Recalibrated from P90/P10 because L1 pools average ~min-threshold observations, where P10/P90 collapse to a single extreme value — not reliably chaseable.
- **Setup KPIs:** add `MROClass` to all 3 levels (1MR0/2MR0/3MR0 from `WildMatch` on reason key).
- **L2 Main and L2 Setup BSP** read from `JobFact_Job_BSP_L2` (not `JobFact_Job_BSP`) because L2 requires board attributes which only the L2 source resolves correctly via the PltMatKey GROUP BY.

### Step 5 — BSP Resolution + Scoring (Sections 29–41)

All 12 BSP tables are immediately converted to 36+ mapping tables then dropped — this eliminates all synthetic keys from keeping them as regular tables.

Then:
- **Section 30–31:** `WeeklyDieKPI` → `WeeklyDieBSP` — 3-level `Coalesce()` fallback per KPI per die per week. `CoveredSchedHours` = SchedHours only for dies where OEE BSP resolved. `WeeklyDieKPI` carries `Department`, `CartonStyle`, `NumberUp` (all Max/Only aggregated at week+die grain); `WeeklyDieBSP` derives `L2_ExtraDim` once and injects it into every L2 mapping lookup key.
- **Section 32:** `WeeklyMachineBSP` — weighted BSP per machine+week using SchedHours as weights across dies. Only covered dies contribute to numerator and denominator.
- **Section 33–35:** `WeeklyMachineKPI_Sorted` → streak calculation using `Peek()`. Must be sorted by `Plant + WC + WeekStart ASC` before `Peek()` runs or streaks compute incorrectly.
- **Section 36–37:** `CurrentPeriod` — 1-week aggregation (last complete week, `v2WeekStart = vLastWeekStart`). `Cur_SchedHours = Sum(Wk_SchedHours)`. `Cur_RunHours = Sum(Wk_RunHours)`. `Cur_SetupEventCount = Sum(Wk_SetupCount)`. `Cur_BSP_CoveragePct = Sum(Wk_CoveredSchedHours) / Sum(Wk_TotalSchedHours)` for that week. `Cur_RunHours` and `Cur_SetupEventCount` are carried through Sections 35 and 36 from `WeeklyMachineKPI` so they survive into `CurrentPeriod`.
- **Sections 38–41:** Reason denominator maps and current-period reason aggs (die grain → machine+reason grain with weighted BSP fallback). Section 38 also builds `Department_Rsn_Map` (WC → Department). Sections 40–41 re-read `vFactQVD` for the 1-week window and carry `CartonStyle` (via `Only()`) and `NumberUp` (via `Max(ApplyMap('OrderOp_NumberUp_Map', ...))`), then apply `Department_Rsn_Map` to derive the L2_ExtraDim string inline in each L2 Coalesce key.

### Step 5 (addition) — Section 41B: 4-week reason streak

Per-reason `Streak_4wk` (range 0–4) is the count of weeks in the last 4 full weeks where the reason's weekly rate exceeded its current-period (1-week) BSP benchmark. Scope is **Downtime (`tPltRsnKey`) and Scrap (`sPltRsnKey`) only** — Feeder/Blanket rows emit `Streak_4wk = 0` (no weekly pipeline). Weekly denominator maps (`WeeklySchedHrs_Rsn_Map`, `WeeklyTotalQty_Rsn_Map`) and BSP-benchmark maps (`Rsn_BSP_Down_Map`, `Rsn_BSP_Scrap_Map`) are built and dropped locally. Output maps consumed by Section 44: `Rsn_Down_Streak_Map`, `Rsn_Scrap_Streak_Map`.

### Step 6 — Insight Records, Scoring, Store (Sections 42–48)

- **Section 42:** `InsightRecords_Raw` — 10 `LOAD` blocks (one per KPI: OEE, Availability, Performance, Quality, Speed, Net Throughput Rate, Downtime %, Scrap Rate, Setup Hrs/Event, Setup Time %) with `Concatenate`. Insight fires when `Cur_Actual` is worse than `BSP_Benchmark` **AND** `Cur_BSP_CoveragePct > 0.5`. Each block emits `Gap_Pct`, `GapHrs`, `Streak_4wk` (`RangeMin(Streak_X, 4)`), and **`KPI_Category`** (`'Outcome'` for Outcome KPIs; `'Lever - <Parent Outcome>'` for Lever KPIs — e.g. `'Lever - OEE'`, `'Lever - Availability'`). Percentage KPIs format `Cur_Actual_Fmt` / `BSP_Benchmark_Fmt` with `Num(..., '0.00%')`. **Ratio / absolute KPIs (Speed, Net Throughput Rate, Setup Hrs/Event) pass the raw numeric through unchanged** so front-end formatting controls display.
- **Section 43:** Unified scoring. `OEE_Impact = Round(GapHrs × (1 + Streak_4wk/4), 0.01)` where `GapHrs` is the true absolute scheduled-hours loss computed per-KPI in Section 42:
  - **Pct-based KPIs** (OEE, Availability, Performance, Quality, Downtime %, Scrap Rate, Setup Time %): `GapHrs = (BSP − Actual) × Cur_SchedHours` (absolute gap × hours, not relative gap)
  - **Speed**: `GapHrs = (BSP_Speed − Cur_Speed) / BSP_Speed × Cur_RunHours` (speed deficit fraction × run-hours)
  - **Net Throughput Rate**: `GapHrs = (BSP_NTR − Cur_NTR) / BSP_NTR × (Cur_RunHours + Cur_DowntimeHrs)` (rate-deficit fraction × production-time hours)
  - **Setup Hrs/Event**: `GapHrs = (Cur_SetupHrsPerEvent − BSP_SetupHrsPerEvent) × Cur_SetupEventCount` (excess hrs/event × event count = total excess setup hours)
  - `Gap_Pct` is unchanged (still relative gap for display). `GapHrs` is an intermediate-only field, not in the final schema. WHERE filter uses `GapHrs > 0`. No more `Composite_Score`, `Gap_Score`, `Trend_Score`. A `Null() as Reasons` column is seeded here so Main rows align with Reason rows downstream.
- **Section 44:** Reason insights. Downtime and scrap reasons resolve `Reasons` via `ApplyMap('TimeReason_Name_Map', …)` / `ApplyMap('ScrapReason_Name_Map', …)`; `Streak_4wk` from the Section 41B maps; `OEE_Impact = Round(GapHrs × (1 + Streak_4wk/4), 0.01)` with `GapHrs` expressed in scheduled hours (scrap uses `ApplyMap('CurSchedHrs_Map', ...)` to convert %-gap × qty → hours). **`tPltRsnKey` / `sPltRsnKey` are NOT emitted** — the single `Reasons` column carries the readable name for both streams, with `KPI_Name ∈ {'Downtime Reason', 'Scrap Reason'}` discriminating type. `KPI_Category`: Downtime Reason → `'Lever - Downtime %'`; Scrap Reason → `'Lever - Scrap Rate'`.
- **Sections 44B / 44C:** Feeder (3 metrics) and Blanket (3 metrics) rows emit `Reasons` = literal KPI name (e.g. `'Feeder DT%'`), `Streak_4wk = 0`, and `OEE_Impact = GapHrs` (no trend uplift). Count Rate / Per10K metrics pass raw numeric to `Cur_Actual_Fmt` / `BSP_Benchmark_Fmt` (no `Num` wrapper). **OEE_Impact for Count Rate and Per10K** uses `excess_trips × avg_hours_per_trip` where `excess_trips = Cur_DownCount − BSP_Rate × denominator` and `avg_hours_per_trip = Cur_DownHours / Cur_DownCount` — so the result is true excess downtime hours in the same unit as DT%. All Feeder and Blanket rows carry `KPI_Category = 'Lever - Downtime %'`.
- **Section 45:** Main KPIs ranked `ORDER BY Plant, OEE_Impact DESC`. Unified schema matches Reason rows.
- **Section 46:** Reason insights ranked `ORDER BY Plant, WC, KPI_Name, OEE_Impact DESC`. **Top-3 cap** applied to `KPI_Name IN ('Downtime Reason', 'Scrap Reason')` only — Feeder/Blanket one-per-machine rows pass through uncapped.
- **Section 47:** Concatenate MainInsightRecords + ReasonInsightRecords into `InsightRecords`. Drop `TimeReason_Name_Map` / `ScrapReason_Name_Map` here.
- **Section 48:** Incremental store — unchanged mechanics. The QVD's historical rows pre-dating this refactor will have legacy fields (`tPltRsnKey`, `Composite_Score`, `Impact_Score`, `Streak_13wk`) as NULL on new writes and new fields (`Reasons`, `OEE_Impact`, `Streak_4wk` for reasons) as NULL on old rows — Qlik concat tolerates this. A one-time full reload cleans up the QVD if desired.
- **Section 49:** `MachineWeekSummary` mart — one row per machine per week, with top-2 Outcomes and top-3 Levers pre-pivoted from `InsightRecords`. Joined to `PlantManagers.xlsx` (Plant → Manager_Email, CC_List). Stored as both `.qvd` and `.csv` (comma-delimited) to `OPEXinsights/MachineWeekSummary.csv` on SharePoint. The `.csv` is the feed for the Python notifier in `notifier/`.

**`MachineWeekSummary.csv` schema** (Section 49 STORE output, in column order):
```
Plant, WC Object ID, Plant - WC, Department, Period_Start,
Manager_Email, CC_List, Total_Sheet_Impact,
Outcome_1_Name, Outcome_1_Sheets, Outcome_2_Name, Outcome_2_Sheets,
Lever_1_Name, Lever_1_Reasons, Lever_1_Sheets, Lever_1_Gap_Pct, Lever_1_Streak, Lever_1_Parent_Outcome,
Lever_2_Name, Lever_2_Reasons, Lever_2_Sheets, Lever_2_Gap_Pct, Lever_2_Streak, Lever_2_Parent_Outcome,
Lever_3_Name, Lever_3_Reasons, Lever_3_Sheets, Lever_3_Gap_Pct, Lever_3_Streak, Lever_3_Parent_Outcome
```
`Plant` is a plant number (joins to `G.WCobjectID` / `Plant` in `Findings.csv`). `Total_Sheet_Impact` is the sum of `OEE_Impact` converted to sheets. Lever columns are contiguous — an absent lever has all its fields as NULL.

**Final `InsightRecords` schema** (both main + reason rows):
```
Insight_ID, Plant, WC Object ID, Plant - WC, Department, Period_Start,
KPI_Name, KPI_Category, Reasons, Cur_Actual, BSP_Benchmark, Cur_Actual_Fmt, BSP_Benchmark_Fmt,
Gap_Pct, Streak_4wk, OEE_Impact,
Cur_BSP_CoveragePct, Cur_BSP_ConfScore, Cur_BSP_PoolSize, BSP_Confidence, Insight_Rank
```

Reason rows have `Cur_BSP_CoveragePct / Cur_BSP_ConfScore / Cur_BSP_PoolSize / BSP_Confidence = Null()`; Main rows have `Reasons = Null()`.

**Removed fields** (no longer in output): `tPltRsnKey`, `sPltRsnKey`, `Streak_13wk`, `Gap_Score`, `Trend_Score`, `Composite_Score`, `Impact_Score`.

---

## Key Design Decisions to Preserve

| Decision | Why it matters |
|---|---|
| Raw QVD load first, then RESIDENT passes | QVD binary read is only optimized with zero transforms. Any `If()`, `ApplyMap()`, or `Sum()` in the FROM clause triggers unoptimized (slow) mode. |
| All BSP tables → mapping tables immediately | 12 BSP tables sharing Plant + WC create cascading synthetic keys. Converting to mappings and dropping source tables eliminates all synthetic keys. |
| L2 BSP from separate `JobFact_Job_BSP_L2` | L1 source has no PltMatKey (Die is the product dimension). L2 needs board attributes which require PltMatKey as a true GROUP BY dimension — `Max(PltMatKey)` produces wrong grouping. |
| Department-specific L2 grain via `L2_ExtraDim` | A single derived column collapses three grain variants (empty / CartonStyle / NumberUp) into one field, avoiding three parallel L2 pipelines. All 12 L2 BSP tables and their mapping keys include this field — empty string for default departments means existing behaviour is preserved for Web/Sheetfed Printing/Other with no separate code path. |
| `Only()` for string fields in aggregations, `Max()` for numerics | `Max()` on a text field in Qlik returns NULL. `Only()` returns the value if the group contains exactly one distinct value (else NULL, which acts as a data-quality signal). Used for `CartonStyle` everywhere it is aggregated. `NumberUp` is numeric so `Max()` is correct. |
| `OEE_Impact` is true hours lost vs BSP | All KPIs now use absolute-gap × time-denominator; `Gap_Pct` keeps the relative display. Scoring numbers were wrong units — plant leaders read `OEE_Impact` as hours. |
| `KPI_Category` encodes Outcome or Lever-with-parent | Outcome rows: `'Outcome'` (OEE, Availability, Quality, Downtime %, Scrap Rate, Net Throughput Rate). Lever rows: `'Lever - <Parent Outcome>'` — each Lever names the Outcome it directly moves: Performance → `'Lever - OEE'`; Speed → `'Lever - Net Throughput Rate'`; Setup Hrs/Event & Setup Time % → `'Lever - Availability'`; Downtime Reason, Feeder (×3), Blanket (×3) → `'Lever - Downtime %'`; Scrap Reason → `'Lever - Scrap Rate'`. Rationale: enables the weekly narrative "you lost N hours on Outcome A — fix these Levers" by joining Lever rows to their parent Outcome via `Replace(KPI_Category, 'Lever - ', '')`. Front-end filter changes from `KPI_Category = 'Lever'` to `WildMatch(KPI_Category, 'Lever - *')`. Outcome rows stay for scorecard context. |
| BSP percentile P25/P75, not P10/P90 | At current ~15–35 run pool sizes, P10/P90 of N obs ≈ a single extreme value — fragile and non-chaseable. P25 of 15 obs is the 4th-best value, demanding but stable. Min thresholds raised to L1=15/L2=25/L3=35 simultaneously to keep ambition. `Cur_BSP_PoolSize` (SchedHours-weighted avg run-count of the resolved BSP level) is emitted in `InsightRecords` so leadership can flag thin-pool benchmarks. |
| `Cur_BSP_CoveragePct` is 1-week coverage | `Sum(CoveredSchedHours) / Sum(TotalSchedHours)` over the single current week (`v2WeekStart = vLastWeekStart`). |
| Coverage threshold is strict `> 0.5` | Not `>= 0.5`. Exactly 50% coverage does not pass. |
| `Cur_SchedHours = Sum(Wk_SchedHours)` | Represents total scheduled hours for the 1-week current period. `Avg` was incorrect. |
| Reason BSPs use L1→L2→L3 fallback | Same 3-level `Coalesce()` pattern as main KPIs, applied at die grain before rolling up to machine+reason level. |
| Streak sorted before `Peek()` | `WeeklyMachineKPI_Sorted` ORDER BY `Plant, WC Object ID, WeekStart ASC` is mandatory for `Peek()` streak logic. |
| `Insight_ID` is stable across reruns | Format: `Plant|WCObjectID|PeriodStart|KPIName`. Incremental store deduplicates on `Period_Start` so reruns in same week overwrite, not duplicate. |

---

## fSched Filtering Rules

Applied inline on every aggregation — never pre-filtered:
- **Time metrics** (RunHours, DownHours, SetupHours, SetupDownHours, NonCrewedHours): `If(IsNull(fSched), 2, fSched) <= 1`
- **Qty metrics** (Yield/Scrap in OEE UOM and BUOM): `If(IsNull(fSched), 2, fSched) >= 1`
- Null fSched rows are treated as 2 (qty-only rows).

## KPI Direction Reference

| Higher-is-better (P75 BSP, fires when Actual < BSP) | Lower-is-better (P25 BSP, fires when Actual > BSP) |
|---|---|
| OEE, Availability, Performance, Quality, Speed, Net Throughput Rate | Downtime %, Scrap Rate, Setup Hrs/Event, Setup Time % |

## MaxSpeed Logic

`MaxSpeed` = `Max Gluer Cartons Per Hour` for Department = `Gluer` or `Window`; `OEM Speed` for all others. Applied via `ApplyMap('Department_Map', ...)` at the enrichment pass, not at the raw load.

## Mapping Table Key Formats (Step 5)

```
L1 Main/Downtime BSP   : Plant|WCObjectID|Die
L2 Main/Downtime BSP   : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 Main/Downtime BSP   : Plant|WCObjectID
L1 Setup BSP           : Plant|WCObjectID|Die|MROClass
L2 Setup BSP           : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim|MROClass
L3 Setup BSP           : Plant|WCObjectID|MROClass
L1 Downtime Reason BSP : Plant|WCObjectID|Die|TimeReasonKey
L2 Downtime Reason BSP : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim|TimeReasonKey
L3 Downtime Reason BSP : Plant|WCObjectID|TimeReasonKey
(Scrap Reason same pattern with ScrapReasonKey)
QualifyingRuns_Map     : Date|WCObjectID|ShiftCode|Die
```

**`L2_ExtraDim` values by department:**
```
Gluer, Window           → Text(CartonStyle)   e.g. "TUCK-END-AUTO"
Sheetfed Cutting,
Web Cutting             → Text(NumberUp)      e.g. "4"
All other departments   → ''                  (empty — same L2 key as before)
```
