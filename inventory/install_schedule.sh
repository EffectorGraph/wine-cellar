#!/usr/bin/env bash
# install_schedule.sh — install (or reload) the biweekly launchd job that refreshes
# the #2302 store inventory. Run once after setup; re-run after moving the repo.
#
# Runs every 14 days in your login session (the stealth browser needs a GUI). If the
# Mac was off/asleep at the due time, launchd fires it at the next login. Disable with
#   launchctl unload ~/Library/LaunchAgents/com.wilterson.wine-inventory-refresh.plist

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.wilterson.wine-inventory-refresh"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$REPO/inventory/refresh_inventory.sh"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$WRAPPER</string>
  </array>
  <key>StartInterval</key><integer>1209600</integer>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>/dev/null</string>
  <key>StandardErrorPath</key><string>/dev/null</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✓ installed $LABEL — refreshes every 14 days"
echo "  plist:   $PLIST"
echo "  wrapper: $WRAPPER"
echo "  log:     $REPO/inventory/.refresh.log"
echo "  check:   launchctl list | grep wine"
echo "  run now: bash $WRAPPER"
echo "  disable: launchctl unload $PLIST"
