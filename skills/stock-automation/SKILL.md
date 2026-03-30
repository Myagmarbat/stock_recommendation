# Stock Automation Skill

## Purpose
Run the analysis pipeline automatically in background during US market hours, every 30 minutes, while preserving timestamped historical results.

## Schedule and Cadence
- Main cycle: every 30 minutes, weekdays during regular US market session.
- Default schedule window: `06:30–13:00 America/Los_Angeles` (09:30–16:00 ET), no weekends.
- Off-hours execution is manual by command.
- Hourly archive: store additional snapshot when minute is `00`.
- Daily archive: store additional snapshot near market close (around 16:00 local).
- Daily strategy summary: one generation per weekday after close (>=16:00 ET).
- Every cycle must run in this order:
  1. Post-analyze previous run.
  2. Learn from wrong recommendations.
  3. Apply updated parameters to current run.
  4. Publish new top-10 recommendations.

## Execution
1. Use runner script `scripts/run_agent.sh`.
2. Runner must execute the analysis module and write logs per run.
3. Prefer project virtual environment Python (`.venv/bin/python`) when available.

## Background Runtime (macOS)
- Install: `scripts/install_launchd.sh`
- Remove: `scripts/uninstall_launchd.sh`
- Launchd interval: scheduled calendar triggers every 30 minutes within market-hour windows.

## Storage Contract
- Daily root:
  - `data/daily/YYYYMMDD/` with isolated `runs/`, `latest/`, `history/`, `model/`, and `logs/`
  - `data/today` symlink for quick access to current day
- Per-run timestamp folder:
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/market_context.json`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/candidates.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.md`
- Latest rolling outputs:
  - `data/daily/YYYYMMDD/latest/top10.csv`
  - `data/daily/YYYYMMDD/latest/top10.md`
  - `data/daily/YYYYMMDD/latest/post_analysis.json`
  - `data/daily/YYYYMMDD/latest/portfolio_status.json`
  - `data/daily/YYYYMMDD/latest/portfolio_report.md`
  - `data/daily/YYYYMMDD/latest/alerts.json`
  - `data/daily/YYYYMMDD/latest/daily_summary.md`
- History files:
  - `data/daily/YYYYMMDD/history/top10_history.csv` (all runs)
  - `data/daily/YYYYMMDD/history/top10_hourly.csv` (hourly)
  - `data/daily/YYYYMMDD/history/top10_daily.csv` (daily)
  - `data/daily/YYYYMMDD/history/post_analysis_history.jsonl`
  - `data/daily/YYYYMMDD/history/equity_curve.csv`
  - `data/daily/YYYYMMDD/history/trades_log.csv`
  - `data/daily/YYYYMMDD/history/daily_summary_YYYYMMDD.md`
  - `data/daily/YYYYMMDD/history/daily_summary_state.json`
- Model/adaptation state:
  - `data/daily/YYYYMMDD/model/model_params.json`
- Logs:
  - `data/daily/YYYYMMDD/logs/run_<UTC_TIMESTAMP>.log`
  - `data/logs/launchd.out.log`
  - `data/logs/launchd.err.log`

## Reliability Rules
- Never stop the scheduler because of one failed fetch.
- On upstream failure, write a stale snapshot with explicit status note and error message.
- Preserve previous latest output for continuity.

## Recommendation Output Requirement
Each run must produce top-10 recommendations with direction:
- Stock direction: buy, short sell, or hold.
- Option direction: buy call, buy put, or no option.
- Default conservative profile: stock-only (`action_option=NO_OPTION`).
- Trade-level direction:
  - buy/short at (`entry_price`)
  - sell/cover at (`target_price`)
  - stop at (`stop_price`)
  - `risk_reward`
- Include execution timing from market-hours status:
  - `NOW` when market is open
  - `NEXT_MARKET_OPEN` when market is closed.
