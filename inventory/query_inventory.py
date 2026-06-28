#!/usr/bin/env python3
"""Token-tight query over the local #2302 store inventory (totalwine-centennial.jsonl).

The ONLY scraper-side thing to run AT THE STORE. Filters the local index and prints
only the matches — price, stock count, and shelf location — never the whole file.
Refresh the index at home with scan_store.py (or the wine-inventory-refresh skill).

Examples:
  python3 inventory/query_inventory.py --varietal cabernet --max-price 60
  python3 inventory/query_inventory.py --type red-wine --region napa --sort stock
  python3 inventory/query_inventory.py --text caymus
"""
import argparse
import json
from pathlib import Path

INDEX = Path(__file__).parent / "totalwine-centennial.jsonl"


def load():
    if not INDEX.exists():
        raise SystemExit(f"no index at {INDEX} — run scan_store.py at home first")
    return [json.loads(line) for line in INDEX.read_text().splitlines() if line.strip()]


def matches(r, a):
    name = r["name"].lower()
    if a.varietal and a.varietal.lower() not in (r["varietal"] or "").lower():
        return False
    if a.type and a.type.lower() not in (r["wine_type"] or "").lower():
        return False
    if a.region and a.region.lower() not in name:  # region words live in the wine name
        return False
    for t in a.text or []:
        if t.lower() not in (name + " " + (r.get("brand") or "").lower()):
            return False
    price = r.get("price")
    if a.min_price is not None and price < a.min_price:
        return False
    if a.max_price is not None and price > a.max_price:
        return False
    if a.min_stock is not None and (r.get("stock") or 0) < a.min_stock:
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Filter the local Total Wine #2302 in-stock inventory.")
    ap.add_argument("--varietal", help="substring of varietal, e.g. cabernet")
    ap.add_argument("--type", help="wine_type, e.g. red-wine, white-wine")
    ap.add_argument("--region", help="region word as it appears in the wine name, e.g. napa, sonoma")
    ap.add_argument("--text", action="append", help="substring on name/brand (repeatable)")
    ap.add_argument("--min-price", type=float)
    ap.add_argument("--max-price", type=float)
    ap.add_argument("--min-stock", type=int, help="only wines with at least N bottles in stock")
    ap.add_argument("--sort", choices=["price", "stock", "name"], default="price")
    ap.add_argument("--urls", action="store_true", help="also print product URLs")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()

    rows = [r for r in load() if matches(r, a)]
    keyfn = {
        "price": lambda r: (r["price"], r["name"]),
        "stock": lambda r: (-(r.get("stock") or 0), r["price"]),
        "name": lambda r: r["name"],
    }[a.sort]
    rows.sort(key=keyfn)
    shown = rows[: a.limit]

    for r in shown:
        loc = r.get("location") or "-"
        stk = r.get("stock")
        stk_s = f"{stk} in stk" if stk is not None else ""
        print(f'${r["price"]:>7.2f} | {r["varietal"]:<22} | {loc:<16} | {r["name"]}  {stk_s}')
        if a.urls:
            print(f'          {r["url"]}')

    print(f"\n{len(shown)} shown / {len(rows)} matched, in stock @ Total Wine Centennial #2302")


if __name__ == "__main__":
    main()
