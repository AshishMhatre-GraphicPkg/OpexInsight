# BSP Explained — OEE & Availability Walkthrough
### Machine 10005999 | Plant 0008 | Dept: Sheetfed Printing

---

## Setup Assumptions

| Parameter | Value |
|---|---|
| Machine | 10005999 |
| OEM Speed (MaxSpeed) | 10,000 units/hr |
| Department | Sheetfed Printing (not Gluer/Window → uses OEM Speed) |
| Dies run historically | Die A, Die B |
| BSP window | Jan 1, 2025 → last completed week |
| Current period | 2 most recent completed weeks |

---

## PART 1 — Building the BSP from Historical Runs

### Step 1A — Collect all qualifying job runs (RunHours > 2)

The machine ran **Die A 15 times** and **Die B 5 times** in the BSP window.  
Each row below = one complete job run aggregated to job grain.

#### Die A — 15 qualifying runs

| Run # | SchedHrs | RunHrs | GoodQty | OEE (GoodQty ÷ SchedHrs×10k) | Availability (RunHrs ÷ SchedHrs) |
|---|---|---|---|---|---|
| 1  | 10 | 6.0 | 54,000 | **54.0%** | **60.0%** |
| 2  | 10 | 7.0 | 63,000 | **63.0%** | **70.0%** |
| 3  | 10 | 7.0 | 65,000 | **65.0%** | **70.0%** |
| 4  | 10 | 7.5 | 68,000 | **68.0%** | **75.0%** |
| 5  | 10 | 8.0 | 72,000 | **72.0%** | **80.0%** |
| 6  | 10 | 8.0 | 74,000 | **74.0%** | **80.0%** |
| 7  | 10 | 8.0 | 75,000 | **75.0%** | **80.0%** |
| 8  | 10 | 8.5 | 78,000 | **78.0%** | **85.0%** |
| 9  | 10 | 8.5 | 79,000 | **79.0%** | **85.0%** |
| 10 | 10 | 9.0 | 82,000 | **82.0%** | **90.0%** |
| 11 | 10 | 9.0 | 84,000 | **84.0%** | **90.0%** |
| 12 | 10 | 9.0 | 85,000 | **85.0%** | **90.0%** |
| 13 | 10 | 9.5 | 87,000 | **87.0%** | **95.0%** |
| 14 | 10 | 9.5 | 88,000 | **88.0%** | **95.0%** |
| 15 | 10 | 9.5 | 91,000 | **91.0%** | **95.0%** |

#### Die B — 5 qualifying runs (will NOT get an L1 BSP — explained below)

| Run # | SchedHrs | RunHrs | GoodQty | OEE | Availability |
|---|---|---|---|---|---|
| 1 | 8 | 5.5 | 44,000 | 55.0% | 68.8% |
| 2 | 8 | 6.0 | 50,000 | 62.5% | 75.0% |
| 3 | 8 | 6.5 | 54,000 | 67.5% | 81.3% |
| 4 | 8 | 7.0 | 58,000 | 72.5% | 87.5% |
| 5 | 8 | 7.5 | 64,000 | 80.0% | 93.8% |

---

### Step 1B — Apply the 3-Level BSP Fallback

| Level | Grain | Min runs required | Die A (15 runs) | Die B (5 runs) |
|---|---|---|---|---|
| L1 | Machine + Die | 10 | ✅ Qualifies → **HIGH confidence** | ❌ Only 5 runs |
| L2 | Machine + Board Type Group + Caliper | 20 | ❌ Only 15 | ❌ Only 5 |
| L3 | Machine only | 30 | ❌ Total machine = 20 runs | ❌ Total machine = 20 runs |

> **Result:** Die A gets an **L1 BSP** (HIGH confidence).  
> Die B gets **no BSP** — insufficient history. It will be excluded from coverage calculation.

---

### Step 1C — Calculate Die A's L1 BSP using P90 / P90

P90 = the 90th percentile of all run-level KPI values.  
This is the level the machine has proven it can hit in its **top 10% of runs** on this die.

**Sort OEE values (15 values, 0-indexed 0→14):**

| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OEE% | 54 | 63 | 65 | 68 | 72 | 74 | 75 | 78 | 79 | 82 | 84 | 85 | 87 | 88 | 91 |

