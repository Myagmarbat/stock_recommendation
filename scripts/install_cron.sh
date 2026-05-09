#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/scripts/run_agent.sh"
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

{
  printf "\n%s\n" "$MARKER_START"
  printf "# Weekdays, local machine time. Set the machine timezone to Pacific Time for US market hours.\n"
  printf "# The runner also guards against off-window execution using America/Los_Angeles time.\n"
  printf "30-59/5 6 * * 1-5 cd %q && /bin/bash %q\n" "$ROOT_DIR" "$RUNNER"
  printf "*/5 7-12 * * 1-5 cd %q && /bin/bash %q\n" "$ROOT_DIR" "$RUNNER"
  printf "5 13 * * 1-5 cd %q && /bin/bash %q\n" "$ROOT_DIR" "$RUNNER"
  printf "%s\n" "$MARKER_END"
} >> "$new_file"

crontab "$new_file"

echo "Installed cron entries for stock_option_agent."
echo "Runs weekdays every 5 minutes from 06:30-13:00 local time, plus evaluation at 13:05."
echo "For US market hours, keep this machine timezone set to Pacific Time."
