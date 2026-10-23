---
name: wine-inventory-refresh
description: Refresh the local Total Wine Centennial #2302 index of in-stock wines over $20, or troubleshoot a failed refresh. Run at home when the user asks to update the store index; never refresh during a store visit.
---

# Wine Inventory Refresh

Run the inventory scan at home when the user asks for a refresh or the index needs troubleshooting. At the store, use `wine-buying` and the existing local index. Do not browse or scrape live inventory while the user is shopping.

## Refresh

Locate the repository from the installed skill's `.local-config.json` (`repo_path`) or the current workspace. Run the existing wrapper:

```bash
bash inventory/refresh_inventory.sh
```

The scanner reconciles `inventory/totalwine-centennial.jsonl` and writes a concise change summary to `inventory/.store-changes.txt`. Report the new, removed, and changed counts. State separately whether the data scan succeeded and whether any commit/push step completed; do not imply a public inventory view was deployed.

For a non-mutating sample or a full scan without the wrapper, consult the repository's `inventory/SCHEMA.md` and `inventory/scan_store.py` options first. If the scan returns no parsed products or a captcha/site change, leave the existing index untouched and report the failure. Fix scanner behavior at home; never fall back to live agent research in the aisle.

## Troubleshooting

- Check `inventory/.store-changes.txt` and the refresh log for the first failure.
- A captcha requires a human in the visible browser; never automate bypassing it.
- If the site data shape changes, read `inventory/SCHEMA.md` before adjusting the scanner.
- If the scheduler did not run, inspect the local launchd job and its log, then rerun the installer only when needed.