P90 position (0-indexed) = `(n−1) × 0.9 = 14 × 0.9 = 12.6`  
Interpolate: `value[12] + 0.6 × (value[13] − value[12]) = 87 + 0.6 × (88 − 87)`

> **Die A L1 BSP OEE = 87.6%**

**Sort Availability values:**

| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Avail% | 60 | 70 | 70 | 75 | 80 | 80 | 80 | 85 | 85 | 90 | 90 | 90 | 95 | 95 | 95 |

P90 position = 12.6  
Interpolate: `value[12] + 0.6 × (value[13] − value[12]) = 95 + 0.6 × (95 − 95)`

> **Die A L1 BSP Availability = 95.0%**

---

## PART 2 — Current 2-Week Period (3 runs)

The machine ran **3 jobs** across the 2 most recent completed weeks:

| Run | Week | Die | SchedHrs | RunHrs | GoodQty | OEE_Denom (SchedHrs×MaxSpeed) |
|---|---|---|---|---|---|---|
| 1 | Week −2 | **Die A** | 10 | 7.5 | 65,000 | 100,000 |
| 2 | Week −2 | **Die B** | 6  | 4.5 | 38,000 |  60,000 |
| 3 | Week −1 | **Die A** | 10 | 8.0 | 70,000 | 100,000 |

---

### Step 2A — Weekly Machine KPI (actual performance, both dies combined)

The script aggregates to **machine + week level** first:

#### Week −2:
| Metric | Calculation | Value |
|---|---|---|
| Total SchedHours | 10 + 6 | **16 hrs** |
| Total RunHours | 7.5 + 4.5 | **12 hrs** |
| Total GoodQty | 65,000 + 38,000 | **103,000 units** |
| Total OEE_Denom | 100,000 + 60,000 | **160,000 units** |
| **Wk_OEE** | 103,000 ÷ 160,000 | **64.4%** |
| **Wk_Availability** | 12 ÷ 16 | **75.0%** |

#### Week −1:
| Metric | Calculation | Value |
|---|---|---|
| Total SchedHours | 10 | **10 hrs** |
| Total RunHours | 8.0 | **8 hrs** |
| Total GoodQty | 70,000 | **70,000 units** |
| Total OEE_Denom | 100,000 | **100,000 units** |
| **Wk_OEE** | 70,000 ÷ 100,000 | **70.0%** |
| **Wk_Availability** | 8 ÷ 10 | **80.0%** |

---

### Step 2A-i — WeeklyDieKPI (Section 30)

Before any BSP comparison, the script aggregates `JobFact_Scoring` to **WeekStart + Plant + WC + Die** grain. One row per die per week.

| WeekStart | Die | Wk_Die_SchedHours | Wk_Die_RunHours | Wk_Die_GoodQty | Wk_Die_OEE_Denom |
|---|---|---|---|---|---|
| Week −2 | **Die A** | 10 | 7.5 | 65,000 | 100,000 |
| Week −2 | **Die B** | 6  | 4.5 | 38,000 |  60,000 |
| Week −1 | **Die A** | 10 | 8.0 | 70,000 | 100,000 |

This table carries the raw aggregated KPI fields and SchedHours per die per week. No BSP has been applied yet — these are actuals only.

---

### Step 2A-ii — WeeklyDieBSP (Section 31)

Each row from `WeeklyDieKPI` is enriched with BSP values from the mapping tables built in Step 4. The 3-level `Coalesce(L1 → L2 → L3)` is applied **per KPI per die per row**.

Two extra fields are computed here:
- **`Die_BSP_ConfScore`** — 3 if L1 resolved, 2 if L2, 1 if L3, 0 if no level resolved
- **`CoveredSchedHours`** — equals `Wk_Die_SchedHours` if OEE BSP was resolved for this die, else 0

| WeekStart | Die | Wk_Die_SchedHours | Die_BSP_OEE | Die_BSP_Availability | Die_BSP_ConfScore | CoveredSchedHours |
|---|---|---|---|---|---|---|
| Week −2 | **Die A** | 10 | **87.6%** (L1) | **95.0%** (L1) | **3** | **10** |
| Week −2 | **Die B** | 6  | **Null** (no BSP at any level) | **Null** | **0** | **0** |
| Week −1 | **Die A** | 10 | **87.6%** (L1) | **95.0%** (L1) | **3** | **10** |

