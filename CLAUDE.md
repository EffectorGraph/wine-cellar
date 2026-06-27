# Wine Cellar — repo guide for Claude

Two skills: `wine-cellar` (own / review / drink) and `wine-buying` (shop). Data = JSONL + git. See README.md.

## STORE SESSIONS = TIGHT (hard token-budget rule)

At the store the user is on a phone with a hard token cap. Blow the budget → they buy nothing (this has happened — came home empty-handed). NON-NEGOTIABLE when shopping live:

- **NO live web scraping/research.** None.
- **NO subagent fan-out.** No spawning agents. Never agents that can spawn agents.
- **NO photo-by-photo upload marathons** as the primary path — too slow on store wifi.
- **DO:** read the local index (`inventory/totalwine-centennial.jsonl`) + `cellar.jsonl` + `preferences.json`, match to taste, recommend. Done.
- If the index is missing/stale: recommend from the cellar + general knowledge, say it's unverified, and **still do not scrape live.**

## Inventory index — built at HOME, never at the store

- `inventory/totalwine-centennial.jsonl` — scraped Total Wine store #2302 (9505 E County Line Rd, Centennial). One product per line: name, varietal/region, vintage, price, url, in-stock.
- Stock rotates slowly → refresh ~monthly: `python3 inventory/scrape_totalwine.py`.
- The scraper writes to disk and prints **only a summary** (counts). Never dump the full catalog into context.
- totalwine.com 403s naive fetchers; the scraper uses browser-like headers. If it breaks, fix it **at home** — never fall back to live agent research in the aisle.

## Token discipline generally

- Deterministic scripts > LLM web research. Scrape to disk, read summaries.
- Never spawn agents that can spawn agents.
