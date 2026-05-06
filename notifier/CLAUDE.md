# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

A Python email notifier that sends Monday-morning OEE Insight digests to plant managers. It reads `MachineWeekSummary.csv` from SharePoint (written by Qlik Section 49), checks freshness, fetches Maintenance Findings and PM Compliance data, groups rows by manager, renders Jinja2 templates, and sends via Microsoft Graph API.

---

## Commands

```bash
# Install (editable, with dev extras)
pip install -e ".[dev]"

# Dry run — renders per-manager HTML to out/preview/ without sending
python main.py --dry-run

# Live send
python main.py

# Preview with real SharePoint data — no mail sent, HTML saved to out/test_preview/
python test_without_mail.py --ignore-freshness

# Run tests
pytest tests/

# Run a single test file
pytest tests/test_grouper.py
```

---

## Architecture

```
main.py                  # Orchestrator: fetch → freshness → findings → PM → group → render → send
test_without_mail.py     # Fetch real SharePoint data, render previews to out/test_preview/ — no mail sent
src/
  fetch.py               # Graph API: fetch_csv (with mtime), fetch_findings_csv, fetch_pm_xlsx
  freshness.py           # StaleDataError raised if CSV mtime > freshness_max_hours
  grouper.py             # group_by_manager(df, findings_df=None, pm_df=None) → list[ManagerDigest]
  findings.py            # Pure: load_findings(), build_summary_for_machine() → FindingsSummary | None
  pm_compliance.py       # Pure: load_pm_compliance(), build_pm_summary_for_machine() → PMSummary | None
  renderer.py            # Jinja2 wrappers: render_html / render_text / render_admin_alert
  mailer.py              # Graph API: _post_with_retry (3 attempts, exp backoff), send_mail, send_admin_alert
  logging_setup.py       # configure() called once at startup
templates/
  email.html.j2          # Per-manager HTML digest; findings block then PM block per machine
  email.txt.j2           # Plain-text fallback; includes findings and PM blocks
  admin_alert.html.j2
tests/
  fixtures/sample_summary.csv            # 3 machines, 2 managers
  fixtures/sample_findings.csv           # 7 rows, 3 machines — Open/Missing WO/overdue/corroborated mix
  fixtures/sample_pm_compliance.xlsx     # Sheet1 blank; Sheet2: 7 rows, 3 machines, mixed Urgency
  test_grouper.py         # Unit tests for grouper (no network)
  test_findings.py        # Unit tests for findings module (no network)
  test_pm_compliance.py   # Unit tests for pm_compliance module (no network)
  test_renderer.py        # Assertion-style template tests (no network, no snapshots)
  test_freshness.py
config.yaml   # sharepoint_site_id, sharepoint_file_path, sharepoint_findings_path,
              # sharepoint_pm_path, sender_upn, admin_email
.env          # AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (gitignored)
```

### Data flow

```
SharePoint
  MachineWeekSummary.csv ──► fetch_csv ──► freshness check ──► group_by_manager ──► ManagerDigest[]
  Findings.csv ────────────► fetch_findings_csv ──► load_findings ──► findings_df ──┤
  PMComplianceDump.xlsx ───► fetch_pm_xlsx ──► load_pm_compliance ──► pm_df ─────────┘
                                                                                     │
                                                           build_summary_for_machine (findings, per machine)
                                                           build_pm_summary_for_machine (PM, per machine)
                                                                                     │
                                                           MachineSummary.findings: FindingsSummary | None
                                                           MachineSummary.pm_summary: PMSummary | None
                                                                                     │
                                                           render_html / render_text ──► Graph /sendMail
```

Findings and PM fetch failures each send an admin alert but do **not** abort the digest — machines render without those blocks.

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
| `Driver_Parent_Name` | `'Downtime %'` or `'Scrap Rate'` if either appeared in the original top-3 OEE levers; empty otherwise |
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
- **`grouper.py` is pure** — `findings_df=None` and `pm_df=None` make both optional; existing callers are unchanged. `MachineSummary` carries `outcome_1` / `outcome_1_sheets` (always OEE) and the new `driver_parent` / `driver_parent_sheets` fields (both `None` when neither Downtime % nor Scrap Rate drove the week).
- **Sub-lever swap rule** — Qlik Section 49 replaces each `Downtime %` / `Scrap Rate` occurrence in the top-3 OEE lever pool with up to 2 sub-reasons before writing `MachineWeekSummary.csv`. Python reads the already-swapped rows — there is no swap logic in Python. `Lever_N_Parent_Outcome` on a sub-reason row holds the parent name (e.g. `'Downtime %'`) so templates can show "Sub-lever of Downtime %". `Driver_Parent_Name` / `Driver_Parent_Sheets` are the email headline source — not derived from levers in Python.
- **Summary clause** — `email.html.j2` and `email.txt.j2` render "driven primarily by **\<driver_parent\>** (X sheets)" when `m.driver_parent` is non-null; the clause is omitted entirely otherwise. The old "driven primarily by OEE" wording no longer exists.
- **Findings and PM failures are non-fatal** — each catches exceptions, sends an admin alert, and continues the digest without that block. Pattern reuses `send_admin_alert` at `mailer.py:85`.
- **PM join uses `WC Object ID` only** — Plant is excluded because PMComplianceDump stores it as a short int (`8`) while MachineWeekSummary uses zero-padded strings (`0008`). `WC Object ID` is unique across plants.
- **PM block placement** — amber table rendered immediately below the Findings block within each per-machine card; suppressed entirely when `pm_summary is None`.
- **Renderer uses a module-level `_env`** — Jinja2 environment is created once at import time.
- **Admin alerts are best-effort** — `send_admin_alert` swallows exceptions so a broken credential does not mask the original error.
- **`--dry-run` writes to `out/preview/<email>.html`** — safe to run against production config.
- **`test_without_mail.py`** — fetches all three SharePoint sources, renders previews to `out/test_preview/`, logs findings and PM attachment counts, writes a clickable `_index.html`.

### Upgrade path

To replace Jinja2 with LLM prose, swap `src/renderer.py` for an Azure OpenAI call. `ManagerDigest` / `MachineSummary` / `LeverSummary` / `FindingsSummary` / `PMSummary` are the stable interface.
