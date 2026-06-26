#!/usr/bin/env python3
"""Patch one existing wine in cellar.jsonl, found by wine + vintage.

Used by the review flow (fill cellared_under, flip pending → cellared) and the
drink/feedback flow (set status/verdict, append a dated impression). Rewrites
only the matched line, preserving canonical key order.

Reads a JSON object from stdin:

  {
    "match": {"wine": "<exact name>", "vintage": 2021},
    "set":   {"cellared_under": 2032, "status": "cellared", ...},   // optional
    "append_impression": {"date": "2026-06-26", "note": "..."}      // optional
  }

`set` keys must be canonical schema keys. Exactly one row must match `match`
(0 or >1 is an error — disambiguate first). Prints a verification blob.

Path discovery matches append_wine.py.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema  # noqa: E402


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


def main() -> int:
    try:
        req = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON on stdin: {e}", file=sys.stderr)
        return 2

    match = req.get("match") or {}
    if not match.get("wine") or match.get("vintage") is None:
        print("ERROR: match must include 'wine' and 'vintage'", file=sys.stderr)
        return 2

    set_keys = req.get("set") or {}
    unknown = [k for k in set_keys if k not in schema.CANONICAL_KEYS]
    if unknown:
        print(f"ERROR: unknown keys in 'set': {unknown}", file=sys.stderr)
        return 2

    append_impression = req.get("append_impression")
    if append_impression is not None and not (
        isinstance(append_impression, dict)
        and "date" in append_impression and "note" in append_impression
    ):
        print("ERROR: append_impression must be an object with 'date' and 'note'", file=sys.stderr)
        return 2

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

    matches = [
        idx for idx, r in enumerate(rows)
        if r.get("wine") == match["wine"] and r.get("vintage") == match["vintage"]
    ]
    if not matches:
        print(f"ERROR: no row matches {match['wine']!r} {match['vintage']}", file=sys.stderr)
        return 2
    if len(matches) > 1:
        print(
            f"ERROR: {len(matches)} rows match {match['wine']!r} {match['vintage']} — disambiguate",
            file=sys.stderr,
        )
        return 2

    idx = matches[0]
    row = dict(rows[idx])

    # Apply the patch.
    row.update(set_keys)
    if append_impression is not None:
        impressions = list(row.get("impressions") or [])
        impressions.append(append_impression)
        row["impressions"] = impressions

    # Re-validate just the changed subset, then re-order to canonical 34 keys.
    changed = dict(set_keys)
    if append_impression is not None:
        changed["impressions"] = row["impressions"]
    if not schema.validate(changed, require_objective=False):
        return 2

    updated = schema.normalize(row)
    rows[idx] = updated

    # Rewrite the whole file (one line changed).
    with cellar_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out = {
        "status": "ok",
        "cellar_path": str(cellar_path),
        "matched": {"wine": match["wine"], "vintage": match["vintage"]},
        "total_rows": len(rows),
        "updated": updated,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
