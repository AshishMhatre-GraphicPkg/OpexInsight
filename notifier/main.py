"""Entry point for the weekly OEE Insight email notifier.

Usage:
    python main.py              # send emails via Graph API
    python main.py --dry-run    # write rendered HTML to out/preview/ instead of sending
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import traceback
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from src import logging_setup
from src.fetch import fetch_csv
from src.freshness import StaleDataError, assert_fresh
from src.grouper import group_by_manager
from src.mailer import send_admin_alert, send_mail
from src.renderer import render_admin_alert, render_html, render_text

log = logging.getLogger(__name__)


def _load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _load_env() -> dict:
    load_dotenv()
    required = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return {k: os.environ[k] for k in required}


def _write_preview(manager_email: str, html: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = manager_email.replace("@", "_at_").replace("/", "_")
    dest = out_dir / f"{safe_name}.html"
    dest.write_text(html, encoding="utf-8")
    log.info("Preview written: %s", dest)


def main(args: argparse.Namespace) -> int:
    logging_setup.configure()
    config = _load_config(args.config)
    env = _load_env()

    try:
        csv_bytes, mtime = fetch_csv(config, env)
    except Exception as exc:
        details = traceback.format_exc()
        log.error("Failed to fetch CSV: %s", exc)
        alert_html = render_admin_alert("Fetch failure", details)
        send_admin_alert(config, env, "Insight Notifier — CSV fetch failure", alert_html)
        return 1

    try:
        assert_fresh(mtime, config.get("freshness_max_hours", 24))
    except StaleDataError as exc:
        log.error("%s", exc)
        alert_html = render_admin_alert("Stale data", str(exc))
        send_admin_alert(config, env, "Insight Notifier — stale MachineWeekSummary.csv", alert_html)
        return 1

    df = pd.read_csv(io.BytesIO(csv_bytes))
    digests = group_by_manager(df)

    if not digests:
        log.warning("No manager digests to send — MachineWeekSummary.csv may be empty")
        return 0

    period_start = digests[0].period_start
    subject = f"{config.get('email_subject_prefix', 'Weekly OEE Insight')} — {period_start}"

    errors: list[str] = []
    for digest in digests:
        html = render_html(digest, subject)
        text = render_text(digest, subject)
        if args.dry_run:
            _write_preview(digest.manager_email, html, Path("out/preview"))
        else:
            try:
                send_mail(
                    config=config,
                    env=env,
                    to_email=digest.manager_email,
                    cc_list=digest.cc_list,
                    subject=subject,
                    html_body=html,
                    text_body=text,
                )
            except Exception as exc:
                log.error("Failed to send to %s: %s", digest.manager_email, exc)
                errors.append(f"{digest.manager_email}: {exc}")

    if errors:
        details = "\n".join(errors)
        alert_html = render_admin_alert("Send failure", details)
        send_admin_alert(config, env, "Insight Notifier — some emails failed to send", alert_html)
        return 1

    log.info(
        "Done — %d digests %s",
        len(digests),
        "previewed" if args.dry_run else "sent",
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly OEE Insight email notifier")
    parser.add_argument("--dry-run", action="store_true", help="Write HTML to out/preview/ instead of sending")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    sys.exit(main(parser.parse_args()))
