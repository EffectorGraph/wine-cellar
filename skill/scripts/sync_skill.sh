#!/usr/bin/env bash
# sync_skill.sh — install the wine skills for Codex and Claude, then point them at this repo.
#
# Run this once after cloning, and again after any `git pull` that touches skill files.
# Works for any user — path discovery is based on git rev-parse.

set -euo pipefail

# Find repo root (must be run from somewhere inside the clone)
if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "ERROR: must be run from inside the wine-cellar git repo." >&2
  exit 1
fi

WINE_CELLAR_SRC="$REPO_ROOT/skill"
INSTALL_ROOTS=("$HOME/.agents/skills" "$HOME/.claude/skills")
COMPANION_SKILLS=("wine-buying" "wine-inventory-refresh" "wine-tonight-recommendation")

if [ ! -d "$WINE_CELLAR_SRC" ]; then
  echo "ERROR: $WINE_CELLAR_SRC does not exist. Are you in the wine-cellar repo?" >&2
  exit 1
fi

write_config() {
  local skill_dst="$1"
  printf '{\n  "repo_path": "%s"\n}\n' "$REPO_ROOT" > "$skill_dst/.local-config.json"
}

install_wine_cellar() {
  local install_root="$1"
  local skill_dst="$install_root/wine-cellar"

  mkdir -p "$skill_dst/scripts"
  cp "$WINE_CELLAR_SRC/SKILL.md" "$skill_dst/SKILL.md"
  cp "$WINE_CELLAR_SRC/scripts/schema.py" "$skill_dst/scripts/schema.py"
  cp "$WINE_CELLAR_SRC/scripts/append_wine.py" "$skill_dst/scripts/append_wine.py"
  cp "$WINE_CELLAR_SRC/scripts/update_wine.py" "$skill_dst/scripts/update_wine.py"
  cp "$WINE_CELLAR_SRC/scripts/generate_view.py" "$skill_dst/scripts/generate_view.py"
  cp "$WINE_CELLAR_SRC/scripts/test_backend.py" "$skill_dst/scripts/test_backend.py"
  cp "$WINE_CELLAR_SRC/scripts/sync_skill.sh" "$skill_dst/scripts/sync_skill.sh"
  chmod +x "$skill_dst/scripts/"*.py "$skill_dst/scripts/sync_skill.sh"
  write_config "$skill_dst"
  echo "✓ wine-cellar installed at $skill_dst"
}

install_companion() {
  local install_root="$1"
  local skill_name="$2"
  local skill_src="$REPO_ROOT/$skill_name"
  local skill_dst="$install_root/$skill_name"

  if [ ! -d "$skill_src" ]; then
    echo "ERROR: companion skill source missing: $skill_src" >&2
    exit 1
  fi

  mkdir -p "$skill_dst"
  cp -R "$skill_src/." "$skill_dst/"
  write_config "$skill_dst"
  echo "✓ $skill_name installed at $skill_dst"
}

for install_root in "${INSTALL_ROOTS[@]}"; do
  install_wine_cellar "$install_root"
  for skill_name in "${COMPANION_SKILLS[@]}"; do
    install_companion "$install_root" "$skill_name"
  done
done

echo
echo "Next steps:"
echo "  1. Restart your Codex and Claude sessions to pick up skill changes"
echo "  2. (First-time setup only) cd $REPO_ROOT && git config core.hooksPath .githooks"
