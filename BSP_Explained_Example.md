# BSP Explained — OEE & Availability Walkthrough
### Machine A: 10005999 | Plant 0008 | Dept: Sheetfed Printing  
### Machine B: 10006101 | Plant 0008 | Dept: Gluer *(contrast block — PART 4B)*

---

## Setup Assumptions

| Parameter | Machine A | Machine B |
|---|---|---|
| WC Object ID | 10005999 | 10006101 |
| Plant | 0008 | 0008 |
| Department | Sheetfed Printing | Gluer |
| MaxSpeed | 10,000 u/hr (OEM Speed) | 18,000 cartons/hr (MaxGluerCartons) |
| L2_ExtraDim source | `''` (empty — Sheetfed Printing uses board grain only) | `CartonStyle` (Gluer machines: carton style drives run efficiency) |
| BSP window | Rolling 24 months back (`v2YearStart = MonthStart(AddMonths(Today(), -24))`) | Same |
| Current period | 1 most recent completed week (Week −1, `v2WeekStart = vLastWeekStart`) | Same |

---

## PART 1 — Building the BSP from Historical Runs (Machine A)

### Step 1A — Die population in the BSP window

Machine A ran **four dies** in the BSP history window with the following qualifying run counts (RunHours > 2 per run):

| Die | BoardTypeGroup | BoardCaliper | L2_ExtraDim | Qualifying runs in BSP window |
|---|---|---|---|---|
| Die A | SBS | 24pt | `''` | **18** |
| Die B | SBS | 24pt | `''` | **8** |
| Die C | SBS | 24pt | `''` | **5** |
| Die D | CRB | 18pt | `''` | **4** |

**Die E** has **no historical runs** in the BSP window. It appears only in the current period (Week −1).

---

### Step 1B — Apply the 3-Level BSP Fallback

| Level | Grain | Min runs required | Pool construction | Die A | Die B | Die C | Die D |
|---|---|---|---|---|---|---|---|
| **L1** | Plant + WC + Die | **15** | Individual die runs | ✅ 18 ≥ 15 | ❌ 8 < 15 | ❌ 5 < 15 | ❌ 4 < 15 |
| **L2** | Plant + WC + BoardTypeGroup + BoardCaliper + L2_ExtraDim | **25** | All dies sharing same BTG+Caliper+ExtraDim | — | ✅ SBS+24pt pool = A+B+C = 31 ≥ 25 | ✅ Same pool | ❌ CRB+18pt pool = 4 < 25 |
| **L3** | Plant + WC | **35** | All dies on this machine | — | — | — | ✅ Total = 18+8+5+4 = 35 ≥ 35 |

> **Results:**
> - **Die A** → **L1** (HIGH confidence — 18 runs, own die history)
> - **Die B** → **L2** (MEDIUM — insufficient at L1, but SBS+24pt pool has 31 runs)
> - **Die C** → **L2** (MEDIUM — same pool as Die B)
> - **Die D** → **L3** (LOW — CRB+18pt pool too small; machine pool = 35 just meets threshold)
> - **Die E** → **No BSP at any level** — zero historical runs; uncovered hours

---

### Step 1C — Calculating the BSPs (P75 for higher-is-better KPIs)

The engine uses **P75** for higher-is-better KPIs (OEE, Availability, Performance, Quality, Speed, Net Throughput Rate) and **P25** for lower-is-better KPIs (Downtime %, Scrap Rate, Setup Hrs/Event, Setup Time %). This is the 75th / 25th percentile across all qualifying run-level values in the pool.

#### Die A — L1 BSP (n=18, own die)

**OEE values, sorted ascending (0-indexed 0 → 17):**

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 54 | 58 | 61 | 64 | 66 | 68 | 70 | 72 | 74 | 76 | 78 | 79 | **81** | **83** | 85 | 87 | 89 | 91 |

P75 position (0-indexed) = `(n−1) × 0.75 = 17 × 0.75 = 12.75`  
Interpolate: `value[12] + 0.75 × (value[13] − value[12]) = 81 + 0.75 × (83 − 81) = 81 + 1.5`

> **Die A L1 BSP OEE = 82.5%**

**Availability values, sorted ascending:**

| 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | 63 | 65 | 68 | 70 | 72 | 74 | 76 | 78 | 80 | 82 | 83 | **85** | **86** | 88 | 90 | 92 | 94 |

Interpolate at 12.75: `85 + 0.75 × (86 − 85) = 85.75`

> **Die A L1 BSP Availability = 85.8%**

---

#### L2 Pool (SBS + 24pt + `''`) — Die A + Die B + Die C combined (n=31)

All 31 run-level OEE values from Dies A, B, and C are sorted together (Die A: 18 runs, Die B: 8 runs, Die C: 5 runs).

P75 position = `(31−1) × 0.75 = 30 × 0.75 = 22.5`  
Interpolated across the combined sorted list:

