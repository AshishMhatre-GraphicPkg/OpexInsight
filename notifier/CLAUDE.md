# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

A Python email notifier that sends Monday-morning OEE Insight digests to plant managers. It reads `MachineWeekSummary.csv` from SharePoint (written by Qlik Section 49), checks freshness, groups rows by manager, renders Jinja2 templates, and sends via Microsoft Graph API.

---

## Commands

```bash
# Install (editable, with dev extras)
pip install -e ".[dev]"

# Dry run — renders per-manager HTML to out/preview/ without sending
python main.py --dry-run

# Live send
python main.py

# Run tests
pytest tests/

# Run a single test file
pytest tests/test_grouper.py
```

---

## Architecture

```
main.py              # Orchestrator: fetch → freshness check → findings fetch → group → render → send
src/
  fetch.py           # Graph API: acquire MSAL token; fetch_csv (with mtime), fetch_findings_csv (no mtime)
  freshness.py       # StaleDataError raised if CSV mtime > freshness_max_hours
  grouper.py         # group_by_manager(df, findings_df=None) → list[ManagerDigest]
  findings.py        # Pure: load_findings(), build_summary_for_machine() → FindingsSummary | None
  renderer.py        # Jinja2 wrappers: render_html / render_text / render_admin_alert
  mailer.py          # Graph API: _post_with_retry (3 attempts, exp backoff), send_mail, send_admin_alert
  logging_setup.py   # configure() called once at startup
templates/
  email.html.j2      # Per-manager HTML digest; findings block per machine after levers
  email.txt.j2       # Plain-text fallback; includes simplified findings block
  admin_alert.html.j2
tests/
  fixtures/sample_summary.csv   # 3 machines, 2 managers
  fixtures/sample_findings.csv  # 7 rows, 3 machines — Open/Missing WO/overdue/corroborated mix
  test_grouper.py    # Unit tests for grouper (no network)
  test_findings.py   # Unit tests for findings module (no network)
  test_renderer.py   # Assertion-style template tests (no network, no snapshots)
  test_freshness.py
config.yaml          # sharepoint_site_id, sharepoint_file_path, sharepoint_findings_path, sender_upn, admin_email
.env                 # AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (gitignored)
```

### Data flow

```
SharePoint
  MachineWeekSummary.csv ──► fetch_csv ──► freshness check ──► group_by_manager ──► ManagerDigest[]
  Findings.csv ────────────► fetch_findings_csv ──► load_findings ──► findings_df ──┘
                                                                                     │
                                                                    build_summary_for_machine (per machine)
                                                                                     │
                                                                    MachineSummary.findings: FindingsSummary | None
                                                                                     │
                                                                    render_html / render_text ──► Graph /sendMail
```

Findings fetch failure sends an admin alert but does **not** abort the digest — machines render without a findings block.

### MachineWeekSummary.csv schema (`grouper.py`)

One row per machine. Join key for findings is `Plant` (plant number) + `WC Object ID`.

| Column | Notes |
|---|---|
| `Plant`, `WC Object ID` | Join keys for findings lookup |
| `Manager_Email`, `CC_List` | Routing; CC_List is semicolon-separated |
| `Plant - WC`, `Department`, `Period_Start` | Identity / display |
| `Total_Sheet_Impact` | Primary sort key (DESC) |
| `Outcome_1_Name`, `Outcome_1_Sheets`, `Outcome_2_Name`, `Outcome_2_Sheets` | Top-2 Outcome KPIs |
| `Lever_{1,2,3}_{Name,Reasons,Sheets,Gap_Pct,Streak,Parent_Outcome}` | Top-3 Lever KPIs |

`_build_levers()` stops at the first `Lever_N_Name` that is NaN — levers must be contiguous.

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
- **`findings.py` is pure** — no I/O. `load_findings(bytes)` → DataFrame; `build_summary_for_machine(df, …)` → dataclass. Tests call both directly with no network.
- **`grouper.py` is pure** — `findings_df=None` makes findings opt-in; existing callers are unchanged.
- **Findings failure is non-fatal** — catches exceptions, sends admin alert, continues digest without findings block. Pattern reuses `send_admin_alert` at `mailer.py:85`.
- **Renderer uses a module-level `_env`** — Jinja2 environment is created once at import time.
- **Admin alerts are best-effort** — `send_admin_alert` swallows exceptions so a broken credential does not mask the original error.
- **`--dry-run` writes to `out/preview/<email>.html`** — safe to run against production config.

### Upgrade path

To replace Jinja2 with LLM prose, swap `src/renderer.py` for an Azure OpenAI call. `ManagerDigest` / `MachineSummary` / `LeverSummary` / `FindingsSummary` are the stable interface.
