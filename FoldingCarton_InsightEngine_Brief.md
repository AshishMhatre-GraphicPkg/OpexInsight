# Folding Carton Actionable Intelligence Platform
### Retrospective Insight Engine — Project Brief v1.1

---

## A. Project Overview

### What the System Does
A weekly automated insight engine built in Qlik Sense (QVD architecture) that compares each machine's recent performance against its own Best Shown Performance (BSP) benchmark, scores the gap by size and trend urgency, and produces a ranked action list telling plant supervisors and OE teams exactly where to focus — down to the specific downtime reason or scrap reason driving the loss.

### Key Business Goal
Replace passive dashboard monitoring ("here is what happened") with a prioritized action list ("here is what to fix first and why") — quantified against proven achievable performance on comparable jobs, not arbitrary flat targets.

### Inputs → Outputs

| Input | Source | Grain |
|---|---|---|
| Production fact data | `model Asset Utilization - Facts.qvd` | Date + Plant + Machine + Shift + Operator + Die + Order + Reason Key |
| Machine / Work Center attributes | `WcAttributes.qvd` + Department_lookup.xlsx | Per machine |
| Material / Board attributes | `PlantMaterial.qvd` → `Materials.qvd` → `BoardTypes.qvd` | Per material |
| Downtime reason codes | `TimeReasonCodes.qvd` | Per reason key |
| Scrap reason codes | `ScrapReasonCodes.qvd` | Per reason key |
| Action tracker status | Excel lookup keyed on Insight_ID | Per insight |

| Output | Destination | Grain |
|---|---|---|
| `InsightRecords` QVD | SharePoint `/OPEXinsights/InsightRecord.qvd` | One row per Plant + Machine + KPI + Week (main) or + Reason (reason insights) |

---

## B. Core Business Logic

### KPI Definitions (9 active KPIs)

| KPI | Formula | Direction | BSP Percentile |
|---|---|---|---|
| OEE | `GoodQty_OEE ÷ (SchedHours × MaxSpeed)` | ↑ Higher | P90 |
| Availability | `RunHours ÷ SchedHours` | ↑ Higher | P90 |
| Performance | `TotalQty_OEE ÷ (RunHours × MaxSpeed)` | ↑ Higher | P90 |
| Quality | `GoodQty_OEE ÷ TotalQty_OEE` | ↑ Higher | P90 |
| Speed | `TotalQty_OEE ÷ RunHours` | ↑ Higher | P90 |
| Downtime % | `DownHours ÷ SchedHours` | ↓ Lower | P10 |
| Scrap Rate | `ScrapQty_OEE ÷ TotalQty_OEE` | ↓ Lower | P10 |
| Setup Hrs/Event | `SetupHours ÷ SetupCount` | ↓ Lower | P10 |
| Setup Time % | `SetupHours ÷ SchedHours` | ↓ Lower | P10 |

- `SchedHours = RunHours + DownHours + SetupHours + SetupDownHours + NonCrewedHours`
- `MaxSpeed` = `Max Gluer Cartons Per Hour` for Gluer/Window dept; `OEM Speed` for all others
- All quantities use OEE UOM fields (`Yield in OEE UOM`, `Scrap in OEE UOM`) — no conversion needed
- All backend calculations in BUOM for consistency; front-end UOM conversion via master measures

### fSched Filtering Rules
- Time metrics: `If(IsNull(fSched), 2, fSched) <= 1` — includes fSched 0 and 1
- Qty metrics: `If(IsNull(fSched), 2, fSched) >= 1` — includes fSched 1 and 2
- Null fSched rows filled as 2 before all filtering

### BSP Benchmark Rules
- **Window:** 1 Jan 2025 to last completed week (configurable via `v2YearStart`)
- **Qualifying run:** `RunHours > 2` after full job-level aggregation — filters out partial/trivial runs
- **3-Level fallback per KPI:**
  - L1: Plant + Machine + Die (min 10 qualifying runs) → HIGH confidence
  - L2: Plant + Machine + Board Type Group + Board Caliper (min 20) → MEDIUM confidence
  - L3: Plant + Machine (min 30) → LOW confidence
  - No level resolved → Insufficient History — excluded from scoring
- **Setup KPIs only:** MROClass added to all 3 levels (MRO = changeover complexity 1/2/3, not product complexity)
- **Reason BSPs:** L3 only (Plant + Machine + Reason Key), P10 of reason % over qualifying runs, min 10 occurrences

### Weighted BSP (Machine-Week Level)
- BSP resolved at die level, then **weighted average by SchedHours** across all dies run in the 2-week period
- Only dies with a resolved BSP contribute to numerator and denominator
- `BSP_CoveragePct` = covered SchedHours ÷ total SchedHours — insights suppressed if < 50%
- `BSP_ConfScore` = SchedHours-weighted average of die-level confidence scores (3/2/1/0)

### Current Period
- Rolling 2 completed weeks: `v2WeekStart` to `vCurrentWeekStart` (exclusive)
- `Cur_Actual` = average of two weekly KPI values across the window
- Week starts on Monday (`vWeekStartDay = 0`)

