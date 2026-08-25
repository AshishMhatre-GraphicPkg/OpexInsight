# Template Archive

Snapshots of email templates kept for reference / rollback. Not loaded by
`renderer.py` under normal operation — Jinja's `FileSystemLoader` is rooted at
`notifier/templates/`, so anything under `archive/` is only reachable via an
explicit `archive/<file>` template name.

| File | Archived from | Commit | Notes |
|---|---|---|---|
| `manager_v1.html.j2` | `templates/email.html.j2` | `0f13ea5` | Pre-redesign plant-manager digest: 3 KPI tiles, movers table, maintenance table, per-machine card with lever bullets, findings block, PM table. |
| `manager_v1.txt.j2` | `templates/email.txt.j2` | `0f13ea5` | Plain-text mirror of the above. |
| `regional_v1.html.j2` | `templates/regional.html.j2` | `0f13ea5` | Regional-manager synopsis — unchanged by the manager V2 redesign, archived for when the same redesign is applied to it later. |
| `regional_v1.txt.j2` | `templates/regional.txt.j2` | `0f13ea5` | Plain-text mirror of the above. |
| `manager_v2.html.j2` | `templates/email.html.j2` | `644cee8` | Pre-three-factor plant-manager digest: 3-column Machine/Why/How-to-Fix focus card with a single-sentence action in Card 3. Archived ahead of the "Likely Causes and Recommended Actions" redesign (up to 3 Factor/Action pairs, stacked card layout). |
| `manager_v2.txt.j2` | `templates/email.txt.j2` | `644cee8` | Plain-text mirror of the above. |

## Restoring V1

The manager digest renderer reads `templates/email.html.j2` and
`templates/email.txt.j2` directly (`src/renderer.py:76,81`). To roll back to V1:

```bash
cp templates/archive/manager_v1.html.j2 templates/email.html.j2
cp templates/archive/manager_v1.txt.j2 templates/email.txt.j2
```

## Restoring V2 (pre three-factor redesign)

```bash
cp templates/archive/manager_v2.html.j2 templates/email.html.j2
cp templates/archive/manager_v2.txt.j2 templates/email.txt.j2
```

Regional templates were never modified by the V2 work, so no restore is needed
for those unless a future regional redesign needs the same treatment.
