# -*- coding: utf-8 -*-
"""
Shared content model for the KPI & BSP working-session deliverables.

Single source of truth consumed by build_docx.py and build_pptx.py so the
Word reference and the PowerPoint deck never drift apart. Every fact here is
traceable to InsightOpexv1.qvs (section numbers cited in each KPI's
`source` field). Nothing here should be treated as authoritative business
policy -- it's a plain-language restatement of what the script currently
does, for a plant working session to review.
"""

# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------

DOC_TITLE = "KPI & BSP Calculation Reference"
DOC_SUBTITLE = "Folding Carton Actionable Intelligence Platform — Working Session Reference"

PPT_TITLE = "KPI & BSP Calculation Working Session"
PPT_SUBTITLE = "How we measure performance, and how we calculate the Best Shown Performance (BSP) benchmark"

PURPOSE_PARAGRAPHS = [
    "Every week, the platform compares each machine's recent performance against "
    "its own history and produces a ranked list of the biggest opportunities, "
    "measured in lost sheets. This document explains, in plant language, exactly "
    "how each number in that report is calculated today.",
    "The goal of this working session is not to declare the current methodology "
    "correct. It is to make the calculation logic fully transparent so plant "
    "personnel can review it, ask questions, challenge assumptions, and recommend "
    "changes. Every formula in this document is taken directly from the "
    "production calculation script (InsightOpexv1.qvs) — nothing here is "
    "invented or assumed.",
]

SCOPE_CALLOUT_TITLE = "Current Pilot Scope — Please Note Before Reviewing BSP Targets"
SCOPE_CALLOUT_PARAGRAPHS = [
    "The calculations described in this document are currently running for a "
    "limited pilot, not the full network. Two scope limits affect every BSP "
    "target discussed below and should be kept in mind throughout this review:",
]
SCOPE_CALLOUT_BULLETS = [
    "Only 13 specific machines (work centers) across the network are currently "
    "included in the calculation. All other machines are excluded entirely.",
    "Production history is read starting January 1, 2025 only. The benchmark "
    "logic is designed to look back up to 24 months, but because history only "
    "goes back to that date, every BSP target today is built on less than 24 "
    "months of data — and will keep growing richer as more weeks accumulate.",
    "Because BSP pool sizes are still building up, some machines may show "
    "\"Insufficient History\" confidence, or may not generate a given insight "
    "at all yet, simply because they have not yet reached the minimum number of "
    "qualifying runs described later in this document.",
]

HOW_TO_READ_PARAGRAPHS = [
    "Four terms are used throughout this document and the weekly report. "
    "Keeping them distinct is the key to reading everything else correctly:",
]
HOW_TO_READ_TERMS = [
    ("Actual", "What the machine actually did last week for a given KPI (e.g. "
               "this week's OEE, this week's average changeover time)."),
    ("BSP (Best Shown Performance)", "The benchmark the machine is compared "
               "against. It is not a corporate standard or an engineering "
               "spec — it is calculated from that same machine's own best "
               "historical results (or, when a machine doesn't have enough "
               "history of its own, from similar machines/board types), as "
               "explained in the BSP Calculation section."),
    ("BSP Performance / Gap", "The difference between Actual and BSP, shown "
               "both as a percentage gap and as a converted \"sheets lost\" "
               "number (Sheet Gap) so that very different KPIs — a percentage, "
               "an hour, an event count — can all be compared on the same "
               "scale: sheets."),
    ("Sheet Gap / Sheet Impact", "The gap, converted into an estimated number "
               "of sheets the plant lost last week because performance fell "
               "short of BSP on that KPI. This is what the weekly report ranks "
               "opportunities by."),
]

# ---------------------------------------------------------------------------
# BSP mechanism (shared narrative, used in DOCX "BSP Calculation" section
# and the PPTX "BSP in one picture" slide)
# ---------------------------------------------------------------------------

BSP_FLOW_STEPS = [
    "Production / Event Data",
    "KPI Calculation (per run)",
    "Actual Performance (last week)",
    "BSP / Target (from history)",
    "BSP Performance (Actual vs BSP)",
    "Sheet Gap (converted to sheets)",
]

BSP_MECHANISM_STEPS = [
    ("1. Build the history pool",
     "For most KPIs, the system looks at every individual production run "
     "(a specific machine, shift, and die/tool combination, on a specific day) "
     "over roughly the last 24 months (currently capped at the pilot's "
     "available history — see the Scope note above). Only runs with more than "
     "2 hours of run time are included in this pool — very short test or "
     "trial runs are excluded so they don't skew the benchmark."),
    ("2. Take a percentile, not the best-ever run",
     "BSP is not the single best result the machine ever posted — that would "
     "be a one-off, possibly a fluke. Instead, BSP is the 75th percentile "
     "(top quartile) of the pool for KPIs where higher is better (OEE, Speed), "
     "or the 25th percentile (bottom quartile) for KPIs where lower is better "
     "(Downtime %, Scrap, changeover time, wash/trip time and frequency). In "
     "plain terms: BSP represents a level of performance the machine has "
     "already demonstrated repeatedly and sustainably — roughly its best "
     "quarter of runs — not a single lucky shift."),
    ("3. Calculate BSP at three levels of specificity",
     "The same percentile calculation is repeated at three grains, from most "
     "specific to most general, each requiring a minimum number of qualifying "
     "runs before it is considered reliable enough to use:\n"
     "  • Level 1 (Die-specific): this exact machine + this exact die/tool "
     "— needs at least 15 qualifying runs.\n"
     "  • Level 2 (Board-specific): this machine + this board type + board "
     "thickness (and, on Gluer/Window machines, carton style; on cutting "
     "machines, number-up layout) — needs at least 25 qualifying runs.\n"
     "  • Level 3 (Machine-level): this machine, all product types combined "
     "— needs at least 35 qualifying runs."),
    ("4. Use the most specific level that has enough data",
     "For each die, each week, the system tries Level 1 first. If that die "
     "doesn't yet have 15 qualifying runs, it falls back to Level 2. If that "
     "still isn't enough, it falls back to Level 3. Whichever level actually "
     "resolves is recorded as the confidence for that die: HIGH (Level 1), "
     "MEDIUM (Level 2), or LOW (Level 3). If none of the three levels have "
     "enough history, no BSP is set for that die that week."),
    ("5. Roll die-level BSP up to a single machine-week BSP",
     "A machine typically runs several dies in a week. Each die's resolved "
     "BSP is combined into one machine-level BSP for the week, weighted by "
     "how many scheduled hours that die actually ran — a die that ran 30 "
     "hours counts more than one that ran 2 hours. Dies with no resolved BSP "
     "(not enough history at any level) do not contribute to the machine's "
     "BSP or to its coverage."),
    ("6. Coverage gate — don't publish a thin comparison",
     "\"Coverage\" is the share of the week's scheduled hours that came from "
     "dies where a BSP could actually be resolved. An insight for a KPI is "
     "only generated if coverage for that machine/week is strictly greater "
     "than 50%. If most of the week's hours were on dies with no reliable "
     "benchmark yet, no insight is produced for that KPI that week, rather "
     "than showing a number built on a small, unrepresentative slice of the "
     "week."),
]

