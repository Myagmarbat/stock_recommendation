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
