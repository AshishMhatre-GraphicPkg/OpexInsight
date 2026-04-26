# BSP Explained — A Complete Worked Example
### Machine A: 10005999 | Plant 0008 | Dept: Sheetfed Printing
### Machine B: 10006101 | Plant 0008 | Dept: Gluer *(contrast — PART 4B only)*

---

## What This Document Teaches

- **How a machine's benchmark (BSP) is built** — from its own historical job runs, using the 75th percentile (P75) of all qualifying runs.
- **What happens when a die doesn't have enough history** — the engine falls back to a broader pool (same board type, then whole machine), so almost every die gets *some* benchmark.
- **How this week's actual performance is compared to that benchmark** — and how the result is translated into a single urgency-weighted number (OEE_Impact) expressed in hours.
- **What every output column means** — so you can interpret an InsightRecords row without a decoder ring.

The entire numerical walkthrough uses **one machine, one week (Week −1, the last completed week)**. The scorecard for that single week exercises all four possible BSP resolution outcomes: a die resolved at L1, one at L2, one at L3, and one that gets no benchmark at all.

---

## Setup

| Parameter | Machine A | Machine B |
|---|---|---|
| WC Object ID | 10005999 | 10006101 |
| Plant | 0008 | 0008 |
| Department | Sheetfed Printing | Gluer |
| MaxSpeed | 10,000 u/hr (OEM Speed) | 18,000 cartons/hr (Max Gluer Speed) |
| L2 extra dimension | None — Sheetfed uses board grain only (`L2_ExtraDim = ''`) | Carton style (e.g. `"TUCK-END-AUTO"`) |
| BSP history window | Rolling 24 months → last completed week | Same |
| Current period | Last completed week (Week −1) | Same |

Machine B is a gluer; it appears only in PART 4B to illustrate how the L2 key differs when a department uses carton style as an extra dimension.

---

## PART 1 — Building the BSP from Historical Runs

The BSP is built once from all qualifying historical job runs (RunHours > 2) in the 24-month window. This happens before we look at this week at all.

### Step 1A — What runs exist in history?

Machine A ran five dies during the history window. The table below shows how many qualifying runs each die has accumulated:

| Die | Board Type Group | Board Caliper | Qualifying runs in history |
|---|---|---|---|
| Die A | SBS | 24pt | **18** |
| Die B | SBS | 24pt | **8** |
| Die C | SBS | 24pt | **5** |
| Die D | CRB | 18pt | **4** |
| Die E | CUK | 28pt | **0** — no history at all |

> **Die B note:** Die B has 8 historical runs and contributes to the L2 board-type pool calculated below. However, Die B did not run during our current week (Week −1), so it plays no part in PART 2 onward. It matters here in PART 1 only.

---

### Step 1B — Which benchmark level does each die qualify for?

The engine tries three levels in order, using the first one that passes the minimum-run threshold:

| Level | What the pool is | Min runs required | Die A (18) | Die B (8) | Die C (5) | Die D (4) | Die E (0) |
|---|---|---|---|---|---|---|---|
| **L1** | This die on this machine only | **15** | ✅ 18 ≥ 15 | ❌ 8 < 15 | ❌ 5 < 15 | ❌ 4 < 15 | ❌ |
| **L2** | All dies on this machine sharing the same board type + caliper | **25** | — | ✅ SBS+24pt pool = A+B+C = 31 ≥ 25 | ✅ same pool | ❌ CRB+18pt pool = 4 < 25 | ❌ no pool |
| **L3** | All dies on this machine, regardless of board type | **35** | — | — | — | ✅ all runs = 18+8+5+4 = 35 ≥ 35 | ❌ still 0 history |

**In plain English:**
- **Die A** has enough of its own history — it gets its own private benchmark (L1).
- **Die C** (and Die B) don't have enough runs on their own, but pooling all three SBS/24pt dies gives 31 runs of similar boards — so the engine borrows from that combined pool (L2).
- **Die D** is on a different board type (CRB/18pt) whose pool is too small, so it falls back to the whole machine's combined history (L3).
- **Die E** has no history anywhere — it gets no benchmark and its scheduled hours will be "uncovered."

---

### Step 1C — Calculating the benchmarks

The engine uses the **75th percentile (P75)** for higher-is-better KPIs (OEE, Availability, Performance, Quality, Speed, Net Throughput Rate) and the **25th percentile (P25)** for lower-is-better KPIs (Downtime %, Scrap Rate, Setup Hrs/Event, Setup Time %).

P75 means: the level the machine has proven it can reach in **the top 25% of its qualifying runs** on comparable jobs. Not the single best day — the consistently good zone.

#### Die A — L1 BSP (own history, n=18)

