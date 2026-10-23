"""Shared JSONL schema and file helpers for the wine-cellar backend."""
from __future__ import annotations

import hashlib
import fcntl
import json
import math
import re
import sys
import uuid
from datetime import date
from contextlib import contextmanager
from pathlib import Path

OBJECTIVE_KEYS = [
    "bottle_id", "wine", "winery", "vintage", "grapes", "subregion", "region",
    "country", "estate", "soil", "elevation", "vine_age", "importer",
    "harvest_date", "fermentation_vessel", "whole_bunch_pct", "malolactic",
    "barrel_time", "oak_origin", "new_oak_pct", "abv", "ph", "ta",
    "residual_sugar", "cases_produced", "release_date", "drink_from",
    "cellared_under", "drink_by", "opened_on", "tasting_notes",
    "fallback_tasting_notes",
]
FEEDBACK_KEYS = ["status", "verdict", "impressions"]
CANONICAL_KEYS = OBJECTIVE_KEYS + FEEDBACK_KEYS
INTEGER_KEYS = ("vintage", "drink_from", "drink_by")
OPTIONAL_INTS = ("whole_bunch_pct", "new_oak_pct", "cases_produced", "cellared_under")
OPTIONAL_FLOATS = ("abv", "ph", "ta", "residual_sugar")
ALLOWED_STATUS = ("pending", "cellared", "opened", "love", "like", "meh", "pass", "finished")
FEEDBACK_DEFAULTS = {"status": "cellared", "verdict": None, "impressions": []}


def new_bottle_id() -> str:
    """Return a stable identifier for one physical bottle row."""
    return str(uuid.uuid4())


def needs_review(row: dict) -> bool:
    """Flag bottles awaiting review and impossible opened dates for unopened rows."""
    return (row.get("status") == "pending" or
            (row.get("status") in ("pending", "cellared") and bool(row.get("opened_on"))))


def has_status_date_conflict(row: dict) -> bool:
    """A pending/cellared row with an opened date has contradictory history."""
    return row.get("status") in ("pending", "cellared") and bool(row.get("opened_on"))


def is_available(row: dict) -> bool:
    """Unopened inventory available for choosing a bottle."""
    return row.get("status") in ("pending", "cellared") and not row.get("opened_on")


def available_for_finish(rows, wine=None, vintage=None):
    """Return available matching rows in finish order (target year, then null)."""
    candidates = [row for row in rows if is_available(row)
                  and (wine is None or row.get("wine") == wine)
                  and (vintage is None or row.get("vintage") == vintage)]
    return [row for _, row in sorted(
        enumerate(candidates),
        key=lambda pair: (pair[1].get("cellared_under") is None,
                          pair[1].get("cellared_under") or 0, pair[0]),
    )]


def blank(value):
    return None if value in (None, "") else value


def _check_int(name, value, *, required=False):
    if value in (None, ""):
        return not required
    return isinstance(value, int) and not isinstance(value, bool)


def _is_numeric_estimate(value):
    """Allow documented ~-prefixed estimates for optional technical values."""
    return isinstance(value, str) and bool(re.match(r"^~\s*[<>≤≥]?\s*\d", value))


def _is_iso_date(value):
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def validate(obj, *, require_objective=True, report=True):
    """Validate a row or partial patch. Optional drink-window years may be unknown."""
    errors = []
    if not isinstance(obj, dict):
        errors.append("row must be a JSON object")
    else:
        if require_objective:
            missing = [key for key in OBJECTIVE_KEYS if key not in obj]
            if missing:
                errors.append(f"missing keys: {missing}")
            if not obj.get("wine"):
                errors.append("wine is required")
            if not obj.get("bottle_id"):
                errors.append("bottle_id is required")
            elif not isinstance(obj["bottle_id"], str):
                errors.append("bottle_id must be a UUID string")
            else:
                try:
                    if str(uuid.UUID(obj["bottle_id"])) != obj["bottle_id"]:
                        raise ValueError("not canonical")
                except (ValueError, AttributeError):
                    errors.append("bottle_id must be a UUID string")
            if not isinstance(obj.get("wine"), str) or not obj.get("wine"):
                errors.append("wine must be a non-empty string")
            for key in FEEDBACK_KEYS:
                if key not in obj:
                    errors.append(f"missing key: {key}")
        for key in INTEGER_KEYS:
            if key in obj and not _check_int(key, obj[key]):
                errors.append(f"{key} must be an integer or null")
        for key in OPTIONAL_INTS:
            value = obj.get(key)
            estimate_ok = key != "cellared_under" and _is_numeric_estimate(value)
            if key in obj and not _check_int(key, value) and not estimate_ok:
                errors.append(f"{key} must be an integer, a ~-prefixed estimate, or null")
        for key in OPTIONAL_FLOATS:
            value = obj.get(key)
            if value is not None and (isinstance(value, bool) or
                                      (not isinstance(value, (int, float)) and
                                       not _is_numeric_estimate(value))):
                errors.append(f"{key} must be a number or null")
            elif isinstance(value, float) and not math.isfinite(value):
                errors.append(f"{key} must be finite")
        if "status" in obj and obj["status"] not in ALLOWED_STATUS:
            errors.append(f"status must be one of {ALLOWED_STATUS}")
        if "impressions" in obj:
            impressions = obj["impressions"]
            if not isinstance(impressions, list) or any(
                not isinstance(item, dict) or "date" not in item or "note" not in item
                for item in impressions
            ):
                errors.append("impressions must be an array of objects with date and note")
            elif any(not _is_iso_date(item["date"]) for item in impressions):
                errors.append("impression dates must use YYYY-MM-DD")
        if obj.get("opened_on") is not None and not _is_iso_date(obj["opened_on"]):
            errors.append("opened_on must use YYYY-MM-DD or null")
    if report:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return not errors


def validate_row(row):
    """Whole-row validation API used by the Actions validator and UI."""
    return validate(row, require_objective=True, report=False)


def normalize(data):
    """Build a canonical row; omitted facts are honest unknowns."""
    obj = {key: blank(data.get(key)) for key in OBJECTIVE_KEYS}
    if not obj["bottle_id"]:
        obj["bottle_id"] = new_bottle_id()
    for key, default in FEEDBACK_DEFAULTS.items():
        value = data.get(key)
        obj[key] = default if value is None else value
    return obj


def load_cellar(path):
    """Load JSONL rows with line-numbered errors; skip blank lines."""
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number} is invalid JSON: {exc}") from exc
    return rows


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def locked_cellar(path):
    """Serialize read-modify-write transactions across local skill processes."""
    lock_path = Path(path).with_name(".cellar.jsonl.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
