#!/usr/bin/env python3
"""Patch cellar rows by stable bottle ID or an unambiguous wine/vintage key.

Normal update: {"match":{"bottle_id":"..."},"set":{...},
               "append_impression":{"date":"...","note":"..."}}
Finish quantity: {"action":"finish","match":{"wine":"...","vintage":2021},
                  "count":2,"set":{"opened_on":null}}
`expected_sha256` is optional; when supplied it prevents overwriting a newer
local file. Finish selection orders identical bottles by cellared_under, null
last, then original file order.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema  # noqa: E402


def resolve_cellar_path() -> Path:
    env_path = os.environ.get("WINE_CELLAR_PATH")
    if env_path:
        return Path(env_path)
    repo_path = Path(__file__).resolve().parents[2] / "cellar.jsonl"
    if repo_path.exists():
        return repo_path
    for install_root in (".agents", ".claude"):
        cfg_path = Path.home() / install_root / "skills" / "wine-cellar" / ".local-config.json"
        if not cfg_path.exists():
            continue
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
            repo = config.get("repo_path")
            if repo:
                return Path(repo) / "cellar.jsonl"
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"could not read {cfg_path}: {exc}") from exc
    raise ValueError("cellar.jsonl path not configured; set WINE_CELLAR_PATH")


def _matching_indices(rows, match, *, allow_many=False):
    if not isinstance(match, dict):
        raise ValueError("match must be an object")
    if match.get("bottle_id"):
        hits = [i for i, row in enumerate(rows) if row.get("bottle_id") == match["bottle_id"]]
        if len(hits) > 1:
            raise ValueError(f"bottle_id {match['bottle_id']!r} appears more than once")
        return hits
    if "wine" not in match or "vintage" not in match:
        raise ValueError("match must include bottle_id or both wine and vintage")
    hits = [i for i, row in enumerate(rows)
            if row.get("wine") == match["wine"] and row.get("vintage") == match["vintage"]]
    if len(hits) > 1 and not allow_many:
        raise ValueError(f"{len(hits)} rows match wine and vintage; use bottle_id")
    return hits


class ConcurrentWriteError(Exception):
    pass


def _atomic_write(path, rows, expected_hash=None):
    path = Path(path)
    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    mode = path.stat().st_mode
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, mode)
        if expected_hash is not None and schema.sha256_file(path) != expected_hash:
            raise ConcurrentWriteError("cellar changed during update; refusing conflicting write")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _update_locked(req, cellar_path) -> int:
    if not cellar_path.exists():
        print(f"ERROR: cellar file not found: {cellar_path}", file=sys.stderr)
        return 2
    expected_hash = req.get("expected_sha256")
    observed_hash = schema.sha256_file(cellar_path)
    if expected_hash is not None and expected_hash != observed_hash:
        print("ERROR: cellar changed since it was read; refusing conflicting write", file=sys.stderr)
        return 3
    write_guard_hash = expected_hash or observed_hash
    try:
        rows = schema.load_cellar(cellar_path)
        matched = _matching_indices(rows, req.get("match"), allow_many=req.get("action") == "finish")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not matched:
        print("ERROR: no matching bottle", file=sys.stderr)
        return 2

    action = req.get("action")
    set_keys = req.get("set") or {}
    if not isinstance(set_keys, dict):
        print("ERROR: set must be an object", file=sys.stderr)
        return 2
    unknown = [key for key in set_keys if key not in schema.CANONICAL_KEYS]
    if unknown or "bottle_id" in set_keys:
        print(f"ERROR: invalid or immutable set keys: {unknown or ['bottle_id']}", file=sys.stderr)
        return 2
    if set_keys.get("status") == "finished" and req.get("action") != "finish":
        print("ERROR: use action 'finish' to mark a bottle finished", file=sys.stderr)
        return 2
    impression = req.get("append_impression")
    if impression is not None and (not isinstance(impression, dict) or
                                   "date" not in impression or "note" not in impression):
        print("ERROR: append_impression must contain date and note", file=sys.stderr)
        return 2

    if action == "finish":
        protected = [key for key in ("verdict", "impressions") if key in set_keys]
        if protected:
            print("ERROR: finish preserves verdict/impressions; do not set feedback fields", file=sys.stderr)
            return 2
        count = req.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            print("ERROR: finish requires a positive integer count", file=sys.stderr)
            return 2
        explicit_id = bool((req.get("match") or {}).get("bottle_id"))
        eligible = [i for i in matched
                    if rows[i].get("status") in ("pending", "cellared", "opened")
                    and (explicit_id or not schema.has_status_date_conflict(rows[i]))]
        eligible.sort(key=lambda i: (rows[i].get("cellared_under") is None,
                                     rows[i].get("cellared_under") or 0, i))
        if count > len(eligible):
            if count <= len(matched) and all(
                rows[i].get("status") in ("love", "like", "meh", "pass", "finished")
                for i in matched
            ):
                print(json.dumps({"status": "ok", "no_op": True,
                                  "reason": "rated or already finished bottles are preserved",
                                  "updated_bottle_ids": []}, indent=2))
                return 0
            print(f"ERROR: requested {count} bottles, only {len(eligible)} unfinished match", file=sys.stderr)
            return 2
        targets = eligible[:count]
        set_keys = {**set_keys, "status": "finished"}
    elif action is not None:
        print(f"ERROR: unsupported action {action!r}", file=sys.stderr)
        return 2
    else:
        if len(matched) != 1:
            print("ERROR: updates by wine and vintage must match one row; use bottle_id", file=sys.stderr)
            return 2
        targets = matched

    updated_rows = []
    for idx in targets:
        row = dict(rows[idx])
        row.update(set_keys)
        if impression is not None:
            row["impressions"] = list(row.get("impressions") or []) + [impression]
        if not schema.validate_row(row):
            print(f"ERROR: update would leave invalid row for bottle_id {row.get('bottle_id')}", file=sys.stderr)
            return 2
        # Preserve every original field and its value; only touched fields change.
        rows[idx] = row
        updated_rows.append(row)

    try:
        _atomic_write(cellar_path, rows, write_guard_hash)
    except ConcurrentWriteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"status": "ok", "cellar_path": str(cellar_path),
                      "total_rows": len(rows), "updated": updated_rows,
                      "updated_bottle_ids": [r.get("bottle_id") for r in updated_rows]},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    try:
        req = json.load(sys.stdin)
        cellar_path = resolve_cellar_path()
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not isinstance(req, dict):
        print("ERROR: request must be a JSON object", file=sys.stderr)
        return 2
    try:
        with schema.locked_cellar(cellar_path):
            return _update_locked(req, cellar_path)
    except OSError as exc:
        print(f"ERROR: could not lock cellar: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
