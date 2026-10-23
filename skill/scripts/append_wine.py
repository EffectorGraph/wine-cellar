#!/usr/bin/env python3
"""Append one wine to cellar.jsonl.

Reads a JSON object from stdin. A quick capture may include only `wine` and an
optional `vintage`; omitted facts are stored as null. The 3 feedback keys are
optional and default to {status: "cellared", verdict: null, impressions: []}.

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
  - int or null:             vintage, drink_from, drink_by
  - int (optional/nullable): whole_bunch_pct, new_oak_pct, cases_produced, cellared_under
  - float (optional):        abv, ph, ta, residual_sugar
  - status: one of pending/cellared/opened/love/like/meh/pass/finished
  - impressions: JSON array of {date, note} objects
  - str: everything else.

Path discovery (in order):
  1. WINE_CELLAR_PATH env var — absolute path to cellar.jsonl (override)
  2. Repository containing this script
  3. ~/.agents/skills/wine-cellar/.local-config.json or ~/.claude/... config
  4. Fallback: print instructions and exit non-zero

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

    local_cellar = Path(__file__).resolve().parents[2] / "cellar.jsonl"
    if local_cellar.exists():
        return local_cellar
    for install_root in (".agents", ".claude"):
        cfg_path = Path.home() / install_root / "skills" / "wine-cellar" / ".local-config.json"
        if not cfg_path.exists():
            continue
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


def _append_locked(obj, expected_hash, cellar_path) -> int:
    if not cellar_path.exists():
        print(f"ERROR: cellar file not found: {cellar_path}", file=sys.stderr)
        return 2

    try:
        original_hash = schema.sha256_file(cellar_path)
        rows = schema.load_cellar(cellar_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if expected_hash is not None and expected_hash != original_hash:
        print("ERROR: cellar changed since it was read; refusing conflicting write", file=sys.stderr)
        return 3
    write_guard_hash = expected_hash or original_hash
    if any(row.get("bottle_id") == obj["bottle_id"] for row in rows if isinstance(row, dict)):
        print(f"ERROR: bottle_id already exists: {obj['bottle_id']}", file=sys.stderr)
        return 2
    if schema.sha256_file(cellar_path) != write_guard_hash:
        print("ERROR: cellar changed during append; refusing conflicting write", file=sys.stderr)
        return 3

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


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON on stdin: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or not data.get("wine"):
        print("ERROR: input must be an object with a non-empty 'wine'", file=sys.stderr)
        return 2
    expected_hash = data.pop("expected_sha256", None)
    unknown = [key for key in data if key not in schema.CANONICAL_KEYS]
    if unknown:
        print(f"ERROR: unknown input keys: {unknown}", file=sys.stderr)
        return 2
    if not schema.validate(data, require_objective=False):
        return 2
    data = dict(data)
    if "status" not in data:
        ready = all(data.get(key) is not None for key in ("drink_from", "cellared_under", "drink_by"))
        data["status"] = "cellared" if ready else "pending"
    obj = schema.normalize(data)
    if not schema.validate_row(obj):
        print("ERROR: normalized input does not form a valid row", file=sys.stderr)
        return 2
    try:
        cellar_path = resolve_cellar_path()
        with schema.locked_cellar(cellar_path):
            return _append_locked(obj, expected_hash, cellar_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not lock or update cellar: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