Sort all 18 OEE values from Die A's qualifying runs in ascending order:

| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | **12** | **13** | 14 | 15 | 16 | 17 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OEE% | 54 | 58 | 61 | 64 | 66 | 68 | 70 | 72 | 74 | 76 | 78 | 79 | **81** | **83** | 85 | 87 | 89 | 91 |

P75 position (0-indexed) = `(18 − 1) × 0.75 = 17 × 0.75 = 12.75`

Interpolate between index 12 and 13:
`81 + 0.75 × (83 − 81) = 81 + 1.5 = 82.5%`

> **Die A L1 BSP OEE = 82.5%**

Applying the same calculation to the Availability values from Die A's 18 runs:

> **Die A L1 BSP Availability = 85.8%**

#### L2 Pool (SBS + 24pt, n=31) — used by Die C

The 31 run-level OEE values from Dies A, B, and C are combined and sorted together. Because this pool mixes in the weaker Die B and Die C runs, the P75 comes out lower than Die A's L1:

> **L2 BSP OEE = 77.5%** *(P75 at index 22.5 of 31 combined values)*
> **L2 BSP Availability = 80.5%**

#### L3 Pool (machine-wide, n=35) — used by Die D

All 35 qualifying runs across all four dies (A+B+C+D) are combined. Die D's weaker CRB/18pt runs pull the percentile down further:

> **L3 BSP OEE = 76.5%** *(P75 at index 25.5 of 35 combined values)*
> **L3 BSP Availability = 78.5%**

---

### BSP Summary for Machine A

| Die | Benchmark level | Runs in pool | BSP OEE | BSP Availability | ConfScore |
|---|---|---|---|---|---|
| Die A | **L1** (own die) | 18 | 82.5% | 85.8% | 3 |
| Die B | **L2** (SBS+24pt pool) | 31 | 77.5% | 80.5% | 2 |
| Die C | **L2** (SBS+24pt pool) | 31 | 77.5% | 80.5% | 2 |
| Die D | **L3** (machine-wide) | 35 | 76.5% | 78.5% | 1 |
| Die E | **None** | 0 | — | — | 0 |

`ConfScore`: 3 = L1, 2 = L2, 1 = L3, 0 = no benchmark.

These BSPs are now stored as mapping tables in the script. No further calculation happens on them until we look up each die's benchmark in Week −1 below.

---

## PART 2 — Scoring Week −1 (the Last Completed Week)

The engine keeps a 13-week rolling window to detect trends and compute the streak counter. But the actual performance comparison — the one that fires an insight — happens against **Week −1 only** (the last completed week). Everything in this part is for Week −1.

### Runs in Week −1

Machine A ran four jobs this week, one on each die. Notice the BSP resolution outcome is different for each die — this is deliberate so all four cases are demonstrated in one week:

| Die | SchedHrs | RunHrs | GoodQty | OEE_Denom | BSP resolution |
|---|---|---|---|---|---|
| Die A | 10 | 8.0 | 70,000 | 100,000 | L1 |
| Die C | 5 | 3.5 | 30,000 | 50,000 | L2 |
| Die D | 4 | 2.8 | 22,000 | 40,000 | L3 |
| Die E | 1 | 0.7 | 5,000 | 10,000 | No BSP |
| **Total** | **20** | **15.0** | **127,000** | **200,000** | |

*(OEE_Denom = SchedHrs × MaxSpeed = SchedHrs × 10,000)*

---

### Step 2A — Actual weekly KPIs for the machine

These are pure aggregations of what the machine actually did this week — no benchmark involved yet.

| Metric | Calculation | Value |
|---|---|---|
| Total SchedHours | 10 + 5 + 4 + 1 | **20 hrs** |
| Total RunHours | 8.0 + 3.5 + 2.8 + 0.7 | **15.0 hrs** |
| Total GoodQty | 70,000 + 30,000 + 22,000 + 5,000 | **127,000 units** |
| Total OEE_Denom | 100,000 + 50,000 + 40,000 + 10,000 | **200,000 units** |
| **Wk_OEE** | 127,000 ÷ 200,000 | **63.5%** |
| **Wk_Availability** | 15.0 ÷ 20 | **75.0%** |

---

### Step 2A-i — WeeklyDieKPI (Section 30)

The script aggregates to `WeekStart + Plant + WC + Die` grain first — one row per die. These are the raw actuals, no benchmark yet.

| Die | Wk_Die_SchedHrs | Wk_Die_RunHrs | Wk_Die_GoodQty | Wk_Die_OEE_Denom |
|---|---|---|---|---|
| Die A | 10 | 8.0 | 70,000 | 100,000 |
| Die C | 5 | 3.5 | 30,000 | 50,000 |
| Die D | 4 | 2.8 | 22,000 | 40,000 |
| Die E | 1 | 0.7 | 5,000 | 10,000 |