**How the L1 lookup works for Die A (Week −2):**
```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die A', Null())  →  87.6%   ← found at L1 ✅
```
**How the L1 lookup fails for Die B (Week −2):**
```
ApplyMap('BSP_L1_OEE_Map',  '0008|10005999|Die B', Null())  →  Null   ← only 5 BSP runs < 10 min
ApplyMap('BSP_L2_OEE_Map',  '0008|10005999|...',   Null())  →  Null   ← no L2 either
ApplyMap('BSP_L3_OEE_Map',  '0008|10005999',       Null())  →  Null   ← total runs < 30
Coalesce(Null, Null, Null)  =  Null  →  CoveredSchedHours = 0
```

> **Why CoveredSchedHours matters:** It is the numerator used in the machine-level coverage % calculation. Die B's 6 hours are accounted in total hours but contribute 0 to covered hours, so they penalise coverage without contributing a benchmark.

---

### Step 2A-iii — WeeklyMachineBSP (Section 32)

`WeeklyDieBSP` is rolled up to **WeekStart + Plant + WC** grain. All die rows within a week are collapsed into a single machine-week row using SchedHours-weighted averages.

**Two different denominator rules apply here:**

1. **Weighted BSP (OEE, Availability, etc.):** Uses only the **covered** SchedHours in both numerator and denominator. Uncovered dies are excluded entirely — they cannot drag the benchmark down.

2. **ConfScore:** Uses **total** SchedHours (covered + uncovered) as the denominator. Die B's zero confidence is diluted into the overall score proportionally to its hours.

#### Week −2 Calculation:

```
Covered dies only (for BSP numerator/denominator):
  Die A: SchedHrs=10, Die_BSP_OEE=87.6%

Wk_BSP_OEE     = (10 × 87.6%) ÷ 10            = 87.6%
Wk_BSP_Avail   = (10 × 95.0%) ÷ 10            = 95.0%

All dies (for ConfScore denominator):
  Die A: SchedHrs=10, ConfScore=3
  Die B: SchedHrs=6,  ConfScore=0

BSP_ConfScore   = (3×10 + 0×6) ÷ (10+6)        = 30 ÷ 16  = 1.875  → MEDIUM
BSP_CoveragePct = 10 covered ÷ 16 total         = 62.5%
```

| Field | Week −2 | Week −1 |
|---|---|---|
| Wk_TotalSchedHours | **16** | **10** |
| Wk_CoveredSchedHours | **10** | **10** |
| BSP_CoveragePct | **62.5%** | **100%** |
| Wk_BSP_OEE | **87.6%** | **87.6%** |
| Wk_BSP_Availability | **95.0%** | **95.0%** |
| BSP_ConfScore | **1.875** (MEDIUM) | **3.0** (HIGH) |

> **ConfScore is 1.875 in Week −2 (MEDIUM), not 3.0.** Die B's 6 uncovered hours pull the weighted confidence below the HIGH threshold (≥ 2.5). In Week −1 only Die A ran, so ConfScore = 3.0 (HIGH). The `CurrentPeriod` table takes the **most recent week's** ConfScore → 3.0 → BSP_Confidence = HIGH.

---

### Step 2A-iv — WeeklyMachineKPI (Section 33)

Parallel to the BSP pipeline, `JobFact_Scoring` is also aggregated to **WeekStart + Plant + WC** grain for the full 13-week trend window. This table holds the **actual** weekly KPI values used for streak calculation and current-period actuals.

| WeekStart | Wk_SchedHours | Wk_OEE | Wk_Availability | Wk_DowntimePct | … |
|---|---|---|---|---|---|
| Week −13 | … | … | … | … | |
| … | | | | | |
| **Week −2** | **16** | **64.4%** | **75.0%** | … | |
| **Week −1** | **10** | **70.0%** | **80.0%** | … | |

After this table is sorted by `Plant + WC + WeekStart ASC`, the streak calculation uses `Peek()` to compare each week against the previous row for the same machine. If OEE this week < OEE last week, the streak increments; otherwise it resets to 0.

In this example, assume Week −1 OEE (70.0%) > Week −2 OEE (64.4%), so OEE **improved** → streak resets to 0.