### Trend Scoring (Consecutive-Week Streak)
- Streak = number of consecutive weeks a KPI has deteriorated week-over-week
- Higher-is-better KPIs: deterioration = `current < previous`
- Lower-is-better KPIs: deterioration = `current > previous`
- Null weeks do not increment streak
- `Streak_4wk` = `RangeMin(Streak, 4)` — capped at 4 for short-term signal
- `Streak_13wk` = full streak value from 13-week window
- `Trend_Score = RangeMin(100, ((Streak_4wk + Streak_13wk) / 2) / 4 × 100)`

### Composite Scoring & Ranking
- `Gap_Score = RangeMin(100, gap_formula)` — 0 to 100
- `Composite_Score = Gap_Score × 0.70 + Trend_Score × 0.30`
- Insights only fire when `Cur_Actual` is worse than `BSP_Benchmark`
- Ranked within Plant by Composite_Score DESC — `Insight_Rank = 1` is highest priority

### Reason Insights (Separate Ranked List)
- Fired independently — a reason insight does not require a main KPI insight to exist for the same machine
- Ranked within Machine + Reason Type by `Impact_Score DESC`
- `Impact_Score = (Cur_ReasonPct - BSP_ReasonPct) × TotalSchedHrs_2wk` — converts % gap to actual hours/units above BSP for fair cross-machine comparison
- Downtime Reason: `Cur_Actual = ReasonDownHours ÷ TotalSchedHrs_2wk` (2-week total SchedHours, all rows)
- Scrap Reason: `Cur_Actual = ReasonScrapQty ÷ TotalQty_2wk` (2-week total TotalQty, all rows regardless of scrap key)

### MROClass Derivation
- Derived inline from `Time Plant Reason Key` using `WildMatch`
- `*1MR0*` → 1, `*2MR0*` → 2, `*3MR0*` → 3 (numeric for correct `Max()` behavior)
- Represents complexity of the changeover event, not the product itself
- `Max(MROClass)` per job = most complex changeover event for that order

### Edge Cases
- MRO rows excluded from downtime reason aggregation (setup events, not downtime)
- `Cur_BSP_DowntimePct` BSP denominator must be > 0 before division
- Reason denominator loaded independently from ALL fact rows — not just reason-tagged rows — to prevent ratio inflation
- `ScriptError` check on incremental QVD load handles first-ever run gracefully

### Constraints
- No Snowflake — all logic in Qlik load script using QVD architecture
- No write-back widget — action tracker via manual Excel lookup keyed on Insight_ID
- BSP window fixed from 1 Jan 2025 — adjustable via `v2YearStart` variable
- DowntimeHrs KPI dropped — always returned half the correct value due to Avg() over 2 weeks on absolute hours; Downtime % is sufficient and correct

---

## C. Data Model / Schema

### Final In-Memory Tables (after full load)

| Table | Key Fields | Purpose |
|---|---|---|
| `PlantInformation` | Plant | Plant name and division |
| `WcAttributes` | WC Object ID, DepartmentKey | Machine master — without Plant or Department fields to prevent circular reference |
| `TimeReasonCodes` | tPltRsnKey | Downtime reason descriptions and categories |
| `ScrapReasonCodes` | sPltRsnKey | Scrap reason descriptions |
| `CartonExtraDim` | Carton Style | Carton category for front-end context |
| `MaterialConversions` | Material | UOM conversion factors for front-end master measures |
| `InsightRecords` | Insight_ID | Final output — main KPI + reason insights combined |

### InsightRecords Schema

| Field | Type | Notes |
|---|---|---|
| `Insight_ID` | String | `Plant\|WCObjectID\|PeriodStart\|KPIName` — stable across reruns |
| `Period_Start` | Date | Monday of the 2-week window start (YYYY-MM-DD) |
| `Plant` | String | e.g. `0008` |
| `WC Object ID` | String | Machine number |
| `Plant - WC` | String | Human-readable e.g. `Carol Stream - 7201` |
| `Department` | String | e.g. `Sheetfed Printing` |
| `KPI_Name` | String | One of 9 main KPIs or `Downtime Reason` / `Scrap Reason` |
| `Cur_Actual` | Float | 2-week average actual performance (ratio for %, raw for Speed) |
| `BSP_Benchmark` | Float | Weighted P90/P10 benchmark in same unit as Cur_Actual |
| `Gap_Pct` | Float | % gap between actual and BSP, capped at 100 |
| `Gap_Score` | Float | 0–100 normalized gap — 70% weight in composite |
| `Streak_4wk` | Int | Consecutive deteriorating weeks, capped at 4 |
| `Streak_13wk` | Int | Consecutive deteriorating weeks, full 13-week window |
| `Trend_Score` | Float | 0–100 normalized trend score — 30% weight in composite |
| `Composite_Score` | Float | Final rank score = Gap×0.7 + Trend×0.3 |
| `Insight_Rank` | Int | Rank within Plant (main) or Machine+KPI_Name (reason) |
| `Cur_BSP_CoveragePct` | Float | % of machine's SchedHours with a resolved BSP |
| `Cur_BSP_ConfScore` | Float | Weighted confidence 0–3 |
| `BSP_Confidence` | String | HIGH / MEDIUM / LOW / Insufficient History |
| `Cur_SchedHours` | Float | Machine's total scheduled hours in current 2-week period |
| `tPltRsnKey` | String | Time reason key — populated for Downtime Reason rows only |
| `sPltRsnKey` | String | Scrap reason key — populated for Scrap Reason rows only |
| `Impact_Score` | Float | Excess hours/units above BSP × SchedHours — reason rows only |