---

### Step 2A-ii — WeeklyDieBSP (Section 31)

Each row is enriched with its BSP via a three-level lookup chain: `Coalesce(L1 → L2 → L3)`. The first level that returns a non-null value wins.

#### Die A — L1 hit

```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die A', Null())  →  82.5%   ✅ L1 resolved
```

Die A's own die history exists at L1 (18 runs ≥ 15). No need to check L2 or L3.

#### Die C — L1 miss, L2 hit

```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die C', Null())          →  Null    ❌ only 5 runs < 15
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|SBS|24pt|', Null())      →  77.5%   ✅ L2 resolved
```

The L2 key ends with an empty string for Sheetfed Printing (`L2_ExtraDim = ''`). The SBS+24pt pool (Die A+B+C, 31 combined runs) provides the benchmark.

#### Die D — L1 miss, L2 miss, L3 hit

```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die D', Null())          →  Null    ❌ only 4 runs < 15
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|CRB|18pt|', Null())      →  Null    ❌ CRB+18pt pool = 4 < 25
ApplyMap('BSP_L3_OEE_Map', '0008|10005999', Null())                →  76.5%   ✅ L3 resolved
```

The machine-wide pool (35 runs) barely meets the L3 threshold of 35.

#### Die E — all levels miss

```
ApplyMap('BSP_L1_OEE_Map', '0008|10005999|Die E', Null())          →  Null    ❌ zero history
ApplyMap('BSP_L2_OEE_Map', '0008|10005999|CUK|28pt|', Null())      →  Null    ❌ no pool exists
ApplyMap('BSP_L3_OEE_Map', '0008|10005999', Null())                →  Null    ❌ Die E not in L3 pool (0 history runs)
Coalesce(Null, Null, Null) = Null  →  no benchmark
```

Die E ran 1 hour this week, but because it has no historical runs, the L3 machine pool was built without it. Its scheduled hour will count toward total machine time but contribute nothing to the benchmark.

#### WeeklyDieBSP result table

| Die | Wk_Die_SchedHrs | Die_BSP_OEE | Die_BSP_Avail | ConfScore | PoolSize | CoveredSchedHrs |
|---|---|---|---|---|---|---|
| Die A | 10 | **82.5%** (L1) | **85.8%** (L1) | **3** | **18** | **10** |
| Die C | 5 | **77.5%** (L2) | **80.5%** (L2) | **2** | **31** | **5** |
| Die D | 4 | **76.5%** (L3) | **78.5%** (L3) | **1** | **35** | **4** |
| Die E | 1 | **—** (none) | **—** | **0** | **0** | **0** |

`CoveredSchedHrs` = the die's SchedHours if any BSP resolved, else 0. Die E's 1 hour is uncovered.

---

### Step 2A-iii — WeeklyMachineBSP (Section 32)

The four die rows are collapsed into a single machine-week row using SchedHours-weighted averages. Two different denominator rules apply:

**Rule 1 — BSP values (OEE, Availability, etc.):** Use only the *covered* die hours (19 hrs) in both numerator and denominator. Die E is excluded entirely — if uncovered hours were in the denominator, the benchmark would appear artificially low.

**Rule 2 — ConfScore and PoolSize:** Use *all* die hours (20 hrs) in the denominator. Die E's uncovered hour contributes 0 to the numerator, which drags these quality indicators down proportionally to how much time the machine spent on it.

**Calculations:**

```
Covered dies: Die A (10h), Die C (5h), Die D (4h) — total covered = 19 hrs
Uncovered:    Die E (1h)                           — total = 20 hrs

Wk_BSP_OEE   = (10 × 82.5% + 5 × 77.5% + 4 × 76.5%) ÷ 19
             = (825.0 + 387.5 + 306.0) ÷ 19
             = 1518.5 ÷ 19  =  79.9%

Wk_BSP_Avail = (10 × 85.8% + 5 × 80.5% + 4 × 78.5%) ÷ 19
             = (858.0 + 402.5 + 314.0) ÷ 19
             = 1574.5 ÷ 19  =  82.9%

BSP_CoveragePct = 19 covered ÷ 20 total  =  95.0%

BSP_ConfScore   = (10×3 + 5×2 + 4×1 + 1×0) ÷ 20     ← all 20 hrs in denominator
                = (30 + 10 + 4 + 0) ÷ 20
                = 44 ÷ 20  =  2.20  →  MEDIUM

BSP_PoolSize    = (10×18 + 5×31 + 4×35 + 1×0) ÷ 20   ← all 20 hrs in denominator
                = (180 + 155 + 140 + 0) ÷ 20
                = 475 ÷ 20  =  23.75
```