---

### Step 2B — Weighted BSP at Machine + Week Level

#### Why do we need this step at all?

You already have the BSP per die from Part 1. So why not just compare directly?

Because in any given week **the machine runs multiple dies** — different products, different job types. Each die has its own BSP, and those BSPs can be very different. You cannot use a single die's BSP to judge the machine's overall week performance, because the machine may have spent most of its time on a completely different die.

**Example of why a simple average would be wrong:**

Imagine Die A (BSP OEE = 87.6%) ran for 1 hour this week, and Die B (BSP OEE = 50%) ran for 39 hours. A simple average BSP would be (87.6 + 50) ÷ 2 = 68.8% — but that benchmark is almost entirely from Die A which barely ran. The machine spent 97.5% of its time on Die B, so the benchmark should almost entirely reflect Die B's BSP of 50%.

**The correct approach: weight each die's BSP by how many hours it actually ran (SchedHours).** This produces a benchmark that reflects the actual product mix the machine ran that week — a fair, like-for-like comparison.

Think of it this way:
> *"Given the specific mix of products this machine ran this week, what OEE should it have achieved if it performed at its proven best on each of those products?"*

That is the weighted BSP. It rises when the machine ran more of its high-performing dies, and falls when it ran more challenging product — and the comparison is always fair because the actual performance is measured against the same product mix.

---

#### Week −2 Calculation:

The machine ran Die A (10 hrs) and Die B (6 hrs) this week.  
Die A has an L1 BSP. Die B has no BSP — its hours count in the **total** (denominator for coverage) but cannot contribute a benchmark value.

| Die | SchedHrs | BSP OEE | Has BSP? | Weighted Contribution |
|---|---|---|---|---|
| Die A | 10 | 87.6% | ✅ Yes (L1) | 10 × 87.6% = **876** |
| Die B | 6  | — | ❌ No BSP | excluded from numerator |

```
Covered SchedHours  = 10  (only Die A contributes)
Total SchedHours    = 16  (Die A + Die B)

Wk_BSP_OEE        = 876 ÷ 10               = 87.6%   ← weighted over COVERED hours only
Wk_BSP_Avail      = (10 × 95%) ÷ 10        = 95.0%
BSP_CoveragePct   = 10 covered ÷ 16 total   = 62.5%   ← Die B's 6 hrs had no benchmark
BSP_ConfScore     = (10 × 3) ÷ 10           = 3.0  → HIGH
```

> **Note:** The BSP weighted average uses only covered hours in both numerator and denominator. This prevents Die B's uncovered hours from diluting the benchmark — if they were included in the denominator, the benchmark would appear artificially low.

---

#### Week −1 Calculation:

Only Die A ran this week, so the weighted BSP is simply Die A's BSP — no blending needed.

| Die | SchedHrs | BSP OEE | Has BSP? | Weighted Contribution |
|---|---|---|---|---|
| Die A | 10 | 87.6% | ✅ Yes (L1) | 876 |

```
Wk_BSP_OEE        = 876 ÷ 10               = 87.6%
Wk_BSP_Avail      = (10 × 95%) ÷ 10        = 95.0%
BSP_CoveragePct   = 10 ÷ 10                 = 100%
BSP_ConfScore     = 3.0  → HIGH
```

---

### Step 2C — Current Period Aggregation (2-week average)

`CurrentPeriod` is built from `WeeklyMachineBSP` filtered to the 2-week window, joined with `WeeklyMachineKPI_Sorted` (for actuals and streaks). The coverage spans **both weeks** using summed numerator and denominator:

```
Cur_OEE              = Avg(64.4%, 70.0%)                    = 67.2%
Cur_Availability     = Avg(75.0%, 80.0%)                    = 77.5%

Cur_BSP_OEE          = Avg(87.6%, 87.6%)                    = 87.6%
Cur_BSP_Availability = Avg(95.0%, 95.0%)                    = 95.0%

Cur_SchedHours       = 16 + 10                              = 26 hrs   ← Sum of 2 weeks

Cur_BSP_CoveragePct  = Sum(Wk_CoveredSchedHours)            = 10 + 10  = 20
                     ÷ Sum(Wk_TotalSchedHours)              = 16 + 10  = 26
                     = 20 ÷ 26                              = 76.9%    ← both weeks, not just last

Cur_BSP_ConfScore    = Max(WeekStart = vLastWeekStart → BSP_ConfScore) = 3.0   ← last week's score only
BSP_Confidence       = "HIGH"   ← ConfScore 3.0 ≥ 2.5 threshold
```

