# Stock/Options Auto Scanner (Yahoo Finance)

Automated scanner that:
- Pulls top 50 symbols from Yahoo Finance market movers (default mix: 60% day gainers, 40% day losers).
- Runs fundamental + technical + news sentiment analysis.
- Adds quarterly earnings catalyst scoring (up to ~30 days pre-earnings) and checks if current price setup is favorable.
- Detects broad market trend (bullish/bearish/neutral) and adapts recommendations.
- Produces top 10 picks every run.
- Stores timestamped outputs for historical analysis.
- Runs every 30 minutes in background via `launchd` during market hours only (weekdays).
- Self-adjusts model weights/thresholds after each run based on prior pick correctness.
- Applies run-to-run feedback learning: if last run calls were wrong, logic is updated for the next run.
- Tracks US market session (pre-market / regular / after-hours / weekend) and next open/close times.
- When market is closed, analysis uses regular close as the price reference.
- Tracks virtual portfolio performance from fixed `capital_balance` `$10,000` and updates `simulation_balance` every run.
- Generates one end-of-day strategy summary (weekdays, after 4:00 PM ET) with specific automated next-day improvement actions.
- Uses conservative filtering by default (established mid-cap and large-cap companies, lower volatility/liquidity thresholds).
- Conservative mode is stocks-first and defaults to `NO_OPTION` to lower risk.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run once

```bash
python3 stock_option_agent/agent.py --base-dir data --universe-count 50
```

Daily partition example:
```bash
python3 stock_option_agent/agent.py --base-dir "data/daily/$(date +%Y%m%d)" --universe-count 50
```

## Run one symbol summary

```bash
python3 stock_option_agent/agent.py --base-dir data --symbol AAPL
```

Output files:
- `data/latest/symbol_summary_AAPL.md`
- `data/latest/symbol_summary_AAPL.csv`
- `data/history/symbol_summary_AAPL_history.csv`
- `data/runs/<timestamp>/symbol_summary_AAPL.md`

## Set real balance (one-shot override)

```bash
source .venv/bin/activate
python stock_option_agent/agent.py --base-dir "data/daily/$(date +%Y%m%d)" --set-sim-budget 10000
```

Notes:
- Updates persistent state file: `data/portfolio/state.json`
- Resets open positions and run counters; keeps `capital_balance` fixed and resets `simulation_balance`

After-hours handling:
- Default: disabled (regular session pricing only).
- Enable explicitly:
```bash
python3 stock_option_agent/agent.py --base-dir data --universe-count 50 --enable-after-hours
```

## News tuning
- Unified config file: `config/agent_config.json`
- Supports:
  - `news`: source weights + recency + thresholds
  - `notifications`: Telegram alerts + cooldown
  - `trading`:
    - `real_trading_capital` (fixed capital for quantity recommendations)
    - `simulation_initial_capital` (first-run simulation baseline)
    - `stock_only`
    - `include_downtrend_symbols` + `downtrend_symbol_ratio` (default `true` + `0.4`)
    - `full_budget_deploy` + `full_deploy_target_pct` (deploy most/all simulation cash each run)
- Legacy per-file configs are still supported but no longer required.
- Enable after-hours in background explicitly:
```bash
ENABLE_AFTER_HOURS=1 bash scripts/run_agent.sh
```

## Trading mode
- Config file: `config/agent_config.json` -> `trading.stock_only`
- Current default: `stock_only = true` (options disabled)
- Full deployment mode:
  - `trading.full_budget_deploy = true`
  - `trading.full_deploy_target_pct = 1.0`
  - Uses up to ~100% of simulation balance (higher risk).