> **Why ConfScore is MEDIUM (2.20) and not HIGH:** Even though Die A resolved at L1 (ConfScore=3), Die D's L3 (score=1) and Die E's uncovered hour (score=0) pull the weighted average below the HIGH threshold of 2.5. A machine that ran only Die A all week would score 3.0 (HIGH).

> **What PoolSize 23.75 means:** Each scheduled hour this week was benchmarked against an average of ~24 historical runs. Die A's 10 hours are backed by 18 runs; Die C's 5 hours by 31 runs; Die D's 4 hours by 35 runs; Die E's 1 hour is backed by 0 (no benchmark). The weighted blend gives 23.75.

| Field | Week −1 |
|---|---|
| Wk_TotalSchedHours | **20** |
| Wk_CoveredSchedHours | **19** |
| BSP_CoveragePct | **95.0%** |
| Wk_BSP_OEE | **79.9%** |
| Wk_BSP_Availability | **82.9%** |
| BSP_ConfScore | **2.20** (MEDIUM) |
| BSP_PoolSize | **23.75** |

---

### Step 2A-iv — Streak Detection (WeeklyMachineKPI, Section 33)

The engine maintains a 13-week table of actual weekly OEE, Availability, etc. for every machine. By sorting this table by week and running `Peek()` on consecutive rows, it counts how many of the last 4 weeks the machine's actual was worse than its weekly BSP.

For this example, **assume the machine has been below its OEE BSP for 3 of the last 4 completed weeks: `Streak_4wk = 3`.**

---

### Step 2B — Why Blending Per-Die BSPs Is Necessary

Each die has its own BSP, and different dies ran different amounts this week. You cannot use Die A's BSP (82.5%) as the machine benchmark for a week where Die D and Die E also ran — that would ignore the fact that the machine spent 25% of its time on harder or uncharted product.

The weighted blend (79.9%) answers: *"Given exactly the products this machine ran this week, what OEE should it have hit if it performed at its proven best on each one?"* This makes the benchmark fair — it rises and falls with the actual product mix, not a fixed number.

---

### Step 2C — CurrentPeriod (Section 37)

The CurrentPeriod table holds the final actuals and benchmarks for Week −1. This is the row the scoring engine will compare.

```
Cur_OEE              = 63.5%
Cur_Availability     = 75.0%

Cur_BSP_OEE          = 79.9%   (weighted BSP from Week −1)
Cur_BSP_Availability = 82.9%

Cur_SchedHours       = Sum(Wk_SchedHours)  = 20 hrs
Cur_RunHours         = Sum(Wk_RunHours)    = 15.0 hrs

Cur_BSP_CoveragePct  = 19 ÷ 20  =  95.0%   ← 95% of scheduled hours had a resolved benchmark
Cur_BSP_ConfScore    = 2.20   (last completed week's value)
Cur_BSP_PoolSize     = 23.75  (last completed week's value)
BSP_Confidence       = "MEDIUM"   (ConfScore 2.20: 1.5 ≤ 2.20 < 2.5)
```

Coverage 95.0% is well above the 50% minimum (strict `> 0.5`) — the insight is allowed to fire.

---

## PART 3 — Scoring

### Step 1 — Gap_Pct (display only)

`Gap_Pct` shows the relative shortfall between this week's actual and the benchmark. For higher-is-better KPIs: `Gap_Pct = (BSP − Actual) ÷ BSP × 100`.

```
OEE Gap_Pct          = (79.9% − 63.5%) ÷ 79.9% × 100  =  20.5
Availability Gap_Pct = (82.9% − 75.0%) ÷ 82.9% × 100  =   9.5
```

Gap_Pct is for display only and is **not used to compute OEE_Impact**.

---

### Step 2 — GapHrs (how many scheduled hours were lost?)

GapHrs translates the percentage gap into real scheduled hours. The formula differs by KPI type:

| KPI type | GapHrs formula |
|---|---|
| Pct-based (OEE, Availability, Performance, Quality, Downtime%, Scrap Rate, Setup Time%) | `(BSP − Actual) × Cur_SchedHours` |
| Speed | `(BSP_Speed − Cur_Speed) ÷ BSP_Speed × Cur_RunHours` |
| Net Throughput Rate | `(BSP_NTR − Cur_NTR) ÷ BSP_NTR × (Cur_RunHours + Cur_DowntimeHrs)` |
| Setup Hrs/Event | `(Cur_SetupHrsPerEvent − BSP_SetupHrsPerEvent) × Cur_SetupEventCount` |

For our Week −1 example (pct-based):

