# Insight Notifier

Sends a Monday-morning OEE Insight email digest to plant managers, and a
region-level synopsis to regional managers, driven by `MachineWeekSummary.csv`
written by the Qlik load script (Section 49). Both emails use the company
brand theme (Green `#006548` / Light Green `#76BC21` / Black `#3D3935`).

## How it works

1. **Qlik** (Section 49) materialises `MachineWeekSummary.csv` on SharePoint after each reload — one row per machine per week, with top-5 Levers pre-pivoted, plus `Manager_Email` / `CC_List` / `Regional_Manager_Email` / `Regional_Manager_Name` / `Routing_Match_Level` stamped on from `PlantManagers.xlsx`.
2. **This notifier** pulls the CSV via Microsoft Graph, checks freshness, groups rows by `Manager_Email` into per-plant digests and by `Regional_Manager_Email` into per-region synopses, renders both via Jinja2, and sends via Graph API `/sendMail`.

## Setup

### 1. Azure AD app registration

Create an app registration with these **application** permissions (not delegated):

| API | Permission | Reason |
|---|---|---|
| Microsoft Graph | `Mail.Send` | Send emails as the shared mailbox |
| Microsoft Graph | `Sites.Read.All` | Read the SharePoint CSV |

Scope `Mail.Send` to the sender mailbox only via Exchange Online RBAC (recommended):

```powershell
New-ApplicationAccessPolicy `
  -AppId <CLIENT_ID> `
  -PolicyScopeGroupId <MAILBOX_UPN_OR_GROUP> `
  -AccessRight RestrictAccess `
  -Description "Insight notifier send-as scope"
```

### 2. PlantManagers.xlsx

Upload to SharePoint at the same path as `MachineWeekSummary.csv`:

```
OPEXinsights/PlantManagers.xlsx
```

**This file is read by Qlik, not by the Python notifier** — Section 7B of
`InsightOpexv1.qvs` maps it onto every `MachineWeekSummary.csv` row. The
Python side never opens the workbook directly.

**Grain: one row per Plant + Department** (not one row per Plant). A plant
with machines in several departments needs one row per department;
`Manager_Email` / `Regional_Manager_Email` typically repeat across a
plant's rows since the whole plant usually reports to one plant manager.

Required columns (table name must be `PlantManagers`):

| Column | Example |
|---|---|
| `Plant` | `Elk Grove` |
| `Department` | `Gluer` — must match Qlik's `Department` values exactly (e.g. `Sheetfed Printing`, `Gluer`, `Window`, `Sheetfed Cutting`, `Web Cutting`) |
| `Manager_Name` | `Jane Smith` |
| `Manager_Email` | `j.smith@company.com` |
| `CC_List` | `supervisor@company.com` (semicolon-separated; may be blank) |
| `Regional_Manager` | `Ann Lee` |
| `Regional_Manager_Email` | `a.lee@company.com` |

**Routing fallback:** if a machine's Plant+Department pair isn't in the
workbook, Qlik falls back to a Plant-only lookup (first matching row for
that plant) so the machine still gets routed, and stamps
`Routing_Match_Level = 'Plant'` on that row instead of `'Department'`. The
notifier logs every such fallback and sends one admin alert per run
listing the exact Plant/Department pairs that need a row added to the
workbook — see `src/routing_check.py`.

### 3. Config files

Copy `.env.example` to `.env` and fill in the Azure AD credentials:

```
AZURE_TENANT_ID=...
AZURE_CLIENT_ID=...
AZURE_CLIENT_SECRET=...
```

Edit `config.yaml`:
- `sharepoint_site_id` — get it via: `GET https://graph.microsoft.com/v1.0/sites/{hostname}:/{site-path}`
- `sharepoint_file_path` — path within the default drive, e.g. `BSS_AMC_MFG/.../MachineWeekSummary.csv`
- `sender_upn` — shared mailbox UPN
- `admin_email` — receives freshness-fail and send-error alerts

### 4. Install

```bash
cd notifier
pip install -e ".[dev]"
```

### 5. Run

```bash
# Dry run — renders HTML to out/preview/*.html (plant) and
# out/preview/regional/*.html (regional) without sending
python main.py --dry-run

# Live send — sends both plant-manager digests and regional-manager summaries
python main.py
```

Regional digests are skipped automatically (with a log message, not an
error) if `MachineWeekSummary.csv` predates the Qlik reload that added
`Regional_Manager_Email` — so the plant digests keep working during the
rollout window.

### 6. Tests

```bash
pytest tests/
```

---

## Deployment

### Option A — Windows Task Scheduler

1. Set environment variables machine-wide (or in the task's environment):
   ```
   setx AZURE_TENANT_ID "..."
   setx AZURE_CLIENT_ID "..."
   setx AZURE_CLIENT_SECRET "..."
   ```
2. Create a task in Task Scheduler:
   - **Trigger:** Weekly, Monday, 07:00 local time
   - **Action:** `python.exe C:\path\to\notifier\main.py --config C:\path\to\notifier\config.yaml`
   - **Settings:** Run whether user is logged on or not; retry up to 3 times at 15-minute intervals

### Option B — Azure Function (timer trigger)

1. Create a Function App (Python 3.11+, Consumption or Flex Consumption plan).
2. Add Application Settings for `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` (or use Key Vault references).
3. Wrap `main.main()` in a timer-triggered Azure Function:
   ```python
   # function_app.py
   import azure.functions as func
   import argparse, main

   app = func.FunctionApp()

   @app.timer_trigger(schedule="0 0 7 * * 1", arg_name="timer", run_on_startup=False)
   def weekly_digest(timer: func.TimerRequest) -> None:
       args = argparse.Namespace(dry_run=False, config="config.yaml")
       main.main(args)
   ```
4. Deploy: `func azure functionapp publish <APP_NAME>`

The schedule `0 0 7 * * 1` fires at 07:00 UTC Monday. Adjust for local timezone if needed.

---

## Freshness check

The notifier aborts and sends an admin alert if `MachineWeekSummary.csv` is older than `freshness_max_hours` (default 24h). This catches cases where the Qlik reload did not run or failed silently.

## v2 upgrade path

To replace Jinja2 templates with LLM-generated prose, swap `src/renderer.py` for an Azure OpenAI call. The `ManagerDigest` / `MachineSummary` dataclasses are the stable interface — the rendering layer is the only thing that changes.
