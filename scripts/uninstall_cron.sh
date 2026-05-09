#!/usr/bin/env bash
set -euo pipefail

MARKER_START="# stock_option_agent cron start"
MARKER_END="# stock_option_agent cron end"

existing_file="$(mktemp)"
new_file="$(mktemp)"
trap 'rm -f "$existing_file" "$new_file"' EXIT

crontab -l > "$existing_file" 2>/dev/null || true

awk -v start="$MARKER_START" -v end="$MARKER_END" '
  $0 == start { skip = 1; next }
  $0 == end { skip = 0; next }
  skip != 1 { print }
' "$existing_file" > "$new_file"

crontab "$new_file"

echo "Removed managed stock_option_agent cron entries."