```
OEE GapHrs          = (79.9% − 63.5%) × 20  =  0.164 × 20  =  3.28 hrs
Availability GapHrs = (82.9% − 75.0%) × 20  =  0.079 × 20  =  1.58 hrs
```

GapHrs is an intermediate calculation only — it does not appear in the final output.

---

### Step 3 — OEE_Impact (urgency-weighted hours lost)

Rows where the gap persists for multiple weeks deserve higher priority than a one-off miss. OEE_Impact applies a streak multiplier to GapHrs:

```
OEE_Impact = Round(GapHrs × (1 + RangeMin(Streak_4wk, 4) / 4), 0.01)
```

The streak is capped at 4. At Streak_4wk = 4, the multiplier reaches its maximum of `1 + 4/4 = 2.0×`.

With `Streak_4wk = 3`:

```
OEE OEE_Impact          = Round(3.28 × (1 + 3/4), 0.01)  =  Round(3.28 × 1.75, 0.01)  =  5.74 hrs
Availability OEE_Impact = Round(1.58 × (1 + 3/4), 0.01)  =  Round(1.58 × 1.75, 0.01)  =  2.77 hrs
```

Insights are suppressed when `GapHrs ≤ 0` (machine is at or above BSP that week — no loss to report).

---

## PART 4 — The InsightRecords Output Row

### What Machine A's OEE row looks like

| Field | Value | What it means |
|---|---|---|
| **Insight_ID** | `0008\|10005999\|2025-04-14\|OEE` | Stable dedup key: Plant \| WC \| PeriodStart \| KPI |
| **Plant** | 0008 | |
| **WC Object ID** | 10005999 | |
| **Plant - WC** | Carol Stream - 10005999 | |
| **Department** | Sheetfed Printing | |
| **Period_Start** | 2025-04-14 | Monday of Week −1 |
| **KPI_Name** | OEE | |
| **KPI_Category** | **Outcome** | Classifies whether this KPI is a root-cause lever or a composite result |
| **Reasons** | Null() | Null on main KPI rows; populated only on reason-level rows (Section 44) |
| **Cur_Actual** | **0.635** | 63.5% actual OEE this week |
| **BSP_Benchmark** | **0.799** | 79.9% weighted BSP for this week's product mix |
| **Cur_Actual_Fmt** | **63.50%** | Display-formatted actual |
| **BSP_Benchmark_Fmt** | **79.90%** | Display-formatted benchmark |
| **Gap_Pct** | **20.5** | Relative gap — display only, not used in scoring |
| **Streak_4wk** | **3** | Below BSP in 3 of the last 4 weeks |
| **OEE_Impact** | **5.74** | Hours lost vs BSP, weighted for urgency — the ranking key |
| **Cur_BSP_CoveragePct** | **0.950** | 95% of this week's hours had a resolved BSP |
| **Cur_BSP_ConfScore** | **2.20** | Weighted-average resolution confidence across all dies |
| **Cur_BSP_PoolSize** | **23.75** | Weighted-average historical run count behind the benchmarks |
| **BSP_Confidence** | **MEDIUM** | Category derived from ConfScore |
| **Insight_Rank** | (ranked within Plant 0008 by OEE_Impact DESC) | Determines priority order in the front-end |

---

### Field Guide — Key Columns in Plain English

#### `KPI_Category` — Is this KPI something you can directly fix?

| Value | KPIs | What to do with it |
|---|---|---|
| **Outcome** | OEE, Availability, Quality, Downtime %, Scrap Rate, Net Throughput Rate | Confirms *that* there is a problem. Not directly actionable — these are composite results driven by other causes. |
| **Lever** | Performance, Speed, Setup Hrs/Event, Setup Time %, all reason rows, all feeder/blanket rows | Tells you *what* to fix. These are root-cause drivers the team can act on. |

The weekly action list in the front-end filters to `KPI_Category = 'Lever'`. Outcome rows are preserved for scorecard context but are not the prioritised action list.

---

#### `Cur_BSP_CoveragePct` — What fraction of this week's hours had a benchmark?

**What it is:** `Sum(CoveredSchedHours) ÷ Sum(TotalSchedHours)` for the current week.

In this example: 19 covered ÷ 20 total = 95.0%. Die E's 1 hour is in the denominator (total time the machine ran) but not the numerator (time with a benchmark).

**Why it matters:** An insight fires only when `Cur_BSP_CoveragePct > 0.5` (strict greater-than). If the machine runs mostly new or rare dies with no BSP history, coverage drops below 50% and the insight is suppressed — comparing 63.5% actual against a benchmark built on 1 hour of covered time would be misleading.

**How to read it:** Coverage near 100% means almost all the machine's time was benchmarked. Coverage near 50% (the minimum) means interpret the insight with caution — much of what the machine ran this week had no comparable history.

---

