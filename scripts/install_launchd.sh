#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.local.stock_option_agent.plist"

mkdir -p "$HOME/Library/LaunchAgents"

{
cat <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.local.stock_option_agent</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$ROOT_DIR/scripts/run_agent.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <array>
PLIST

# Weekdays only, every 30 minutes during US regular market hours in Pacific Time:
# 06:30 to 13:00 PT (09:30 to 16:00 ET)
for weekday in 1 2 3 4 5; do
  cat <<PLIST
      <dict><key>Weekday</key><integer>$weekday</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
PLIST
  for hour in 7 8 9 10 11 12; do
    for minute in 0 30; do
      cat <<PLIST
      <dict><key>Weekday</key><integer>$weekday</integer><key>Hour</key><integer>$hour</integer><key>Minute</key><integer>$minute</integer></dict>
PLIST
    done
  done
  cat <<PLIST
      <dict><key>Weekday</key><integer>$weekday</integer><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
PLIST
done

cat <<PLIST
    </array>

    <key>WorkingDirectory</key>
    <string>$ROOT_DIR</string>

    <key>StandardOutPath</key>
    <string>$ROOT_DIR/data/logs/launchd.out.log</string>

    <key>StandardErrorPath</key>
    <string>$ROOT_DIR/data/logs/launchd.err.log</string>
</dict>
</plist>
PLIST
} > "$PLIST_PATH"

mkdir -p "$ROOT_DIR/data/logs"
launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Installed and loaded: $PLIST_PATH"
echo "Runs weekdays 06:30-13:00 PT every 30 minutes (market hours only)."