> Coverage 76.9% > 50% threshold ✅ → Insight is allowed to fire

> **Note on coverage vs confidence:** Coverage (76.9%) uses both weeks to reflect the true share of hours with a resolved BSP. ConfScore (3.0) uses only the most recent week — it answers "how reliable is the benchmark right now?", not "how much of the machine's time was covered overall?"

---

## PART 3 — Scoring the Insight

### Gap Score (0–100, weight 70%)

OEE is higher-is-better: `Gap = (BSP − Actual) ÷ BSP × 100`

```
OEE Gap          = (87.6% − 67.2%) ÷ 87.6% × 100   = 23.3  → Gap_Score = 23.3
Availability Gap = (95.0% − 77.5%) ÷ 95.0% × 100   = 18.4  → Gap_Score = 18.4
```

### Trend Score (0–100, weight 30%)

Assume the machine's OEE has been declining 3 consecutive weeks:
```
Streak_4wk   = Min(3, 4)   = 3
Streak_13wk  = 3

Trend_Score  = Min(100, ((3 + 3) ÷ 2) ÷ 4 × 100)   = Min(100, 75) = 75.0
```

### Composite Score

```
OEE Composite       = 23.3 × 0.70 + 75.0 × 0.30   = 16.3 + 22.5  = 38.8
Availability Composite = 18.4 × 0.70 + 75.0 × 0.30 = 12.9 + 22.5 = 35.4
```

---

## PART 4 — Final InsightRecords Row (OEE)

| Field | Value |
|---|---|
| Insight_ID | `0008\|10005999\|2025-04-07\|OEE` |
| Plant | 0008 |
| WC Object ID | 10005999 |
| Plant - WC | Carol Stream - 10005999 |
| KPI_Name | OEE |
| Period_Start | 2025-04-07 |
| Cur_Actual | **67.2%** |
| BSP_Benchmark | **87.6%** |
| Gap_Pct | 23.3 |
| Gap_Score | 23.3 |
| Streak_4wk | 3 |
| Streak_13wk | 3 |
| Trend_Score | 75.0 |
| **Composite_Score** | **38.8** |
| Cur_SchedHours | 26 hrs |
| Cur_BSP_CoveragePct | 76.9% |
| BSP_Confidence | HIGH |
| Insight_Rank | (ranked within Plant 0008 by Composite_Score DESC) |

---

## Key Takeaways

1. **BSP is not the single best day** — it is the **P90 across all qualifying job runs** on the same die. Outlier great days don't set an impossible target; the top 10% of runs sets it.

2. **Each run is one data point** — a complete order aggregated across all its rows (all shifts, all fSched values), filtered to RunHours > 2.

3. **Die B was ignored in the BSP** because it only had 5 runs — not enough history at any fallback level. It still ran in the current period (lowering the actual OEE), but it had no benchmark to compare against, so it dragged down the actual without changing the benchmark.

4. **Coverage matters** — Die B's 6 hours of SchedHours in Week −2 were "uncovered," pulling coverage to 62.5% that week. Had that been the last week, and if the machine ran Die B more, coverage could drop below 50% and suppress the insight entirely.

5. **BSP_CoveragePct = 76.9% here** (20 covered hrs ÷ 26 total hrs across both weeks). Die B's 6 uncovered hours in Week −2 reduce coverage below 100%. Had coverage dropped below 50%, the insight would have been suppressed entirely. BSP_Confidence = HIGH because it uses only the most recent week's ConfScore (3.0), not the coverage-weighted score.

---

## PART 5 — Pipeline Flowchart: Grain at Every Stage

This shows how data flows from raw fact rows through to `InsightRecords`, what grain each table operates at, and how BSP and actuals are matched and aggregated.