# ---------------------------------------------------------------------------
# Walked example: BSP for Speed, step by step (used by 2 PPTX slides)
# Illustrative figures only — the mechanism (pool -> percentile -> level
# fallback -> gap) is taken directly from the script (Sections 10, 17-19,
# 29-32, 33, 42).
# ---------------------------------------------------------------------------

SPEED_BSP_WALKTHROUGH = {
    "pool_intro": (
        "This machine + this specific die has 15 qualifying runs (RunHours > 2) "
        "over the lookback window. Each run's Speed (sheets produced ÷ run "
        "hours) is one data point in the pool."
    ),
    "sorted_speeds": [
        4800, 4850, 4900, 5000, 5050, 5100, 5150,
        5200, 5300, 5400, 5500, 5600, 5700, 5900, 6100,
    ],
    "percentile_note": (
        "Sorted low to high. Speed is a higher-is-better KPI, so BSP takes the "
        "75th percentile — not the highest value (6,100), which could be a "
        "one-off. With 15 sorted values, the 75th percentile falls between the "
        "11th value (5,500) and 12th value (5,600), interpolating to 5,550."
    ),
    "l1_bsp": 5550,
    "levels": [
        # level, grain, qualifying runs, minimum required, resolved, bsp_value, confidence
        ("Level 1 — Die-specific", "This machine + this exact die", 15, 15, "Yes", "5,550 sheets/hr", "HIGH"),
        ("Level 2 — Board-specific", "This machine + board type/caliper", "(not needed)", 25, "n/a", "—", "—"),
        ("Level 3 — Machine-level", "This machine, all products", "(not needed)", 35, "n/a", "—", "—"),
    ],
    "resolved_summary": (
        "Level 1 has exactly the 15 runs required, so it resolves — no fallback "
        "to Level 2 or Level 3 is needed this week. BSP Speed = 5,550 sheets/hr, "
        "confidence = HIGH."
    ),
    "actual_speed": 5200,
    "run_hours": 90,
    "gap_calc": "(5,550 − 5,200) × 90 = 31,500 sheets",
    "result": "This machine ran 350 sheets/hr below its own demonstrated pace, "
              "costing an estimated 31,500 sheets of output last week.",
    "fallback_illustration": {
        "title": "If this die only had 9 qualifying runs instead of 15...",
        "rows": [
            ("Level 1 — Die-specific", 9, 15, "No — falls back"),
            ("Level 2 — Board-specific", 31, 25, "Yes — resolves here"),
            ("Level 3 — Machine-level", 58, 35, "(not needed)"),
        ],
        "note": (
            "BSP would instead come from Level 2 (this machine's board type/"
            "caliper pool, 31 runs) — a slightly broader comparison group, "
            "shown with MEDIUM confidence instead of HIGH, so the plant can see "
            "at a glance that the benchmark is less die-specific than usual."
        ),
    },
}

BSP_CHECKLIST_HEADER = (
    "For every KPI below, the same 13 questions can be asked. The answers "
    "that are common to (almost) all KPIs are summarized once here; anything "
    "KPI-specific is called out in that KPI's own section."
)
BSP_CHECKLIST_COMMON = [
    ("Is BSP fixed or calculated?", "Calculated — recomputed every reload from "
     "rolling history, not a fixed corporate target (except where noted)."),
    ("How is BSP applied?", "Compared directly against the machine's actual "
     "result for the most recently completed week."),
    ("Higher or lower better?", "KPI-specific — see each KPI's Direction field."),
    ("How is Actual vs BSP compared?", "A gap is computed (Actual − BSP or "
     "BSP − Actual, whichever direction indicates a shortfall), then converted "
     "into a percentage (Gap %) and into an estimated sheet-loss number (Sheet "
     "Gap) — see the Sheet Gap section."),
    ("Minimum/maximum limits?", "Minimum qualifying-run thresholds per BSP "
     "level (15 / 25 / 35) and the 50% coverage gate. No maximum caps on the "
     "gap itself."),
    ("Exclusions?", "Runs of 2 scheduled hours or less are excluded from every "
     "BSP pool. KPI-specific exclusions (e.g. MRO/setup reason codes, Blanket "
     "Wash and Feeder Trip reason codes in the general Downtime Reason list) "
     "are called out per KPI."),
    ("Weighting?", "Scheduled hours weight the roll-up from die-level BSP to "
     "machine-level BSP, and from die-level actuals to machine-level actuals."),
    ("Normalization?", "None beyond the percentile calculation itself and the "
     "sheet-conversion described in the Sheet Gap section."),
    ("What happens before the BSP comparison?", "Raw event data is filtered "
     "to scheduled/crewed time, aggregated to the run grain, then the "
     "KPI-specific ratio (e.g. good qty ÷ hours × speed) is computed per run "
     "before it enters the BSP pool."),
]

# ---------------------------------------------------------------------------
# KPI catalogue — the 10 published KPIs
# Each dict is deliberately flat/simple so both generators can iterate it.
# ---------------------------------------------------------------------------

