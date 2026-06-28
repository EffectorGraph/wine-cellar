#!/usr/bin/env bash
# refresh_inventory.sh — refresh the #2302 in-stock >$20 store index, at home.
# pull -> scan -> (only if the index changed) commit + push. Logs to .refresh.log.
# Safe: a blocked/empty scan leaves the index untouched and never commits.
#
# Run by hand (or via the wine-inventory-refresh skill), or by the biweekly
# launchd job (see install_schedule.sh). Must run in a logged-in GUI session so
# the stealth browser has a display.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$REPO/inventory/.refresh.log"
VENV_PY="$REPO/inventory/.venv/bin/python"
INDEX_REL="inventory/totalwine-centennial.jsonl"

# Interactive (by hand / skill): show output live AND log it. Under launchd (no
# TTY): append straight to the log so lines aren't duplicated.
if [ -t 1 ]; then
  exec > >(tee -a "$LOG") 2>&1
else
  exec >> "$LOG" 2>&1
fi

echo "===== refresh $(date '+%Y-%m-%d %H:%M:%S') ====="
cd "$REPO" || { echo "FATAL: repo not found at $REPO"; exit 1; }

if [ ! -x "$VENV_PY" ]; then
  echo "FATAL: venv python missing ($VENV_PY). Run: uv venv inventory/.venv && uv pip install --python $VENV_PY -r inventory/requirements.txt"
  exit 1
fi

git pull --ff-only || echo "WARN: git pull failed — continuing with local state"

"$VENV_PY" "$REPO/inventory/scan_store.py"
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "scan exited $RC — index left untouched, nothing committed"
  exit "$RC"
fi

if git diff --quiet -- "$INDEX_REL"; then
  echo "no inventory changes since last refresh"
  echo "===== done $(date '+%H:%M:%S') ====="
  exit 0
fi

git add "$INDEX_REL"
CHANGES="$REPO/inventory/.store-changes.txt"
SUMMARY="$( [ -f "$CHANGES" ] && cat "$CHANGES" || echo "inventory updated" )"
printf 'Inventory refresh %s\n\n%s\n' "$(date '+%Y-%m-%d')" "$SUMMARY" | git commit -F -

if GIT_TERMINAL_PROMPT=0 git push; then
  echo "pushed"
else
  echo "WARN: git push failed — commit is local, push manually later"
fi
echo "===== done $(date '+%H:%M:%S') ====="
