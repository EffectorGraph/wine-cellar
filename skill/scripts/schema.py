"""Shared schema definition for the wine-cellar backend scripts.

Single source of truth for the JSONL field order, types, and validation —
imported by append_wine.py, update_wine.py, and generate_view.py so the three
never drift apart.

The row has 34 keys: 31 objective (technical) fields followed by 3 subjective
(feedback) fields. Feedback fields were added on top of the original schema and
are optional on input (defaulted), so older 31-key payloads still append cleanly.
"""
from __future__ import annotations

import sys

# ─────────────────────────────────────────────────────────────────────
# Canonical field order. Output rows always use exactly this order so git
# diffs stay readable.
# ─────────────────────────────────────────────────────────────────────
OBJECTIVE_KEYS = [
    "wine", "winery", "vintage", "grapes", "subregion", "region",
    "country", "estate", "soil", "elevation", "vine_age", "importer",
    "harvest_date", "fermentation_vessel", "whole_bunch_pct", "malolactic",
    "barrel_time", "oak_origin", "new_oak_pct",
    "abv", "ph", "ta", "residual_sugar",
    "cases_produced", "release_date",
    "drink_from", "cellared_under", "drink_by", "opened_on",
    "tasting_notes", "fallback_tasting_notes",
]

# Subjective layer (ported from green-tea-log): a categorical verdict, a prose
# summary, and an evolving impressions log. No numeric scores.
FEEDBACK_KEYS = ["status", "verdict", "impressions"]

CANONICAL_KEYS = OBJECTIVE_KEYS + FEEDBACK_KEYS

# ─────────────────────────────────────────────────────────────────────
# Type rules.
#   cellared_under is the user's target open year — optional now, because
#   bottles staged at the store ("pending") don't have it until review.
# ─────────────────────────────────────────────────────────────────────
REQUIRED_INTS = ("vintage", "drink_from", "drink_by")
OPTIONAL_INTS = ("whole_bunch_pct", "new_oak_pct", "cases_produced", "cellared_under")
OPTIONAL_FLOATS = ("abv", "ph", "ta", "residual_sugar")

# status lifecycle: pending (staged, awaiting review) → cellared (reviewed,
# target year set, not yet drunk) → a verdict once drunk. Mirrors the
# green-tea love/maybe/reject vocabulary.
ALLOWED_STATUS = ("pending", "cellared", "love", "like", "meh", "pass")

FEEDBACK_DEFAULTS = {
    "status": "cellared",
    "verdict": None,
    "impressions": [],
}


def blank(v):
    """Normalize empty string to None; pass everything else through."""
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


def check_status(v):
    if v not in ALLOWED_STATUS:
        print(
            f"ERROR: status must be one of {ALLOWED_STATUS}, got {v!r}",
            file=sys.stderr,
        )
        return False
    return True


def check_impressions(v):
    """impressions must be a list of {date, note} objects."""
    if not isinstance(v, list):
        print(f"ERROR: impressions must be a JSON array, got {type(v).__name__}", file=sys.stderr)
        return False
    for i, item in enumerate(v):
        if not isinstance(item, dict) or "date" not in item or "note" not in item:
            print(
                f"ERROR: impressions[{i}] must be an object with 'date' and 'note', got {item!r}",
                file=sys.stderr,
            )
            return False
    return True


def validate(obj, *, require_objective=True):
    """Validate a row dict in place. Returns True if all checks pass.

    require_objective=False relaxes the presence check (used by update_wine,
    which only supplies the fields being changed).
    """
    ok = True
    if require_objective:
        missing = [k for k in OBJECTIVE_KEYS if k not in obj]
        if missing:
            print(f"ERROR: missing keys: {missing}", file=sys.stderr)
            return False
    for k in REQUIRED_INTS:
        if k in obj:
            ok &= check_int(k, obj[k], required=require_objective)
    for k in OPTIONAL_INTS:
        if k in obj:
            ok &= check_int(k, obj[k], required=False)
    for k in OPTIONAL_FLOATS:
        if k in obj:
            ok &= check_float(k, obj[k])
    if "status" in obj and obj["status"] is not None:
        ok &= check_status(obj["status"])
    if "impressions" in obj and obj["impressions"] is not None:
        ok &= check_impressions(obj["impressions"])
    return ok


def normalize(data):
    """Build a full 34-key row in canonical order from an input dict.

    Objective string fields get blank-normalized; feedback fields fall back to
    their defaults when absent. Integer fields are passed through as validated.
    """
    obj = {}
    for k in OBJECTIVE_KEYS:
        v = data.get(k)
        if k in REQUIRED_INTS or k in OPTIONAL_INTS or k in OPTIONAL_FLOATS:
            obj[k] = None if v in ("",) else v
        else:
            obj[k] = blank(v)
    for k in FEEDBACK_KEYS:
        if k in data and data[k] is not None:
            obj[k] = data[k]
        else:
            obj[k] = FEEDBACK_DEFAULTS[k]
    return obj