## Output
- Quickest view: `data/simple/` (curated, auto-refreshed each run)
- `data/runs/<timestamp>/...` full snapshot per run
- `data/latest/top10.csv` and `data/latest/top10.md` current recommendation
- `data/latest/symbol_summary_<SYMBOL>.md` on-demand single-symbol summary
- `top10.md` includes separate sections: `Daily Trading Section` and `Earnings Swing Section`
- Includes trade levels per pick: `entry_price`, `target_price`, `stop_price`, `risk_reward`
- Includes sizing per run: `stock_qty`, `stock_notional_usd`, `option_contracts`, `option_premium_est_usd`
- Includes simulation budget plan from base `$10,000`: deploy amount, capped deploy, reserve cash, and per-pick budget
- Portfolio/budget state is persistent across days in `data/portfolio/state.json` (not reset by daily folders)
- Includes earnings catalyst fields: `upcoming_earnings_days`, `earnings_event_score`
- Includes execution timing: `NOW` (market open) or `NEXT_MARKET_OPEN` (market closed)
- `data/history/top10_history.csv` append-only run history
- `data/history/top10_hourly.csv` hourly snapshots
- `data/history/top10_daily.csv` daily snapshots
- Adaptive model state: `data/model/model_params.json`
- Post-analysis logs:
  - `data/latest/post_analysis.json`
  - `data/history/post_analysis_history.jsonl`
- Portfolio tracking:
  - `data/latest/portfolio_status.json`
  - `data/latest/portfolio_report.md`
  - `data/latest/alerts.json`
  - `data/latest/last_alert.txt`
- Runtime map:
  - `data/today` -> symlink to current day partition
  - `data/daily/YYYYMMDD/` -> primary partitioned storage
  - `data/model/` -> adaptive model parameters
  - `data/portfolio/` -> persistent state (`capital_balance`, `simulation_balance`)
  - `data/simple/` -> simplified outputs for daily usage
- `data/history/equity_curve.csv`
  - `data/history/trades_log.csv`
  - `data/portfolio/state.json`
  - Daily summary:
    - `data/latest/daily_summary.md`
    - `data/history/daily_summary_YYYYMMDD.md`
    - `data/history/daily_summary_state.json` (one-summary-per-day guard)

## Telegram Alerts (Very Good Setups)
- Config: `config/agent_config.json` -> `notifications`
- Trigger: high-confidence setups (score + risk/reward thresholds)
- Anti-spam: cooldown + duplicate message suppression
- Delivery backend: Telegram Bot API using env vars:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID` (or set `telegram_chat_id` in config)

## How Learning Works
- Every run first evaluates the previous recommendations.
- Correct vs wrong outcome is computed from latest available price.
- Model weights and decision thresholds are updated automatically.
- Updated parameters are saved and used immediately in the current run.

## Portfolio Strategy (Low Risk)
- Capital balance: `$10,000` (fixed benchmark).
- Simulation balance: updates every run from simulated trades.
- Risk per trade: `0.75%` of equity.
- Max stock allocation per position: `12%`.
- Max options allocation per position: `1%`.
- Max total exposure: `60%` of equity.
- Positions can span multiple days:
  - stock max hold: `5` trading days equivalent
  - option max hold: `3` trading days equivalent

## Portfolio Strategy (Full Budget Deploy)
- Enable in `config/agent_config.json`:
  - `trading.full_budget_deploy = true`
  - `trading.full_deploy_target_pct = 1.0`
- Behavior:
  - Increases target exposure to configured deploy target (up to 100%).
  - Distributes available cash across actionable picks each run.
  - Keeps `capital_balance` fixed while `simulation_balance` reflects full deployment P/L.

## Run every 30 minutes in background (macOS)

```bash
bash scripts/install_launchd.sh
```

Default schedule behavior:
- Runs only on weekdays during regular US market hours (`06:30–13:00 PT` / `09:30–16:00 ET`).
- Does not auto-run after-hours or weekends.
- Each run day is isolated under `data/daily/YYYYMMDD/` with its own `runs/`, `latest/`, `history/`, and `logs/`.
- Quick pointer to today's folder: `data/today` (symlink).
- For off-hours analysis, run manually:

```bash
bash scripts/run_agent.sh
```

Check status:

```bash
launchctl list | rg stock_option_agent
```

Remove job:

```bash
bash scripts/uninstall_launchd.sh
```

## Important
- The engine ranks opportunities; it does not guarantee profitability.
- Validate fills, bid/ask spread, and position sizing before trading live.
# codex_sample
