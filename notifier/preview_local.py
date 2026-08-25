"""Render plant-manager + regional-manager email previews from a local CSV.

Fully offline — no SharePoint, no Graph API, no .env required. Reuses the
same grouping/rendering code the live notifier uses, so what you see here
is exactly what main.py would send.

Usage:
    # Zero setup — renders the bundled test fixture (4 plant managers, 2 regional managers)
    python preview_local.py

    # Preview a real MachineWeekSummary.csv you've downloaded from SharePoint
    python preview_local.py --csv "C:\\path\\to\\MachineWeekSummary.csv"

    # Include the Maintenance Report block (Findings.csv / PMComplianceDump.xlsx)
    python preview_local.py --csv MachineWeekSummary.csv --findings Findings.csv --pm PMComplianceDump.xlsx

Output goes to out/preview/local/ (plant digests) and
out/preview/local/regional/ (regional digests), with an _index.html linking
both. Open that in a browser.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

from src import logging_setup
from src.findings import load_findings
from src.grouper import group_by_manager
from src.pm_compliance import load_pm_compliance
from src.regional import group_by_regional_manager
from test_without_mail import _write_index, _write_previews, _write_regional_previews

DEFAULT_CSV = Path(__file__).parent / "tests" / "fixtures" / "sample_summary.csv"


def main(args: argparse.Namespace) -> int:
    logging_setup.configure()

    df = pd.read_csv(args.csv)

    findings_df = load_findings(Path(args.findings).read_bytes()) if args.findings else None
    pm_df = load_pm_compliance(Path(args.pm).read_bytes()) if args.pm else None

    # Offline preview: build ack links from config alone (no Forms responses
    # fetch — there's no SharePoint access here), so the buttons render but
    # last week's recall line never does.
    feedback_cfg = None
    if args.config:
        try:
            with open(args.config) as f:
                feedback_cfg = yaml.safe_load(f).get("feedback")
        except FileNotFoundError:
            pass

    digests = group_by_manager(df, findings_df=findings_df, pm_df=pm_df, feedback_cfg=feedback_cfg)
    regional_digests = group_by_regional_manager(
        df, findings_df=findings_df, pm_df=pm_df, top_n=args.top_n, feedback_cfg=feedback_cfg
    )

    if not digests and not regional_digests:
        print("No digests produced — check Manager_Email / Regional_Manager_Email are populated in the CSV.")
        return 1

    period_start = digests[0].period_start if digests else regional_digests[0].period_start
    subject = f"Weekly OEE Insight Digest — {period_start}"
    regional_subject = f"Regional OEE Summary — {period_start}"

    out_dir = Path(args.out)
    _write_previews(digests, subject, out_dir)
    _write_regional_previews(regional_digests, regional_subject, out_dir / "regional")
    _write_index(digests, regional_digests, subject, regional_subject, out_dir)

    print(f"\n{len(digests)} plant digest(s), {len(regional_digests)} regional digest(s) rendered.")
    print(f"Open: {(out_dir / '_index.html').resolve()}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render plant + regional email previews offline, no network calls")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to MachineWeekSummary.csv (defaults to the bundled test fixture)")
    parser.add_argument("--findings", default=None, help="Optional path to Findings.csv")
    parser.add_argument("--pm", default=None, help="Optional path to PMComplianceDump.xlsx")
    parser.add_argument("--out", default="out/preview/local")
    parser.add_argument("--top-n", type=int, default=3, dest="top_n", help="Machines shown per department in regional digests")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml, read only for the feedback: block (offline — no SharePoint calls)")
    sys.exit(main(parser.parse_args()))
