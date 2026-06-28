#!/usr/bin/env python3
"""Build the Total Wine wine catalog index from PerimeterX-free sitemaps.

RUN AT HOME, ~monthly. Writes inventory/totalwine-centennial.jsonl and prints
only a summary + a small random sample, so it costs the agent almost no tokens
(the whole point — see repo CLAUDE.md).

Why sitemaps: totalwine.com listing/product pages sit behind PerimeterX and 403
every static fetch. The XML sitemaps (sitemap.xml -> Product-en-USD-*.xml) are
open, list every product URL, and the wine fields parse straight out of the URL
slug:  /wine/{type}/{varietal}/{producer-bottling-slug}/p/{code}

Per-store price & stock are NOT here (getting past PerimeterX needs a browser) —
see enrich_prices.py. This layer is the bulletproof, store-agnostic catalog.

Usage:
  python3 inventory/build_catalog.py              # full build -> JSONL + report
  python3 inventory/build_catalog.py --sample 20  # parse, print 20 random rows, write nothing
"""
import json
import random
import re
import sys
import time
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "totalwine-centennial.jsonl"
SAMPLE_FILE = HERE / ".catalog-sample.txt"
SITEMAP_INDEX = "https://www.totalwine.com/sitemap.xml"
STORE_ID = "2302"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/xml,text/xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

WINE_URL = re.compile(r'https://www\.totalwine\.com/wine/[^"\s<]+/p/\d+')
PARTS = re.compile(r"https://www\.totalwine\.com/wine/([^/]+)/([^/]+)/(.+)/p/(\d+)$")

# Merchandising buckets that occupy the {type} slot under /wine/ but aren't a real
# wine taxonomy — the same bottles are also listed under their true type path, so
# skipping these drops only promo cross-listings, not unique wines.
SKIP_TYPES = {
    "new-arrivals", "deals", "gift-center", "gift-baskets-sets", "gift-baskets",
    "gifts", "wine-club", "best-sellers", "top-rated", "staff-picks", "sale", "new",
}