```
╔══════════════════════════════════════════════════════════════════════════╗
║  JobFact_Raw                                                             ║
║  Grain: Date + WC + Shift + Operator + Order + Die + Reason + fSched    ║
║  (one row per scheduling slot — a single shift × order × reason combo)  ║
╚══════════════════════╦═══════════════════════════════════════════════════╝
                       │
         ┌─────────────┴─────────────────────────┐
         │  BSP PIPELINE                         │  SCORING PIPELINE
         │  (Historical window: Jan 2025 →        │  (13-week trend window)
         │   last completed week)                 │
         ▼                                        ▼
╔════════════════════════════╗        ╔═══════════════════════════════════╗
║  JobFact_Job_BSP_Agg       ║        ║  JobFact_Scoring_Agg              ║
║  Grain: Date+WC+Shift+Die  ║        ║  Grain: Date+WC+Die+PltMat+       ║
║  (all fSched rows summed   ║        ║         Carton+Shift+Operator+    ║
║   into one shift-die unit) ║        ║         Order                     ║
╚════════════╦═══════════════╝        ╚═══════════════╦═══════════════════╝
             │ RunHours > 2 filter                     │ Board attrs applied
             ▼                                        ▼
╔════════════════════════════╗        ╔═══════════════════════════════════╗
║  JobFact_Job_BSP  (L1)     ║        ║  JobFact_Scoring                  ║
║  Grain: Date+WC+Shift+Die  ║        ║  Same grain + board attributes    ║
║                            ║        ║  + MaxSpeed + OEE_Denom           ║
║  JobFact_Job_BSP_L2        ║        ╚═══════════════╦═══════════════════╝
║  Grain: Date+WC+Shift+     ║                        │
║         Die+PltMatKey      ║                        ▼
╚════════════╦═══════════════╝        ╔═══════════════════════════════════╗
             │                        ║  WeeklyDieKPI  (Section 30)       ║
             │  GROUP BY:             ║  Grain: WeekStart+Plant+WC+Die    ║
             │  L1: Plant+WC+Die      ║  Actual SchedHrs, GoodQty, etc.   ║
             │  L2: Plant+WC+         ║  per die per week                 ║
             │      BoardTypeGrp+     ╚═══════════════╦═══════════════════╝
             │      BoardCaliper                      │
             │  L3: Plant+WC          ╔═══════════════▼═══════════════════╗
             ▼                        ║  WeeklyDieBSP  (Section 31)       ║
╔════════════════════════════╗        ║  Grain: WeekStart+Plant+WC+Die    ║
║  BSP Tables (L1/L2/L3)     ║        ║                                   ║
║  Main (9 KPIs):            ║        ║  BSP LOOKUP per die:              ║
║   L1: Plant+WC+Die         ║        ║  Coalesce(                        ║
║   L2: Plant+WC+BTG+Caliper ║◄───────║    L1 map: Plant|WC|Die           ║
║   L3: Plant+WC             ║        ║    L2 map: Plant|WC|BTG|Caliper   ║
║                            ║        ║    L3 map: Plant|WC               ║
║  Setup (2 KPIs):           ║        ║  )                                ║
║   adds MROClass to key     ║        ║                                   ║
║                            ║        ║  Die_BSP_ConfScore: 3/2/1/0       ║
║  DownReason / ScrReason:   ║        ║  CoveredSchedHours:               ║
║   adds ReasonKey to key    ║        ║    = SchedHrs if BSP resolved     ║
╚════════════╦═══════════════╝        ║    = 0 if no BSP                  ║
             │ → converted to         ╚═══════════════╦═══════════════════╝
             │   mapping tables                       │
             │   (36+ maps, no                        │  GROUP BY WeekStart+Plant+WC
             │   regular tables                       │  Weighted avg by SchedHrs
             │   → no synth keys)                     ▼
             │                        ╔═══════════════════════════════════╗
             │                        ║  WeeklyMachineBSP  (Section 32)   ║
             │                        ║  Grain: WeekStart+Plant+WC        ║
             │                        ║                                   ║
             │                        ║  Wk_BSP_OEE   = weighted avg of   ║
             │                        ║    covered dies only              ║
             │                        ║  BSP_CoveragePct = Covered÷Total  ║
             │                        ║  BSP_ConfScore = weighted avg of   ║
             │                        ║    ALL dies (covered + uncovered) ║
             │                        ╚═══════════════╦═══════════════════╝
             │                                        │
             │          ╔═════════════════════════════╝
             │          │
             │          │   WeeklyMachineKPI (Section 33)
             │          │   Grain: WeekStart+Plant+WC
             │          │   Actual Wk_OEE, Wk_Avail, …
             │          │   (all 13 weeks)
             │          │         │
             │          │         ▼
             │          │   Streak via Peek() (sorted ASC by WeekStart)
             │          │   Streak_OEE, Streak_Avail, …
             │          │         │
             │          └────┬────┘
             │               │
             │               ▼
             │   ╔═══════════════════════════════════╗
             │   ║  CurrentPeriod  (Section 37)       ║
             │   ║  Grain: Plant+WC  (2-week summary) ║
             │   ║                                    ║
             │   ║  Cur_OEE      = Avg(Wk_OEE)        ║
             │   ║  Cur_BSP_OEE  = Avg(Wk_BSP_OEE)   ║
             │   ║  Cur_SchedHrs = Sum(Wk_SchedHrs)   ║
             │   ║  Cur_Coverage = Sum(Covered)÷       ║
             │   ║                 Sum(Total) ← both   ║
             │   ║                 weeks               ║
             │   ║  Cur_ConfScore = last week's only   ║
             │   ╚═══════════════╦═══════════════════╝
             │                   │
             │     Fires insight when:
             │       Cur_Actual worse than BSP_Benchmark
             │       AND CoveragePct > 50%  (strict)
             │                   │
             │                   ▼
             │   ╔═══════════════════════════════════╗
             └──►║  InsightRecords  (Section 42–47)  ║
                 ║  Grain: Plant+WC+KPI_Name         ║
                 ║  (one row per machine per KPI)    ║
                 ║                                   ║
                 ║  Composite = Gap×0.7 + Trend×0.3  ║
                 ║  Ranked by Composite DESC         ║
                 ║  within Plant                     ║
                 ╚═══════════════════════════════════╝
```

