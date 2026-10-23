#!/usr/bin/env python3
"""Round-trip tests for append_wine.py and update_wine.py.

Self-contained: seeds a throwaway cellar in a temp dir via WINE_CELLAR_PATH,
so it never touches the real cellar.jsonl. Run: python3 test_backend.py
Writes a results file alongside stdout to avoid truncation.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPEND = HERE / "append_wine.py"
UPDATE = HERE / "update_wine.py"
RESULTS = Path(tempfile.gettempdir()) / "wine_cellar_test_results.txt"

sys.path.insert(0, str(HERE))
from schema import (CANONICAL_KEYS, has_status_date_conflict, is_available, needs_review,
                    sha256_file, validate_row)  # noqa: E402

# A full payload plus quick-capture cases for fake bottles.
SAMPLE = {
    "wine": "Test Bottle Reserve", "winery": "Testing Estate", "vintage": 2021,
    "grapes": "Cabernet Sauvignon", "subregion": "Oakville", "region": "Napa Valley",
    "country": "USA", "estate": "Yes", "soil": "~Volcanic", "elevation": "~500 ft",
    "vine_age": None, "importer": None, "harvest_date": None,
    "fermentation_vessel": None, "whole_bunch_pct": None, "malolactic": None,
    "barrel_time": None, "oak_origin": None, "new_oak_pct": None, "abv": None,
    "ph": None, "ta": None, "residual_sugar": None, "cases_produced": None,
    "release_date": None, "drink_from": 2026, "cellared_under": None, "drink_by": 2040,
    "opened_on": None, "tasting_notes": None, "fallback_tasting_notes": None,
}

results = []


def run(script, payload, cellar):
    env = {**os.environ, "WINE_CELLAR_PATH": str(cellar)}
    p = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return p.returncode, p.stdout, p.stderr


def last_row(cellar):
    lines = [l for l in cellar.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1])


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    line = f"[{status}] {name}" + (f" — {detail}" if detail and not cond else "")
    results.append(line)
    print(line)
    return cond


def main():
    all_ok = True
    with tempfile.TemporaryDirectory() as td:
        cellar = Path(td) / "cellar.jsonl"
        cellar.write_text("")

        # 1. Stage a pending bottle with no cellared_under — must succeed.
        rc, out, err = run(APPEND, {**SAMPLE, "status": "pending"}, cellar)
        all_ok &= check("append: pending bottle, null cellared_under -> rc 0", rc == 0, err)
        row = last_row(cellar)
        all_ok &= check("append: row has canonical keys in order",
                        list(row.keys()) == CANONICAL_KEYS, list(row.keys()))
        all_ok &= check("append: status pending", row.get("status") == "pending")
        all_ok &= check("append: cellared_under is null", row.get("cellared_under") is None)
        all_ok &= check("append: impressions defaults to []", row.get("impressions") == [])
        all_ok &= check("append: verdict defaults to null", row.get("verdict") is None)
        all_ok &= check("append: stable bottle id assigned", bool(row.get("bottle_id")))

        # 2. Bad status value must be rejected.
        rc, out, err = run(APPEND, {**SAMPLE, "status": "bogus"}, cellar)
        all_ok &= check("append: bogus status -> nonzero exit", rc != 0)
        prior_count = len(cellar.read_text(encoding="utf-8").splitlines())
        rc, out, err = run(APPEND, {"wine": "Duplicate ID", "bottle_id": row.get("bottle_id")}, cellar)
        all_ok &= check("append: duplicate bottle ID rejected without append", rc != 0
                        and len(cellar.read_text(encoding="utf-8").splitlines()) == prior_count)

        # 3. Update: fill cellared_under + flip to cellared (review flow).
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021},
            "set": {"cellared_under": 2032, "status": "cellared"},
        }, cellar)
        all_ok &= check("update: set cellared_under + status -> rc 0", rc == 0, err)
        row = last_row(cellar)
        all_ok &= check("update: cellared_under now 2032", row.get("cellared_under") == 2032)
        all_ok &= check("update: status now cellared", row.get("status") == "cellared")
        all_ok &= check("update: key order preserved",
                        list(row.keys()) == CANONICAL_KEYS, list(row.keys()))

        # 4. Opening without feedback records the date without assigning a verdict.
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021},
            "set": {"status": "opened", "opened_on": "2026-06-26"},
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("update: opened before tasting -> rc 0", rc == 0, err)
        all_ok &= check("update: opening has no verdict or impressions",
                        row.get("status") == "opened" and row.get("opened_on") == "2026-06-26"
                        and row.get("verdict") is None and row.get("impressions") == [])

        # 5. Update: append an impression + set verdict + verdict status (drink flow).
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021},
            "set": {"status": "love", "verdict": "Punches above its weight.", "opened_on": "2026-06-26"},
            "append_impression": {"date": "2026-06-26", "note": "First pour: tight, opens after 30 min."},
        }, cellar)
        all_ok &= check("update: drink feedback -> rc 0", rc == 0, err)
        row = last_row(cellar)
        all_ok &= check("update: status love", row.get("status") == "love")
        all_ok &= check("update: verdict set", bool(row.get("verdict")))
        all_ok &= check("update: one impression appended", len(row.get("impressions", [])) == 1)
        original_verdict = row["verdict"]

        # 6. Append a second impression — array grows, not replaced.
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021},
            "append_impression": {"date": "2026-06-27", "note": "Next day, recorked: still bright."},
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("update: impressions now length 2", len(row.get("impressions", [])) == 2)

        # 8. Late finish preserves all feedback and allows unknown consumption date.
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"bottle_id": row["bottle_id"]}, "count": 1,
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("finish: rated bottle is an idempotent no-op", rc == 0 and json.loads(out).get("no_op"), err)
        all_ok &= check("finish: rated status and feedback preserved", row.get("status") == "love"
                        and row.get("verdict") == original_verdict and len(row.get("impressions", [])) == 2
                        and row.get("opened_on") == "2026-06-26")
        rc, out, err = run(UPDATE, {
            "match": {"bottle_id": row["bottle_id"]}, "set": {"status": "opened"},
        }, cellar)
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"bottle_id": row["bottle_id"]}, "count": 1,
            "append_impression": {"date": "2026-06-28", "note": "Bottle finished."},
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("finish: opened bottle marked finished", rc == 0 and row.get("status") == "finished", err)
        all_ok &= check("finish: verdict and impression history survive with append",
                        row.get("verdict") == original_verdict and len(row.get("impressions", [])) == 3
                        and row.get("impressions", [])[0].get("note", "").startswith("First pour"))

        # 9. Quick capture only needs a wine name; unknown window and vintage stay null.
        rc, out, err = run(APPEND, {"wine": "Quick Capture"}, cellar)
        row = last_row(cellar)
        all_ok &= check("append: quick capture with unknown vintage/window -> rc 0", rc == 0, err)
        all_ok &= check("append: quick capture unknowns are null", row.get("vintage") is None
                        and row.get("drink_from") is None and row.get("drink_by") is None)
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"bottle_id": row["bottle_id"]}, "count": 1,
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("finish: unknown opened date remains null", rc == 0 and row.get("opened_on") is None, err)

        # 10. A duplicated label/year is ambiguous for an ordinary update.
        duplicate = dict(row)
        duplicate["wine"] = "Test Bottle Reserve"
        duplicate["vintage"] = 2021
        duplicate["bottle_id"] = "00000000-0000-4000-8000-000000000002"
        duplicate["status"] = "cellared"
        duplicate["cellared_under"] = None
        with cellar.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(duplicate) + "\n")
        earliest = dict(duplicate)
        earliest["bottle_id"] = "00000000-0000-4000-8000-000000000003"
        earliest["cellared_under"] = 2030
        with cellar.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(earliest) + "\n")
        rated = dict(duplicate)
        rated["bottle_id"] = "00000000-0000-4000-8000-000000000004"
        rated["status"] = "love"
        rated["verdict"] = "Favorite vintage."
        with cellar.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(rated) + "\n")
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021}, "set": {"status": "like"},
        }, cellar)
        all_ok &= check("update: duplicate wine/vintage requires ID -> nonzero", rc != 0)
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"wine": "Test Bottle Reserve", "vintage": 2021}, "count": 1,
        }, cellar)
        final_rows = [json.loads(line) for line in cellar.read_text(encoding="utf-8").splitlines() if line.strip()]
        by_id = {r["bottle_id"]: r for r in final_rows}
        all_ok &= check("finish: lowest target year chosen; null-target duplicate remains",
                        rc == 0 and by_id[earliest["bottle_id"]]["status"] == "finished"
                        and by_id[duplicate["bottle_id"]]["status"] == "cellared"
                        and by_id[rated["bottle_id"]]["status"] == "love"
                        and by_id[rated["bottle_id"]]["verdict"] == "Favorite vintage.", err)

        # 11. File hash guard refuses a write after another local edit.
        expected = sha256_file(cellar)
        cellar.write_text(cellar.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        before_conflict = cellar.read_bytes()
        rc, out, err = run(UPDATE, {
            "expected_sha256": expected,
            "match": {"bottle_id": row["bottle_id"]}, "set": {"status": "cellared"},
        }, cellar)
        all_ok &= check("update: stale expected hash rejects conflicting write without overwrite",
                        rc == 3 and cellar.read_bytes() == before_conflict)

        all_ok &= check("review helper includes all pending rows",
                        needs_review({"status": "pending", "opened_on": None}))
        all_ok &= check("review helper flags cellared/opened contradiction",
                        needs_review({"status": "cellared", "opened_on": "2024-01-01"})
                        and has_status_date_conflict({"status": "cellared", "opened_on": "2024-01-01"}))
        legacy_estimate = dict(SAMPLE, bottle_id="00000000-0000-4000-8000-000000000001",
                              residual_sugar="~<3 g/L (estimated)")
        all_ok &= check("schema: accepts documented tilde estimate in numeric technical field",
                        validate_row({**legacy_estimate, "status": "cellared", "verdict": None, "impressions": []}))
        bad_target = {**legacy_estimate, "cellared_under": "~2030", "status": "cellared",
                      "verdict": None, "impressions": []}
        all_ok &= check("schema: cellared_under rejects estimated string", not validate_row(bad_target))
        all_ok &= check("availability: rated and opened rows are unavailable",
                        not is_available({"status": "love", "opened_on": None})
                        and not is_available({"status": "opened", "opened_on": "2026-06-26"}))

        # A contradictory row is excluded from name/vintage batch finish; explicit ID may resolve it.
        conflict_cellar = Path(td) / "conflict.jsonl"
        conflict_row = {**SAMPLE, "bottle_id": "00000000-0000-4000-8000-000000000010",
                        "status": "pending", "opened_on": "2026-06-26", "verdict": None, "impressions": []}
        conflict_cellar.write_text(json.dumps(conflict_row) + "\n", encoding="utf-8")
        before = conflict_cellar.read_bytes()
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"wine": conflict_row["wine"], "vintage": conflict_row["vintage"]},
            "count": 1,
        }, conflict_cellar)
        all_ok &= check("finish: batch excludes contradictory status/date row", rc != 0
                        and conflict_cellar.read_bytes() == before)
        rc, out, err = run(UPDATE, {
            "action": "finish", "match": {"bottle_id": conflict_row["bottle_id"]}, "count": 1,
        }, conflict_cellar)
        resolved = json.loads(conflict_cellar.read_text(encoding="utf-8"))
        all_ok &= check("finish: explicit bottle ID can resolve contradictory row",
                        rc == 0 and resolved["status"] == "finished", err)

        # Duplicate IDs are rejected as ambiguous even when the caller provides the ID.
        duplicate_id_cellar = Path(td) / "duplicate-id.jsonl"
        duplicate_id_cellar.write_text(json.dumps(conflict_row) + "\n" + json.dumps(conflict_row) + "\n",
                                       encoding="utf-8")
        rc, out, err = run(UPDATE, {
            "match": {"bottle_id": conflict_row["bottle_id"]}, "set": {"verdict": "changed"},
        }, duplicate_id_cellar)
        all_ok &= check("update: duplicate bottle ID rejected as ambiguous", rc != 0)

        # 7. No match -> error.
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Does Not Exist", "vintage": 1900},
            "set": {"status": "love"},
        }, cellar)
        all_ok &= check("update: no match -> nonzero exit", rc != 0)

    summary = f"\n{'ALL PASS' if all_ok else 'SOME FAILED'} — {len(results)} checks"
    print(summary)
    RESULTS.write_text("\n".join(results) + summary + "\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