# Best-effort region recovery: appellation/region tokens that show up in slugs.
# Longest tokens are tried first so "napa-valley" wins over "napa". Null if none.
REGIONS = {
    # Bordeaux (user buys a lot of left/right bank)
    "pauillac": "Pauillac, Bordeaux",
    "saint-julien": "Saint-Julien, Bordeaux",
    "st-julien": "Saint-Julien, Bordeaux",
    "saint-estephe": "Saint-Estèphe, Bordeaux",
    "st-estephe": "Saint-Estèphe, Bordeaux",
    "margaux": "Margaux, Bordeaux",
    "pessac-leognan": "Pessac-Léognan, Bordeaux",
    "pessac": "Pessac-Léognan, Bordeaux",
    "haut-medoc": "Haut-Médoc, Bordeaux",
    "saint-emilion": "Saint-Émilion, Bordeaux",
    "st-emilion": "Saint-Émilion, Bordeaux",
    "pomerol": "Pomerol, Bordeaux",
    "sauternes": "Sauternes, Bordeaux",
    "graves": "Graves, Bordeaux",
    # California
    "napa-valley": "Napa Valley",
    "oakville": "Oakville, Napa",
    "rutherford": "Rutherford, Napa",
    "stags-leap": "Stags Leap, Napa",
    "howell-mountain": "Howell Mountain, Napa",
    "coombsville": "Coombsville, Napa",
    "mount-veeder": "Mount Veeder, Napa",
    "spring-mountain": "Spring Mountain, Napa",
    "diamond-mountain": "Diamond Mountain, Napa",
    "calistoga": "Calistoga, Napa",
    "yountville": "Yountville, Napa",
    "st-helena": "St. Helena, Napa",
    "alexander-valley": "Alexander Valley, Sonoma",
    "dry-creek": "Dry Creek, Sonoma",
    "russian-river": "Russian River, Sonoma",
    "sonoma-coast": "Sonoma Coast",
    "sonoma-county": "Sonoma County",
    "knights-valley": "Knights Valley, Sonoma",
    "paso-robles": "Paso Robles",
    "santa-rita-hills": "Sta. Rita Hills",
    "santa-barbara": "Santa Barbara",
    "anderson-valley": "Anderson Valley",
    "lodi": "Lodi",
    "napa": "Napa Valley",
    "sonoma": "Sonoma",
    # Pacific NW
    "willamette": "Willamette Valley, Oregon",
    "columbia-valley": "Columbia Valley, Washington",
    "walla-walla": "Walla Walla, Washington",
    "red-mountain": "Red Mountain, Washington",
    # France (other)
    "chateauneuf": "Châteauneuf-du-Pape, Rhône",
    "cote-rotie": "Côte-Rôtie, Rhône",
    "hermitage": "Hermitage, Rhône",
    "gigondas": "Gigondas, Rhône",
    "sancerre": "Sancerre, Loire",
    "chablis": "Chablis, Burgundy",
    "puligny": "Puligny-Montrachet, Burgundy",
    "meursault": "Meursault, Burgundy",
    "gevrey": "Gevrey-Chambertin, Burgundy",
    "nuits-st-georges": "Nuits-St-Georges, Burgundy",
    "vosne": "Vosne-Romanée, Burgundy",
    "chambolle": "Chambolle-Musigny, Burgundy",
    "pommard": "Pommard, Burgundy",
    "champagne": "Champagne",
    # Italy / Spain / Portugal / Argentina / Chile
    "barolo": "Barolo, Piedmont",
    "barbaresco": "Barbaresco, Piedmont",
    "brunello": "Brunello di Montalcino, Tuscany",
    "montalcino": "Montalcino, Tuscany",
    "chianti": "Chianti, Tuscany",
    "bolgheri": "Bolgheri, Tuscany",
    "rioja": "Rioja",
    "ribera": "Ribera del Duero",
    "priorat": "Priorat",
    "douro": "Douro",
    "mendoza": "Mendoza",
    "maipo": "Maipo Valley",
    # Broader catch-alls (lower priority — shorter, so checked after specific AVAs)
    "california": "California",
    "oregon": "Oregon",
    "washington": "Washington",
    "barossa": "Barossa Valley, Australia",
    "mclaren-vale": "McLaren Vale, Australia",
    "coonawarra": "Coonawarra, Australia",
    "marlborough": "Marlborough, New Zealand",
    "central-otago": "Central Otago, New Zealand",
    "toscana": "Tuscany",
    "tuscany": "Tuscany",
    "piedmont": "Piedmont",
    "piemonte": "Piedmont",
    "veneto": "Veneto",
    "amarone": "Amarone, Veneto",
    "valpolicella": "Valpolicella, Veneto",
    "soave": "Soave, Veneto",
    "sicilia": "Sicily",
    "sicily": "Sicily",
    "etna": "Etna, Sicily",
    "alsace": "Alsace",
    "beaujolais": "Beaujolais",
    "languedoc": "Languedoc",
    "provence": "Provence",
    "rhone": "Rhône",
    "loire": "Loire",
    "prosecco": "Prosecco, Italy",
    "cava": "Cava, Spain",
    "mosel": "Mosel, Germany",
    "rheingau": "Rheingau, Germany",
    "stellenbosch": "Stellenbosch, South Africa",
}
REGION_TOKENS = sorted(REGIONS, key=len, reverse=True)  # longest match wins


def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def product_sitemaps():
    idx = fetch(SITEMAP_INDEX)
    locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", idx)
    return [u for u in locs if re.search(r"/Product-en-USD-\d+\.xml$", u)]


def deslug(slug):
    words = slug.replace("/", " ").replace("-", " ").split()
    return " ".join(w.capitalize() for w in words)


