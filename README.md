# Wine Cellar

A shared wine cellar managed with JSONL and GitHub. The source of truth is `cellar.jsonl`; GitHub Actions validates it and rebuilds the read-only HTML view after source changes. A successful data save and a successful view build/publication are separate outcomes.

The intended public read-only view is <https://effectorgraph.github.io/wine-cellar/cellar-view.html>. Its availability depends on GitHub Pages publication; do not assume a recent save is visible until Actions confirms it.

## Skills

- [`wine-cellar`](skill/SKILL.md): add bottles, set opening-year targets, and record opening or tasting feedback.
- [`wine-buying`](wine-buying/SKILL.md): concise store recommendations and logging confirmed purchases.
- [`wine-tonight-recommendation`](wine-tonight-recommendation/SKILL.md): choose an owned bottle for tonight.
- [`wine-inventory-refresh`](wine-inventory-refresh/SKILL.md): refresh or troubleshoot the local store inventory index at home.
- [`AGENTS.md`](AGENTS.md): canonical data-safety, phone-shopping, and shared workflow guide. `CLAUDE.md` imports it.

## Data and generated files

| Path | Purpose |
|---|---|
| `cellar.jsonl` | Source of truth; one complete bottle record per line, including stable `bottle_id`, facts, status, verdict, and impressions. |
| `preferences.json` | Living taste profile informed by recorded verdicts. |
| `cellar-view.html` | Generated, read-only view. Do not edit by hand. |
| `skill/scripts/` | Schema, local JSONL helpers, guarded updates, and validation. |
| `inventory/totalwine-centennial.jsonl` | Local snapshot of in-stock wines over $20 at Total Wine Centennial #2302. |
| `inventory/query_inventory.py` | Filters the local store index and prints matches only. |
| `inventory/SCHEMA.md` | Store index fields and scanner data path; read before changing the scanner. |

Bottle status describes what happened after purchase. `pending` means owned and awaiting review, which may include an opening-year choice; optional research gaps can be deferred. `cellared` means owned and unopened; `opened` means opened without a settled verdict; `love`, `like`, `meh`, and `pass` record a verdict; `finished` records consumption without a rating. Do not infer purchase or consumption from a recommendation.

Use GitHub MCP to fetch the current complete `cellar.jsonl` and its SHA before a phone edit. Update the full file with that SHA as the expected version. If it changed, refetch and reapply only the user's confirmed intent. Local updates should use the scripts' SHA guard. Preserve bottle IDs, ratings, and impression history.

## Local setup

Clone the repository and run:

```bash
bash skill/scripts/sync_skill.sh
```

The installer places the four skills in Codex and Claude skill directories, copies the canonical `AGENTS.md` reference, and writes a per-user `.local-config.json` that points to this clone. Restart the client after installing or updating the skills.

To enable local Git checks, configure the repository's hooks once:

```bash
git config core.hooksPath .githooks
```

For local development, use the helpers under `skill/scripts/` and check the latest `AGENTS.md` workflow before changing data. Source-data save, validation, HTML rebuild, and publication should be reported as separate steps.

## Store inventory

The local inventory index is a convenience snapshot, not guaranteed live stock. At the store, query it with `inventory/query_inventory.py`; do not load the raw JSONL or scrape the live site. If it is missing or stale, say that availability is unverified and recommend from the cellar and known preferences. Refresh at home with `wine-inventory-refresh`.
