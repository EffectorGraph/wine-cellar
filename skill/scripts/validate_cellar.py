#!/usr/bin/env python3
"""Validate every JSONL row; intended for local use and GitHub Actions."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema  # noqa: E402


def resolve_path():
    env_path = os.environ.get("WINE_CELLAR_PATH")
    if env_path:
        return Path(env_path)
    repo_path = Path(__file__).resolve().parents[2] / "cellar.jsonl"
    if repo_path.exists():
        return repo_path
    for install_root in (".agents", ".claude"):
        cfg_path = Path.home() / install_root / "skills" / "wine-cellar" / ".local-config.json"
        if cfg_path.exists():
            import json
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            if config.get("repo_path"):
                return Path(config["repo_path"]) / "cellar.jsonl"
    raise ValueError("cellar.jsonl not found; set WINE_CELLAR_PATH")


def main():
    try:
        if len(sys.argv) > 2:
            raise ValueError("usage: validate_cellar.py [path-to-cellar.jsonl]")
        path = Path(sys.argv[1]) if len(sys.argv) == 2 else resolve_path()
        rows = schema.load_cellar(path)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = []
    warnings = []
    ids = set()
    for line_number, row in enumerate(rows, 1):
        if not schema.validate_row(row):
            errors.append(f"row {line_number}: schema validation failed")
        bottle_id = row.get("bottle_id") if isinstance(row, dict) else None
        if bottle_id in ids:
            errors.append(f"row {line_number}: duplicate bottle_id {bottle_id!r}")
        if bottle_id:
            ids.add(bottle_id)
        if isinstance(row, dict) and schema.has_status_date_conflict(row):
            warnings.append(f"row {line_number}: status {row.get('status')!r} conflicts with opened_on")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"OK: {len(rows)} rows valid in {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
