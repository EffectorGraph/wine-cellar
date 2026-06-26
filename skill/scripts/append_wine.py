#!/usr/bin/env python3
"""Append one wine to cellar.jsonl.

Reads a JSON object from stdin with the 31 objective keys (all present; use null
or "" for blanks). The 3 feedback keys (status, verdict, impressions) are
optional and default to {status: "cellared", verdict: null, impressions: []} —
the wine-buying skill passes status: "pending" when staging a store purchase.

  wine, winery, vintage, grapes, subregion, region, country, estate,
  soil, elevation, vine_age, importer,
  harvest_date, fermentation_vessel, whole_bunch_pct, malolactic,
  barrel_time, oak_origin, new_oak_pct,
  abv, ph, ta, residual_sugar,
  cases_produced, release_date,
  drink_from, cellared_under, drink_by, opened_on,
  tasting_notes, fallback_tasting_notes,
  [status, verdict, impressions]

Typed fields:
  - int (required):          vintage, drink_from, drink_by
  - int (optional/nullable): whole_bunch_pct, new_oak_pct, cases_produced, cellared_under
  - float (optional):        abv, ph, ta, residual_sugar
  - status: one of pending/cellared/love/like/meh/pass
  - impressions: JSON array of {date, note} objects
  - str: everything else.

Path discovery (in order):
  1. WINE_CELLAR_PATH env var — absolute path to cellar.jsonl (override)
  2. ~/.claude/skills/wine-cellar/.local-config.json → {"repo_path": "..."}
  3. Fallback: print instructions and exit non-zero

Prints a JSON verification blob on stdout after writing.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema  # noqa: E402


def resolve_cellar_path() -> Path:
    """Resolve the path to cellar.jsonl using the documented lookup order."""
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
        "  Run `bash <repo>/skill/scripts/sync_skill.sh` from inside your cloned wine-cellar repo\n"
        "  to install the skill and write the local config.\n"
        "  Or set WINE_CELLAR_PATH to the absolute path of cellar.jsonl.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON on stdin: {e}", file=sys.stderr)
        return 2

    if not schema.validate(data, require_objective=True):
        return 2

    obj = schema.normalize(data)

    cellar_path = resolve_cellar_path()
    if not cellar_path.exists():
        print(f"ERROR: cellar file not found: {cellar_path}", file=sys.stderr)
        return 2

    # Append one line
    line = json.dumps(obj, ensure_ascii=False)
    with cellar_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    # Count rows for verification
    with cellar_path.open(encoding="utf-8") as f:
        total_rows = sum(1 for _ in f)

    out = {
        "status": "ok",
        "cellar_path": str(cellar_path),
        "total_rows": total_rows,
        "appended": obj,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
