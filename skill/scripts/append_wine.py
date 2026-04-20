#!/usr/bin/env python3
"""Append one wine to /Users/sarah/.../cellar.jsonl.

Reads a JSON object from stdin with these keys (all required; use null or "" for blanks):

  wine, winery, vintage, grapes, subregion, region, country, estate,
  soil, elevation, vine_age, importer,
  harvest_date, fermentation_vessel, whole_bunch_pct, malolactic,
  barrel_time, oak_origin, new_oak_pct,
  abv, ph, ta, residual_sugar,
  cases_produced, release_date,
  drink_from, cellared_under, drink_by, opened_on,
  tasting_notes, fallback_tasting_notes

Typed fields:
  - int (required):          vintage, drink_from, cellared_under, drink_by
  - int (optional/nullable): whole_bunch_pct, new_oak_pct, cases_produced
  - float (optional):        abv, ph, ta, residual_sugar
  - str: everything else. `estate` should be "Yes"/"No"/blank.
    `opened_on`, `harvest_date`, `release_date` are ISO date strings or descriptive.
    `soil`, `elevation`, `vine_age` use the `~` prefix convention for inferred values.

Path discovery (in order):
  1. WINE_CELLAR_PATH env var — absolute path to cellar.jsonl (override)
  2. ~/.claude/skills/wine-cellar/.local-config.json → {"repo_path": "..."}; cellar.jsonl = repo_path + "/cellar.jsonl"
  3. Fallback: print instructions and exit non-zero

Prints a JSON verification blob on stdout after writing.
"""
import json
import os
import sys
from pathlib import Path

# Schema definition — these drive validation
REQUIRED_KEYS = [
    "wine", "winery", "vintage", "grapes", "subregion", "region",
    "country", "estate", "soil", "elevation", "vine_age", "importer",
    "harvest_date", "fermentation_vessel", "whole_bunch_pct", "malolactic",
    "barrel_time", "oak_origin", "new_oak_pct",
    "abv", "ph", "ta", "residual_sugar",
    "cases_produced", "release_date",
    "drink_from", "cellared_under", "drink_by", "opened_on",
    "tasting_notes", "fallback_tasting_notes",
]
REQUIRED_INTS = ("vintage", "drink_from", "cellared_under", "drink_by")
OPTIONAL_INTS = ("whole_bunch_pct", "new_oak_pct", "cases_produced")
OPTIONAL_FLOATS = ("abv", "ph", "ta", "residual_sugar")


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


def blank(v):
    return None if v in (None, "") else v


def check_int(name, v, required):
    if v is None or v == "":
        if required:
            print(f"ERROR: {name} is required and must be an integer", file=sys.stderr)
            return False
        return True
    if not isinstance(v, int) or isinstance(v, bool):
        print(
            f"ERROR: {name} must be a JSON integer (or null for optional fields), "
            f"got {type(v).__name__}={v!r}",
            file=sys.stderr,
        )
        return False
    return True


def check_float(name, v):
    if v is None or v == "":
        return True
    if isinstance(v, bool):
        print(f"ERROR: {name} must be a number (or null), got bool", file=sys.stderr)
        return False
    if not isinstance(v, (int, float)):
        print(
            f"ERROR: {name} must be a JSON number (or null), got {type(v).__name__}={v!r}",
            file=sys.stderr,
        )
        return False
    return True


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON on stdin: {e}", file=sys.stderr)
        return 2

    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        print(f"ERROR: missing keys: {missing}", file=sys.stderr)
        return 2

    ok = True
    for k in REQUIRED_INTS:
        ok &= check_int(k, data[k], required=True)
    for k in OPTIONAL_INTS:
        ok &= check_int(k, data[k], required=False)
    for k in OPTIONAL_FLOATS:
        ok &= check_float(k, data[k])
    if not ok:
        return 2

    # Build the output object with normalized blanks and the canonical key order
    obj = {}
    for k in REQUIRED_KEYS:
        v = data[k]
        if k in REQUIRED_INTS:
            obj[k] = v  # already int-validated
        else:
            obj[k] = blank(v)

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
