# Total Wine #2302 inventory — schema & scraping reference

Strong records so a future refresh, debug, or rewrite is fast — not a re-discovery.
Store: **Total Wine & More #2302**, 9505 E County Line Rd, Centennial CO 80112.

- **Builder:** `scan_store.py` → writes `totalwine-centennial.jsonl`
- **Reader (store-time):** `query_inventory.py`
- **Refresh wrapper / skill:** `refresh_inventory.sh`, `wine-inventory-refresh` skill
- **Scope:** every wine **in stock** at #2302 with **price > $20** (one row per SKU).

---

## 1. Index row schema — `totalwine-centennial.jsonl`

One JSON object per line, keys in this fixed order (see `FIELD_ORDER` in `scan_store.py`).
Reconcile compares every field **except `scraped_date`** to decide if a row changed.

| Key | Type | Example | Meaning | Source in the page JSON |
|---|---|---|---|---|
| `skuId` | str | `"164328010-1"` | **Reconcile key** (unique per SKU). | `product.skuId` |
| `product_code` | str | `"164328010"` | Product id (size/vintage-specific). | `product.id` |
| `name` | str | `"Opus One, 2022"` | Display name; **often includes vintage**. | `product.name` |
| `brand` | str | `"Caymus"` | Brand/producer. | `product.brand.name` |
| `varietal` | str | `"cabernet-sauvignon"` | Grape/category slug. | 2nd path seg of `productUrl` |
| `wine_type` | str | `"red-wine"` | red-wine / white-wine / champagne-sparkling-wine / … | 1st path seg of `productUrl` |
| `price` | float | `459.99` | Shelf price at #2302 (USD). Always > 20. | first numeric `product.price[].price` |
| `stock` | int/null | `22` | Live on-hand count at #2302. | `product.stockLevel[0].stock` |
| `size` | str | `"Bottle"` | Volume + container, best-effort. | `product.volume` + `product.containerType` |
| `location` | str | `"Aisle 05, Right"` | **Shelf location** ("Wine Cellar"/"Backwall" for some). | `product.location` |
| `bay` | str | `""` | Bay within the aisle, when present. | `product.bay` |
| `url` | str | `https://www.totalwine.com/wine/...` | Product page. | `"https://www.totalwine.com" + product.productUrl` |
| `store_id` | str | `"2302"` | Always 2302. | constant |
| `scraped_date` | str | `"2026-06-27"` | Date this row's data last **changed** (not last seen). | run date on add/change |

Gitignored per-run artifacts: `.refresh.log` (wrapper output), `.store-changes.txt`
(the `+N -M ~K` changelog), `.venv/`.

---

## 2. Where the data comes from (the important part)

Total Wine's **listing pages server-render `window.INITIAL_STATE`**. The product array
is the gold — clean JSON, store-scoped, ~200 wines per page load, no per-product visits.

- **Set store first:** `GET https://www.totalwine.com/store-info/colorado/centennial/2302`
  then wait — this pins #2302 (cookie) and clears PerimeterX. Confirm via
  `window.dtm_datalayer.storeId == "2302"`.
- **Wine root listing:** `https://www.totalwine.com/wine/c/c0020?pageSize=200&page=N`
  - `page` is **1-indexed** (`page=1` == default; omit param for page 1).
  - **`pageSize` caps at 200** — 480/1000 return an empty `INITIAL_STATE` (`{}`). Don't exceed 200.
  - Whole store ≈ **8,461 listings → 43 pages** (incl. out-of-stock + all prices). We filter client-side.
- **Products array:** `window.INITIAL_STATE.search.results.products` (list of product objects).
- **Pagination:** `window.INITIAL_STATE.search.results.pagination` =
  `{page, pageSize, totalPages, totalResults}` → drives the loop.

