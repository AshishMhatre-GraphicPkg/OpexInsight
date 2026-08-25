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

## Digest acknowledgement loop (feedback)

A Yes/No button pair at the bottom of each digest lets a manager confirm
they'll act on the week's insights, or mark it not relevant — with an
optional comment. It reuses the Azure AD app's existing `Sites.Read.All`
permission; no new Azure permission, hosting, or licence is required. The
receiver is a Microsoft **group Form** on the same SharePoint site; nothing
in this repo can accept an inbound HTTP request, so the buttons link out to
a page the tenant already hosts.

### 1. Create the Form

1. In [forms.office.com](https://forms.office.com), create a **group form**
   owned by the group behind the SharePoint site used above — **not** a
   personal form. A personal form's results workbook lands in the creator's
   OneDrive, which the notifier's `Sites.Read.All` cannot read.
2. Add three questions, in this order:
   - **Choice**, required — *"Will your plant action these insights this
     week?"* Options exactly:
     - `Yes - we will action this`
     - `No - not relevant this week`
   - **Text**, optional — *"Anything we should know? (optional)"* — Forms
     trims the `(optional)` suffix off the question title before it becomes
     an Excel column header, so `config.yaml`'s `col_comment` should be just
     `"Anything we should know?"` (confirmed against a real synced workbook).
   - **Text**, required — *"Reference (Do not edit)"* — this receives the
     hidden token that identifies the digest; the button URL fills it in
     automatically. Whatever capitalization you use becomes the literal
     Excel column header, so `config.yaml`'s `col_token` must match exactly.
3. Under **Settings**, set responses to **people in your organization** and
   turn on **record name**. This cross-checks the token against the actual
   signed-in responder, so a forwarded email can't spoof someone else's
   acknowledgement. If the sign-in wall hurts response rates, relax this —
   the token still identifies who the digest was addressed to. Note: the
   synced Excel workbook does **not** carry a submitted-by or timestamp
   column regardless of this setting — only the three question-answer
   columns are exported (confirmed against a real synced workbook, table
   name `"Response"`).
4. **Collect responses → Get a link to collect responses → Get pre-filled
   link**. Answer the Choice and Reference questions with placeholder text,
   copy the generated URL, and read off the `r<id>=` parameter names — one
   for the Choice question, one for the Reference question. Those go into
   `config.yaml`'s `feedback.param_answer` / `feedback.param_token`. Note
   the Choice answer's value in that URL is wrapped in literal `%22...%22`
   (URL-encoded double quotes) — that's Forms' pre-fill format for Choice
   questions, and `build_ack_links()` reproduces it automatically; you don't
   need to add the quotes yourself in `config.yaml`'s `answer_yes`/`answer_no`.
5. Open the form's **Responses → Open in Excel** to create the syncing
   results workbook in the site's document library. Note its path.

### 2. Configure `config.yaml`

```yaml
feedback:
  enabled: true
  form_url: "https://forms.office.com/Pages/ResponsePage.aspx?id=<FORM_ID>"
  param_answer: "r<id-of-choice-question>"
  param_token: "r<id-of-reference-question>"
  answer_yes: "Yes - we will action this"   # must match the Form's Choice option text exactly
  answer_no: "No - not relevant this week"  # must match the Form's Choice option text exactly
  yes_button_label: "Yes"   # the button TEXT in the email — independent of answer_yes above
  no_button_label: "No"
  responses_path: "Master Data/Control Room/Qlikcloud Lookups/OPEXinsights/InsightEngineAcknowledgement.xlsx"
  col_token: "Reference (Do not edit)"      # exact capitalization used in the question title
  col_answer: "Will your plant action these insights this week?"
  col_comment: "Anything we should know?"   # no "(optional)" — Forms trims it
```

`col_token` / `col_answer` / `col_comment` / `col_submitted` must match the
actual Excel column headers exactly (Forms names them after the question
text, with the caveats above) — if you word the questions differently,
override these. `col_submitted` will typically not exist in the sheet at
all (see the note in step 3 above); that's fine, `load_responses()` treats
it as optional.

Leave `feedback.enabled: false` (the default) until the form exists and
these fields are filled in — with it disabled, the buttons and the "last
week" recall line are both omitted from every digest.

### 3. How it works

- Each button URL encodes a plain-text, human-readable token —
  `<plant>|<department>|<period_start>|<manager label>`, e.g.
  `Elk Grove|Gluer|2026-04-20|Manager A` — so a click can be traced back to
  the exact digest and week it came from just by reading the "Reference"
  column in the results workbook. Regional digests use the constant
  placeholders `Region|All Plants` in place of a single plant/department.
  The "manager label" is **derived from the email** (`manager.a@company.com`
  → `Manager A`), not a real name pulled from `PlantManagers.xlsx` — see
  `notifier/CLAUDE.md` § Acknowledgement loop if you want to wire in the
  real `Manager_Name` later.
- Button text is just **"Yes" / "No"** (`feedback.yes_button_label` /
  `no_button_label`) — independent of `answer_yes` / `answer_no`, which
  must match the Form's Choice option text exactly.
- The notifier reads the Form's results workbook each run (same
  `Sites.Read.All` GET pattern as `Findings.csv` / `PMComplianceDump.xlsx`)
  and shows each manager whether they acknowledged **last week's** digest,
  right above this week's buttons.
- A fetch failure here is non-fatal: digests still send, just without the
  recall line, and one admin alert fires (`src/feedback.py`,
  `main.py`).
- **The workbook's stored bytes only update when someone opens the file**
  (confirmed empirically: a real form submission did not appear via the
  Graph API download until the workbook was opened in Excel Online, at
  which point it synced and the notifier picked it up on the next fetch).
  In practice this means a Monday-morning run could occasionally read a
  slightly stale snapshot if nobody has opened the workbook recently — the
  loop still works, it just isn't guaranteed instant. If this turns out to
  matter, consider a small scheduled task that opens/saves the workbook
  ahead of the weekly send, or querying the Forms API directly instead of
  the Excel sync.

## Freshness check

The notifier aborts and sends an admin alert if `MachineWeekSummary.csv` is older than `freshness_max_hours` (default 24h). This catches cases where the Qlik reload did not run or failed silently.

## v2 upgrade path

To replace Jinja2 templates with LLM-generated prose, swap `src/renderer.py` for an Azure OpenAI call. The `ManagerDigest` / `MachineSummary` dataclasses are the stable interface — the rendering layer is the only thing that changes.
