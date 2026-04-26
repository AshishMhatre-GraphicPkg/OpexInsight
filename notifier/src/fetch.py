"""Pull MachineWeekSummary.csv from SharePoint via Microsoft Graph API."""

import logging
from datetime import datetime, timezone

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


def fetch_csv(config: dict, env: dict) -> tuple[bytes, datetime]:
    """Return (csv_bytes, last_modified_utc) for MachineWeekSummary.csv."""
    token = _get_token(
        env["AZURE_TENANT_ID"], env["AZURE_CLIENT_ID"], env["AZURE_CLIENT_SECRET"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    site_id = config["sharepoint_site_id"]
    file_path = config["sharepoint_file_path"]

    # Resolve item metadata (for lastModifiedDateTime)
    meta_url = f"{GRAPH_BASE}/sites/{site_id}/drive/root:/{file_path}"
    meta = requests.get(meta_url, headers=headers, timeout=30)
    meta.raise_for_status()
    meta_json = meta.json()
    mtime_str = meta_json["lastModifiedDateTime"]  # ISO 8601 UTC
    mtime = datetime.fromisoformat(mtime_str.replace("Z", "+00:00"))

    # Download content
    download_url = meta_json["@microsoft.graph.downloadUrl"]
    content = requests.get(download_url, timeout=60)
    content.raise_for_status()

    log.info("Fetched %s bytes from SharePoint (mtime %s)", len(content.content), mtime)
    return content.content, mtime