def region_for(slugpath):
    """Word-aware region match: single-word tokens must be a whole slug word
    (so "lodi" doesn't fire inside "melodious"); multi-word tokens match the
    hyphen-joined slug. Longest tokens win (specific AVA over broad region)."""
    words = re.split(r"[-/]", slugpath)
    wset = set(words)
    joined = "-".join(words)
    for tok in REGION_TOKENS:
        if "-" in tok:
            if tok in joined:
                return REGIONS[tok]
        elif tok in wset:
            return REGIONS[tok]
    return None


def parse_catalog():
    seen = {}
    maps = product_sitemaps()
    if not maps:
        return []
    for sm in maps:
        try:
            text = fetch(sm)
        except Exception as e:
            print(f"  skip {sm}: {e}", file=sys.stderr)
            continue
        for url in WINE_URL.findall(text):
            m = PARTS.match(url)
            if not m:
                continue
            wine_type, varietal, slugpath, code = m.groups()
            if wine_type in SKIP_TYPES:
                continue
            slug = slugpath.split("/")[-1]  # canonical product slug (last segment)
            if slug in seen:  # collapse size/vintage SKUs AND promo cross-listings
                continue
            seen[slug] = {
                "name": deslug(slug),
                "slug": slug,
                "varietal": varietal,
                "wine_type": wine_type,
                "region": region_for(slugpath),
                "product_code": code,
                "url": url,
                "price": None,
                "in_stock": None,
                "aisle": None,
                "store_id": STORE_ID,
                "source": "sitemap",
                "scraped_date": date.today().isoformat(),
            }
        time.sleep(0.3)  # be polite
    return list(seen.values())


def coverage_report(rows):
    n = len(rows)
    with_region = sum(1 for r in rows if r["region"])
    vt = Counter(r["wine_type"] for r in rows)
    var = Counter(r["varietal"] for r in rows)
    lines = [
        f"distinct wines: {n}",
        f"region recovered: {with_region} ({100 * with_region // max(n, 1)}%)",
        "wine_type: " + ", ".join(f"{k} {v}" for k, v in vt.most_common()),
        "top varietals: " + ", ".join(f"{k} {v}" for k, v in var.most_common(15)),
    ]
    alarms = []
    if n < 8000:
        alarms.append(f"LOW distinct count ({n}) — sitemap parse may have regressed")
    if with_region == 0:
        alarms.append("region recovery is 0% — token map or slug shape changed")
    if var.get("", 0) or vt.get("", 0):
        alarms.append("empty varietal/type present — URL shape changed")
    return "\n".join(lines), alarms


def render_sample(rows, n):
    pick = random.sample(rows, min(n, len(rows)))
    return "\n".join(
        f'{r["wine_type"]:>26} | {r["varietal"]:>22} | {(r["region"] or "-"):>22} | {r["name"]}'
        for r in pick
    )


def main():
    sample_n = 0
    if "--sample" in sys.argv:
        i = sys.argv.index("--sample")
        sample_n = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 20

    rows = parse_catalog()
    if not rows:
        print("EMPTY — no wine URLs parsed. Sitemap shape changed; inspect before trusting.", file=sys.stderr)
        return 1

    report, alarms = coverage_report(rows)

    if sample_n:
        print(f"--sample {sample_n} (nothing written)\n")
        print(render_sample(rows, sample_n))
        print("\n" + report)
        for a in alarms:
            print("ALARM:", a, file=sys.stderr)
        return 0

    rows.sort(key=lambda r: (r["wine_type"], r["varietal"], r["slug"]))
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    sample_txt = render_sample(rows, 25)
    SAMPLE_FILE.write_text(sample_txt + "\n\n" + report + "\n", encoding="utf-8")

    print(f"wrote {len(rows)} distinct wines -> {OUT}")
    print(report)
    print(f"\nsample (25) + report also in {SAMPLE_FILE.name}:\n")
    print(sample_txt)
    for a in alarms:
        print("ALARM:", a, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