#### `Cur_BSP_ConfScore` — How confident are we in the benchmark?

**What it is:** A SchedHours-weighted average of the resolution level for each die, where L1=3, L2=2, L3=1, no BSP=0. All scheduled hours — covered and uncovered — are in the denominator.

In this example: `(10×3 + 5×2 + 4×1 + 1×0) ÷ 20 = 44 ÷ 20 = 2.20`

**Why it matters:** An L1 benchmark (own die history) is more reliable than an L3 benchmark (all dies mixed together). A mix of L1 and L2 dies with one uncovered die gives a score between 1 and 3.

**Binned into `BSP_Confidence` as:**

| ConfScore | BSP_Confidence |
|---|---|
| ≥ 2.5 | HIGH |
| ≥ 1.5 | MEDIUM |
| ≥ 0.5 | LOW |
| < 0.5 | Insufficient History |

---

#### `BSP_Confidence` — The one-word summary for plant leaders

HIGH means the benchmarks are solid, mostly built from this specific die's own history. MEDIUM means there is a mix — some L2 or L3 fallbacks, or some uncovered time. LOW means most of the week ran on thin history. "Insufficient History" means the machine ran too little benchmarked product to trust the number at all.

---

#### `Cur_BSP_PoolSize` — How much data is behind this benchmark?

**What it is:** A SchedHours-weighted average of the historical run count behind the resolved BSP level for each die. All hours (covered and uncovered) are in the denominator.

In this example: `(10×18 + 5×31 + 4×35 + 1×0) ÷ 20 = 475 ÷ 20 = 23.75`

Die A's 18-run L1 benchmark: solid. Die C's 31-run L2 pool: solid. Die D's 35-run L3 pool: just at the minimum. Die E's 0: no data. Blended by hours → 23.75.

**How to read it:** Think of it as "the typical hour this machine ran was benchmarked against ~24 historical runs."

| Range | What it signals |
|---|---|
| < 15 | Thin benchmark — one unusual run could shift the BSP materially next period |
| 15–30 | Within the reliable range |
| > 30 | Robust benchmark |

---

#### `Streak_4wk` — How long has this been going on?

The count of the last 4 full completed weeks in which the machine's weekly actual was worse than its weekly weighted BSP. Range 0–4 (capped at 4). A value of 0 means the machine met or beat its BSP in every recent week — this week's insight fired from a one-off miss.

---

#### `Gap_Pct` — The size of the gap in relative terms

`(BSP − Actual) ÷ BSP × 100` for higher-is-better KPIs (reversed for lower-is-better). Shown in the front-end for context. Not an input to scoring — two machines can have the same Gap_Pct but very different OEE_Impact if they run different volumes of scheduled hours.

---

#### `OEE_Impact` — The number that determines priority

True scheduled-hours-equivalent loss vs BSP, multiplied by a streak urgency factor.

`OEE_Impact = Round(GapHrs × (1 + RangeMin(Streak_4wk, 4) / 4), 0.01)`

Maximum multiplier = 2.0× when Streak_4wk ≥ 4. OEE_Impact is in the same unit (hours) across all KPIs and all machines, so rows can be sorted and compared directly. A Setup Hrs/Event insight scoring 4.0 hrs and an OEE insight scoring 4.0 hrs represent the same magnitude of loss.

---

## PART 4B — Machine B (Gluer): L2 Key Format and Reason Rows

### How the L2 key differs for Gluer machines

Gluer department machines use `L2_ExtraDim = CartonStyle`. The carton style (e.g. `"TUCK-END-AUTO"`) is appended to the L2 lookup key because different styles have meaningfully different run efficiencies — using the same benchmark for all styles on the same board type would be unfair.

**Example L2 lookup key for Machine B:**
```
L2 key  →  '0008|10006101|SBS|18pt|TUCK-END-AUTO'

ApplyMap('BSP_L2_OEE_Map', '0008|10006101|SBS|18pt|TUCK-END-AUTO', Null())  →  74.3%
```

The same die running `"STRAIGHT-TUCK"` resolves a *separate* L2 BSP: `'0008|10006101|SBS|18pt|STRAIGHT-TUCK'`. The key format is identical to Machine A — only the trailing segment (which is empty for Sheetfed Printing) differs.

---

### What a Downtime Reason row looks like

After the main KPI rows are built (Section 42), Section 44 evaluates per-reason benchmarks. Suppose "Mechanical - Belt Slip" exceeded its downtime-rate BSP this week on Machine B:

