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

Total Wine store #2302 (9505 E County Line Rd, Centennial). Two decoupled layers, both run at home:

- **`inventory/build_catalog.py`** — the catalog. Parses Total Wine's **public XML sitemaps** (`sitemap.xml` → `Product-en-USD-*.xml`), which are NOT bot-walled, into `inventory/totalwine-centennial.jsonl` (~19k distinct wines: name, varietal, wine_type, region best-effort, product_code, url). Refresh ~monthly. Prints only a summary + 25-row sample + coverage report; writes `.catalog-sample.txt`. Never dumps the catalog.
  - **Why sitemaps, not page scraping:** totalwine.com listing/product pages sit behind **PerimeterX** (HUMAN) and 403 every static fetch — a JS challenge no header-spoofing beats. The sitemaps sidestep it entirely. Vintage & price are NOT in the sitemap (they live per-SKU); vintage is read off the bottle at the shelf.
- **`inventory/enrich_prices.py`** — optional. Fills per-store **price, stock & shelf aisle** for #2302 (the PerimeterX-walled data). A local `nodriver` Chrome sets the store, clears PerimeterX, then reads each wine's page: stock from `dtm_datalayer.productAvailability`, price from the rendered buy-box, aisle/bay/shelf when in stock. (Price is JS-hydrated → a plain HTTP client can't see it, so it renders pages in a real browser; slow-ish, run on a taste-matched subset.) Sitemap codes are sometimes a non-stocked size → those read `in_stock:false`, price null (confirm at shelf). Degrades to null on block; the catalog still stands. Needs `pip install -r inventory/requirements.txt`.
- **`inventory/query_inventory.py`** — the store-time tool (above). Token-tight: prints only matches.
- If a parse breaks (sitemap shape changed), fix it **at home** — never fall back to live agent research in the aisle.

## Token discipline generally

- Deterministic scripts > LLM web research. Scrape to disk, read summaries.
- Never spawn agents that can spawn agents.