> **L2 BSP OEE = 77.5%** &nbsp;*(pulled below Die A's L1 = 82.5% because the pool includes weaker Die B and Die C runs)*  
> **L2 BSP Availability = 80.5%**

---

#### L3 Pool (Machine-only) — All dies combined (n=35)

All 35 qualifying runs across Dies A, B, C, and D are sorted together. Die D's CRB/18pt runs are lower-performing, pulling the percentile down further.

P75 position = `(35−1) × 0.75 = 34 × 0.75 = 25.5`

> **L3 BSP OEE = 76.5%**  
> **L3 BSP Availability = 78.5%**

---

### BSP Summary for Machine A

| Die | Resolved Level | Pool Size (n) | BSP OEE | BSP Availability | Die_BSP_ConfScore |
|---|---|---|---|---|---|
| Die A | L1 | 18 | 82.5% | 85.8% | 3 |
| Die B | L2 (SBS+24pt) | 31 | 77.5% | 80.5% | 2 |
| Die C | L2 (SBS+24pt) | 31 | 77.5% | 80.5% | 2 |
| Die D | L3 (Machine) | 35 | 76.5% | 78.5% | 1 |
| Die E | None | 0 | Null | Null | 0 |

`Die_BSP_ConfScore`: 3 = L1 resolved, 2 = L2, 1 = L3, 0 = no BSP.

---

## PART 2 — Trend Window & Current 1-Week Period

Machine A ran 6 job runs across the two most recent weeks. The **13-week trend window** captures all of them; the **current period** is only **Week −1**.

| Run | Week | Die | SchedHrs | RunHrs | GoodQty | OEE_Denom (SchedHrs × MaxSpeed) |
|---|---|---|---|---|---|---|
| 1 | Week −2 | Die A | 8 | 6.5 | 56,000 | 80,000 |
| 2 | Week −2 | Die B | 6 | 4.8 | 38,000 | 60,000 |
| 3 | Week −2 | Die D | 4 | 3.0 | 22,000 | 40,000 |
| 4 | Week −1 | Die A | 10 | 7.5 | 65,000 | 100,000 |
| 5 | Week −1 | Die C | 5 | 3.8 | 30,000 | 50,000 |
| 6 | Week −1 | **Die E** | 3 | 2.1 | 16,000 | 30,000 |

> **Week −1 deliberately has all four resolution outcomes:** Die A (L1), Die C (L2), Die E (no BSP). Week −2 has Die D (L3) so the L3 path is demonstrated in the trend narrative.

---

### Step 2A — Weekly Machine KPI (actuals, both weeks)

#### Week −2:
| Metric | Calculation | Value |
|---|---|---|
| Total SchedHours | 8 + 6 + 4 | **18 hrs** |
| Total RunHours | 6.5 + 4.8 + 3.0 | **14.3 hrs** |
| Total GoodQty | 56,000 + 38,000 + 22,000 | **116,000 units** |
| Total OEE_Denom | 80,000 + 60,000 + 40,000 | **180,000 units** |
| **Wk_OEE** | 116,000 ÷ 180,000 | **64.4%** |
| **Wk_Availability** | 14.3 ÷ 18 | **79.4%** |

#### Week −1:
| Metric | Calculation | Value |
|---|---|---|
| Total SchedHours | 10 + 5 + 3 | **18 hrs** |
| Total RunHours | 7.5 + 3.8 + 2.1 | **13.4 hrs** |
| Total GoodQty | 65,000 + 30,000 + 16,000 | **111,000 units** |
| Total OEE_Denom | 100,000 + 50,000 + 30,000 | **180,000 units** |
| **Wk_OEE** | 111,000 ÷ 180,000 | **61.7%** |
| **Wk_Availability** | 13.4 ÷ 18 | **74.4%** |

---

### Step 2A-i — WeeklyDieKPI (Section 30)

Aggregated to `WeekStart + Plant + WC + Die` grain. Actuals only — no BSP applied yet.

| WeekStart | Die | Wk_Die_SchedHours | Wk_Die_RunHours | Wk_Die_GoodQty | Wk_Die_OEE_Denom |
|---|---|---|---|---|---|
| Week −2 | Die A | 8 | 6.5 | 56,000 | 80,000 |
| Week −2 | Die B | 6 | 4.8 | 38,000 | 60,000 |
| Week −2 | Die D | 4 | 3.0 | 22,000 | 40,000 |
| Week −1 | Die A | 10 | 7.5 | 65,000 | 100,000 |
| Week −1 | Die C | 5 | 3.8 | 30,000 | 50,000 |
| Week −1 | Die E | 3 | 2.1 | 16,000 | 30,000 |

---

### Step 2A-ii — WeeklyDieBSP (Section 31)

Each row from `WeeklyDieKPI` is enriched by a 3-level `Coalesce(L1 → L2 → L3)` lookup per KPI per die.

#### Week −1 — lookup trace for each die:

**Die A (L1 resolves):**
```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die A', Null())  →  82.5%   ← L1 hit ✅
```

**Die C (L1 misses, L2 resolves):**
```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die C', Null())              →  Null   ← <15 runs
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|SBS|24pt|', Null())          →  77.5%  ← L2 hit ✅
  (L2_ExtraDim = '' for Sheetfed Printing → key ends with empty string)
```

**Die E (all levels miss):**
```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die E', Null())              →  Null   ← no history
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|CUK|28pt|', Null())          →  Null   ← no pool
ApplyMap('BSP_L3_OEE_Map', '0008|10005999',            Null())          →  Null   ← Die E excluded from L3 pool
Coalesce(Null, Null, Null) = Null   → CoveredSchedHours = 0
```

#### Week −2 — Die D trace (L3 path):

**Die D (L1 and L2 miss, L3 resolves):**
```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die D', Null())              →  Null   ← 4 < 15
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|CRB|18pt|', Null())          →  Null   ← CRB+18pt pool = 4 < 25
ApplyMap('BSP_L3_OEE_Map', '0008|10005999',            Null())          →  76.5%  ← L3 hit ✅ (pool=35)
```

#### WeeklyDieBSP table:

| WeekStart | Die | Wk_Die_SchedHours | Die_BSP_OEE | Die_BSP_Availability | Die_BSP_ConfScore | Die_BSP_PoolSize | CoveredSchedHours |
|---|---|---|---|---|---|---|---|
| Week −2 | Die A | 8 | **82.5%** (L1) | **85.8%** (L1) | **3** | **18** | **8** |
| Week −2 | Die B | 6 | **77.5%** (L2) | **80.5%** (L2) | **2** | **31** | **6** |
| Week −2 | Die D | 4 | **76.5%** (L3) | **78.5%** (L3) | **1** | **35** | **4** |
| Week −1 | Die A | 10 | **82.5%** (L1) | **85.8%** (L1) | **3** | **18** | **10** |
| Week −1 | Die C | 5 | **77.5%** (L2) | **80.5%** (L2) | **2** | **31** | **5** |
| Week −1 | Die E | 3 | **Null** (no BSP) | **Null** | **0** | **0** | **0** |

---

### Step 2A-iii — WeeklyMachineBSP (Section 32)

`WeeklyDieBSP` is rolled up to `WeekStart + Plant + WC` using **SchedHours-weighted averages**.

Two denominator rules apply:
1. **Weighted BSP (OEE, Availability, …):** Uses only **covered** SchedHours (dies with a resolved BSP) in both numerator and denominator.
2. **ConfScore and PoolSize:** Uses **total** SchedHours (covered + uncovered). Uncovered dies contribute 0 to numerator, pulling both metrics down proportionally.
3. **BSP_CoveragePct:** `Sum(CoveredSchedHours) ÷ Sum(TotalSchedHours)` — all dies in denominator.

#### Week −2 Calculation (all 3 dies have a resolved BSP → 100% coverage):

```
Covered dies: Die A (8h, L1), Die B (6h, L2), Die D (4h, L3)
Total SchedHours = 18   Covered SchedHours = 18

Wk_BSP_OEE   = (8×82.5% + 6×77.5% + 4×76.5%) ÷ 18
             = (660.0 + 465.0 + 306.0) ÷ 18
             = 1431.0 ÷ 18  =  79.5%

Wk_BSP_Avail = (8×85.8% + 6×80.5% + 4×78.5%) ÷ 18
             = (686.4 + 483.0 + 314.0) ÷ 18
             = 1483.4 ÷ 18  =  82.4%

BSP_CoveragePct = 18 covered ÷ 18 total = 100%

BSP_ConfScore   = (8×3 + 6×2 + 4×1) ÷ 18
                = (24 + 12 + 4) ÷ 18
                = 40 ÷ 18  =  2.22  →  MEDIUM

BSP_PoolSize    = (8×18 + 6×31 + 4×35) ÷ 18
                = (144 + 186 + 140) ÷ 18
                = 470 ÷ 18  =  26.1
```

#### Week −1 Calculation (Die E is uncovered):

```
Covered dies: Die A (10h, L1), Die C (5h, L2)
Uncovered:    Die E (3h, no BSP)
Total SchedHours = 18   Covered SchedHours = 15

Wk_BSP_OEE   = (10×82.5% + 5×77.5%) ÷ 15          ← denominator = COVERED only
             = (825.0 + 387.5) ÷ 15
             = 1212.5 ÷ 15  =  80.8%

Wk_BSP_Avail = (10×85.8% + 5×80.5%) ÷ 15
             = (858.0 + 402.5) ÷ 15
             = 1260.5 ÷ 15  =  84.0%

BSP_CoveragePct = 15 covered ÷ 18 total = 83.3%

BSP_ConfScore   = (10×3 + 5×2 + 3×0) ÷ 18          ← denominator = ALL dies
                = (30 + 10 + 0) ÷ 18
                = 40 ÷ 18  =  2.22  →  MEDIUM

BSP_PoolSize    = (10×18 + 5×31 + 3×0) ÷ 18         ← denominator = ALL dies
                = (180 + 155 + 0) ÷ 18
                = 335 ÷ 18  =  18.6
```

> **Why PoolSize is 18.6, not 18 or 31:** It is a SchedHours-weighted average of the run-count behind each die's resolved BSP, taken over all dies (covered and uncovered). Die E contributes 3 hours of weight but 0 pool runs, pulling the weighted average down. If only Die A had run (10 hrs, L1, 18 runs), PoolSize would simply be 18.0.

**WeeklyMachineBSP summary:**

| Field | Week −2 | Week −1 |
|---|---|---|
| Wk_TotalSchedHours | **18** | **18** |
| Wk_CoveredSchedHours | **18** | **15** |
| BSP_CoveragePct | **100.0%** | **83.3%** |
| Wk_BSP_OEE | **79.5%** | **80.8%** |
| Wk_BSP_Availability | **82.4%** | **84.0%** |
| BSP_ConfScore | **2.22** (MEDIUM) | **2.22** (MEDIUM) |
| BSP_PoolSize | **26.1** | **18.6** |

> **Why ConfScore is 2.22 in both weeks (MEDIUM), not HIGH:**  
> Week −2: Die D's L3 resolution (ConfScore=1) and Die B's L2 (ConfScore=2) pull the weighted average below the HIGH threshold (≥ 2.5). If only Die A had run in Week −2, ConfScore would be 3.0 (HIGH).  
> Week −1: Die E's zero confidence (ConfScore=0) across 3 uncovered hours pulls the weighted average from what would be 2.67 (if only A+C ran) down to 2.22.  
> The `CurrentPeriod` table takes **Week −1's** ConfScore → 2.22 → **BSP_Confidence = MEDIUM**.

---

### Step 2A-iv — WeeklyMachineKPI (Section 33)

Parallel to the BSP pipeline, `JobFact_Scoring` is aggregated to `WeekStart + Plant + WC` grain for the full 13-week trend window. This table holds the **actual** weekly KPI values used for streak calculation.

| WeekStart | Wk_SchedHours | Wk_OEE | Wk_Availability | … |
|---|---|---|---|---|
| Week −13 … | … | … | … | |
| **Week −2** | **18** | **64.4%** | **79.4%** | |
| **Week −1** | **18** | **61.7%** | **74.4%** | |

After sorting by `Plant + WC + WeekStart ASC`, `Peek()` compares each week to the previous row for the same machine. In this example, OEE worsened from 64.4% (Wk−2) to 61.7% (Wk−1) — the streak increments rather than resets.

Assume OEE was below its weekly BSP benchmark for **3 of the last 4 completed weeks**: **`Streak_4wk = 3`**.

---

### Step 2B — Why the Weighted BSP Is Necessary

Die A's L1 BSP (82.5%) is the only per-die BSP that could describe this machine, yet Die C and Die E also ran in Week −1. Applying Die A's BSP to a week that was 28% Die E (which has no benchmark) and 28% Die C (which is weaker) would misrepresent the week's difficulty.

The weighted BSP (80.8%) answers: *"Given the specific product mix this machine ran this week, what OEE should it have achieved if it performed at its proven best on each of those products?"* The benchmark rises when the machine ran more of its high-confidence dies and falls when it ran more challenging or new product.

---

### Step 2C — Current Period Aggregation (Week −1 only)

`CurrentPeriod` is built from `WeeklyMachineBSP` and `WeeklyMachineKPI_Sorted` filtered to **Week −1 only** (`v2WeekStart = vLastWeekStart`).

```
Cur_OEE              = 61.7%   (Week −1 actual)
Cur_Availability     = 74.4%

Cur_BSP_OEE          = 80.8%   (weighted BSP for Week −1)
Cur_BSP_Availability = 84.0%

Cur_SchedHours       = Sum(Wk_SchedHours)    = 18 hrs
Cur_RunHours         = Sum(Wk_RunHours)      = 13.4 hrs

Cur_BSP_CoveragePct  = Sum(Wk_CoveredSchedHours) ÷ Sum(Wk_TotalSchedHours)
                     = 15 ÷ 18 = 83.3%

Cur_BSP_ConfScore    = Max(If(WeekStart = vLastWeekStart, BSP_ConfScore))  = 2.22
Cur_BSP_PoolSize     = Max(If(WeekStart = vLastWeekStart, BSP_PoolSize))   = 18.6
BSP_Confidence       = "MEDIUM"   ← ConfScore 2.22 ≥ 1.5 and < 2.5
```

> Coverage 83.3% > 50% threshold ✅ → Insight is allowed to fire

> **Note:** `v2WeekStart = vLastWeekStart` (both set to −1). Despite the variable name, the current period is exactly **1 week**. The name is a legacy artifact.

---

## PART 3 — Scoring the Insight

### Step 1 — Gap_Pct (relative gap, display only)

OEE is higher-is-better: `Gap_Pct = (BSP − Actual) ÷ BSP × 100`

```
OEE Gap_Pct          = (80.8% − 61.7%) ÷ 80.8% × 100   = 23.6
Availability Gap_Pct = (84.0% − 74.4%) ÷ 84.0% × 100   = 11.4
```

`Gap_Pct` is for display in the front-end only — it is **not used in scoring**.

---

### Step 2 — GapHrs (true scheduled hours lost, computed in Section 42)

GapHrs converts the percentage gap into real scheduled hours. The formula differs by KPI type:

| KPI type | GapHrs formula | Example |
|---|---|---|
| **Pct-based** (OEE, Avail, Performance, Quality, Downtime%, ScrapRate, SetupTime%) | `(BSP − Actual) × Cur_SchedHours` | See below |
| **Speed** | `(BSP_Speed − Cur_Speed) ÷ BSP_Speed × Cur_RunHours` | Speed deficit fraction × run-hours |
| **Net Throughput Rate** | `(BSP_NTR − Cur_NTR) ÷ BSP_NTR × (Cur_RunHours + Cur_DowntimeHrs)` | Rate-deficit fraction × production-time hours |
| **Setup Hrs/Event** | `(Cur_SetupHrsPerEvent − BSP_SetupHrsPerEvent) × Cur_SetupEventCount` | Excess hrs/event × event count |

```
OEE GapHrs          = (80.8% − 61.7%) × 18   = 0.191 × 18   = 3.44 hrs
Availability GapHrs = (84.0% − 74.4%) × 18   = 0.096 × 18   = 1.73 hrs
```

> GapHrs is an **intermediate field only** — it does not appear in the final `InsightRecords` schema.

---

### Step 3 — OEE_Impact (hours lost + urgency weighting, Section 43)

With `Streak_4wk = 3`:

```
OEE_Impact = Round(GapHrs × (1 + RangeMin(Streak_4wk, 4) / 4), 0.01)

OEE:
  = Round(3.44 × (1 + 3/4), 0.01)
  = Round(3.44 × 1.75, 0.01)
  = 6.02 hrs

Availability:
  = Round(1.73 × 1.75, 0.01)
  = 3.03 hrs
```

The streak multiplier (`1 + Streak/4`, capped at `1 + 4/4 = 2.0×`) adds urgency for persistent problems. A machine missing OEE BSP for 4+ consecutive weeks gets a **2.0× uplift** over a one-time miss, reflecting the compounding cost of a sustained gap. Streak is capped at 4 via `RangeMin(Streak_4wk, 4)`.

`WHERE GapHrs > 0` — rows where actual already meets or beats BSP are suppressed entirely (no negative impacts reported).

---

## PART 4 — Final InsightRecords Schema and Field Guide

### InsightRecords Row — Machine A, OEE

| Field | Value | Notes |
|---|---|---|
| **Insight_ID** | `0008\|10005999\|2025-04-14\|OEE` | `Plant\|WC\|PeriodStart\|KPIName` — stable dedup key |
| **Plant** | 0008 | |
| **WC Object ID** | 10005999 | |
| **Plant - WC** | Carol Stream - 10005999 | |
| **Department** | Sheetfed Printing | |
| **Period_Start** | 2025-04-14 | Start of Week −1 (the 1-week current period) |
| **KPI_Name** | OEE | |
| **KPI_Category** | **Outcome** | See field guide below |
| **Reasons** | Null() | Main KPI rows carry no reason; only Reason rows (Section 44) populate this |
| **Cur_Actual** | **0.617** | 61.7% — raw decimal |
| **BSP_Benchmark** | **0.808** | 80.8% — weighted BSP for Week −1 |
| **Cur_Actual_Fmt** | **61.70%** | `Num(0.617, '0.00%')` |
| **BSP_Benchmark_Fmt** | **80.80%** | `Num(0.808, '0.00%')` |
| **Gap_Pct** | **23.6** | (BSP − Actual) ÷ BSP × 100 — display only |
| **Streak_4wk** | **3** | 3 of last 4 weeks below BSP |
| **OEE_Impact** | **6.02** | Scheduled hours lost vs BSP, urgency-weighted |
| **Cur_BSP_CoveragePct** | **0.833** | 83.3% — 15 of 18 SchedHours had a resolved BSP |
| **Cur_BSP_ConfScore** | **2.22** | Weighted avg confidence across all dies |
| **Cur_BSP_PoolSize** | **18.6** | Weighted avg historical run count behind resolved BSPs |
| **BSP_Confidence** | **MEDIUM** | ConfScore 2.22 ≥ 1.5 and < 2.5 |
| **Insight_Rank** | (ranked within Plant 0008 by OEE_Impact DESC) | |

---

### Field Guide — Key Columns Explained

#### `KPI_Category`
Classifies each KPI as either a composite indicator or a direct action lever.

| Category | KPIs included | Purpose |
|---|---|---|
| **Outcome** | OEE, Availability, Quality, Downtime %, Scrap Rate, Net Throughput Rate | Composite results — show *that* there is a problem; not directly fixable |
| **Lever** | Performance, Speed, Setup Hrs/Event, Setup Time %, all Reason rows, Feeder/Blanket rows | Root-cause drivers — directly actionable |

The front-end weekly action list filters `KPI_Category = 'Lever'`. Outcome rows remain available for scorecard context but are not the prioritised action list.

---

#### `Cur_BSP_PoolSize`
**SchedHours-weighted average of the historical run count behind the resolved BSP level for each die that ran in the current week.**

In this example (Week −1):
- Die A resolved at L1 → pool = 18 runs, weight = 10h
- Die C resolved at L2 → pool = 31 runs, weight = 5h
- Die E had no resolve → pool = 0, weight = 3h

`Cur_BSP_PoolSize = (10×18 + 5×31 + 3×0) ÷ 18 = 335 ÷ 18 = 18.6`

**How to interpret:**
- **< 15**: Benchmark is built from very few runs — treat as directional. One unusual job can shift the BSP materially next period.
- **15–30**: Benchmark is reliable. Within the intended operating range.
- **> 30**: Robust benchmark, especially if weighted toward an L1 die.

The field does not tell you which *level* resolved — that varies per die. It tells you how much *data* the benchmark represents on average for the hours this machine ran.

---

#### `Cur_BSP_ConfScore`
**SchedHours-weighted average of `Die_BSP_ConfScore` (3/2/1/0) across all dies in the current week, including uncovered dies.**

Binned into `BSP_Confidence` as:
| ConfScore range | BSP_Confidence label |
|---|---|
| ≥ 2.5 | HIGH |
| ≥ 1.5 | MEDIUM |
| ≥ 0.5 | LOW |
| < 0.5 | Insufficient History |

In this example, 2.22 falls in MEDIUM. Even if all covered dies resolved at L1 (score=3), an uncovered die running sufficient hours will pull ConfScore below 2.5 because it contributes ConfScore=0 to the weighted average.

---

#### `BSP_Confidence`
Categorical label derived from `Cur_BSP_ConfScore`. Displayed directly in the front-end. Use this to communicate how much to trust the benchmark to plant leaders — "MEDIUM" means the mix of L1/L2 or presence of uncovered dies warrants scrutiny before escalating.

---

#### `Cur_BSP_CoveragePct`
**The fraction of this week's SchedHours for which any BSP level resolved.**

`= Sum(CoveredSchedHours) ÷ Sum(TotalSchedHours)` over Week −1.

Here: 15 ÷ 18 = 83.3%. The 3 uncovered hours (Die E) are counted in the denominator but not the numerator.

Gate: insight fires only when `Cur_BSP_CoveragePct > 0.5` (strict — exactly 50% does not pass). If Die E had run 16+ hours this week, coverage would drop below 50% and the OEE insight row would be suppressed entirely, regardless of how large the gap is.

---

#### `Streak_4wk`
Count of the last 4 full completed weeks in which the machine's weekly actual KPI was worse than its weekly weighted BSP. Range 0–4 (capped at 4 via `RangeMin`). A value of 0 means the machine met or beat its BSP in every recent week — the insight fires because of this week's miss alone.

---

#### `Gap_Pct`
Relative percentage gap between BSP and actual: `(BSP − Actual) ÷ BSP × 100` for higher-is-better; reversed for lower-is-better. Used only for display — it is **not an input to OEE_Impact scoring**. Two machines can have the same `Gap_Pct` but very different `OEE_Impact` if one runs more scheduled hours.

---

#### `OEE_Impact`
True scheduled-hours-equivalent loss vs BSP, urgency-weighted by streak. This is the ranking key for `Insight_Rank`.

`OEE_Impact = Round(GapHrs × (1 + RangeMin(Streak_4wk, 4) / 4), 0.01)`

Maximum multiplier = 2.0× (when Streak_4wk ≥ 4). The `OEE_Impact` number is in the same unit (hours) across all KPIs, so rows can be compared and ranked directly within a plant.

---

## PART 4B — Contrast: Machine B (Gluer) — L2_ExtraDim and Reason Rows

### Gluer-specific: L2_ExtraDim = CartonStyle

Machine B (Gluer, Dept = "Gluer") uses `L2_ExtraDim = CartonStyle` instead of the empty string used by Sheetfed Printing. The carton style (e.g. `"TUCK-END-AUTO"`, `"STRAIGHT-TUCK"`) captures a meaningful dimension of run difficulty for gluing machines that board type and caliper alone do not.

**Example L2 BSP mapping key for Machine B:**
```
L2 key = '0008|10006101|SBS|18pt|TUCK-END-AUTO'

ApplyMap('BSP_L2_OEE_Map', '0008|10006101|SBS|18pt|TUCK-END-AUTO', Null())  →  74.3%
```

The same die on the same machine running `"STRAIGHT-TUCK"` would look up a **separate** L2 BSP (`'0008|10006101|SBS|18pt|STRAIGHT-TUCK'`) — reflecting that different carton styles have different natural run efficiencies. This prevents a fast-running style from setting an unreachable benchmark for a harder one.

For Sheetfed Printing, `L2_ExtraDim = ''` — the empty string is appended to the L2 key, which means Sheetfed L2 BSPs are pooled across all jobs on that BTG+Caliper without further subdivision. The key format is identical; only the trailing segment differs.

---

### Gluer: Downtime Reason Insight Row

After the main KPI rows fire, Section 44 evaluates **per-reason** benchmarks. Suppose "Mechanical - Belt Slip" downtime rate exceeds its per-die reason BSP this week:

| Field | Value | Notes |
|---|---|---|
| **Insight_ID** | `0008\|10006101\|2025-04-14\|Downtime Reason` | KPI_Name = `Downtime Reason` for all downtime reason rows |
| **KPI_Name** | Downtime Reason | |
| **KPI_Category** | **Lever** | All reason rows are Lever — directly actionable |
| **Reasons** | **Mechanical - Belt Slip** | Resolved via `ApplyMap('TimeReason_Name_Map', tPltRsnKey)` |
| **Cur_Actual** | 0.082 | 8.2% downtime rate attributed to this reason |
| **BSP_Benchmark** | 0.041 | 4.1% — reason-level P25 BSP (lower-is-better) |
| **Gap_Pct** | 100.0 | (Actual − BSP) ÷ BSP × 100 |
| **Streak_4wk** | 2 | This reason exceeded BSP in 2 of last 4 weeks |
| **OEE_Impact** | 1.26 | GapHrs × (1 + 2/4) |
| **Cur_BSP_CoveragePct** | **Null()** | Reason rows do not carry machine-level BSP coverage |
| **Cur_BSP_ConfScore** | **Null()** | |
| **Cur_BSP_PoolSize** | **Null()** | |
| **BSP_Confidence** | **Null()** | |
| **Insight_Rank** | (ranked within Plant+WC+KPI_Name by OEE_Impact DESC, top 3 per type) | |

**Why BSP_* fields are Null on reason rows:** The machine-level BSP pipeline (WeeklyDieBSP → WeeklyMachineBSP → CurrentPeriod) computes coverage and confidence for the *overall machine OEE benchmark*, not for individual reason rates. Reason BSPs are per-reason per-die lookups (a separate set of L1/L2/L3 maps), and they do not have an analogous "coverage" concept — every reason either resolved a BSP or did not. Emitting Null avoids confusing the machine-level BSP confidence with the reason-level one.

---

## Key Takeaways

1. **BSP is not the single best day** — it is the **P75** across all qualifying job runs in the pool. The top 25% of runs set the target; extreme outlier days do not.

2. **The three fallback levels (L1→L2→L3) handle thin history.** A new or rare die with only 8 runs still gets a benchmark via the L2 board-type pool. A die with 4 runs falls through to the machine-level L3 pool. Only a die with zero historical runs (or one whose pool is still below 35 at machine level) gets no BSP.

3. **L2_ExtraDim refines the L2 pool without separate code paths.** Gluers use CartonStyle, Sheetfed/Web Cutting use NumberUp, all others use `''`. The empty string means Sheetfed Printing L2 BSPs behave identically to the pre-ExtraDim logic.

4. **Uncovered hours drag two metrics:** they add to `Wk_TotalSchedHours` (lowering `BSP_CoveragePct`) and add weight to the `BSP_ConfScore` average with a value of 0 (lowering `BSP_Confidence`). A machine that routinely runs product with no BSP history will see both metrics suppress or flag its insights.

5. **Cur_BSP_PoolSize tells you how thin the benchmark data is.** Values near 15 (the L1 minimum) mean a single unusual run could shift the BSP noticeably next period. Values above 30 indicate a stable, well-supported benchmark.

6. **OEE_Impact is in true scheduled hours — comparable across all KPIs.** A setup KPI that wastes 4 hours/week of setup time and an OEE gap that wastes 4 hours/week of production capacity score identically. This allows plant leaders to rank insights from different KPI types side by side.

7. **KPI_Category = Lever is the action list.** Outcome KPIs (OEE, Availability, etc.) confirm the problem exists. Lever KPIs (Performance, Speed, Setup, Reasons) tell the operator what to fix. The front-end filters to Lever for the weekly prioritised action list.

---

## PART 5 — Pipeline Flowchart: Grain at Every Stage

```
╔══════════════════════════════════════════════════════════════════════════╗
║  JobFact_Raw                                                             ║
║  Grain: Date + WC + Shift + Operator + Order + Die + Reason + fSched    ║
║  (one row per scheduling slot — a single shift × order × reason combo)  ║
╚══════════════════════╦═══════════════════════════════════════════════════╝
                       │
         ┌─────────────┴─────────────────────────┐
         │  BSP PIPELINE                         │  SCORING PIPELINE
         │  (Historical window: rolling 24 mo    │  (13-week trend window)
         │   → last completed week)              │
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
             │      BTG+Caliper+      ╚═══════════════╦═══════════════════╝
             │      L2_ExtraDim                       │
             │  L3: Plant+WC          ╔═══════════════▼═══════════════════╗
             ▼                        ║  WeeklyDieBSP  (Section 31)       ║
╔════════════════════════════╗        ║  Grain: WeekStart+Plant+WC+Die    ║
║  BSP Tables (L1/L2/L3)     ║        ║                                   ║
║  Min run thresholds:        ║        ║  BSP LOOKUP per die:              ║
║   L1: 15   L2: 25   L3: 35 ║        ║  Coalesce(                        ║
║   P75 higher-is-better      ║        ║    L1 map: Plant|WC|Die           ║
║   P25 lower-is-better       ║        ║    L2 map: Plant|WC|BTG|Cal|Xdim ║
║                            ║        ║    L3 map: Plant|WC               ║
║  Main (9 KPIs):            ║        ║  )                                ║
║   L1: Plant+WC+Die         ║        ║                                   ║
║   L2: Plant+WC+BTG+Cal+    ║◄───────║  Die_BSP_ConfScore: 3/2/1/0       ║
║       L2_ExtraDim          ║        ║  Die_BSP_PoolSize:                ║
║   L3: Plant+WC             ║        ║    run count at resolved level     ║
║                            ║        ║  CoveredSchedHours:               ║
║  Setup (2 KPIs):           ║        ║    = SchedHrs if BSP resolved     ║
║   adds MROClass to key     ║        ║    = 0 if no BSP                  ║
║                            ║        ╚═══════════════╦═══════════════════╝
║  DownReason / ScrReason:   ║                        │
║   adds ReasonKey to key    ║                        │  GROUP BY WeekStart+Plant+WC
╚════════════╦═══════════════╝                        │  Weighted avg by SchedHrs
             │ → converted to                         ▼
             │   mapping tables        ╔═══════════════════════════════════╗
             │   (36+ maps)            ║  WeeklyMachineBSP  (Section 32)   ║
             │                        ║  Grain: WeekStart+Plant+WC        ║
             │                        ║                                   ║
             │                        ║  Wk_BSP_OEE   = weighted avg of   ║
             │                        ║    covered dies only              ║
             │                        ║  BSP_CoveragePct = Covered÷Total  ║
             │                        ║  BSP_ConfScore = weighted avg of   ║
             │                        ║    ALL dies (covered + uncovered) ║
             │                        ║  BSP_PoolSize  = weighted avg of  ║
             │                        ║    ALL dies' pool run counts      ║
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
             │   ║  Grain: Plant+WC  (1-week: Week−1) ║
             │   ║                                    ║
             │   ║  Cur_OEE           = Wk_OEE        ║
             │   ║  Cur_BSP_OEE       = Wk_BSP_OEE   ║
             │   ║  Cur_SchedHrs      = Sum(Wk_SchedHrs) ║
             │   ║  Cur_RunHours      = Sum(Wk_RunHrs)║
             │   ║  Cur_Coverage = Covered÷Total      ║
             │   ║  Cur_ConfScore = last week's only   ║
             │   ║  Cur_PoolSize  = last week's only   ║
             │   ╚═══════════════╦═══════════════════╝
             │                   │
             │     Fires insight when:
             │       Cur_Actual worse than BSP_Benchmark
             │       AND CoveragePct > 0.5  (strict)
             │                   │
             │                   ▼
             │   ╔═══════════════════════════════════╗
             └──►║  InsightRecords  (Sections 42–47) ║
                 ║  Grain: Plant+WC+KPI_Name+Reasons ║
                 ║  (one row per machine per KPI      ║
                 ║   or per machine+reason)           ║
                 ║                                   ║
                 ║  GapHrs = abs_gap × time_denom    ║
                 ║  OEE_Impact = GapHrs×(1+Streak/4) ║
                 ║  KPI_Category: Outcome or Lever   ║
                 ║  Ranked by OEE_Impact DESC        ║
                 ║  within Plant                     ║
                 ╚═══════════════════════════════════╝
```

---

### Grain Summary Table

| Table | Grain | What it represents |
|---|---|---|
| `JobFact_Raw` | Date + WC + Shift + Operator + Order + Die + ReasonKey + fSched | Every scheduling slot row in the source QVD |
| `JobFact_Job_BSP` (L1) | Date + WC + Shift + Die | One unit of BSP history — all hours/qty for a single die on a single shift |
| `JobFact_Job_BSP_L2` | Date + WC + Shift + Die + PltMatKey | Same as L1 but split by material for board attribute resolution |
| `BSP_Main_L1` | Plant + WC + Die | P75/P25 benchmark across qualifying runs for this machine+die (n ≥ 15) |
| `BSP_Main_L2` | Plant + WC + BoardTypeGroup + BoardCaliper + L2_ExtraDim | P75/P25 benchmark across qualifying runs for this machine+board type+extra dim (n ≥ 25) |
| `BSP_Main_L3` | Plant + WC | P75/P25 benchmark across qualifying runs for this machine regardless of die (n ≥ 35) |
| `WeeklyDieKPI` | WeekStart + Plant + WC + Die | Actual weekly totals per die — raw material for scoring |
| `WeeklyDieBSP` | WeekStart + Plant + WC + Die | Actual + BSP resolved per die — coverage, confidence, pool size assigned here |
| `WeeklyMachineBSP` | WeekStart + Plant + WC | BSP and coverage rolled to machine level — weighted by SchedHours |
| `WeeklyMachineKPI` | WeekStart + Plant + WC | Actual weekly KPI per machine — streak computed via Peek() on this table |
| `CurrentPeriod` | Plant + WC | 1-week actuals + BSP (last completed week only) — the comparison happens here |
| `InsightRecords` | Plant + WC + KPI_Name + Reasons | Final output — one row per machine per KPI/reason that fires; `Reasons` is Null for main KPI rows |

### How BSP and Current Period Match

The BSP is calculated at **die grain** (L1), **board type + L2_ExtraDim grain** (L2), or **machine grain** (L3). The current period actual is always at **machine grain** (WeekStart + Plant + WC after `WeeklyMachineKPI` aggregation). The bridge:

1. BSP is resolved per die (in `WeeklyDieBSP`) using the dies that **actually ran in the last completed week**
2. Those per-die BSPs are weighted together into a single machine-level BSP (in `WeeklyMachineBSP`) using the **same week's SchedHours as weights** — only covered dies enter the numerator and denominator
3. The weighted BSP from Week −1 is carried into `CurrentPeriod` and compared to the actual machine-level KPI for that same week
4. `GapHrs = (BSP − Actual) × Cur_SchedHours` converts the percentage gap into true scheduled hours lost (for pct-based KPIs), which is then urgency-weighted by streak to produce `OEE_Impact`

This ensures the benchmark always reflects the specific product mix the machine ran — not a generic machine average. `OEE_Impact` expresses the loss as actual hours, so plant leaders can compare rows directly across machines and KPI types.
