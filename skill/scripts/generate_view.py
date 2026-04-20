#!/usr/bin/env python3
"""Read cellar.jsonl and write cellar-view.html — a self-contained sortable/filterable table.

Path discovery matches append_wine.py (WINE_CELLAR_PATH env var → .local-config.json → error).
Output path is `<repo>/cellar-view.html` (sibling of cellar.jsonl).
"""
import json
import os
import sys
from html import escape
from pathlib import Path

# Column order + display labels (matches skill schema)
COLUMNS = [
    ("wine", "Wine"),
    ("winery", "Winery"),
    ("vintage", "Vintage"),
    ("grapes", "Grapes"),
    ("subregion", "Subregion"),
    ("region", "Region"),
    ("country", "Country"),
    ("estate", "Estate"),
    ("soil", "Soil"),
    ("elevation", "Elevation"),
    ("vine_age", "Vine Age"),
    ("importer", "Importer"),
    ("harvest_date", "Harvest Date"),
    ("fermentation_vessel", "Fermentation Vessel"),
    ("whole_bunch_pct", "Whole-bunch %"),
    ("malolactic", "Malolactic"),
    ("barrel_time", "Barrel Time"),
    ("oak_origin", "Oak Origin"),
    ("new_oak_pct", "New Oak %"),
    ("abv", "ABV"),
    ("ph", "pH"),
    ("ta", "TA"),
    ("residual_sugar", "RS"),
    ("cases_produced", "Cases"),
    ("release_date", "Release Date"),
    ("drink_from", "Drink From"),
    ("cellared_under", "Cellared Under"),
    ("drink_by", "Drink By"),
    ("opened_on", "Opened On"),
    ("tasting_notes", "Tasting Notes"),
    ("fallback_tasting_notes", "Fallback Tasting Notes"),
]

# Display hints: formatting per column
PCT_KEYS = {"whole_bunch_pct", "new_oak_pct"}
PCT_FLOAT_KEYS = {"abv"}


def resolve_cellar_path() -> Path:
    env = os.environ.get("WINE_CELLAR_PATH")
    if env:
        return Path(env)
    cfg_path = Path.home() / ".claude" / "skills" / "wine-cellar" / ".local-config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            repo_path = cfg.get("repo_path")
            if repo_path:
                return Path(repo_path) / "cellar.jsonl"
        except (json.JSONDecodeError, OSError) as e:
            print(f"ERROR: could not read {cfg_path}: {e}", file=sys.stderr)
            sys.exit(2)
    print(
        "ERROR: cellar.jsonl path not configured.\n"
        "  Run `bash <repo>/skill/scripts/sync_skill.sh` to set it up,\n"
        "  or set WINE_CELLAR_PATH env var.",
        file=sys.stderr,
    )
    sys.exit(2)


def format_cell(key: str, val) -> str:
    """Render one cell's display value."""
    if val is None:
        return ""
    if key in PCT_KEYS:
        return f"{val}%"
    if key in PCT_FLOAT_KEYS:
        return f"{val:.1f}%"
    if key == "ph":
        return f"{val:.2f}"
    if key in {"ta", "residual_sugar"}:
        return f"{val} g/L" if val not in (None, "") else ""
    if key == "cases_produced":
        try:
            return f"{int(val):,}"
        except (TypeError, ValueError):
            return str(val)
    return str(val)