KPIS = [
    {
        "name": "OEE",
        "category": "Outcome",
        "direction": "Higher is better",
        "measures": (
            "The single headline number for how well the machine converted its "
            "scheduled time into good product, versus what it could have made "
            "running at its rated speed with zero downtime and zero scrap."
        ),
        "formula": "OEE = Good Sheets Produced ÷ (Scheduled Hours × Rated Speed)",
        "numerator": "Good (non-scrap) sheets produced in the week, in OEE units of measure.",
        "denominator": (
            "Scheduled hours for the week × the machine's rated speed (nameplate "
            "OEM speed, or maximum Gluer output rate on Gluer/Window machines) — "
            "i.e. the theoretical maximum good sheets possible."
        ),
        "filters": [
            "Only time explicitly flagged as scheduled/crewed production time counts toward Scheduled Hours.",
            "Rated speed is machine-specific: Gluer and Window departments use their maximum recorded Gluer output rate; every other department uses OEM (nameplate) speed.",
        ],
        "actual": "Computed per completed week from the formula above, using last week's totals.",
        "bsp": (
            "BSP OEE is the 75th-percentile OEE achieved across the machine's own "
            "qualifying historical runs (Level 1 die-specific, falling back to "
            "Level 2 board-specific, then Level 3 machine-level — see BSP "
            "Calculation section)."
        ),
        "bsp_performance": "Insight fires when this week's Actual OEE is below BSP OEE, and coverage exceeds 50%.",
        "sheet_gap_formula": "Sheet Gap = (BSP OEE − Actual OEE) × Scheduled Hours × Rated Speed",
        "special_logic": (
            "Sheet Gap uses the machine's nameplate rated speed (not the BSP "
            "Speed benchmark) — because the OEE denominator itself is defined "
            "using rated speed, not benchmark speed. This is the one KPI whose "
            "own KPI_Category is \"Outcome\" rather than \"Lever\" — every other "
            "published KPI is treated as a lever that feeds into OEE."
        ),
        "example": {
            "actual": "72.0% OEE",
            "bsp": "80.0% BSP OEE",
            "inputs": "Scheduled Hours = 120, Rated Speed = 6,000 sheets/hr",
            "calc": "(0.80 − 0.72) × 120 × 6,000 = 57,600 sheets",
            "result": "≈ 57,600 sheets of lost output vs. this machine's own demonstrated best.",
        },
        "source": "Sections 10, 17-19, 29-32, 33, 42 (KPI_ID: OEE)",
    },
    {
        "name": "Speed",
        "category": "Lever - OEE",
        "direction": "Higher is better",
        "measures": "How fast the machine actually ran while producing, in sheets per run-hour.",
        "formula": "Speed = Total Sheets Produced (good + scrap) ÷ Run Hours",
        "numerator": "Total sheets produced (good plus scrap) during the week.",
        "denominator": "Actual run hours (time the machine was physically running, not just scheduled).",
        "filters": ["Run hours counted only from scheduled/crewed time rows."],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "75th-percentile Speed from the same 3-level qualifying-run pool used for OEE.",
        "bsp_performance": "Insight fires when Actual Speed is below BSP Speed, with coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = (BSP Speed − Actual Speed) × Run Hours",
        "special_logic": "None beyond the standard 3-level BSP mechanism.",
        "example": {
            "actual": "5,400 sheets/hr",
            "bsp": "6,000 sheets/hr BSP",
            "inputs": "Run Hours = 90",
            "calc": "(6,000 − 5,400) × 90 = 54,000 sheets",
            "result": "≈ 54,000 sheets of output the machine could have produced running at its own demonstrated pace.",
        },
        "source": "Sections 10, 17-19, 29-32, 33, 42 (KPI_ID: SPEED)",
    },
    {
        "name": "Downtime %",
        "category": "Lever - OEE",
        "direction": "Lower is better",
        "measures": "The share of scheduled time the machine was down (stopped) or in setup-down, rather than running.",
        "formula": "Downtime % = (Down Hours + Setup-Down Hours) ÷ Scheduled Hours",
        "numerator": "Down hours plus setup-down hours (both counted as downtime under the plant's definition of \"machine downtime\").",
        "denominator": "Scheduled hours for the week.",
        "filters": [
            "Scheduled/crewed time only.",
            "Setup Down time is counted as downtime here, per the plant definition of downtime as (Time − Run) plus (Time − Setup), i.e. everything that is not productive running or productive setup.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "25th-percentile Downtime % from the same 3-level pool (a low downtime % is \"good\", so the bottom quartile is the benchmark).",
        "bsp_performance": "Insight fires when Actual Downtime % is above BSP Downtime %, with coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = (Actual Downtime % − BSP Downtime %) × Scheduled Hours × BSP Speed",
        "special_logic": (
            "Unlike OEE's Sheet Gap, this uses BSP Speed (the demonstrated best "
            "speed), not the nameplate rated speed, to convert the excess "
            "downtime hours into an estimated sheet loss. Downtime attributed to "
            "specific reason codes (see Downtime Reason KPI below) is measured "
            "differently — reason-level downtime excludes Setup Down and only "
            "counts named-reason Down Hours."
        ),
        "example": {
            "actual": "18.0% downtime",
            "bsp": "12.0% BSP downtime",
            "inputs": "Scheduled Hours = 120, BSP Speed = 6,000 sheets/hr",
            "calc": "(0.18 − 0.12) × 120 × 6,000 = 43,200 sheets",
            "result": "≈ 43,200 sheets of lost capacity from excess downtime.",
        },
        "source": "Sections 10, 17-19, 29-32, 33, 42 (KPI_ID: DOWNTIMEPCT)",
    },
    {
        "name": "Scrap Loss",
        "category": "Lever - OEE",
        "direction": "Lower is better",
        "measures": (
            "How many more sheets were scrapped last week than the plant would "
            "expect, given the size of the orders actually run and this "
            "machine's own demonstrated scrap performance on similarly-sized "
            "orders."
        ),
        "formula": "Scrap Loss (sheets) = Actual Scrap Sheets − Expected Scrap Sheets",
        "numerator": "Actual scrapped sheets across the week's orders.",
        "denominator": "N/A — this KPI is a direct sheet count, not a ratio (see Special Logic below for how the benchmark is built).",
        "filters": [
            "Both the current-week actuals and the historical benchmark pool are limited to single-setup orders (orders that had exactly one changeover) — multi-setup orders are excluded because their scrap is harder to attribute cleanly to one run.",
        ],
        "actual": (
            "Total scrapped sheets summed across this week's single-setup "
            "orders. (Note: the Actual Scrap Rate shown elsewhere on the "
            "machine's week — Cur_ScrapRate — is calculated across ALL orders, "
            "not just single-setup ones; see Item for Plant Review below.)"
        ),
        "bsp": "See Special Logic — this KPI does not use a single fixed BSP percentage; see the dedicated Special BSP Logic / Expected Scrap section.",
        "bsp_performance": "Insight fires when Actual Scrap Sheets exceed Expected Scrap Sheets, with sheet-coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = Actual Scrap Sheets − Expected Scrap Sheets (direct sheet count, no speed multiplier)",
        "special_logic": (
            "Scrap uses an order-size-aware \"expected scrap\" benchmark instead "
            "of one flat BSP rate per machine — see the dedicated Special BSP "
            "Logic section below for the full explanation and worked example."
        ),
        "example": {
            "actual": "Actual Scrap = 4.0% of order sheets",
            "bsp": "Expected Scrap = 3.0% of order sheets (bucket-specific benchmark)",
            "inputs": "One order of 40,000 sheets in that bucket",
            "calc": "Actual scrap = 1,600 sheets; Expected scrap = 1,200 sheets; Gap = 1,600 − 1,200",
            "result": "= 400 sheets of excess scrap vs. expected for that order size.",
        },
        "source": "Sections 15B, 28B, 40B, 42 (KPI_ID: SCRAPRATE / display name Scrap Loss)",
    },
    {
        "name": "Avg MR Time (Changeover / Makeready Time)",
        "category": "Lever - OEE",
        "direction": "Lower is better",
        "measures": "The average time spent per changeover (makeready/setup) event.",
        "formula": "Avg MR Time = Total Setup Hours ÷ Number of Setup Events",
        "numerator": "Total setup hours for the week.",
        "denominator": "Count of setup events for the week.",
        "filters": [
            "Only rows with at least one setup event count toward this KPI.",
            "The benchmark additionally distinguishes changeover complexity — a numeric MRO Class (1, 2, or 3) derived from the reason code — and, at the most specific level, the exact material used, since a simple changeover and a complex one shouldn't be benchmarked against each other.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": (
            "25th-percentile setup hours-per-event from the qualifying pool, "
            "resolved at 3 levels the same way as other KPIs, but the pool is "
            "further split by MRO Class at every level, and by exact Material "
            "Description at Level 1 only."
        ),
        "bsp_performance": "Insight fires when Actual Avg MR Time is above BSP Avg MR Time, with coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = (Actual Avg MR Time − BSP Avg MR Time) × Number of Setup Events × BSP Speed",
        "special_logic": (
            "This is the only KPI whose BSP grain includes changeover "
            "complexity (MRO Class) at every level, plus exact material at "
            "the most specific level — a narrower, more apples-to-apples "
            "benchmark than the other KPIs use."
        ),
        "example": {
            "actual": "0.75 hr (45 min) average changeover",
            "bsp": "0.45 hr (27 min) BSP average changeover",
            "inputs": "Setup Events = 8, BSP Speed = 6,000 sheets/hr",
            "calc": "(0.75 − 0.45) × 8 × 6,000 = 14,400 sheets",
            "result": "≈ 14,400 sheets of capacity lost to slower-than-demonstrated changeovers.",
        },
        "source": "Sections 20-22, 29-32, 33, 42 (KPI_ID: SETUPHRSEV, display name Avg MR Time)",
    },
    {
        "name": "Avg Blanket Wash Time",
        "category": "Lever - Downtime %",
        "direction": "Lower is better",
        "measures": "The average duration of a blanket wash event on the press.",
        "formula": "Avg Blanket Wash Time = Total Blanket Wash Hours ÷ Number of Blanket Wash Events",
        "numerator": "Hours attributed to blanket wash events during the week.",
        "denominator": "Count of blanket wash events during the week.",
        "filters": [
            "Only runs with at least one blanket wash event contribute to the benchmark pool.",
            "\"Blanket wash event\" is identified from an approved list of exact reason-code descriptions (not a broad text-search) — see the Special BSP Logic section on Blanket Wash / Feeder Trip identification.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "25th-percentile average wash time from the qualifying pool (3-level fallback as usual).",
        "bsp_performance": "Insight fires when Actual wash time is above BSP wash time, with coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = (Actual Wash Time − BSP Wash Time) × Number of Wash Events × BSP Speed",
        "special_logic": (
            "Displayed in the weekly email as minutes (e.g. 0.45 hr → 27 Mins) "
            "even though it is stored and calculated in fractional hours — a "
            "display-only conversion, not a calculation change."
        ),
        "example": {
            "actual": "0.30 hr (18 min) average wash",
            "bsp": "0.20 hr (12 min) BSP average wash",
            "inputs": "Wash Events = 5, BSP Speed = 6,000 sheets/hr",
            "calc": "(0.30 − 0.20) × 5 × 6,000 = 3,000 sheets",
            "result": "≈ 3,000 sheets of capacity lost to slower-than-demonstrated wash events.",
        },
        "source": "Sections 5, 9, 15, 29A, 29C, 33, 42 (KPI_ID: BWTTIME)",
    },
    {
        "name": "Avg Feeder Trip Time",
        "category": "Lever - Downtime %",
        "direction": "Lower is better",
        "measures": "The average duration of a feeder trip (feeder stoppage) event.",
        "formula": "Avg Feeder Trip Time = Total Feeder Trip Hours ÷ Number of Feeder Trip Events",
        "numerator": "Hours attributed to feeder trip events during the week.",
        "denominator": "Count of feeder trip events during the week.",
        "filters": [
            "Only runs with at least one feeder trip event contribute to the benchmark pool.",
            "\"Feeder trip event\" is identified from an approved list of exact reason-code descriptions, scoped deliberately to press-feeder trips only — no gluer/cutting/sheeter feeders, infeed, web-guide, splicer, or unwind codes are included.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "25th-percentile average trip time from the qualifying pool (3-level fallback as usual).",
        "bsp_performance": "Insight fires when Actual trip time is above BSP trip time, with coverage > 50%.",
        "sheet_gap_formula": "Sheet Gap = (Actual Trip Time − BSP Trip Time) × Number of Trip Events × BSP Speed",
        "special_logic": "Displayed in the weekly email as minutes, same display-only conversion as Avg Blanket Wash Time.",
        "example": {
            "actual": "0.12 hr (7 min) average trip",
            "bsp": "0.08 hr (5 min) BSP average trip",
            "inputs": "Trip Events = 20, BSP Speed = 6,000 sheets/hr",
            "calc": "(0.12 − 0.08) × 20 × 6,000 = 4,800 sheets",
            "result": "≈ 4,800 sheets of capacity lost to slower-than-demonstrated feeder-trip recovery.",
        },
        "source": "Sections 5, 9, 15, 29B, 29C, 33, 42 (KPI_ID: FTTIME)",
    },
    {
        "name": "Blanket Washes per 10K",
        "category": "Lever - Downtime %",
        "direction": "Lower is better",
        "measures": "How often blanket washes happen, expressed as a rate per 10,000 sheets produced — i.e. how frequently the event occurs, not how long each one lasts.",
        "formula": "Blanket Washes per 10K = (Number of Blanket Wash Events ÷ Total Sheets Produced) × 10,000",
        "numerator": "Count of blanket wash events during the week.",
        "denominator": "Total sheets produced (good + scrap) during the week, expressed per 10,000 sheets.",
        "filters": [
            "The benchmark pool for this rate includes every qualifying run with production (Total Sheets > 0) — including runs with zero wash events, because a clean run with no washes is itself a valid (and good) data point for a frequency benchmark. This differs from the Avg Wash Time KPI above, which can only be calculated on runs that actually had at least one wash event.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "25th-percentile wash rate from the qualifying pool (3-level fallback as usual).",
        "bsp_performance": "Insight fires when Actual wash rate is above BSP wash rate, with coverage > 50%.",
        "sheet_gap_formula": (
            "Sheet Gap = ((Actual Rate − BSP Rate) ÷ 10,000) × Total Sheets Produced "
            "× this machine's own Avg Wash Time × BSP Speed"
        ),
        "special_logic": (
            "The sheet-loss conversion first turns the excess rate back into an "
            "estimated excess number of wash events (using this week's total "
            "sheets), then multiplies by this machine's own actual average wash "
            "duration (not the BSP wash duration) and by BSP Speed. This is the "
            "one KPI whose benchmark pool intentionally includes zero-event runs."
        ),
        "example": {
            "actual": "3.0 washes per 10K sheets",
            "bsp": "1.5 washes per 10K BSP",
            "inputs": "Total Sheets = 200,000, Avg Wash Time (this machine) = 0.25 hr, BSP Speed = 6,000 sheets/hr",
            "calc": "((3.0 − 1.5) / 10,000) × 200,000 × 0.25 × 6,000 = 45,000 sheets",
            "result": "≈ 45,000 sheets of capacity lost to excess wash frequency.",
        },
        "source": "Sections 5, 9, 15, 29C, 33, 42 (KPI_ID: BWPER10K)",
    },
    {
        "name": "Feeder Trips per 10K",
        "category": "Lever - Downtime %",
        "direction": "Lower is better",
        "measures": "How often feeder trips happen, expressed as a rate per 10,000 sheets produced.",
        "formula": "Feeder Trips per 10K = (Number of Feeder Trip Events ÷ Total Sheets Produced) × 10,000",
        "numerator": "Count of feeder trip events during the week.",
        "denominator": "Total sheets produced (good + scrap) during the week, expressed per 10,000 sheets.",
        "filters": [
            "Same zero-event-inclusive pool logic as Blanket Washes per 10K above.",
        ],
        "actual": "Computed per completed week from the formula above.",
        "bsp": "25th-percentile trip rate from the qualifying pool (3-level fallback as usual).",
        "bsp_performance": "Insight fires when Actual trip rate is above BSP trip rate, with coverage > 50%.",
        "sheet_gap_formula": (
            "Sheet Gap = ((Actual Rate − BSP Rate) ÷ 10,000) × Total Sheets Produced "
            "× this machine's own Avg Trip Time × BSP Speed"
        ),
        "special_logic": "Same conversion logic as Blanket Washes per 10K, using this machine's own average trip duration.",
        "example": {
            "actual": "12.0 trips per 10K sheets",
            "bsp": "8.0 trips per 10K BSP",
            "inputs": "Total Sheets = 200,000, Avg Trip Time (this machine) = 0.10 hr, BSP Speed = 6,000 sheets/hr",
            "calc": "((12.0 − 8.0) / 10,000) × 200,000 × 0.10 × 6,000 = 48,000 sheets",
            "result": "≈ 48,000 sheets of capacity lost to excess trip frequency.",
        },
        "source": "Sections 5, 9, 15, 29C, 33, 42 (KPI_ID: FTPER10K)",
    },
    {
        "name": "Downtime Reason (sub-reason breakdown)",
        "category": "Lever - Downtime % (sub-reason of Downtime %)",
        "direction": "Lower is better",
        "measures": (
            "Which specific named downtime reason codes (e.g. mechanical jam, "
            "material issue, quality check, etc. — excluding Blanket Wash / "
            "Feeder Trip / changeover reasons, which are their own KPIs above) "
            "are driving a machine's Downtime % problem. Up to the top 3 "
            "reasons by sheet impact are shown per machine per week."
        ),
        "formula": "Reason Downtime % = Down Hours for that specific reason ÷ Total Scheduled Hours",
        "numerator": "Down hours attributed specifically to that one reason code during the week.",
        "denominator": "Total scheduled hours for the machine that week (all reasons combined, not just this one).",
        "filters": [
            "Excludes MRO/changeover-coded reason rows (those belong to Avg MR Time).",
            "Excludes any reason code on the approved Blanket Wash / Feeder Trip list (those are their own dedicated KPIs above) — this prevents the same minutes of downtime being counted twice, once under a specific reason and again under Blanket Wash/Feeder Trip.",
            "Reason rows with no reason code recorded are excluded.",
        ],
        "actual": "Computed per completed week per reason code from the formula above.",
        "bsp": (
            "25th-percentile of that specific reason's downtime rate, from a "
            "pool of qualifying runs that had that same reason recorded, "
            "resolved with the same Level 1 → 2 → 3 fallback as other KPIs "
            "(die-specific → board-specific → machine-level, always keyed by "
            "reason code)."
        ),
        "bsp_performance": (
            "A reason is only listed if this week's rate for that reason is "
            "above its own BSP for that reason. Reasons are ranked by "
            "estimated sheet impact, and only the top 3 per machine per week "
            "are shown."
        ),
        "sheet_gap_formula": "Sheet Gap = (Actual Reason Rate − BSP Reason Rate) × Total Scheduled Hours × BSP Speed",
        "special_logic": (
            "This is a breakdown of the Downtime % KPI, not a separate outcome "
            "— in the weekly report, when Downtime % appears among a machine's "
            "top opportunities, it can be automatically replaced by its top "
            "2 specific reasons (if any qualify), so the plant sees the "
            "actionable reason rather than just the aggregate percentage. This "
            "KPI also has its own streak definition — see Filters and Business "
            "Rules section."
        ),
        "example": {
            "actual": "6.0% of scheduled hours lost to \"Mechanical Jam\"",
            "bsp": "3.5% BSP for that same reason on that machine",
            "inputs": "Total Scheduled Hours = 120, BSP Speed = 6,000 sheets/hr",
            "calc": "(0.06 − 0.035) × 120 × 6,000 = 18,000 sheets",
            "result": "≈ 18,000 sheets of lost output attributable specifically to Mechanical Jam.",
        },
        "source": "Sections 12, 23-25, 29, 38-41B, 44, 46 (KPI_Name: Downtime Reason)",
    },
]

# ---------------------------------------------------------------------------
# Special BSP logic — Scrap
# ---------------------------------------------------------------------------

SCRAP_SPECIAL_TITLE = "Special BSP Logic: Scrap Loss uses \"Expected Scrap\", not a flat target"
SCRAP_SPECIAL_WHY = (
    "A single machine can run a huge range of order sizes — a short 3,000-sheet "
    "trial order and a 500,000-sheet production run behave very differently on "
    "scrap. A flat \"this machine's scrap rate should be X%\" benchmark would be "
    "unfair to machines that happen to run more small orders (which naturally "
    "scrap a higher percentage, because setup waste is spread over fewer good "
    "sheets). To make the comparison fair, the script builds a benchmark that "
    "is aware of order size."
)
SCRAP_SPECIAL_STEPS = [
    ("Step 1 — Bucket every order by size",
     "Every order is placed into one of 10 size buckets, from \"XLow\" (fewer "
     "than 5,000 sheets) up to \"Mega\" (2.5 million sheets or more), based on "
     "its total sheet count (good + scrap)."),
    ("Step 2 — Build a scrap benchmark per machine, per bucket",
     "For each machine and each size bucket, the system looks at that "
     "machine's own single-setup orders (one changeover only) from roughly "
     "the last 6 months, and takes the 25th percentile of scrap percentage "
     "within that bucket. This is the \"expected\" scrap rate for an order of "
     "that size on that machine — deliberately narrower and more recent than "
     "the 24-month window used for other KPIs, and with no minimum number of "
     "orders required (a thin bucket is simply flagged with a low pool-size "
     "count rather than being blocked)."),
    ("Step 3 — Apply the bucket benchmark to this week's actual orders",
     "For every single-setup order the machine ran in the most recently "
     "completed week, the system looks up that order's bucket, applies the "
     "bucket's expected scrap %, and multiplies by that order's total sheets "
     "to get an Expected Scrap (in sheets) for that specific order."),
    ("Step 4 — Compare actual sheets scrapped to expected sheets scrapped",
     "The machine's total actual scrapped sheets for the week is compared "
     "directly to the sum of Expected Scrap across all its orders. The "
     "difference, in sheets, is the Scrap Loss Sheet Gap — no percentage "
     "conversion or speed multiplier is applied; it is a direct sheet count."),
]
SCRAP_SPECIAL_EXAMPLE = {
    "setup": "Machine runs one order in the \"Mid\" bucket (40,000 total sheets) this week.",
    "bench": "This machine's 25th-percentile scrap rate for \"Mid\"-bucket orders, from its own last 6 months of single-setup orders, is 3.0%.",
    "expected": "Expected Scrap = 3.0% × 40,000 = 1,200 sheets.",
    "actual": "This order actually scrapped 1,600 sheets (4.0% of the order).",
    "gap": "Scrap Loss = 1,600 − 1,200 = 400 sheets of excess scrap for this order.",
    "note": (
        "At the machine level, Actual and Expected are summed across all of "
        "the week's single-setup orders before the comparison is made and an "
        "insight is generated only if the total excess is positive and at "
        "least half the week's sheet volume came from orders where a bucket "
        "benchmark could be resolved."
    ),
}

# ---------------------------------------------------------------------------
# Sheet Gap — dedicated section
# ---------------------------------------------------------------------------

SHEET_GAP_INTRO = (
    "Sheet Gap is the platform's common currency for comparing very different "
    "kinds of shortfalls — a percentage-point gap in OEE, extra minutes per "
    "changeover, extra downtime events — on one scale: an estimated number of "
    "sheets the plant did not produce last week because performance on that "
    "KPI fell short of its own demonstrated BSP benchmark."
)
SHEET_GAP_POINTS = [
    ("What it represents", "An estimate, in sheets, of the output the plant "
     "left on the table on a single KPI, in the most recently completed week, "
     "relative to the benchmark that same machine/board/die combination has "
     "already demonstrated it can hit."),
    ("Which KPIs contribute", "All 9 published KPIs (OEE, Speed, Downtime %, "
     "Scrap Loss, Avg MR Time, Avg Blanket Wash Time, Avg Feeder Trip Time, "
     "Blanket Washes per 10K, Feeder Trips per 10K), plus the Downtime Reason "
     "breakdown, each with its own formula documented in the KPI-by-KPI "
     "section above."),
    ("How it avoids double-counting", "Speed, Downtime %, Scrap Loss, Avg MR "
     "Time, and the Blanket Wash/Feeder Trip KPIs are all treated as \"levers\" "
     "that ladder up into the single OEE outcome. On the weekly summary report, "
     "the headline \"Total Sheet Impact\" for a machine is the OEE row's Sheet "
     "Gap only — the lever rows are not added on top of it, because OEE "
     "already reflects their combined effect. The lever rows exist to explain "
     "*why* OEE fell short, not to be summed alongside it."),
    ("Filters / gating", "A Sheet Gap only becomes a published insight if (a) "
     "it is positive (an actual shortfall, not an improvement) and (b) the "
     "BSP coverage requirement (over 50% of the week's scheduled hours came "
     "from dies/orders with a resolvable benchmark) is met for that KPI."),
    ("Rounding", "The final number shown (Sheet Impact) is the calculated "
     "Sheet Gap rounded to two decimal places — no other adjustment or "
     "multiplier is applied."),
    ("Ranking use", "Within a plant, KPI opportunities are ranked by Sheet "
     "Impact, largest first, so the report surfaces the biggest sheet-loss "
     "opportunities at the top."),
]
SHEET_GAP_HISTORICAL_NOTE = (
    "A \"Streak\" value (0-4) is also shown next to each KPI, counting "
    "consecutive weeks of worsening performance (for the 9 main KPIs) or "
    "weeks above BSP out of the last 4 (for Downtime Reasons). This is "
    "display information only — it does not multiply or otherwise change the "
    "Sheet Gap number itself."
)
SHEET_GAP_EXAMPLE = {
    "kpi": "OEE",
    "line1": "BSP OEE = 80%, Actual OEE = 72%",
    "line2": "Scheduled Hours = 120, Rated Speed = 6,000 sheets/hr",
    "calc": "Sheet Gap = (0.80 − 0.72) × 120 × 6,000 = 57,600 sheets",
    "line3": "That 57,600-sheet OEE gap becomes the machine's Total Sheet Impact for the week on the summary report.",
}

# ---------------------------------------------------------------------------
# Filters & business rules summary table
# ---------------------------------------------------------------------------

FILTER_SUMMARY_TABLE = [
    # (KPI, Main Filters, Direction, BSP Type, Special Logic)
    ("OEE", "Scheduled/crewed time only; rated speed by department", "Higher better", "Calculated (3-level, 24 mo.)", "Sheet Gap uses nameplate speed, not BSP speed"),
    ("Speed", "Scheduled/crewed time only", "Higher better", "Calculated (3-level, 24 mo.)", "—"),
    ("Downtime %", "Scheduled time; includes Setup-Down as downtime", "Lower better", "Calculated (3-level, 24 mo.)", "Sheet Gap uses BSP speed"),
    ("Scrap Loss", "Single-setup orders only, both actual and benchmark", "Lower better", "Calculated per order-size bucket (6 mo.)", "Expected-scrap methodology — see dedicated section"),
    ("Avg MR Time", "Setup events only; split by changeover complexity (MRO Class) and, at Level 1, exact material", "Lower better", "Calculated (3-level, 24 mo.)", "Narrower grain than other KPIs"),
    ("Avg Blanket Wash Time", "Runs with ≥1 wash event; approved reason-text allow-list", "Lower better", "Calculated (3-level, 24 mo.)", "Excluded from general Downtime Reason list"),
    ("Avg Feeder Trip Time", "Runs with ≥1 trip event; approved reason-text allow-list, press-feeder only", "Lower better", "Calculated (3-level, 24 mo.)", "Excluded from general Downtime Reason list"),
    ("Blanket Washes per 10K", "All qualifying runs, incl. zero-wash runs", "Lower better", "Calculated (3-level, 24 mo.)", "Sheet Gap uses machine's own wash duration"),
    ("Feeder Trips per 10K", "All qualifying runs, incl. zero-trip runs", "Lower better", "Calculated (3-level, 24 mo.)", "Sheet Gap uses machine's own trip duration"),
    ("Downtime Reason", "Excludes MRO and Blanket Wash/Feeder Trip reason codes", "Lower better", "Calculated per reason code (3-level, 24 mo.)", "Top-3 by sheet impact; can replace Downtime % in the report"),
]

# ---------------------------------------------------------------------------
# Dependencies (cannot be fully verified from this script alone)
# ---------------------------------------------------------------------------

DEPENDENCIES = [
    ("Production/event source", "\"Asset Utilization - Facts\" data source — "
     "the underlying system(s) that record run time, downtime, setup, yield "
     "and scrap by machine/shift/die are outside this script and were not "
     "reviewed as part of this document."),
    ("Machine & department reference data", "Work Center Attributes, Plant "
     "Information, Department lookup — define which machines exist, which "
     "plant/department they belong to, and their nameplate speed. Maintained "
     "outside this script."),
    ("Material/board reference data", "Plant Material, Materials, Board Types "
     "— define board type, caliper, and material description used to build "
     "the Level 2 benchmark grain. Maintained outside this script."),
    ("Reason code reference data", "Time Reason Codes — the master list of "
     "downtime reason codes and descriptions, including which exact "
     "descriptions are classified as Blanket Wash or Feeder Trip. Plant "
     "input is the intended way to keep this list current."),
    ("Order/number-up reference data", "Order Operation data — supplies "
     "number-up (sheets per layout) used in cutting-department benchmarks."),
    ("Manager routing data", "Plant Managers workbook — supplies the "
     "email addresses used to route the weekly report; does not affect any "
     "KPI or BSP calculation."),
    ("Downstream notifier", "A separate Python program formats and sends the "
     "weekly email digest from this script's output. It re-displays some "
     "values (e.g. hours shown as minutes) but does not recalculate any KPI "
     "or BSP number — all math happens in this script."),
]

# ---------------------------------------------------------------------------
# Items for Plant Review / Discussion
# ---------------------------------------------------------------------------

REVIEW_ITEMS = [
    ("Pilot scope", "Only 13 machines are currently in scope, and history "
     "only goes back to January 1, 2025, so every BSP today is built on less "
     "than the intended 24 months of data. Confirm whether this is the "
     "expected pilot footprint and timeline for expanding."),
    ("Percentile ambition (P25/P75) and minimum pool sizes (15/25/35)",
     "Confirm whether the top/bottom-quartile benchmark, and the minimum "
     "number of qualifying runs required at each level, represent the right "
     "level of ambition and reliability for your machines."),
    ("2-hour minimum run-time filter", "Runs of 2 scheduled hours or less are "
     "excluded from every benchmark pool. Confirm this correctly separates "
     "trial/test runs from legitimate short production runs."),
    ("Scrap benchmark: single-setup orders only, no minimum bucket size, "
     "6-month window", "Confirm whether excluding multi-setup orders from "
     "the scrap benchmark is appropriate, whether a thin bucket (very few "
     "historical orders of that size) should be flagged more strongly before "
     "being used as a benchmark, and whether 6 months (vs. the 24 months used "
     "elsewhere) is the right lookback for scrap."),
    ("Scrap actual vs. scrap benchmark use different order pools", "The "
     "displayed \"current scrap rate\" for a machine is calculated across all "
     "orders, while the Scrap Loss KPI's actual and benchmark are both "
     "restricted to single-setup orders. Confirm this distinction is "
     "understood and acceptable, or whether they should be aligned."),
    ("Blanket Wash / Feeder Trip reason-text list completeness", "These two "
     "KPIs, and their exclusion from the general Downtime Reason list, "
     "depend on an approved list of exact reason-code descriptions. Confirm "
     "the list captures every wash/trip description your plant actually "
     "uses, and flag any missing or mis-scoped entries."),
    ("OEE Sheet Gap uses nameplate speed; other levers use BSP speed",
     "Confirm whether it is appropriate for the OEE conversion to sheets to "
     "use the machine's rated (nameplate) speed while every other lever "
     "(Downtime %, Avg MR Time, Wash/Trip KPIs) uses the demonstrated BSP "
     "speed instead."),
    ("Two different streak definitions", "The 9 main KPIs count consecutive "
     "weeks of worsening performance; Downtime Reasons count weeks above "
     "benchmark out of the last 4 (not necessarily consecutive). Confirm "
     "both are acceptable, or whether they should be made consistent."),
    ("Coverage gate uses OEE's benchmark coverage as the gatekeeper for other KPIs",
     "The same 50%-coverage requirement (based on how much of the week's "
     "hours had a resolvable OEE benchmark) governs whether *every* KPI's "
     "insight is allowed to fire that week. Confirm this proxy makes sense, "
     "or whether some KPIs should have their own independent coverage check."),
    ("Per-10K frequency KPIs use the machine's own actual event duration "
     "in the sheet-loss conversion", "Confirm this is the intended approach, "
     "versus using the benchmark duration instead."),
    ("Mixed board/material dies fall back to a coarser benchmark level",
     "When a die runs more than one carton style, material, or board "
     "combination within a week, the system cannot resolve a single value for "
     "that attribute and automatically falls back to a broader (Level 2 or "
     "Level 3) benchmark for that die. Confirm this fallback behavior is "
     "understood and acceptable."),
]

# ---------------------------------------------------------------------------
# Appendix - technical source mapping
# ---------------------------------------------------------------------------

APPENDIX_TRACE = [
    ("KPI thresholds & scope variables", "Step 1 (vBSP_L1_Min=15, "
     "vBSP_L2_Min=25, vBSP_L3_Min=35, vMinCoverage=0.5, date/machine scope filters)"),
    ("Qualifying-run pool build", "Sections 8-15 (JobFact_Job_BSP / "
     "JobFact_Job_BSP_L2, RunHours > 2 filter, fSched handling)"),
    ("Main KPI BSP (OEE, Speed, Downtime %, Scrap Rate legacy) — 3 levels",
     "Sections 17-19 (BSP_Main_L1/L2/L3)"),
    ("Setup (Avg MR Time) BSP — 3 levels", "Sections 20-22 (BSP_Setup_L1/L2/L3)"),
    ("Downtime Reason BSP — 3 levels", "Sections 23-25 (BSP_DownReason_L1/L2/L3)"),
    ("Avg Blanket Wash / Feeder Trip Time BSP", "Sections 29A-29B"),
    ("Blanket Wash / Feeder Trip per-10K BSP", "Section 29C"),
    ("Scrap bucket BSP", "Sections 15B, 28B (JobFact_Order_Scrap, BSP_ScrapBucket_Map)"),
    ("BSP resolution / 3-level fallback per die", "Section 31 (WeeklyDieBSP)"),
    ("Machine-week weighted BSP roll-up", "Section 32 (WeeklyMachineBSP)"),
    ("Weekly actual KPI aggregation & streaks", "Sections 33-35"),
    ("Current-period (1-week) actual + BSP aggregation", "Sections 36-37 (CurrentPeriod)"),
    ("Downtime reason current-period + streak", "Sections 38-41B"),
    ("Scrap current-period + expected scrap", "Section 40B"),
    ("Insight generation, Sheet_Gap formulas per KPI", "Section 42"),
    ("Sheet_Impact scoring & ranking", "Section 43, 45-46"),
    ("Final InsightRecords schema", "Section 47"),
    ("Incremental QVD store", "Section 48"),
    ("Weekly Machine Summary export (email source)", "Section 49"),
    ("Blanket Wash / Feeder Trip reason-text allow-list", "Section 5 (ApprovedRsnText_Map, RsnBucket_Map)"),
    ("MaxSpeed (rated speed) logic", "Sections 10, 15 (Department-based If/Else on MaxGluerCPH vs OEMSpeed)"),
]
