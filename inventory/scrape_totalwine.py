#!/usr/bin/env python3
"""Index the Total Wine & More Centennial CO catalog into a local JSONL file.

RUN AT HOME, NOT AT THE STORE. Stock rotates slowly — refresh ~monthly.
Writes inventory/totalwine-centennial.jsonl and prints ONLY a summary, so it
costs the agent almost no tokens to run (the whole point — see repo CLAUDE.md).

Store: #2302, 9505 E County Line Rd, Centennial CO 80112.

totalwine.com 403s naive fetchers, so we use a browser-like session and pin the
store via cookie. If the catalog comes back empty on the FIRST run, the parse
target needs confirming: a raw sample of the first response is saved to
inventory/.sample.html — open it, find where the product list JSON lives, and
adjust parse_products() accordingly. Do this fix at home; never live in-store.

Usage:
  python3 inventory/scrape_totalwine.py            # full crawl
  python3 inventory/scrape_totalwine.py --sample   # fetch 1 page, save sample, exit
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

STORE_ID = "2302"
OUT = Path(__file__).parent / "totalwine-centennial.jsonl"
SAMPLE = Path(__file__).parent / ".sample.html"
BASE = "https://www.totalwine.com"

# Category codes confirmed from totalwine.com URLs. Add more to widen the index;
# "all wine" via the broad red/white roots keeps it whole-store.
CATEGORIES = {
    "bordeaux": "/wine/france/bordeaux/c/000303",
    "pauillac": "/wine/france/bordeaux/pauillac/c/000690",
    "st-julien": "/wine/france/bordeaux/saint-julien/c/000691",
    "st-estephe": "/wine/france/bordeaux/saint-estephe/c/000689",
    "margaux": "/wine/france/bordeaux/margaux/c/000692",
    "haut-medoc": "/wine/france/bordeaux/haut-medoc/c/000648",
    "pessac-leognan": "/wine/france/bordeaux/pessac-leognan/c/000542",
    "us-cabernet": "/wine/red-wine/cabernet-sauvignon/c/000009",
    "bordeaux-blend": "/wine/red-wine/bordeaux-blend/c/000058",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cookie": f"storeId={STORE_ID}; market={STORE_ID}",
}


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse_products(html):
    """Extract products from a listing page.

    Total Wine embeds listing data as JSON in the page. We look for product
    objects with name + price. CONFIRM/adjust this on the first home run by
    inspecting inventory/.sample.html — the exact key names may differ.
    """
    out = []
    # Heuristic: find JSON objects that look like products.
    for m in re.finditer(r'\{"[^{}]*?"(?:name|productName)"\s*:\s*"([^"]+)"[^{}]*\}', html):
        blob = m.group(0)
        name = m.group(1)
        price = None
        pm = re.search(r'"(?:price|listPrice|salePrice)"\s*:\s*"?(\d+\.?\d*)', blob)
        if pm:
            price = float(pm.group(1))
        url = None
        um = re.search(r'"(?:url|productUrl|seoUrl)"\s*:\s*"([^"]+)"', blob)
        if um:
            url = um.group(1)
        out.append({"name": name, "price": price, "url": url})
    return out


def main():
    sample_only = "--sample" in sys.argv
    seen = {}
    for cat, path in CATEGORIES.items():
        page = 0
        while True:
            url = f"{BASE}{path}?pageSize=200&page={page}"
            try:
                html = fetch(url)
            except Exception as e:
                print(f"  {cat} p{page}: fetch failed ({e})", file=sys.stderr)
                break
            if sample_only:
                SAMPLE.write_text(html, encoding="utf-8")
                print(f"saved sample ({len(html)} bytes) to {SAMPLE} — inspect, then fix parse_products()")
                return 0
            prods = parse_products(html)
            if not prods:
                break
            for p in prods:
                p["category"] = cat
                p["store_id"] = STORE_ID
                seen[(p["name"], p.get("url"))] = p
            page += 1
            time.sleep(1.0)  # be polite
    rows = list(seen.values())
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"indexed {len(rows)} products across {len(CATEGORIES)} categories -> {OUT}")
    if not rows:
        print("EMPTY — run with --sample, inspect .sample.html, fix parse_products(). Do this at home.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
