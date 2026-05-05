"""Fetch real SharePoint data and render per-manager email previews to disk.

No mail is sent. Requires Sites.Read.All but NOT Mail.Send.

Usage:
    python test_without_mail.py [--config config.yaml] [--out out/test_preview] [--ignore-freshness]
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from src import logging_setup
from src.fetch import fetch_csv, fetch_findings_csv, fetch_pm_xlsx
from src.findings import load_findings
from src.pm_compliance import load_pm_compliance
from src.freshness import StaleDataError, assert_fresh
from src.grouper import group_by_manager
from src.renderer import render_html, render_text

log = logging.getLogger(__name__)


def _load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _load_env() -> dict:
    load_dotenv()
    required = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return {k: os.environ[k] for k in required}


def _safe_name(email: str) -> str:
    return email.replace("@", "_at_").replace("/", "_").replace("\\", "_")


def _write_previews(digests, subject: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for digest in digests:
        html = render_html(digest, subject)
        text = render_text(digest, subject)
        base = out_dir / _safe_name(digest.manager_email)
        base.with_suffix(".html").write_text(html, encoding="utf-8")
        base.with_suffix(".txt").write_text(text, encoding="utf-8")
        log.info("Written: %s.{html,txt}", base)


def _write_index(digests, subject: str, out_dir: Path) -> None:
    rows = []
    for digest in digests:
        safe = _safe_name(digest.manager_email)
        total = sum(m.total_sheet_impact for m in digest.machines)
        findings_count = sum(
            (m.findings.total_open if m.findings else 0) for m in digest.machines
        )
        pm_count = sum(
            (m.pm_summary.total_overdue if m.pm_summary else 0) for m in digest.machines
        )
        rows.append(
            f'<tr>'
            f'<td><a href="{safe}.html">{digest.manager_email}</a></td>'
            f'<td style="text-align:right">{len(digest.machines)}</td>'
            f'<td style="text-align:right">{total:,.0f}</td>'
            f'<td style="text-align:right">{findings_count}</td>'
            f'<td style="text-align:right">{pm_count}</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Preview index — {subject}</title>
  <style>
    body {{ font-family: sans-serif; padding: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 700px; }}
    th, td {{ border: 1px solid #ccc; padding: 0.5rem 1rem; text-align: left; }}
    th {{ background: #f0f0f0; }}
    a {{ color: #1a73e8; }}
  </style>
</head>
<body>
  <h2>Email preview index</h2>
  <p><strong>Subject:</strong> {subject}</p>
  <table>
    <thead>
      <tr>
        <th>Manager</th>
        <th>Machines</th>
        <th>Total Sheet Impact</th>
        <th>Open Findings</th>
        <th>Overdue PMs</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
</body>
</html>"""
    index_path = out_dir / "_index.html"
    index_path.write_text(html, encoding="utf-8")
    log.info("Index written: %s", index_path)


def main(args: argparse.Namespace) -> int:
    logging_setup.configure()
    config = _load_config(args.config)
    env = _load_env()

    # --- Fetch MachineWeekSummary.csv ---
    log.info("Fetching MachineWeekSummary.csv …")
    csv_bytes, mtime = fetch_csv(config, env)
    log.info("Fetched %d bytes, mtime=%s", len(csv_bytes), mtime)

    # --- Freshness check (skippable) ---
    if args.ignore_freshness:
        log.warning("Freshness check skipped (--ignore-freshness)")
    else:
        try:
            assert_fresh(mtime, config.get("freshness_max_hours", 24))
            log.info("Freshness OK")
        except StaleDataError as exc:
            log.error("Stale data: %s", exc)
            log.error("Rerun with --ignore-freshness to skip this check.")
            return 1

    # --- Fetch Findings.csv (non-fatal) ---
    findings_df = None
    if config.get("sharepoint_findings_path"):
        log.info("Fetching Findings.csv …")
        try:
            findings_bytes = fetch_findings_csv(config, env)
            findings_df = load_findings(findings_bytes)
            log.info("Findings loaded: %d rows", len(findings_df))
        except Exception as exc:
            log.warning("Findings fetch failed — digest will render without findings block: %s", exc)
    else:
        log.info("sharepoint_findings_path not configured — skipping findings")

    # --- Fetch PMComplianceDump.xlsx (non-fatal) ---
    pm_df = None
    if config.get("sharepoint_pm_path"):
        log.info("Fetching PMComplianceDump.xlsx …")
        try:
            pm_bytes = fetch_pm_xlsx(config, env)
            pm_df = load_pm_compliance(pm_bytes)
            log.info("PM compliance loaded: %d rows", len(pm_df))
        except Exception as exc:
            log.warning("PM compliance fetch failed — digest will render without PM block: %s", exc)
    else:
        log.info("sharepoint_pm_path not configured — skipping PM compliance")

    # --- Group and render ---
    df = pd.read_csv(io.BytesIO(csv_bytes))

    # Quick diagnostic: show Manager_Email column status
    email_col = df.get("Manager_Email") if "Manager_Email" in df.columns else None
    if email_col is None:
        log.error("CSV has no Manager_Email column. Columns: %s", list(df.columns))
    else:
        null_count = email_col.isna().sum()
        log.info("Manager_Email: %d rows, %d null. Unique values: %s",
                 len(df), null_count, email_col.dropna().unique().tolist())
        if "Plant" in df.columns:
            log.info("Plants in CSV: %s", df["Plant"].unique().tolist())

    if findings_df is not None:
        f_plants = sorted(str(v) for v in findings_df["plant"].dropna().unique())
        f_wcids = sorted(str(v) for v in findings_df["wc_object_id"].dropna().unique())
        log.info("Findings plants (unique): %s", f_plants[:20])
        log.info("Findings WC IDs (sample): %s", f_wcids[:20])
    if "WC Object ID" in df.columns:
        log.info("Summary WC Object IDs: %s", df["WC Object ID"].astype(str).unique().tolist())

    digests = group_by_manager(df, findings_df=findings_df, pm_df=pm_df)

    if not digests:
        log.warning("No manager digests — MachineWeekSummary.csv may be empty")
        return 0

    total_machines_count = sum(len(d.machines) for d in digests)
    attached_findings = sum(1 for d in digests for m in d.machines if m.findings is not None)
    attached_pm = sum(1 for d in digests for m in d.machines if m.pm_summary is not None)
    log.info("Findings attached: %d / %d machines", attached_findings, total_machines_count)
    log.info("PM blocks attached: %d / %d machines", attached_pm, total_machines_count)

    period_start = digests[0].period_start
    subject = f"{config.get('email_subject_prefix', 'Weekly OEE Insight')} — {period_start}"

    out_dir = Path(args.out)
    _write_previews(digests, subject, out_dir)
    _write_index(digests, subject, out_dir)

    total_machines = sum(len(d.machines) for d in digests)
    findings_rows = len(findings_df) if findings_df is not None else 0
    print(
        f"\nDone — {len(digests)} manager(s), {total_machines} machine(s), "
        f"findings rows={findings_rows}\n"
        f"Open: {out_dir.resolve() / '_index.html'}"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render OEE Insight email previews without sending")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default="out/test_preview")
    parser.add_argument("--ignore-freshness", action="store_true")
    sys.exit(main(parser.parse_args()))
