#!/usr/bin/env python3
"""Read cellar.jsonl and write cellar-view.html — a self-contained sortable/filterable table.

Path discovery matches append_wine.py (WINE_CELLAR_PATH env var → .local-config.json → error).
Output path is `<repo>/cellar-view.html` (sibling of cellar.jsonl).
"""
import json
import os
import sys
from collections import Counter
from html import escape
from pathlib import Path

# Column order + display labels. The first 31 are the objective fields; the last
# three (status, verdict, impressions) are the subjective feedback layer.
COLUMNS = [
    ("status", "Status"),
    ("wine", "Wine"),
    ("winery", "Winery"),
    ("vintage", "Vintage"),
    ("verdict", "Verdict"),
    ("impressions", "Impressions"),
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
NUM_KEYS = {
    "vintage", "whole_bunch_pct", "new_oak_pct", "abv", "ph", "ta",
    "residual_sugar", "cases_produced", "drink_from", "cellared_under", "drink_by",
}
WIDE_KEYS = {"verdict", "impressions", "tasting_notes", "fallback_tasting_notes"}

# Human labels for the status vocabulary.
STATUS_LABELS = {
    "pending": "⏳ Pending",
    "cellared": "Cellared",
    "love": "♥ Love",
    "like": "Like",
    "meh": "Meh",
    "pass": "Pass",
}


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
    if val is None or val == "":
        return ""
    if key == "status":
        return STATUS_LABELS.get(val, str(val))
    if key == "impressions":
        # list of {date, note} → stacked "date — note" lines
        if not isinstance(val, list):
            return str(val)
        return "\n".join(f"{escape(str(i.get('date','')))} — {escape(str(i.get('note','')))}" for i in val)
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
    status_counts = Counter((r.get("status") or "cellared") for r in rows)
    pending = status_counts.get("pending", 0)
    opened_rows = sum(1 for r in rows if r.get("opened_on"))
    vintages = [r.get("vintage") for r in rows if r.get("vintage") is not None]
    vintage_range = f"{min(vintages)}–{max(vintages)}" if vintages else "—"

    # Verdict tally (drunk + rated bottles)
    rated = {k: status_counts.get(k, 0) for k in ("love", "like", "meh", "pass")}

    out_path = cellar_path.parent / "cellar-view.html"

    # Build the HTML
    head_cells = "".join(
        f'<th data-key="{escape(key)}" data-type="{"num" if key in NUM_KEYS else "text"}">'
        f'{escape(label)}<span class="sort-arrow"></span></th>'
        for key, label in COLUMNS
    )

    body_rows = []
    for r in rows:
        status = r.get("status") or "cellared"
        cells = []
        for key, _ in COLUMNS:
            val = r.get(key)
            display = format_cell(key, val)
            sort_val = escape(str(val) if val not in (None, "") else "", quote=True)
            if key == "status":
                badge = (
                    f'<span class="badge badge-{escape(status)}">{escape(display)}</span>'
                    if status else ""
                )
                cells.append(f'<td data-sort="{escape(status)}">{badge}</td>')
                continue
            classes = []
            if key in WIDE_KEYS:
                classes.append("wide")
            if key == "verdict":
                classes.append("verdict")
            if key == "impressions":
                classes.append("impressions")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            # impressions display is pre-escaped (mixed markup) — others escape here
            content = display if key == "impressions" else escape(display)
            cells.append(f'<td{cls} data-sort="{sort_val}">{content}</td>')
        row_classes = [f"status-{status}"]
        if r.get("opened_on"):
            row_classes.append("opened")
        body_rows.append(f'<tr class="{" ".join(row_classes)}">{"".join(cells)}</tr>')
    body_html = "\n      ".join(body_rows)

    rated_html = " · ".join(
        f'<strong>{rated[k]}</strong> {STATUS_LABELS[k].split(" ")[-1].lower()}'
        for k in ("love", "like", "meh", "pass") if rated[k]
    ) or "none rated yet"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
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
    --pending: #fbf1d9;
    --pending-edge: #c79a2e;
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
  .pending-stat {{
    cursor: pointer;
    border: 1px solid var(--pending-edge);
    background: var(--pending);
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    color: #7a5a12 !important;
    user-select: none;
  }}
  .pending-stat:hover {{ filter: brightness(0.97); }}
  .pending-stat.active {{ background: var(--pending-edge); color: #fff !important; }}
  .pending-stat strong {{ color: inherit !important; }}
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
  /* Pending bottles awaiting your review — the actionable highlight. */
  tr.status-pending {{ background: var(--pending); }}
  tr.status-pending td:first-child {{ box-shadow: inset 3px 0 0 var(--pending-edge); }}
  tr.status-pending:hover {{ background: #f6e9c8; }}
  /* Opened bottles read as quieter, italic. */
  tr.opened {{ color: var(--muted); font-style: italic; }}
  td.wide {{ max-width: 34ch; min-width: 18ch; font-size: 12px; }}
  td.verdict {{ font-style: italic; color: #5a4a30; }}
  td.impressions {{ font-size: 11.5px; color: #555; }}
  td:nth-child(2) {{ min-width: 16ch; font-style: normal; }}
  /* status badges */
  .badge {{
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    font-style: normal;
  }}
  .badge-pending  {{ background: #f6e3b0; color: #6b4e0e; }}
  .badge-cellared {{ background: #e6e1d8; color: #5c574e; }}
  .badge-love     {{ background: #2f7d4f; color: #fff; }}
  .badge-like     {{ background: #cfe7d4; color: #235c38; }}
  .badge-meh      {{ background: #e8e0d2; color: #7a6f55; }}
  .badge-pass     {{ background: #e9c9c4; color: #7a2d2d; }}
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
      <span><strong>{total_rows}</strong> bottles</span>
      <span class="pending-stat" id="pendingStat" title="Click to show only bottles awaiting your review"><strong>{pending}</strong> pending review</span>
      <span><strong>{opened_rows}</strong> opened</span>
      <span>Rated: {rated_html}</span>
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
    Click a column header to sort. Amber rows are pending your review. Opened bottles are italic.
  </footer>
<script>
(() => {{
  const table = document.getElementById("cellar");
  const tbody = table.querySelector("tbody");
  const filter = document.getElementById("filter");
  const pendingStat = document.getElementById("pendingStat");

  let sortKey = null;
  let sortDir = 1;
  let pendingOnly = false;

  function applyFilters() {{
    const q = filter.value.trim().toLowerCase();
    tbody.querySelectorAll("tr").forEach((r) => {{
      const matchesText = !q || r.textContent.toLowerCase().includes(q);
      const matchesPending = !pendingOnly || r.classList.contains("status-pending");
      r.style.display = (matchesText && matchesPending) ? "" : "none";
    }});
  }}

  function sortBy(th) {{
    const key = th.dataset.key;
    const type = th.dataset.type;
    if (sortKey === key) {{
      sortDir *= -1;
    }} else {{
      sortKey = key;
      sortDir = 1;
    }}
    table.querySelectorAll("th").forEach((h) => h.classList.remove("sort-asc", "sort-desc"));
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

  filter.addEventListener("input", applyFilters);
  if (pendingStat) {{
    pendingStat.addEventListener("click", () => {{
      pendingOnly = !pendingOnly;
      pendingStat.classList.toggle("active", pendingOnly);
      applyFilters();
    }});
  }}
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