### Key Relationships
```
PlantInformation  ──── Plant ──────────────────────── InsightRecords
WcAttributes      ──── WC Object ID ────────────────── InsightRecords
TimeReasonCodes   ──── tPltRsnKey ──────────────────── InsightRecords
ScrapReasonCodes  ──── sPltRsnKey ──────────────────── InsightRecords
CartonExtraDim    ──── Carton Style ─── (display only, not in InsightRecords)
MaterialConversions─── Material ──────── (front-end conversion only)
```

### Intermediate Computation Tables (all dropped before final model)
All BSP source tables, job aggregation tables, weekly KPI tables, reason aggregation tables, and scoring intermediate tables are built then dropped. Only the 7 final tables above exist in the loaded data model.

---

## D. Assumptions + Decisions

### Why things were done this way

| Decision | Rationale |
|---|---|
| P90 for higher-is-better, P10 for lower-is-better | BSP must reflect direction — P90 of downtime would benchmark the worst performers, not the best |
| Weighted BSP by SchedHours across dies | A machine running 80% of its time on Die A should be benchmarked primarily against Die A's BSP, not an unweighted average that treats a 2-hour die run equally to a 40-hour run |
| MROClass excluded from main KPI BSP levels | MRO describes the changeover transition, not the product — a Die can be 1MRO or 3MRO depending on what ran before it, making it an unstable product attribute |
| MROClass retained in Setup BSP levels | Setup time IS directly driven by changeover complexity — a 3MRO changeover is structurally harder than a 1MRO and should be benchmarked only against other 3MRO events |
| Consecutive-week streak over regression slope | Streaks are explainable to plant supervisors — "this has been getting worse for 3 weeks in a row" is actionable. A regression slope coefficient is not. |
| 70/30 gap-to-trend weighting | Gap size is the primary driver of business impact. Trend is an urgency multiplier. A large gap on a stable machine is still more important than a small gap on an accelerating one. |
| Raw QVD load first, then resident transformations | Qlik QVD binary read is only optimized (fastest) with zero transformations. All `If()`, `ApplyMap()`, `Sum()` expressions trigger unoptimized mode. Single QVD read + resident passes is significantly faster on 15M row tables. |
| BSP tables converted to mapping tables immediately | All 12 BSP result tables share Plant + WC Object ID combinations — keeping them as regular tables creates cascading synthetic keys. Converting to 36 mapping tables and dropping source tables eliminates all synthetic keys. |
| Reason BSP at L3 only for current period | Current period reason aggregation is at machine level (not die level) because 2 weeks is too short to slice by die + reason. L3 (machine + reason) is the most granular level with sufficient data. |
| Incremental STORE with Period_Start deduplication | Daily reloads for the same week should overwrite that week's records, not duplicate them. Historical weeks from prior reloads are preserved. |
| Plant excluded from WcAttributes in-memory table | Plant exists in both WcAttributes and all enriched fact tables. Keeping it in WcAttributes creates a circular reference loop through PlantInformation. Plant is stamped onto fact tables via ApplyMap at load time instead. |

### Known Limitations

- **BSP window is fixed from 1/1/2025.** As history grows the window will naturally expand. A 2-year rolling window would be more robust but requires a date variable update.
- **Reason BSP uses L3 only** — no die-level or board-level reason benchmarking. Machines with highly variable job mixes may have reason benchmarks that are less comparable to specific product types.
- **Weighted BSP coverage below 50% suppresses the insight entirely.** This protects against unreliable benchmarks but means new dies with no history won't appear in the action list even if performing poorly.
- **Streak resets to zero on any non-deteriorating week.** A machine that recovers for one week and then declines again loses its streak history. This is by design — the engine rewards recovery — but it means a machine with a saw-tooth pattern never accumulates a high trend score.
- **Action tracker is manual.** The Excel lookup requires manual updates. There is no automated closure or escalation logic.
- **MROClass null for jobs with no setup event.** Jobs where no MRO reason code row exists (e.g. very short runs or non-standard events) will have null MROClass and will be excluded from Setup BSP benchmarks.

---

## E. Current Status + Next Tasks

### Current State
- Load script complete across 6 steps — all validated
- 0 synthetic keys, 0 circular references
- InsightRecords QVD stored to SharePoint with incremental append logic
- Validated against Plant 0008, Machine 10005999:
  - All main KPI Cur_Actuals match existing OEE dashboard within 1% variance
  - Downtime Reason and Scrap Reason denominators corrected and validated
  - DowntimeHrs KPI dropped
  - Plant - WC added for readability
  - BSP_Confidence label (HIGH/MEDIUM/LOW/Insufficient History) implemented


