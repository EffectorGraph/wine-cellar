#!/usr/bin/env python3
"""Scan the live in-stock wine inventory (> $20) at Total Wine #2302.

Total Wine's listing pages server-render `window.INITIAL_STATE`, and
`INITIAL_STATE.search.results.products` is a clean array carrying, per wine, the
store-#2302 price, live stock count, in-stock flag, shelf location/bay, varietal
and size. One browser walk of the wine root (`/wine/c/c0020`, pageSize=200, ~43
pages) yields the whole store as structured JSON — no per-product page visits.

A local `nodriver` Chrome sets the store and clears PerimeterX (the easy case:
real Mac, real home IP). RUN AT HOME. Needs: pip install -r inventory/requirements.txt

Incremental: a re-scan reconciles against the existing index — only rows whose
value actually moved are rewritten, delisted/out-of-stock wines drop out, new
arrivals are added. Unchanged rows stay byte-identical so `git diff` is a clean
changelog. Degrades safely: a blocked/empty scan writes nothing.

Usage:
  python3 inventory/scan_store.py --sample 2        # read 2 pages, print, write nothing
  python3 inventory/scan_store.py                    # full scan -> reconcile the index
  python3 inventory/scan_store.py --min-price 30     # different price floor
"""
import argparse
import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
INDEX = HERE / "totalwine-centennial.jsonl"
CHANGES = HERE / ".store-changes.txt"
STORE_ID = "2302"
STORE_URL = "https://www.totalwine.com/store-info/colorado/centennial/2302"
WINE_ROOT = "https://www.totalwine.com/wine/c/c0020"
PAGE_SIZE = 200
PARTS = re.compile(r"/wine/([^/]+)/([^/]+)/")

FIELD_ORDER = ["skuId", "product_code", "name", "brand", "varietal", "wine_type",
               "price", "stock", "size", "location", "bay", "url", "store_id", "scraped_date"]


# ---------- per-product extraction ----------

def in_stock_pickup(p):
    for m in (p.get("stockMessages") or {}).get("messages", []):
        if m.get("shoppingMethod") == "INSTORE_PICKUP":
            return bool(m.get("addToCartStatus"))
    sl = p.get("stockLevel") or []
    if sl and isinstance(sl[0], dict):
        return (sl[0].get("stock") or 0) > 0
    return False


def first_price(p):
    for entry in (p.get("price") or []):
        if isinstance(entry, dict) and entry.get("price") is not None:
            try:
                return float(entry["price"])
            except (TypeError, ValueError):
                continue
    return None


def to_row(p, today):
    url = p.get("productUrl") or ""
    m = PARTS.search(url)
    wine_type, varietal = (m.group(1), m.group(2)) if m else ("", "")
    sl = p.get("stockLevel") or []
    stock = sl[0].get("stock") if sl and isinstance(sl[0], dict) else None
    brand = p.get("brand") or {}
    size = " ".join(x for x in (p.get("volume") or "", p.get("containerType") or "") if x).strip()
    return {
        "skuId": p.get("skuId") or "",
        "product_code": str(p.get("id") or ""),
        "name": p.get("name") or "",
        "brand": brand.get("name", "") if isinstance(brand, dict) else "",
        "varietal": varietal,
        "wine_type": wine_type,
        "price": first_price(p),
        "stock": stock,
        "size": size,
        "location": p.get("location") or "",
        "bay": p.get("bay") or "",
        "url": ("https://www.totalwine.com" + url) if url.startswith("/") else url,
        "store_id": STORE_ID,
        "scraped_date": today,
    }


def ordered(row):
    return {k: row.get(k) for k in FIELD_ORDER}


# ---------- the browser walk ----------

