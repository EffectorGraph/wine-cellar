# Wine Cellar — repo guide for Claude

Two skills: `wine-cellar` (own / review / drink) and `wine-buying` (shop). Data = JSONL + git. See README.md.

## STORE SESSIONS = TIGHT (hard token-budget rule)

At the store the user is on a phone with a hard token cap. Blow the budget → they buy nothing (this has happened — came home empty-handed). NON-NEGOTIABLE when shopping live:

- **NO live web scraping/research.** None.
- **NO subagent fan-out.** No spawning agents. Never agents that can spawn agents.
- **NO photo-by-photo upload marathons** as the primary path — too slow on store wifi.
- **DO:** query the local index with `query_inventory.py` (it prints only matches — never read the raw JSONL into context), cross-ref `cellar.jsonl` + `preferences.json`, match to taste, recommend. Done.
  - e.g. `python3 inventory/query_inventory.py --varietal cabernet --region napa --max-price 60 --limit 10`
- If the index is missing/stale: recommend from the cellar + general knowledge, say it's unverified, and **still do not scrape live.**

## Inventory index — built at HOME, never at the store

Total Wine store #2302 (9505 E County Line Rd, Centennial). One live index, refreshed at home:

- **`inventory/totalwine-centennial.jsonl`** — every **in-stock wine over $20 at #2302** (~3.6k rows: name, brand, varietal, wine_type, price, live stock count, size, shelf `location`/bay, url, skuId). This is the store index `query_inventory.py` reads at the store.
- **`inventory/scan_store.py`** — builds/refreshes it. A local `nodriver` Chrome sets store #2302, clears **PerimeterX** (HUMAN), and walks the wine listing `/wine/c/c0020?pageSize=200` (~43 pages, ~3 min), reading each page's server-rendered `window.INITIAL_STATE.search.results.products` — clean JSON with price + stock + aisle per wine, no per-product visits. Filters to in-stock + price>20. **Incremental reconcile**: only rows whose value moved are rewritten, delisted/sold-out wines drop, new arrivals add; unchanged rows stay byte-identical so `git diff` is a changelog. Prints only the `+N -M ~K` summary (also `.store-changes.txt`). `--sample N` reads N pages and prints without writing. Needs `pip install -r inventory/requirements.txt`.
  - **Why the listing JSON, not static fetch:** totalwine.com listing/product pages sit behind PerimeterX and 403 every static fetch; price/stock are JS-hydrated. nodriver renders the real page (real Mac + home IP = the easy case) and reads `INITIAL_STATE`. pageSize caps at 200.
- **Refresh = the `wine-inventory-refresh` skill** (or `bash inventory/refresh_inventory.sh`): pull → scan → commit/push the diff. A **biweekly launchd job** (`inventory/install_schedule.sh`, run once to activate) does it unattended. Troubleshooting lives in that skill.
- If the scan breaks (site shape changed), fix `scan_store.py` **at home** — never fall back to live agent research in the aisle.

## Token discipline generally

- Deterministic scripts > LLM web research. Scrape to disk, read summaries.
- Never spawn agents that can spawn agents.
