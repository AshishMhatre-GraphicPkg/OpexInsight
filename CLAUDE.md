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
| **Email notifier** | `notifier/` | Python 3.11+ | Reads `MachineWeekSummary.csv` and `Findings.csv` from SharePoint, renders per-plant-manager digest emails and per-regional-manager synopsis emails, sends via Microsoft Graph API |

The interface between them is two CSV files on SharePoint (`OPEXinsights/`):

- **`MachineWeekSummary.csv`** — written by Qlik Section 49 after each Monday reload. One row per machine per week, with Outcome + up to 5 Levers pre-pivoted, plus `Manager_Email` / `CC_List` / `Regional_Manager_Email` / `Regional_Manager_Name` / `Routing_Match_Level` stamped on for the notifier's routing. Join key: `Plant` (plant number) + `WC Object ID`.
- **`Findings.csv`** — written by an external maintenance system (daily). One row per open/missing-WO finding. Join key: `Plant` + `G.WCobjectID`.

A third SharePoint file, **`PlantManagers.xlsx`**, is read only by Qlik
(Section 7B) — one row per **Plant + Department** carrying
`Manager_Email` / `CC_List` / `Regional_Manager` / `Regional_Manager_Email`.
Qlik resolves each machine's routing at Plant+Department grain, falling
back to a Plant-only match (and stamping `Routing_Match_Level` accordingly)
when a department isn't yet in the workbook. See Section 7B (Step 2) and
Section 49 (Step 6) in the script below, and `notifier/CLAUDE.md` for how
the notifier consumes this.

See `notifier/CLAUDE.md` for the full notifier architecture (plant-manager digests + regional-manager synopses + brand theme).

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

