#!/usr/bin/env python3
"""Token-tight query over the local Total Wine catalog (totalwine-centennial.jsonl).

This is the ONLY scraper-side thing to run AT THE STORE. It filters the local
index and prints just the handful of matches — it never loads the whole catalog
into the agent's context. Build/refresh the index at home with build_catalog.py;
fill price/stock at home with enrich_prices.py.

Examples:
  python3 inventory/query_inventory.py --varietal cabernet --region napa --max-price 60
  python3 inventory/query_inventory.py --type red-wine --text bordeaux-blend --limit 10
  python3 inventory/query_inventory.py --text mouton
"""
import argparse
import json
from pathlib import Path

INDEX = Path(__file__).parent / "totalwine-centennial.jsonl"


def load():
    if not INDEX.exists():
        raise SystemExit(f"no index at {INDEX} — run build_catalog.py at home first")
    return [json.loads(line) for line in INDEX.read_text().splitlines() if line.strip()]


def matches(r, a):
    slug = r["slug"].lower()
    name = r["name"].lower()
    region = (r["region"] or "").lower()
    if a.varietal and a.varietal.lower() not in (r["varietal"] or "").lower():
        return False
    if a.type and a.type.lower() not in (r["wine_type"] or "").lower():
        return False
    if a.region and a.region.lower() not in (region + " " + slug):
        return False
    for t in a.text or []:
        if t.lower() not in (name + " " + slug):
            return False
    price = r.get("price")
    if a.priced_only and price is None:
        return False
    if price is not None:
        if a.max_price is not None and price > a.max_price:
            return False
        if a.min_price is not None and price < a.min_price:
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Filter the local Total Wine catalog.")
    ap.add_argument("--varietal", help="substring of varietal, e.g. cabernet")
    ap.add_argument("--type", help="wine_type, e.g. red-wine, white-wine")
    ap.add_argument("--region", help="substring of region or slug, e.g. napa, pauillac")
    ap.add_argument("--text", action="append", help="substring on name/slug (repeatable)")
    ap.add_argument("--min-price", type=float)
    ap.add_argument("--max-price", type=float)
    ap.add_argument("--priced-only", action="store_true", help="only rows with a scraped price")
    ap.add_argument("--urls", action="store_true", help="also print product URLs")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()

    rows = [r for r in load() if matches(r, a)]
    rows.sort(key=lambda r: (r.get("price") is None, r.get("price") or 0, r["name"]))
    shown = rows[: a.limit]

    for r in shown:
        price = r.get("price")
        ptxt = f"${price:.0f}" if price is not None else "n/a"
        stock = "" if r.get("in_stock") is None else (" [in stock]" if r["in_stock"] else " [OOS]")
        aisle = f"  @ {r['aisle']}" if r.get("aisle") else ""
        print(f'{ptxt:>5} | {r["varietal"]:<22} | {(r["region"] or "-"):<24} | {r["name"]}{stock}{aisle}')
        if a.urls:
            print(f"        {r['url']}")

    note = "price n/a = not yet enriched; confirm at shelf" if any(r.get("price") is None for r in shown) else ""
    print(f"\n{len(shown)} shown / {len(rows)} matched. {note}")


if __name__ == "__main__":
    main()
