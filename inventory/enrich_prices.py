#!/usr/bin/env python3
"""Fill per-store price, stock & shelf location for Total Wine #2302 into the catalog.

This is Layer 2 — the PerimeterX-walled dynamic data the sitemaps don't carry.
A local `nodriver` Chrome (real Mac, real home IP — PerimeterX's easy case) sets
store #2302 once, then visits each wine's page and reads:
  - stock   from window.dtm_datalayer.productAvailability  ("..._Available" / "..._NotAvailable")
  - price   the first $NN.NN in the rendered buy-box (only trusted when available)
  - aisle   the "Aisle .. | Bay .. | Shelf .." line, when in stock at the store

Why a browser and not a plain HTTP fetch: price is hydrated client-side by a
micro-frontend — it is NOT in the static HTML, so curl/requests can't see it.
nodriver renders the page; we read the live DOM.

Caveat (verified by sampling): sitemap product codes are sometimes a size/vintage
SKU not stocked at #2302 (e.g. an Opus One 375ml shows "Not Available"). Those get
in_stock=False, price=None — honest; confirm at the shelf.

RUN AT HOME. Needs:  pip install -r inventory/requirements.txt
Degrades gracefully: anything unreadable stays null, and Layer 1 (the catalog) is
never touched — a PerimeterX change can't strand you, it just leaves prices to the
shelf tag. Sequential + polite, so a few hundred wines per run (~minutes).

Usage:
  python3 inventory/enrich_prices.py --sample 8                    # set store, read 8, PRINT, write nothing
  python3 inventory/enrich_prices.py --varietal cabernet --max 300  # enrich a taste subset, patch the JSONL
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "totalwine-centennial.jsonl"
STORE_URL = "https://www.totalwine.com/store-info/colorado/centennial/2302"
PRICE_RE = re.compile(r"\$\s?(\d{1,4}\.\d{2})")
PAGE_WAIT = 5  # seconds to let the product micro-frontend hydrate


def load_rows():
    return [json.loads(line) for line in INDEX.read_text().splitlines() if line.strip()]


def write_rows(rows):
    INDEX.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def select(rows, a):
    out = []
    for r in rows:
        if a.varietal and a.varietal.lower() not in (r["varietal"] or "").lower():
            continue
        if a.type and a.type.lower() not in (r["wine_type"] or "").lower():
            continue
        if a.region and a.region.lower() not in ((r["region"] or "").lower() + " " + r["slug"].lower()):
            continue
        if a.text and a.text.lower() not in (r["name"].lower() + " " + r["slug"].lower()):
            continue
        out.append(r)
    return out[: a.max]


def parse_stock(availability):
    al = (availability or "").lower()
    if "notavailable" in al:
        return False
    if "available" in al:
        return True
    return None


def parse_aisle(text):
    parts = []
    for pat in (r"Aisle\s+[^\n|]+", r"Bay\s+[^\n|]+", r"Shelf\s+[^\n|]+"):
        m = re.search(pat, text)
        if m:
            parts.append(m.group(0).strip())
    return ", ".join(parts) or None


def read_page(dtm_json, text):
    """Return (price, in_stock, aisle, note) from one product page's globals."""
    try:
        avail = json.loads(dtm_json).get("productAvailability", "") if dtm_json else ""
    except Exception:
        avail = ""
    in_stock = parse_stock(avail)
    if in_stock is None and "perimeterx" in (text or "").lower():
        return None, None, None, "BLOCKED"
    if in_stock is False:
        return None, False, None, "not-at-2302"
    m = PRICE_RE.search(text or "")
    price = float(m.group(1)) if m else None
    aisle = parse_aisle(text or "")
    note = "ok" if price is not None else ("available-no-price" if in_stock else "unknown")
    return price, in_stock, aisle, note


async def run(targets, sample):
    import nodriver as uc

    browser = await uc.start(headless=False)
    results = []
    try:
        page = await browser.get(STORE_URL)
        await page.sleep(6)  # set store #2302 + warm PerimeterX
        blocked_streak = 0
        for i, r in enumerate(targets, 1):
            try:
                page = await browser.get(r["url"])
                await page.sleep(PAGE_WAIT)
                dtm = await page.evaluate("JSON.stringify(window.dtm_datalayer||null)", await_promise=False)
                text = await page.evaluate("document.body.innerText", await_promise=False)
                price, stock, aisle, note = read_page(str(dtm), str(text))
            except Exception as e:
                price, stock, aisle, note = None, None, None, f"err:{e}"
            results.append((r, price, stock, aisle, note))
            blocked_streak = blocked_streak + 1 if note == "BLOCKED" else 0
            if sample:
                ptxt = f"${price:.2f}" if price is not None else "n/a"
                stk = "stk" if stock else ("oos" if stock is False else "?")
                print(f"[{i}/{len(targets)}] {ptxt:>8} {stk:>3} {note:<18} {r['name']}  // {aisle or ''}")
            if blocked_streak >= 5:
                print("5 blocks in a row — session stale; stopping. Re-run to re-warm.", file=sys.stderr)
                break
            await page.sleep(1.2)  # be polite
    finally:
        try:
            browser.stop()
        except Exception:
            pass
    return results


def main():
    ap = argparse.ArgumentParser(description="Enrich the catalog with #2302 price/stock/aisle.")
    ap.add_argument("--varietal")
    ap.add_argument("--type")
    ap.add_argument("--region")
    ap.add_argument("--text")
    ap.add_argument("--max", type=int, default=300, help="cap how many wines to enrich per run")
    ap.add_argument("--sample", type=int, default=0, help="read N, print findings, write nothing")
    a = ap.parse_args()

    if not INDEX.exists():
        raise SystemExit(f"no catalog at {INDEX} — run build_catalog.py first")
    rows = load_rows()
    if a.sample:
        a.max = a.sample
    targets = select(rows, a)
    if not targets:
        raise SystemExit("no wines matched the filters")
    print(f"opening Chrome, setting store #2302, reading {len(targets)} wines...", file=sys.stderr)

    results = asyncio.run(run(targets, a.sample))
    got = [(r, p, s, ai) for (r, p, s, ai, n) in results if p is not None or s is not None]

    if a.sample:
        priced = sum(1 for (r, p, s, ai, n) in results if p is not None)
        print(f"\n{priced}/{len(results)} priced, "
              f"{sum(1 for x in results if x[2])}/{len(results)} in stock (nothing written — sample mode)")
        return 0

    patch = {r["slug"]: (p, s, ai) for (r, p, s, ai) in got}
    from datetime import date
    today = date.today().isoformat()
    for r in rows:
        if r["slug"] in patch:
            r["price"], r["in_stock"], r["aisle"] = patch[r["slug"]]
            r["scraped_date"] = today
            r["source"] = "sitemap+pdp"
    write_rows(rows)
    priced = sum(1 for v in patch.values() if v[0] is not None)
    print(f"enriched {len(patch)}/{len(targets)} wines ({priced} priced, "
          f"{sum(1 for v in patch.values() if v[1])} in stock) -> {INDEX.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
