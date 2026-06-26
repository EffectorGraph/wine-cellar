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
from schema import CANONICAL_KEYS  # noqa: E402

# A schema-complete objective payload (the 31 technical keys) for a fake bottle.
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
        all_ok &= check("append: row has 34 keys in canonical order",
                        list(row.keys()) == CANONICAL_KEYS, list(row.keys()))
        all_ok &= check("append: status pending", row.get("status") == "pending")
        all_ok &= check("append: cellared_under is null", row.get("cellared_under") is None)
        all_ok &= check("append: impressions defaults to []", row.get("impressions") == [])
        all_ok &= check("append: verdict defaults to null", row.get("verdict") is None)

        # 2. Bad status value must be rejected.
        rc, out, err = run(APPEND, {**SAMPLE, "status": "bogus"}, cellar)
        all_ok &= check("append: bogus status -> nonzero exit", rc != 0)

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

        # 4. Update: append an impression + set verdict + verdict status (drink flow).
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

        # 5. Append a second impression — array grows, not replaced.
        rc, out, err = run(UPDATE, {
            "match": {"wine": "Test Bottle Reserve", "vintage": 2021},
            "append_impression": {"date": "2026-06-27", "note": "Next day, recorked: still bright."},
        }, cellar)
        row = last_row(cellar)
        all_ok &= check("update: impressions now length 2", len(row.get("impressions", [])) == 2)

        # 6. No match -> error.
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