### Product object fields we read (`product.*`)
```
name, brand{name}, id, skuId, productUrl,
price[{price, type}],                 # type EDLP = everyday; take first numeric
stockLevel[{stock, purchaseLimit}],   # stock = on-hand count
stockMessages{messages:[{shoppingMethod, stockMessage, addToCartStatus}]},
location, bay,                        # shelf placement
volume, containerType, packageValue,  # size (volume sometimes "")
categories[{name, type}],            # type PRODUCT_TYPE / VARIETAL_TYPE (we use productUrl instead)
customerAverageRating, itemStyle, itemTasteProfile   # available but NOT stored (churn/lean)
```

### Derivations / filters (mirror `scan_store.py`)
- **In stock @ #2302** = the `INSTORE_PICKUP` entry in `stockMessages.messages` has
  `addToCartStatus: true` (fallback: `stockLevel[0].stock > 0`). Listings include OOS, so this filter matters.
- **Price** = first numeric `price[].price`; keep only `> --min-price` (default 20).
- **varietal / wine_type** = regex `"/wine/([^/]+)/([^/]+)/"` on `productUrl`.
- **Dedupe** by `skuId`.

---

## 3. Bot-wall context

- `www.totalwine.com` listing/product pages are behind **PerimeterX (HUMAN)** → every
  static `curl`/`urllib` fetch 403s with a `px-captcha` page. Price/stock are JS-hydrated.
- **`nodriver`** (CDP stealth Chrome, local Mac, real home IP = the easy case) renders the
  real page and clears the challenge. Non-headless. If a captcha shows, solve once in the window.
- The whole approach degrades safely: a block yields an empty parse → `scan_store.py`
  exits non-zero and **leaves the index untouched** (never commits garbage).

---

## 4. Useful facets / params for future filtering (not all wired up)

From `INITIAL_STATE.search`:
- **Facets are URL query params**, format `?facetName=Value1|Value2` (`|` = `%7C`), e.g.
  observed `?volume=Standard 750 ml|Magnum 1.5L&sales=Winery Direct`.
- **Price facet** (`results.facets[id="price"]`) values/ids: `up-to-10`, `-10-to-20`,
  `-20-to-30`, `-30-to-40`, `-40-to-50`, `-50-above` (each with a live `count`). The exact
  **price param name isn't confirmed** — we filter client-side instead. If you want to cut
  page count, confirm the param and select the ≥$20 bands server-side.
- `search.availability` = `{INSTORE_PICKUP, DELIVERY, SHIPPING, ALLSTORES}` booleans.
- `search.results.pagination.totalResults` is the live store-wide wine count.

---

## 5. Emergency fallback — PX-free sitemap catalog (retired, but documented)

If PerimeterX ever hardens and `nodriver` can't clear it, the **public XML sitemaps are
NOT bot-walled** and give a national catalog (name/varietal/region/code, **no price/stock**):
`https://www.totalwine.com/sitemap.xml` → `Product-en-USD-0.xml … -16.xml`; wine product
URLs are `/wine/{type}/{varietal}/{producer-slug}/p/{code}` (~34k SKUs → ~19k distinct by
slug). This was the original `build_catalog.py` approach (git history before commit 41387e2).
Use it as a last-resort "what exists" layer; price/stock would still need a different source.

---

## 6. Gotchas

- **Stale SKU sizes:** a sitemap/older code can point at a non-stocked bottle size (e.g. an
  Opus One 375ml reads "Not Available"). The listing scan avoids this by reading the store's
  *current* stocked SKUs directly — trust `scan_store.py`'s output, not arbitrary `/p/CODE` URLs.
- **`scraped_date` only bumps on change** → unchanged rows stay byte-identical → clean diffs.
  A back-to-back re-scan reporting `+0 -0 ~0` with no git diff is correct, not a bug.
- **Index is #2302-specific.** Re-point by changing `STORE_URL` + `STORE_ID` in `scan_store.py`
  (and confirm the new store's `storeId` in the data layer).