| Field | Value |
|---|---|
| **KPI_Name** | Downtime Reason |
| **KPI_Category** | **Lever** — all reason rows are Lever |
| **Reasons** | **Mechanical - Belt Slip** |
| **Cur_Actual** | 0.082 (8.2% downtime rate for this reason) |
| **BSP_Benchmark** | 0.041 (4.1% — P25 reason BSP, lower-is-better) |
| **Gap_Pct** | 100.0 |
| **Streak_4wk** | 2 |
| **OEE_Impact** | 1.26 (GapHrs × 1.5) |
| **Cur_BSP_CoveragePct** | **Null** |
| **Cur_BSP_ConfScore** | **Null** |
| **Cur_BSP_PoolSize** | **Null** |
| **BSP_Confidence** | **Null** |
| **Insight_Rank** | Ranked within Plant+WC+KPI_Name (top 3 per type) |

The four `BSP_*` fields are Null on reason rows. The machine-level BSP pipeline (WeeklyDieBSP → WeeklyMachineBSP → CurrentPeriod) produces coverage and confidence for the machine's overall OEE benchmark — not for individual reason rates. Reason BSPs are separate per-reason lookups and do not have an equivalent "coverage" concept.

---

## Key Takeaways

1. **BSP is the P75 of proven performance, not the single best day.** The top 25% of qualifying runs set the target — ambitious but repeatedly achievable.

2. **Three fallback levels mean most dies get a benchmark even with thin history.** L1 uses the die's own runs (≥15). L2 pools similar board types (≥25 combined). L3 pools the whole machine (≥35). A die with no history at all gets nothing, and its scheduled hours count as uncovered.

3. **Uncovered hours drag both CoveragePct and ConfScore.** If a machine regularly runs product with no history, coverage drops toward 50% and insights get suppressed. ConfScore falls toward 0 and BSP_Confidence shows LOW or Insufficient History.

4. **PoolSize tells you how thin the data is behind the benchmark.** Below 15 means a single unusual run can shift the BSP materially. Above 30 means the benchmark is well-supported.

5. **OEE_Impact is in hours, so it ranks across all KPIs and machines directly.** A Setup insight costing 5 hrs/week and an OEE insight costing 5 hrs/week are equally urgent. The front-end weekly action list filters to `KPI_Category = 'Lever'` and sorts by OEE_Impact descending.

---

## PART 5 — Pipeline Flowchart

```
╔══════════════════════════════════════════════════════════════════════════╗
║  JobFact_Raw                                                             ║
║  Grain: Date + WC + Shift + Operator + Order + Die + Reason + fSched    ║
║  (one row per scheduling slot)                                           ║
╚══════════════════════╦═══════════════════════════════════════════════════╝
                       │
         ┌─────────────┴──────────────────────────┐
         │  BSP PIPELINE                          │  SCORING PIPELINE
         │  (24-month history window)             │  (13-week trend window)
         ▼                                        ▼
╔════════════════════════════╗        ╔═══════════════════════════════════╗
║  JobFact_Job_BSP_Agg       ║        ║  JobFact_Scoring_Agg              ║
║  Grain: Date+WC+Shift+Die  ║        ║  Grain: Date+WC+Die+PltMat+       ║
║  (all fSched rows summed)  ║        ║         Carton+Shift+Operator+    ║
╚════════════╦═══════════════╝        ║         Order                     ║
             │ RunHours > 2 filter    ╚═══════════════╦═══════════════════╝
             ▼                                        │ Board attrs applied
╔════════════════════════════╗                        ▼
║  JobFact_Job_BSP (L1)      ║        ╔═══════════════════════════════════╗
║  Grain: Date+WC+Shift+Die  ║        ║  JobFact_Scoring                  ║
║                            ║        ║  + MaxSpeed + OEE_Denom           ║
║  JobFact_Job_BSP_L2        ║        ╚═══════════════╦═══════════════════╝
║  Grain: +PltMatKey         ║                        ▼
╚════════════╦═══════════════╝        ╔═══════════════════════════════════╗
             │                        ║  WeeklyDieKPI  (Section 30)       ║
             │  GROUP BY:             ║  Grain: WeekStart+Plant+WC+Die    ║
             │  L1: Plant+WC+Die      ║  Actual per-die totals            ║
             │  L2: Plant+WC+         ╚═══════════════╦═══════════════════╝
             │      BTG+Caliper+                      │
             │      L2_ExtraDim       ╔═══════════════▼═══════════════════╗
             │  L3: Plant+WC          ║  WeeklyDieBSP  (Section 31)       ║
             ▼                        ║  Grain: WeekStart+Plant+WC+Die    ║
╔════════════════════════════╗        ║                                   ║
║  BSP Tables (L1 / L2 / L3) ║        ║  Coalesce(L1 → L2 → L3) per KPI  ║
║  Min runs: 15 / 25 / 35    ║        ║  Die_BSP_ConfScore: 3/2/1/0       ║
║  P75 higher-is-better      ║◄───────║  Die_BSP_PoolSize: pool run count  ║
║  P25 lower-is-better       ║        ║  CoveredSchedHrs: hrs if resolved ║
║                            ║        ╚═══════════════╦═══════════════════╝
║  Setup: adds MROClass      ║                        │
║  Reasons: adds ReasonKey   ║                        │  Weighted avg by SchedHrs
╚════════════╦═══════════════╝                        ▼
             │ → converted to          ╔═══════════════════════════════════╗
             │   mapping tables        ║  WeeklyMachineBSP  (Section 32)   ║
             │   (36+ maps)            ║  Grain: WeekStart+Plant+WC        ║
             │                        ║  BSP values: covered hrs only     ║
             │                        ║  ConfScore/PoolSize: all hrs       ║
             │                        ║  BSP_CoveragePct: covered÷total   ║
             │                        ╚═══════════════╦═══════════════════╝
             │                                        │
             │          ╔═════════════════════════════╝
             │          │
             │          │   WeeklyMachineKPI (Section 33)
             │          │   Grain: WeekStart+Plant+WC
             │          │   Actual weekly KPIs, all 13 weeks
             │          │   Streak via Peek() sorted ASC
             │          │
             │          └────┬────┘
             │               │
             │               ▼
             │   ╔═══════════════════════════════════╗
             │   ║  CurrentPeriod  (Section 37)       ║
             │   ║  Grain: Plant+WC  (Week −1 only)   ║
             │   ║  Cur_OEE, Cur_BSP_OEE, …           ║
             │   ║  Cur_SchedHours, Cur_RunHours      ║
             │   ║  Cur_BSP_CoveragePct               ║
             │   ║  Cur_BSP_ConfScore (last week)     ║
             │   ║  Cur_BSP_PoolSize  (last week)     ║
             │   ╚═══════════════╦═══════════════════╝
             │                   │
             │     Fires when: Actual < BSP
             │     AND CoveragePct > 0.5 (strict)
             │                   │
             │                   ▼
             │   ╔═══════════════════════════════════╗
             └──►║  InsightRecords  (Sections 42–47) ║
                 ║  Grain: Plant+WC+KPI_Name+Reasons ║
                 ║  GapHrs = gap × time denominator  ║
                 ║  OEE_Impact = GapHrs×(1+Streak/4) ║
                 ║  KPI_Category: Outcome or Lever   ║
                 ║  Ranked by OEE_Impact DESC        ║
                 ╚═══════════════════════════════════╝
```