async def scan(min_price, max_pages):
    import nodriver as uc

    today = date.today().isoformat()
    keep = {}
    browser = await uc.start(headless=False)
    try:
        page = await browser.get(STORE_URL)
        await page.sleep(6)  # set store #2302 + clear PerimeterX

        async def fetch_page(n):
            url = WINE_ROOT + f"?pageSize={PAGE_SIZE}" + (f"&page={n}" if n > 1 else "")
            pg = await browser.get(url)
            await pg.sleep(3)
            prods = await pg.evaluate(
                "JSON.stringify((window.INITIAL_STATE&&window.INITIAL_STATE.search.results.products)||[])",
                await_promise=False)
            pag = await pg.evaluate(
                "JSON.stringify((window.INITIAL_STATE&&window.INITIAL_STATE.search.results.pagination)||{})",
                await_promise=False)
            return json.loads(str(prods)), json.loads(str(pag))

        prods, pag = await fetch_page(1)
        total_pages = pag.get("totalPages", 1)
        last = min(total_pages, max_pages) if max_pages else total_pages
        print(f"store reports {pag.get('totalResults', '?')} wine listings across "
              f"{total_pages} pages; walking {last}", file=sys.stderr)

        def absorb(batch):
            for p in batch:
                if not in_stock_pickup(p):
                    continue
                price = first_price(p)
                if price is None or price <= min_price:
                    continue
                row = to_row(p, today)
                if row["skuId"]:
                    keep[row["skuId"]] = row

        absorb(prods)
        for n in range(2, last + 1):
            prods, _ = await fetch_page(n)
            if not prods:
                print(f"page {n} empty — stopping early", file=sys.stderr)
                break
            absorb(prods)
            await page.sleep(0.8)  # be polite
    finally:
        try:
            browser.stop()
        except Exception:
            pass
    return keep


# ---------- index IO + reconcile ----------

def load_existing():
    if not INDEX.exists():
        return {}
    out = {}
    for line in INDEX.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("skuId"):  # ignore rows from the old (pre-store-scan) schema
            out[r["skuId"]] = r
    return out


def data_eq(a, b):
    da = {k: v for k, v in a.items() if k != "scraped_date"}
    db = {k: v for k, v in b.items() if k != "scraped_date"}
    return da == db


def reconcile(old, new):
    added, changed, kept = [], [], []
    for sku, row in new.items():
        prev = old.get(sku)
        if prev is None:
            added.append(row)
        elif data_eq(prev, row):
            kept.append(ordered(prev))  # byte-identical, keep old date
        else:
            changed.append((prev, row))
    removed = [old[s] for s in old if s not in new]
    final = ([ordered(r) for r in added]
             + [ordered(n) for _, n in changed]
             + kept)
    final.sort(key=lambda r: r["skuId"])
    return final, added, changed, removed


def write_index(rows):
    INDEX.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def summarize(added, changed, removed):
    lines = [f"+{len(added)} new   -{len(removed)} gone   ~{len(changed)} changed"]
    for prev, new in changed[:8]:
        if prev.get("price") != new.get("price"):
            lines.append(f"  ~ {new['name']}: ${prev.get('price')}→${new.get('price')}")
        elif prev.get("stock") != new.get("stock"):
            lines.append(f"  ~ {new['name']}: stock {prev.get('stock')}→{new.get('stock')}")
        else:
            lines.append(f"  ~ {new['name']}: location moved")
    for r in added[:6]:
        lines.append(f"  + {r['name']}  ${r['price']}")
    for r in removed[:6]:
        lines.append(f"  - {r['name']} (gone)")
    return "\n".join(lines)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Scan in-stock >$20 wines at Total Wine #2302.")
    ap.add_argument("--min-price", type=float, default=20.0)
    ap.add_argument("--sample", type=int, default=0, help="read N pages, print, write nothing")
    ap.add_argument("--max-pages", type=int, default=0, help="cap pages walked (testing)")
    a = ap.parse_args()

    max_pages = a.sample if a.sample else a.max_pages
    keep = asyncio.run(scan(a.min_price, max_pages))

    if not keep:
        print("EMPTY — no in-stock >$20 wines parsed. Likely a PerimeterX block or a site "
              "shape change; index left untouched. See the refresh skill's troubleshooting.",
              file=sys.stderr)
        return 1

    if a.sample:
        for r in list(keep.values())[:40]:
            print(f'${r["price"]:>6.2f}  stk {str(r["stock"]):>3}  {r["varietal"]:<20} '
                  f'{(r["location"] or "-"):<14} {r["name"]}')
        print(f"\n{len(keep)} in-stock >${a.min_price:.0f} wines across {a.sample} page(s) "
              f"(nothing written — sample mode)")
        return 0

    old = load_existing()
    final, added, changed, removed = reconcile(old, keep)
    write_index(final)
    report = summarize(added, changed, removed)
    CHANGES.write_text(report + "\n", encoding="utf-8")
    print(f"index: {len(final)} in-stock >${a.min_price:.0f} wines @ #2302 -> {INDEX.name}")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
