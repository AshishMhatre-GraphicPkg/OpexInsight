"""Send emails via Microsoft Graph API /sendMail endpoint."""

from __future__ import annotations

import logging
import time

import msal
import requests

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"]


def _get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" not in result:
        raise RuntimeError(f"MSAL token error: {result.get('error_description')}")
    return result["access_token"]


def _build_message(
    to_email: str,
    cc_list: str | None,
    subject: str,
    html_body: str,
    text_body: str,
) -> dict:
    cc_recipients = []
    if cc_list:
        for addr in cc_list.split(";"):
            addr = addr.strip()
            if addr:
                cc_recipients.append({"emailAddress": {"address": addr}})

    return {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
            "ccRecipients": cc_recipients,
        },
        "saveToSentItems": True,
    }


def _post_with_retry(url: str, headers: dict, payload: dict, max_attempts: int = 3) -> None:
    delay = 10
    for attempt in range(1, max_attempts + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 202:
            return
        log.warning("Send attempt %d/%d failed: %s %s", attempt, max_attempts, resp.status_code, resp.text)
        if attempt < max_attempts:
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Failed to send after {max_attempts} attempts. Last status: {resp.status_code}")


def send_mail(
    config: dict,
    env: dict,
    to_email: str,
    cc_list: str | None,
    subject: str,
    html_body: str,
    text_body: str,
) -> None:
    token = _get_token(env["AZURE_TENANT_ID"], env["AZURE_CLIENT_ID"], env["AZURE_CLIENT_SECRET"])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    sender = config["sender_upn"]
    url = f"{GRAPH_BASE}/users/{sender}/sendMail"
    payload = _build_message(to_email, cc_list, subject, html_body, text_body)
    _post_with_retry(url, headers, payload)
    log.info("Sent to %s", to_email)


def send_admin_alert(config: dict, env: dict, subject: str, html_body: str) -> None:
    """Send an alert to the admin recipient — best-effort, no retry escalation."""
    try:
        send_mail(
            config=config,
            env=env,
            to_email=config["admin_email"],
            cc_list=None,
            subject=subject,
            html_body=html_body,
            text_body=subject,
        )
    except Exception:
        log.exception("Could not send admin alert — check credentials and config")
