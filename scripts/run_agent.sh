#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi
AGENT_CONFIG_PATH="${AGENT_CONFIG_PATH:-$ROOT_DIR/config/agent_config.json}"
ENABLE_AFTER_HOURS="${ENABLE_AFTER_HOURS:-0}"
FORCE="${FORCE:-0}"
DAILY_EVALUATION_ONLY="${DAILY_EVALUATION_ONLY:-0}"
DAY_KEY="${DAY_KEY:-$(date +%Y%m%d)}"
BASE_DIR="${BASE_DIR:-$ROOT_DIR/data/daily/$DAY_KEY}"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"
mkdir -p "$ROOT_DIR/data/daily"
ln -sfn "$BASE_DIR" "$ROOT_DIR/data/today"

TS="$(date -u +"%Y%m%d_%H%M%S")"
LOG_FILE="$LOG_DIR/run_${TS}.log"

EXTRA_ARGS=()
if [[ "$ENABLE_AFTER_HOURS" == "1" ]]; then
  EXTRA_ARGS+=(--enable-after-hours)
fi

if [[ "$ENABLE_AFTER_HOURS" != "1" && "$FORCE" != "1" ]]; then
  weekday="$(TZ=America/Los_Angeles date +%u)"
  hour="$(TZ=America/Los_Angeles date +%H)"
  minute="$(TZ=America/Los_Angeles date +%M)"
  now_minutes=$((10#$hour * 60 + 10#$minute))
  open_minutes=$((6 * 60 + 30))
  close_minutes=$((13 * 60))
  evaluation_end_minutes=$((13 * 60 + 15))

  if [[ "$weekday" -ge 1 && "$weekday" -le 5 && "$now_minutes" -ge "$open_minutes" && "$now_minutes" -lt "$close_minutes" ]]; then
    :
  elif [[ "$weekday" -ge 1 && "$weekday" -le 5 && "$now_minutes" -ge "$close_minutes" && "$now_minutes" -lt "$evaluation_end_minutes" ]]; then
    DAILY_EVALUATION_ONLY=1
  else
    {
      echo "Skipped scheduled run outside regular market schedule window."
      echo "Current PT time: $(TZ=America/Los_Angeles date '+%Y-%m-%d %H:%M:%S %Z')"
      echo "Allowed scan window: weekdays 06:30 <= time < 13:00 PT"
      echo "Allowed final evaluation window: weekdays 13:00 <= time < 13:15 PT"
      echo "Use FORCE=1 for a manual off-hours run or ENABLE_AFTER_HOURS=1 for after-hours processing."
    } >> "$LOG_FILE" 2>&1
    echo "Skipped scheduled run outside allowed PT weekday windows. See $LOG_FILE"
    exit 0
  fi
fi

if [[ "$DAILY_EVALUATION_ONLY" == "1" ]]; then
  EXTRA_ARGS+=(--daily-evaluation-only)
fi

CMD=(
  "$PYTHON_BIN"
  stock_option_agent/agent.py
  --base-dir "$BASE_DIR"
  --universe-count 50
  --config "$AGENT_CONFIG_PATH"
)
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  CMD+=("${EXTRA_ARGS[@]}")
fi

"${CMD[@]}" >> "$LOG_FILE" 2>&1