**`ApprovedRsnText_Map` / `RsnBucket_Map` lifecycle:** Also defined in Step 2 (Section 5), alongside `TimeReason_Name_Map`. Classifies each `"Time Plant Reason Key"` as `'BW'` (Blanket Wash) / `'FT'` (Feeder Trip) / unclassified — see [Downtime Reason Key Exclusions](#downtime-reason-key-exclusions). Used through Step 3's fact-table passes and Step 5's reason pipelines (Sections 12, 40, 41B); dropped in Section 47.

**Section 7B — Plant / Regional Manager Email Mapping:** Reads `PlantManagers.xlsx` (grain: one row per Plant + Department) into 8 mapping tables — 4 keyed on `Plant|Department` (`PlantManager_Map`, `PlantManager_CC_Map`, `RegionalManager_Map`, `RegionalManagerName_Map`) and 4 plant-only fallback maps with the `_Fallback_Map` suffix (first-row-wins per plant, used when a machine's department isn't yet in the workbook). Consumed in Section 49 to stamp `Manager_Email`, `CC_List`, `Regional_Manager_Email`, `Regional_Manager_Name`, and `Routing_Match_Level` (`'Department'` / `'Plant'` / `'None'`) onto `MachineWeekSummary`. Kept alive for the whole script (not dropped) like other small mapping tables.

### Step 3 — Fact Table Passes (Sections 8–15)

This is the most complex step. `JobFact_Raw` is loaded once (full binary QVD read, no transforms) then re-read via `RESIDENT` passes:

| Table | Grain | Purpose |
|---|---|---|
| `JobFact_Job_BSP_Agg` | Date + WC + Shift + Die | L1 BSP source aggregation |
| `JobFact_Job_BSP` | Same grain, RunHours > 2 filter | L1 BSP qualifying runs (all KPIs) |
| `JobFact_Job_BSP_L2_Agg` | Date + WC + Shift + Die + **PltMatKey** | L2 BSP source (PltMatKey as true GROUP BY, not Max()) |
| `JobFact_Job_BSP_L2` | Same + board attributes resolved | L2 BSP qualifying runs (all KPIs) |
| `JobFact_DownReason_BSP` | Date + WC + Shift + Die + PltMatKey + ReasonKey | Downtime reason BSP source |
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

9 BSP tables are computed (L1/L2/L3 × Main KPI / Setup KPI / Downtime Reason). Each follows the same pattern:
1. `BSP_X_Raw` — `FRACTILE()` grouped at the appropriate grain
2. `BSP_X` — filtered to min run count threshold
3. Raw table dropped

- **Main KPIs** (`BSP_Main_L1/L2/L3_Raw`): OEE (P75), Speed (P75), Downtime % (P25), Downtime Hrs (P25), Scrap Rate (P25). Net Throughput Rate removed.
- **Setup KPIs** (`BSP_Setup_L1/L2/L3_Raw`): Avg MR Time / `SetupHrsPerEvent` (P25). Setup Frequency removed. MROClass added to grain at all 3 levels.
- **New machine-level KPIs** (Sections 29A–29B): Avg Blanket Wash Time (P25, `BSP_BlanketWashTime_L1/L2/L3`), Avg Feeder Trip Time (P25, `BSP_FeederTripTime_L1/L2/L3`).
- **Frequency KPIs** (Section 29C): Blanket Washes per 10K (P25, `BSP_BlanketWashPer10K_L1/L2/L3`), Feeder Trips per 10K (P25, `BSP_FeederTripPer10K_L1/L2/L3`) — `Events / TotalQty_OEE × 10000`, fractile pool is `TotalQty_OEE > 0` (all qualifying runs, including zero-event runs, unlike the Avg-Time KPIs which require `Events > 0`).
- **Reason KPIs:** Downtime Reason (P25) only. Scrap Reason removed — Scrap Rate (the parent lever) is still computed as a Main KPI.
- **L2 Main and L2 Setup BSP** read from `JobFact_Job_BSP_L2` (not `JobFact_Job_BSP`) because L2 requires board attributes which only the L2 source resolves correctly via the PltMatKey GROUP BY.

### Step 5 — BSP Resolution + Scoring (Sections 29–41)

All 12 BSP tables are immediately converted to 36+ mapping tables then dropped — this eliminates all synthetic keys from keeping them as regular tables.

Then:
- **Section 30–31:** `WeeklyDieKPI` → `WeeklyDieBSP` — 3-level `Coalesce()` fallback per KPI per die per week. `CoveredSchedHours` = SchedHours only for dies where OEE BSP resolved. `WeeklyDieKPI` carries `Department`, `CartonStyle`, `NumberUp`, **`MaxSpeed`**, `MaterialDescription` (all Max/Only aggregated at week+die grain); `WeeklyDieBSP` derives `L2_ExtraDim` once and injects it into every L2 mapping lookup key. BSP fields resolved: OEE, Speed, DT%, DT Hrs, Scrap Rate, SetupHrsPerEvent, BlanketWashTime, FeederTripTime, BlanketWashPer10K, FeederTripPer10K.
- **Section 32:** `WeeklyMachineBSP` — weighted BSP per machine+week using SchedHours as weights across dies. Only covered dies contribute to numerator and denominator.
- **Section 33–35:** `WeeklyMachineKPI` carries `Wk_MaxSpeed = Max(MaxSpeed)`, `Wk_BlanketWashTime`, `Wk_FeederTripTime`, `Wk_BlanketWashPer10K`, `Wk_FeederTripPer10K`, `Wk_BlanketWashEvents`, `Wk_FeederTripEvents`, `Wk_TotalQty`. `WeeklyMachineKPI_Sorted` → streak calculation using `Peek()`. Active streaks: OEE, Speed, DT%, DT Hrs, Scrap Rate, SetupHrsPerEvent (higher-is-better), BlanketWashTime, FeederTripTime, BlanketWashPer10K, FeederTripPer10K (lower-is-better). Must be sorted by `Plant + WC + WeekStart ASC` before `Peek()` runs or streaks compute incorrectly.
- **Section 36–37:** `CurrentPeriod` — 1-week aggregation (last complete week, `v2WeekStart = vLastWeekStart`). `Cur_SchedHours = Sum(Wk_SchedHours)`. `Cur_RunHours = Sum(Wk_RunHours)`. `Cur_SetupEventCount = Sum(Wk_SetupCount)`. `Cur_MaxSpeed = Max(Wk_MaxSpeed)` for the last week. `Cur_BSP_CoveragePct = Sum(Wk_CoveredSchedHours) / Sum(Wk_TotalSchedHours)` for that week. New current-period fields: `Cur_BlanketWashTime = Avg(Wk_BlanketWashTime)`, `Cur_FeederTripTime = Avg(Wk_FeederTripTime)`, `Cur_BlanketWashEvents = Sum(Wk_BlanketWashEvents)`, `Cur_FeederTripEvents = Sum(Wk_FeederTripEvents)`, `Cur_BlanketWashPer10K = Avg(Wk_BlanketWashPer10K)`, `Cur_FeederTripPer10K = Avg(Wk_FeederTripPer10K)`, `Cur_TotalQty = Sum(Wk_TotalQty)`.
- **Sections 38–40:** Reason denominator maps and current-period downtime reason aggs (die grain → machine+reason grain with weighted BSP fallback). Section 38 also builds `Department_Rsn_Map` (WC → Department). Section 40 re-reads `vFactQVD` for the 1-week window and carries `CartonStyle` (via `Only()`) and `NumberUp` (via `Max(ApplyMap('OrderOp_NumberUp_Map', ...))`), then applies `Department_Rsn_Map` to derive the L2_ExtraDim string inline in each L2 Coalesce key. Section 41 (Scrap Reason aggregation) removed.

### Step 5 (addition) — Section 41B: 4-week reason streak

Per-reason `Streak_4wk` (range 0–4) is the count of weeks in the last 4 full weeks where the reason's weekly rate exceeded its current-period (1-week) BSP benchmark. Scope is **Downtime (`tPltRsnKey`) only** — Scrap Reason was removed. Weekly denominator map `WeeklySchedHrs_Rsn_Map` and BSP-benchmark map `Rsn_BSP_Down_Map` are built and dropped locally. Output map consumed by Section 44: `Rsn_Down_Streak_Map`. `Streak_4wk` is a **display field only** — it no longer multiplies `Sheet_Impact`/`OEE_Impact`.

### Step 6 — Insight Records, Scoring, Store (Sections 42–48)

- **Section 42:** `InsightRecords_Raw` — 9 `LOAD` blocks (one per KPI: OEE, Speed, Downtime %, Scrap Rate, Avg MR Time, Avg Blanket Wash Time, Avg Feeder Trip Time, Blanket Washes per 10K, Feeder Trips per 10K) with `Concatenate`. **Removed:** ARQ, Net Throughput Rate, Setup Frequency, Availability, Performance %, Quality Rate, Setup Time %. Insight fires when `Cur_Actual` is worse than `BSP_Benchmark` **AND** `Cur_BSP_CoveragePct > 0.5`. Each block emits `Gap_Pct`, `Sheet_Gap`, `Streak_4wk` (`RangeMin(Streak_X, 4)`), and **`KPI_Category`** (`'Outcome'` for OEE only; `'Lever - OEE'` for Speed/Avg MR Time; `'Lever - Downtime %'` for Downtime %/Avg Blanket Wash Time/Avg Feeder Trip Time/Blanket Washes per 10K/Feeder Trips per 10K; `'Lever - Scrap Rate'` for Scrap Rate). Percentage KPIs format `Cur_Actual_Fmt` / `BSP_Benchmark_Fmt` with `Num(..., '0.00%')`. **Ratio / absolute KPIs pass the raw numeric through unchanged** (this includes the two per-10K rate KPIs). `Insight_ID` token for Avg MR Time remains `SETUPHRSEV` for QVD continuity; the per-10K KPIs use `BWPER10K` / `FTPER10K`.

  **Sheet_Gap formulas (in sheets lost vs BSP):**
  - **OEE**: `(BSP_OEE − Cur_OEE) × Cur_SchedHours × Cur_MaxSpeed` — uses `Cur_MaxSpeed` (OEM Speed or Max Gluer CPH), not BSP Speed, because OEE denominator is SchedHours × MaxSpeed
  - **Downtime %**: `(Cur_DTPct − BSP_DTPct) × Cur_SchedHours × Cur_BSP_Speed` — numerator is `(DownHours + SetupDownHours) / SchedHours` at all levels (current + L1/L2/L3 BSP). Setup Down counts as machine downtime per plant definition `(Time − Down) + (Time − Setup Down)`. Reason-level DT (`L*_BSP_ReasonDownPct`) is unchanged — reason codes attribute only `DownHours`; Setup Down is its own bucket.
  - **Scrap Loss**: `Sum(Cur_ActualScrapSheets) − Sum(Cur_ExpectedScrapSheets)` — direct excess sheets; expected scrap is the sum of `BSP_ScrapPct × TotalSheets` per order across all single-setup orders in the current week, where BSP_ScrapPct comes from the order's size bucket. No speed multiplier.
  - **Speed**: `(BSP_Speed − Cur_Speed) × Cur_RunHours` — sheets directly, speed deficit × run hours
  - **Avg MR Time**: `(Cur_SetupHrsPerEvent − BSP_SetupHrsPerEvent) × Cur_SetupEventCount × Cur_BSP_Speed` — excess duration × actual event count × speed
  - **Avg Blanket Wash Time**: `(Cur_BlanketWashTime − BSP_BlanketWashTime) × Cur_BlanketWashEvents × Cur_BSP_Speed`
  - **Avg Feeder Trip Time**: `(Cur_FeederTripTime − BSP_FeederTripTime) × Cur_FeederTripEvents × Cur_BSP_Speed`
  - **Blanket Washes per 10K**: `(Cur_BlanketWashPer10K − BSP_BlanketWashPer10K) / 10000 × Cur_TotalQty × Cur_BlanketWashTime × Cur_BSP_Speed` — excess events (converted from the rate using `Cur_TotalQty`) × this machine's actual avg wash duration × speed
  - **Feeder Trips per 10K**: `(Cur_FeederTripPer10K − BSP_FeederTripPer10K) / 10000 × Cur_TotalQty × Cur_FeederTripTime × Cur_BSP_Speed`

- **Section 43:** Unified scoring. `Sheet_Impact = Round(Sheet_Gap, 0.01)`. **Streak multiplier removed** — `Streak_4wk` is emitted as a display field only and no longer affects `Sheet_Impact`. WHERE filter uses `Sheet_Gap > 0`. A `Null() as Reasons` column is seeded here so Main rows align with Reason rows downstream.
- **Section 44:** Reason insights. Downtime reasons resolve `Reasons` via `ApplyMap('TimeReason_Name_Map', …)`; `Streak_4wk` from `Rsn_Down_Streak_Map`. **`tPltRsnKey` is NOT emitted** — the single `Reasons` column carries the readable name. `KPI_Category`: Downtime Reason → `'Lever - Downtime %'`. Scrap Reason block removed.
- **Section 45:** Main KPIs ranked `ORDER BY Plant, OEE_Impact DESC`. Unified schema matches Reason rows.
- **Section 46:** Reason insights ranked `ORDER BY Plant, WC, KPI_Name, OEE_Impact DESC`. **Top-3 cap** applied to `KPI_Name = 'Downtime Reason'` only.
- **Section 47:** Concatenate MainInsightRecords + ReasonInsightRecords into `InsightRecords`. Drop `TimeReason_Name_Map` here.
- **Section 48:** Incremental store — unchanged mechanics.
- **Section 49:** `MachineWeekSummary.csv` export. `Total_Sheet_Impact` = the OEE row's `Sheet_Impact` only (`WHERE KPI_Name = 'OEE'`). Levers ladder into OEE so summing all rows double-counts; OEE Sheet_Impact captures total loss vs BSP. Machines with no OEE insight (OEE >= BSP) are excluded. The QVD's historical rows pre-dating this refactor will have legacy fields (`tPltRsnKey`, `Composite_Score`, `Impact_Score`, `Streak_13wk`) as NULL on new writes and new fields (`Reasons`, `OEE_Impact`, `Streak_4wk` for reasons) as NULL on old rows — Qlik concat tolerates this. A one-time full reload cleans up the QVD if desired.

  **Manager routing columns:** `Manager_Email`, `CC_List`, `Regional_Manager_Email`, `Regional_Manager_Name`, `Routing_Match_Level` are resolved via the Section 7B maps and added to every row (see Step 2 above). Each is looked up first at `Plant|Upper(Trim(Department))` grain, falling back to a plant-only map when that misses; `Routing_Match_Level` records which map actually resolved (`'Department'` / `'Plant'` / `'None'`) so the notifier can alert on rows that fell back. The lookup key fields (`%RouteKey`, `%RoutePlantKey`) are computed inline in the LOAD and dropped from the stored table immediately after (`DROP FIELD ... FROM MachineWeekSummary`).

  **Sub-reason swap rule (Section 49):** Before writing `Lever_N_*` columns, each occurrence of `Downtime %` in the top-3 `'Lever - OEE'` pool is replaced by its top-2 sub-reasons (by `Sheet_Impact`). Sub-reason source: `KPI_Category = 'Lever - Downtime %'` (Downtime Reason only — Scrap Reason removed). Each swap expands one parent slot into up to 2 sub-reason rows; total lever count grows from 3 to up to 4. Unaffected parent levers keep their original rank position; sub-reasons are inserted at the parent's position ordered by Sheet_Impact DESC. **Fallback:** if a machine has Downtime % in top-3 but zero qualifying sub-reason rows, the parent stays in place.

  **Driver parent clause:** Two columns are added to the export (retained for data completeness even though the email no longer renders the "driven primarily by" sentence):
  - `Driver_Parent_Name` — whichever of `{Downtime %, Scrap Rate}` had the highest `Sheet_Impact` in the original top-3; `Null()` if neither appeared.
  - `Driver_Parent_Sheets` — that parent's `Sheet_Impact`.

  **Section 49 intermediate tables:**
  - `Temp_PoolLeversRanked` — top-3 `'Lever - OEE'` rows ranked per machine.
  - `Temp_DriverParent` → `DriverParent_Name_Map` / `DriverParent_Sheets_Map` — keyed by `Plant|WC Object ID`.
  - `Temp_SubLeversRanked` — sub-reason rows ranked per machine+parent, `Sub_Rank` 1..2.
  - 14 `Sub_R{1,2}_*_Map` tables — keyed by `Plant|WC Object ID|Sub_Parent`; one map per (rank × field).
  - `Temp_FinalLevers` — assembled via 6 CONCATENATE passes (pool pass + fallback pass for unaffected parents, sub_R1 pass, sub_R2 pass, each for pool and fallback sources).
  - `Temp_FinalLeversRanked` — re-ranked by `Order_Key ASC`; 40 position maps (8 fields × 5 ranks) written then all intermediates dropped.

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
| `KPI_Category` encodes Outcome or Lever-with-parent | **Single Outcome:** `'Outcome'` applies to OEE only. Main levers (`'Lever - OEE'`): Speed, Downtime %, Scrap Rate, Avg MR Time. New machine-level levers (`'Lever - Downtime %'`): Avg Blanket Wash Time, Avg Feeder Trip Time. Sub-levers: Downtime Reason → `'Lever - Downtime %'`. Scrap Reason removed — no sub-levers for Scrap Rate. Joining lever rows to their parent via `Replace(KPI_Category, 'Lever - ', '')` resolves to OEE for main levers; sub-levers resolve to their parent lever name. Front-end filter: `WildMatch(KPI_Category, 'Lever - *')`. |
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
- **Time metrics** (RunHours, DownHours, SetupHours, SetupDownHours, NonCrewedHours): `fSched = 1` — exact match only. Matches the dashboard formula `{<fSched={'1'}>}`. fSched=0 rows are excluded (they were previously included under the old `<= 1` filter and inflated the OEE denominator for machines with fSched=0 time rows).
- **Qty metrics** (Yield/Scrap in OEE UOM and BUOM): `If(IsNull(fSched), 2, fSched) >= 1` — unchanged; includes fSched=1 and fSched=2 (qty-only) rows.
- Null fSched rows are treated as 2 for qty purposes; excluded from time calculations (fSched=1 exact filter naturally excludes null).

## Downtime Reason Key Exclusions

Three downtime-reason pipelines share a common exclusion filter on `"Time Plant Reason Key"`:

```qlik
AND Not WildMatch("Time Plant Reason Key", '*MR0*')
AND Len(ApplyMap('RsnBucket_Map', "Time Plant Reason Key", '')) = 0
```

Applied in:
- **Section 12** (`JobFact_DownReason_BSP_Agg`) — 2-year BSP source
- **Section 40** (`CurPeriod_DwnReason_DieLvl_Raw`) — 1-week current-period actuals
- **Section 41B** (`WeeklyDwnReason_Raw`) — 4-week streak source

**Why:** `*MR0*` = MRO setup reasons (excluded since always). `RsnBucket_Map` = BlanketWash + FeederTrip events (bucket `'BW'` / `'FT'`). These are already captured by the Avg Blanket Wash Time and Avg Feeder Trip Time KPIs — including them in Downtime Reason insights would double-count their sheet impact. Because both the inclusion (Section 5) and exclusion (Sections 12/40/41B) read the same map, they can never drift apart.

**`ApprovedRsnText_Map` / `RsnBucket_Map` (Section 5):** Blanket Wash and Feeder Trip event classification is **not** done via substring `WildMatch` on the reason code — the old `'*PQBW*'` / `'*PLG5*'`, `'*PLDF*'`, `'*PLF*'` patterns false-matched `PLF0` ("Baldwin fountain solution") into Feeder Trip, and missed several genuine wash codes (`PQB0`, `PQBO`, `PQB1`, `PQB2`, `PQBK`, `PQBP`, `PQ58`). Instead, `ApprovedRsnText_Map` is an inline allow-list of exact `"Time Reason"` description strings (not codes — the same code means different things at different plants, e.g. `PQ58` = "Blanket - Wash General" at one plant, "Offset/Picking" at another), and `RsnBucket_Map` joins it against `TimeReasonCodes.qvd` to produce a `"Time Plant Reason Key" → 'BW' | 'FT' | ''` mapping. Scope is deliberately narrow: Feeder Trip = press feeder proper only (no gluer/cutting/sheeter feeder codes, no infeed/web-guide, no splicer/unwind-only codes); Blanket Wash = wash events only (no blanket change/problem codes, no plate/cylinder wash, no generic wash-up). Both maps are dropped alongside `TimeReason_Name_Map` in Section 47. To add a newly-identified code, add its exact `"Time Reason"` string to `ApprovedRsnText_Map` — no other change is needed since all 6 consuming sites read `RsnBucket_Map`.

## KPI Direction Reference

| Higher-is-better (P75 BSP, fires when Actual < BSP) | Lower-is-better (fires when Actual > BSP) |
|---|---|
| OEE, Speed | Downtime %, Scrap Loss, Avg MR Time, Avg Blanket Wash Time, Avg Feeder Trip Time, Blanket Washes per 10K, Feeder Trips per 10K |

**Removed KPIs (no longer computed):** ARQ, Net Throughput Rate, Setup Frequency, Availability, Performance %, Quality Rate, Setup Time %

**Scrap Loss (replaces Scrap Rate):** `KPI_Name = 'Scrap Loss'`, `KPI_Category = 'Lever - OEE'`. Uses a bucket-aware BSP instead of a single per-machine BSP. Orders are segmented into 10 size buckets by `TotalSheets` (Yield + Scrap in OEE UOM) using the parameterised variable `vScrapBucket` (defined in Tab 1). BSP is computed per Plant + Machine + Bucket over a 6-month rolling window (`v6MonthStart`) at P25 scrap rate, `SetupCount = 1` orders only. Mapping table `BSP_ScrapBucket_Map` is keyed `Plant|WCObjectID|Bucket`. Current-period aggregation re-reads the fact QVD for 1-week window at order grain (Section 40B), computes `ExpectedScrap = BSP_Pct × TotalSheets` per order, then rolls up to machine level. `Sheet_Gap = Sum(ActualScrap) − Sum(ExpectedScrap)` (direct sheets, no speed multiplier). Coverage = `CoveredSheets / TotalSheets` where CoveredSheets counts only orders where the bucket BSP resolved.

**Email display formatting (notifier):** Avg MR Time, Avg Blanket Wash Time, Avg Feeder Trip Time are stored in Qlik as fractional hours but displayed in the email digest as integer minutes (e.g. 0.45 hr → `27 Mins`). Speed is displayed as an integer (no decimal). Formatting applied in `notifier/src/grouper.py:_format_kpi_value`.

## MaxSpeed Logic

`MaxSpeed` = `Max Gluer Cartons Per Hour` for Department = `Gluer` or `Window`; `OEM Speed` for all others. Applied via `ApplyMap('Department_Map', ...)` at the enrichment pass, not at the raw load.

## Mapping Table Key Formats (Step 5)

```
L1 Main/Downtime BSP   : Plant|WCObjectID|Die
L2 Main/Downtime BSP   : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 Main/Downtime BSP   : Plant|WCObjectID
L1 Setup BSP (Avg MR Time) : Plant|WCObjectID|Die|MROClass|MaterialDescription
L2 Setup BSP               : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim|MROClass
L3 Setup BSP               : Plant|WCObjectID|MROClass
L1 BlanketWashTime BSP     : Plant|WCObjectID|Die
L2 BlanketWashTime BSP     : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 BlanketWashTime BSP     : Plant|WCObjectID
L1 FeederTripTime BSP      : Plant|WCObjectID|Die
L2 FeederTripTime BSP      : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 FeederTripTime BSP      : Plant|WCObjectID
L1 BlanketWashPer10K BSP   : Plant|WCObjectID|Die
L2 BlanketWashPer10K BSP   : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 BlanketWashPer10K BSP   : Plant|WCObjectID
L1 FeederTripPer10K BSP    : Plant|WCObjectID|Die
L2 FeederTripPer10K BSP    : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim
L3 FeederTripPer10K BSP    : Plant|WCObjectID
L1 Downtime Reason BSP     : Plant|WCObjectID|Die|TimeReasonKey
L2 Downtime Reason BSP     : Plant|WCObjectID|BoardTypeGroup|BoardCaliper|L2_ExtraDim|TimeReasonKey
L3 Downtime Reason BSP     : Plant|WCObjectID|TimeReasonKey
QualifyingRuns_Map         : Date|WCObjectID|ShiftCode|Die
```

**MaterialDescription** is brought in via `MaterialDesc_Map` (built in Step 2 from `Materials_Temp`, keyed on `Material`). Applied as: `ApplyMap('MaterialDesc_Map', ApplyMap('Material_Map', PltMatKey, Null()), Null())`. If a die runs multiple materials in a week, `Only(MaterialDescription)` returns NULL → L1 lookup misses → falls back to L2 (intended behaviour for mixed-material dies).

**`L2_ExtraDim` values by department:**
```
Gluer, Window           → Text(CartonStyle)   e.g. "TUCK-END-AUTO"
Sheetfed Cutting,
Web Cutting             → Text(NumberUp)      e.g. "4"
All other departments   → ''                  (empty — same L2 key as before)
```