def main() -> int:
    cellar_path = resolve_cellar_path()
    if not cellar_path.exists():
        print(f"ERROR: cellar file not found: {cellar_path}", file=sys.stderr)
        return 2

    rows = []
    with cellar_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"ERROR: line {i} of cellar.jsonl is invalid JSON: {e}", file=sys.stderr)
                return 2

    # Totals
    total_rows = len(rows)
    opened_rows = sum(1 for r in rows if r.get("opened_on"))
    in_cellar = total_rows - opened_rows
    vintages = [r.get("vintage") for r in rows if r.get("vintage") is not None]
    vintage_range = f"{min(vintages)}–{max(vintages)}" if vintages else "—"

    out_path = cellar_path.parent / "cellar-view.html"

    # Build the HTML
    head_cells = "".join(
        f'<th data-key="{escape(key)}" data-type="{"num" if key in {"vintage","whole_bunch_pct","new_oak_pct","abv","ph","ta","residual_sugar","cases_produced","drink_from","cellared_under","drink_by"} else "text"}">'
        f'{escape(label)}<span class="sort-arrow"></span></th>'
        for key, label in COLUMNS
    )

    body_rows = []
    for r in rows:
        cells = []
        for key, _ in COLUMNS:
            val = r.get(key)
            display = format_cell(key, val)
            # Sort data uses the raw value for numerics, display string otherwise
            sort_val = escape(str(val) if val is not None else "", quote=True)
            cells.append(f'<td data-sort="{sort_val}">{escape(display)}</td>')
        opened_class = " class=\"opened\"" if r.get("opened_on") else ""
        body_rows.append(f"<tr{opened_class}>{''.join(cells)}</tr>")
    body_html = "\n      ".join(body_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Wine Cellar — {escape(str(total_rows))} bottles</title>
<style>
  :root {{
    --bg: #fafaf7;
    --fg: #2a2a2a;
    --muted: #8a8580;
    --border: #e0dcd5;
    --accent: #7a2d2d;
    --hover: #f3efe8;
    --opened: #e8dfd5;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--fg);
    margin: 0;
    padding: 1.5rem;
    font-size: 14px;
  }}
  header {{
    display: flex;
    align-items: baseline;
    gap: 1.5rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }}
  h1 {{
    margin: 0;
    font-size: 1.6rem;
    color: var(--accent);
    font-weight: 600;
  }}
  .stats {{
    color: var(--muted);
    font-size: 0.9rem;
  }}
  .stats span {{
    margin-right: 1rem;
  }}
  .stats strong {{
    color: var(--fg);
  }}
  .filter-wrap {{
    margin-bottom: 0.75rem;
  }}
  #filter {{
    padding: 0.4rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 0.9rem;
    width: 320px;
    background: white;
  }}
  #filter:focus {{
    outline: 2px solid var(--accent);
    outline-offset: -1px;
  }}
  .table-wrap {{
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: white;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    font-size: 12.5px;
  }}
  th, td {{
    padding: 0.45rem 0.6rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    white-space: pre-wrap;
  }}
  th {{
    background: #f0ebe2;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    position: sticky;
    top: 0;
    z-index: 1;
    white-space: nowrap;
    border-bottom: 2px solid var(--border);
  }}
  th:hover {{
    background: #e8e2d6;
  }}
  .sort-arrow {{
    display: inline-block;
    width: 1em;
    color: var(--muted);
    margin-left: 0.25em;
  }}
  th.sort-asc .sort-arrow::before {{ content: "▲"; color: var(--accent); }}
  th.sort-desc .sort-arrow::before {{ content: "▼"; color: var(--accent); }}
  tr:hover {{ background: var(--hover); }}
  tr.opened {{ background: var(--opened); font-style: italic; color: var(--muted); }}
  tr.opened:hover {{ background: #ddd2c3; }}
  td:first-child {{ min-width: 18ch; }}
  /* Tasting notes columns: allow wider display but cap */
  td:nth-last-child(1), td:nth-last-child(2) {{
    max-width: 36ch;
    min-width: 20ch;
    font-size: 12px;
  }}
  footer {{
    margin-top: 1rem;
    color: var(--muted);
    font-size: 0.8rem;
  }}
</style>
</head>
<body>
  <header>
    <h1>Wine Cellar</h1>
    <div class="stats">
      <span><strong>{total_rows}</strong> rows</span>
      <span><strong>{in_cellar}</strong> in cellar</span>
      <span><strong>{opened_rows}</strong> opened</span>
      <span>Vintages: <strong>{escape(vintage_range)}</strong></span>
    </div>
  </header>
  <div class="filter-wrap">
    <input type="text" id="filter" placeholder="Filter (any column)…" autocomplete="off">
  </div>
  <div class="table-wrap">
    <table id="cellar">
      <thead><tr>{head_cells}</tr></thead>
      <tbody>
      {body_html}
      </tbody>
    </table>
  </div>
  <footer>
    Auto-generated from <code>cellar.jsonl</code> by <code>skill/scripts/generate_view.py</code>.
    Click any column header to sort. Italic rows are opened bottles.
  </footer>
<script>
(() => {{
  const table = document.getElementById("cellar");
  const tbody = table.querySelector("tbody");
  const filter = document.getElementById("filter");

  let sortKey = null;
  let sortDir = 1;

  function sortBy(th) {{
    const key = th.dataset.key;
    const type = th.dataset.type;
    if (sortKey === key) {{
      sortDir *= -1;
    }} else {{
      sortKey = key;
      sortDir = 1;
    }}
    // Mark arrows
    table.querySelectorAll("th").forEach((h) => {{
      h.classList.remove("sort-asc", "sort-desc");
    }});
    th.classList.add(sortDir === 1 ? "sort-asc" : "sort-desc");

    const idx = [...th.parentNode.children].indexOf(th);
    const rows = [...tbody.querySelectorAll("tr")];
    rows.sort((a, b) => {{
      const av = a.children[idx].dataset.sort;
      const bv = b.children[idx].dataset.sort;
      if (type === "num") {{
        const an = av === "" ? Infinity : parseFloat(av);
        const bn = bv === "" ? Infinity : parseFloat(bv);
        return (an - bn) * sortDir;
      }}
      return av.localeCompare(bv) * sortDir;
    }});
    rows.forEach((r) => tbody.appendChild(r));
  }}
  table.querySelectorAll("th").forEach((th) => th.addEventListener("click", () => sortBy(th)));

  filter.addEventListener("input", () => {{
    const q = filter.value.trim().toLowerCase();
    const rows = tbody.querySelectorAll("tr");
    rows.forEach((r) => {{
      const text = r.textContent.toLowerCase();
      r.style.display = text.includes(q) ? "" : "none";
    }});
  }});
}})();
</script>
</body>
</html>
"""

    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {total_rows} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