---

### Grain Summary Table

| Table | Grain | What it represents |
|---|---|---|
| `JobFact_Raw` | Date + WC + Shift + Operator + Order + Die + ReasonKey + fSched | Every scheduling slot row in the source QVD |
| `JobFact_Job_BSP` (L1) | Date + WC + Shift + Die | One unit of BSP history — all hours/qty for a single die on a single shift on a single date |
| `JobFact_Job_BSP_L2` | Date + WC + Shift + Die + PltMatKey | Same as L1 but split by material for board attribute resolution |
| `BSP_Main_L1` | Plant + WC + Die | P90/P10 benchmark across all qualifying runs for this machine+die |
| `BSP_Main_L2` | Plant + WC + BoardTypeGroup + BoardCaliper | P90/P10 benchmark across all qualifying runs for this machine+board type |
| `BSP_Main_L3` | Plant + WC | P90/P10 benchmark across all qualifying runs for this machine regardless of die |
| `WeeklyDieKPI` | WeekStart + Plant + WC + Die | Actual weekly totals per die — raw material for scoring |
| `WeeklyDieBSP` | WeekStart + Plant + WC + Die | Actual + BSP resolved per die — coverage and confidence assigned here |
| `WeeklyMachineBSP` | WeekStart + Plant + WC | BSP and coverage rolled to machine level — weighted by SchedHours |
| `WeeklyMachineKPI` | WeekStart + Plant + WC | Actual weekly KPI per machine — streak computed via Peek() on this table |
| `CurrentPeriod` | Plant + WC | 2-week average actuals + BSP — the comparison happens here |
| `InsightRecords` | Plant + WC + KPI_Name (+ ReasonKey for reason insights) | Final output — one row per machine per KPI that fires |

### How BSP and Current Period Match

The BSP is calculated at **die grain** (L1) or **board type grain** (L2) or **machine grain** (L3). The current period actual is always at **machine grain** (WeekStart + Plant + WC after `WeeklyMachineKPI` aggregation). The bridge between the two is:

1. BSP is resolved per die (in `WeeklyDieBSP`) using the die that **actually ran in the current period**
2. Those per-die BSPs are weighted together into a single machine-level BSP (in `WeeklyMachineBSP`) using the **same period's SchedHours as weights**
3. The weighted BSP is then compared to the actual machine-level KPI (in `CurrentPeriod`)

This ensures the benchmark always reflects the specific product mix the machine ran — not a generic machine average.
