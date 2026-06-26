#!/usr/bin/env bash
# sync_skill.sh — install the wine-cellar skill into the current user's ~/.claude/skills/wine-cellar/
# and write a .local-config.json pointing at this repo.
#
# Run this once after cloning, and again after any `git pull` that touches skill files.
# Works for any user — path discovery is based on git rev-parse.

set -euo pipefail

# Find repo root (must be run from somewhere inside the clone)
if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: must be run from inside the wine-cellar git repo." >&2
  exit 1
fi

SKILL_SRC="$REPO_ROOT/skill"
SKILL_DST="$HOME/.claude/skills/wine-cellar"

if [ ! -d "$SKILL_SRC" ]; then
  echo "ERROR: $SKILL_SRC does not exist. Are you in the wine-cellar repo?" >&2
  exit 1
fi

# Create destination + scripts subdir
mkdir -p "$SKILL_DST/scripts"

# Copy skill files
cp "$SKILL_SRC/SKILL.md" "$SKILL_DST/SKILL.md"
cp "$SKILL_SRC/scripts/schema.py" "$SKILL_DST/scripts/schema.py"
cp "$SKILL_SRC/scripts/append_wine.py" "$SKILL_DST/scripts/append_wine.py"
cp "$SKILL_SRC/scripts/update_wine.py" "$SKILL_DST/scripts/update_wine.py"
cp "$SKILL_SRC/scripts/generate_view.py" "$SKILL_DST/scripts/generate_view.py"
cp "$SKILL_SRC/scripts/test_backend.py" "$SKILL_DST/scripts/test_backend.py"
cp "$SKILL_SRC/scripts/sync_skill.sh" "$SKILL_DST/scripts/sync_skill.sh"
chmod +x "$SKILL_DST/scripts/"*.py "$SKILL_DST/scripts/sync_skill.sh"

# Remove any obsolete xlsx-era scripts that might still be in the destination
for obsolete in fix_widths.py; do
  if [ -f "$SKILL_DST/scripts/$obsolete" ]; then
    echo "  Removing obsolete: $SKILL_DST/scripts/$obsolete"
    rm "$SKILL_DST/scripts/$obsolete"
  fi
done

# Write local config — points the Python scripts at this repo's cellar.jsonl
CONFIG_PATH="$SKILL_DST/.local-config.json"
cat > "$CONFIG_PATH" <<EOF
{
  "repo_path": "$REPO_ROOT"
}
EOF

echo "✓ Skill installed at $SKILL_DST"
echo "✓ Config written: $CONFIG_PATH"
echo "  repo_path → $REPO_ROOT"

# ── Companion wine-buying skill (shares this repo's cellar + backend scripts) ──
BUYING_SRC="$REPO_ROOT/wine-buying"
BUYING_DST="$HOME/.claude/skills/wine-buying"
if [ -d "$BUYING_SRC" ]; then
  mkdir -p "$BUYING_DST"
  cp "$BUYING_SRC/SKILL.md" "$BUYING_DST/SKILL.md"
  cat > "$BUYING_DST/.local-config.json" <<EOF
{
  "repo_path": "$REPO_ROOT"
}
EOF
  echo "✓ wine-buying skill installed at $BUYING_DST"
fi
echo ""
echo "Next steps:"
echo "  1. Restart your Claude session to pick up skill changes"
echo "  2. (First-time setup only) cd $REPO_ROOT && git config core.hooksPath .githooks"
