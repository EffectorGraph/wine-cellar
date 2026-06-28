---
name: wine-inventory-refresh
description: Refresh the local Total Wine Centennial #2302 in-stock inventory index (price, stock, shelf aisle for every in-stock wine over $20). Use this skill AT HOME (never at the store) when the user wants to update / rescan / rebuild the store stock list — e.g. "refresh my wine inventory", "rescan Total Wine", "update the store stock", "the inventory looks stale", or when the biweekly auto-refresh failed and needs a hand. It drives a local stealth browser to read the store's live listing data, reconciles it against the existing index (only real changes are written), and commits + pushes the update. Also the place to go for troubleshooting a failed scan. Do NOT use at the store (that's `wine-buying` querying the already-built index), and do NOT use for entering/reviewing/rating owned wines (that's `wine-cellar`).
---

# Wine Inventory Refresh (Total Wine #2302)

Rebuilds `inventory/totalwine-centennial.jsonl` — every **in-stock wine over $20** at
Total Wine Centennial #2302, with price, live stock count, and shelf aisle. **Run at
home only** (it drives a real browser past Total Wine's bot-wall — never do this at the
store; that blows the token budget and isn't needed, since the store just *queries* the
already-built index).

Find `<repo>`: `~/.claude/skills/wine-inventory-refresh/.local-config.json` → `repo_path`.

## How it works (one command)

The wrapper does pull → scan → commit/push and logs everything:

```bash
bash <repo>/inventory/refresh_inventory.sh
```

Or run the scanner directly (no commit) to eyeball first:

```bash
<repo>/inventory/.venv/bin/python <repo>/inventory/scan_store.py --sample 2   # read 2 pages, print, write nothing
<repo>/inventory/.venv/bin/python <repo>/inventory/scan_store.py              # full scan -> reconcile + write
```

A Chrome window opens, sets store #2302, and walks ~43 listing pages (~3 min). The scan
reads each page's `window.INITIAL_STATE.search.results.products` — no per-wine visits.

## What to report back

Read the reconcile summary (also saved to `inventory/.store-changes.txt`) and tell the
user in plain language:
- **`+N new`** — wines that just showed up over $20 in stock.
- **`-M gone`** — wines no longer stocked / dropped below nothing (delisted or sold out).
- **`~K changed`** — price moves and stock swings (a few examples are printed).

If the wrapper committed, say so (it pushes automatically). The index now has the fresh
numbers; the `wine-buying` skill queries it at the store via `query_inventory.py`.

## Incremental by design

A re-scan rewrites a row only when its value actually moved; unchanged rows stay
byte-identical, so `git diff` is a clean changelog. Running it twice back-to-back yields
`+0 -0 ~0` and no diff — that's expected, not a bug.

## Troubleshooting

| Symptom | What it means / fix |
|---|---|
| `EMPTY — no in-stock >$20 wines parsed` | A PerimeterX block or a site-shape change. The index is left untouched (safe). Re-run once; if it persists, a captcha may be showing — see next row. |
| A captcha / "press & hold" shows in the Chrome window | PerimeterX wants a human. Solve it once in the visible window, then let the scan continue. Keep the browser **non-headless**. A real home IP + real Chrome usually clears on its own. |
| `nodriver` error / Chrome won't launch | Install Google Chrome. Reinstall deps: `<repo>/inventory/.venv/bin/pip install -r <repo>/inventory/requirements.txt` (or recreate the venv with `uv venv <repo>/inventory/.venv`). |
| Prices look wrong / not Centennial | Confirm the store set: the page data layer should show `storeId:2302`. If Total Wine changed the store-set URL, update `STORE_URL` in `scan_store.py`. |
| `0 products` on every page / count way off | Total Wine changed the listing shape (the `INITIAL_STATE.search.results.products` path or the `pageSize=200` cap). Re-probe one listing page and adjust `scan_store.py`. This is a fix-at-home, never a fall-back-to-live-scraping-at-the-store. |
| Reconcile shows *everything* changed | `skuId` keying or sort drift — check the dedupe key and the stable sort in `scan_store.py`. |
| Scheduled (biweekly) run didn't happen | `launchctl list \| grep wine` to confirm it's loaded; read `<repo>/inventory/.refresh.log`. The Mac must have been **logged in** (the job needs a GUI session for Chrome). Reload: `bash <repo>/inventory/install_schedule.sh`. |

## Hard rule

Scanning happens **at home**. At the store, never scan — query the existing index. If the
index is stale and you're already at the store, recommend from it + general knowledge and
say it's stale; do **not** kick off a scan live.