---

### Grain Summary

| Table | Grain | Purpose |
|---|---|---|
| `JobFact_Raw` | Date + WC + Shift + Operator + Order + Die + ReasonKey + fSched | Raw source |
| `JobFact_Job_BSP` | Date + WC + Shift + Die | One BSP qualifying run (RunHours > 2) |
| `JobFact_Job_BSP_L2` | Date + WC + Shift + Die + PltMatKey | Same + board attributes for L2 grain |
| `BSP_Main_L1` | Plant + WC + Die | P75/P25 benchmark, n ≥ 15 |
| `BSP_Main_L2` | Plant + WC + BTG + Caliper + L2_ExtraDim | P75/P25 benchmark, n ≥ 25 |
| `BSP_Main_L3` | Plant + WC | P75/P25 benchmark, n ≥ 35 |
| `WeeklyDieKPI` | WeekStart + Plant + WC + Die | Actual weekly per-die totals |
| `WeeklyDieBSP` | WeekStart + Plant + WC + Die | Per-die actuals + resolved BSP, coverage, confidence |
| `WeeklyMachineBSP` | WeekStart + Plant + WC | Machine-week weighted BSP + coverage + confidence |
| `WeeklyMachineKPI` | WeekStart + Plant + WC | Machine-week actuals + streak (13-week window) |
| `CurrentPeriod` | Plant + WC | Week −1 actuals + BSP — where the comparison fires |
| `InsightRecords` | Plant + WC + KPI_Name + Reasons | Final output rows |

### How BSP and Current Period Connect

1. BSP is resolved per die (in `WeeklyDieBSP`) using the dies that actually ran in Week −1, each getting its best available BSP level.
2. Per-die BSPs are blended into one machine-week BSP (in `WeeklyMachineBSP`) weighted by SchedHours — covered dies only in the BSP calculation, all dies in ConfScore/PoolSize/Coverage.
3. This blended BSP travels into `CurrentPeriod` and is compared to the machine's actual Week −1 performance.
4. `GapHrs = (BSP − Actual) × Cur_SchedHours` converts the gap into scheduled hours lost; `OEE_Impact = GapHrs × streak_multiplier` adds urgency weighting.
