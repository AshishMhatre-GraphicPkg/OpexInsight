"""List all document libraries on the SharePoint site to find the correct list ID."""

import os
import yaml
import msal
import requests
from dotenv import load_dotenv

load_dotenv()
with open("config.yaml") as f:
    config = yaml.safe_load(f)

env = {k: os.environ[k] for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")}

app = msal.ConfidentialClientApplication(
    env["AZURE_CLIENT_ID"],
    authority=f"https://login.microsoftonline.com/{env['AZURE_TENANT_ID']}",
    client_credential=env["AZURE_CLIENT_SECRET"],
)
result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
if "access_token" not in result:
    raise RuntimeError(result.get("error_description"))

token = result["access_token"]
headers = {"Authorization": f"Bearer {token}"}
site_id = config["sharepoint_site_id"]

print(f"\nSite: {site_id}\n")

# List all document libraries
url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists?$select=id,name,displayName,webUrl&$filter=list/template eq 'documentLibrary'"
resp = requests.get(url, headers=headers, timeout=30)
print(f"GET /lists (documentLibrary) → {resp.status_code}")

if resp.ok:
    items = resp.json().get("value", [])
    print(f"Found {len(items)} document libraries:\n")
    for item in items:
        print(f"  id          : {item.get('id')}")
        print(f"  name        : {item.get('name')}")
        print(f"  displayName : {item.get('displayName')}")
        print(f"  webUrl      : {item.get('webUrl')}")
        print()
else:
    print(resp.text)

# Also try drives endpoint for comparison
print("\n--- /drives ---")
drives_resp = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives?$select=id,name,webUrl",
    headers=headers, timeout=30
)
print(f"GET /drives → {drives_resp.status_code}")
drives = drives_resp.json().get("value", [])
print(f"Found {len(drives)} drives:")
for d in drives:
    print(f"  id: {d.get('id')}  name: {d.get('name')}  url: {d.get('webUrl')}")
