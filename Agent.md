# Agent.md

## Objective
Run a Yahoo Finance driven scanner every 10 minutes, analyze top 50 symbols, and output top 10 weekly opportunity picks for stocks/options with buy/sell direction and trade levels.
Track virtual portfolio growth/decline from initial capital `$10,000` on every run, and show simulation budget changes based on recommendations.

## Run Format
- Universe source: Yahoo predefined screener `day_gainers`, top 50 symbols.
- On-demand symbol mode: `--symbol <TICKER>` produces a single-stock summary snapshot.
- Analysis layers:
  1. Fundamental score
  2. Technical score
  3. Headline/news sentiment score (ticker feed + web RSS news search, source-weighted with recency decay)
  4. Market regime / market trend (bullish / bearish / neutral)
  5. Category trend score (sector/macro context)
  6. Earnings catalyst score (upcoming quarterly result within ~30 days, with outlook + current price setup gate)
- Recommendation fields:
  - `action_stock`: `BUY_STOCK` / `SELL_SHORT` / `HOLD`
  - `action_option`: `BUY_CALL` / `BUY_PUT` / `NO_OPTION`
  - `execution_timing`: `NOW` / `NEXT_MARKET_OPEN`
  - `entry_price` (buy/short at), `target_price` (sell/cover at), `stop_price`, `risk_reward`
  - `stock_qty`, `stock_notional_usd`, `option_contracts`, `option_premium_est_usd`
  - `upcoming_earnings_days`, `earnings_event_score`
  - `strategy_bucket`: `DAILY_TRADING` or `EARNINGS_SWING`
  - `option_symbol_hint`, `option_expiry`, `option_strike`

## Storage Contract
- Daily root:
  - `data/daily/YYYYMMDD/`
  - `data/today` (symlink to current day folder)
- Per run snapshot:
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/market_context.json`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/candidates.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.md`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/symbol_summary_<SYMBOL>.md` (when symbol mode is used)
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/symbol_summary_<SYMBOL>.csv` (when symbol mode is used)
- Rolling files:
  - `data/daily/YYYYMMDD/latest/top10.csv`
  - `data/daily/YYYYMMDD/latest/top10.md`
  - `data/daily/YYYYMMDD/latest/symbol_summary_<SYMBOL>.md` (on-demand)
  - `data/daily/YYYYMMDD/latest/symbol_summary_<SYMBOL>.csv` (on-demand)
  - `data/daily/YYYYMMDD/latest/post_analysis.json`
  - `data/daily/YYYYMMDD/latest/portfolio_status.json`
  - `data/daily/YYYYMMDD/latest/portfolio_report.md`
  - `data/daily/YYYYMMDD/latest/alerts.json`
  - `data/daily/YYYYMMDD/latest/last_alert.txt`
  - `data/daily/YYYYMMDD/latest/daily_summary.md` (latest daily report)
- Historical files:
  - `data/daily/YYYYMMDD/history/top10_history.csv` (every run)
  - `data/daily/YYYYMMDD/history/top10_hourly.csv` (minute == 00)
  - `data/daily/YYYYMMDD/history/top10_daily.csv` (around 16:00 local)
  - `data/daily/YYYYMMDD/history/post_analysis_history.jsonl`
  - `data/daily/YYYYMMDD/history/equity_curve.csv`
  - `data/daily/YYYYMMDD/history/trades_log.csv`
  - `data/daily/YYYYMMDD/history/symbol_summary_<SYMBOL>_history.csv` (on-demand append history)
- `data/daily/YYYYMMDD/history/daily_summary_YYYYMMDD.md` (once per weekday after market close)
- `data/daily/YYYYMMDD/history/daily_summary_state.json` (daily generation state)
- `data/daily/YYYYMMDD/model/model_params.json`
- `data/daily/YYYYMMDD/logs/run_<UTC_TIMESTAMP>.log`
- Global persistent budget state:
  - `data/portfolio/state.json` (continuous equity/cash/open positions across days)

## Automation
- Runner: `scripts/run_agent.sh`
- Install background schedule (10 min): `scripts/install_launchd.sh`
- Remove schedule: `scripts/uninstall_launchd.sh`
- Default schedule: weekdays, regular US market session only (`06:30–13:00 PT` / `09:30–16:00 ET`)
- No automatic after-hours/weekend runs; run manually off-hours if needed.
- Real-balance override command:
  - `python stock_option_agent/agent.py --base-dir data/daily/YYYYMMDD --set-sim-budget <USD>`
  - Writes `data/portfolio/state.json` and resets open positions for clean resync.

## Notes
- This is a systematic ranking engine, not guaranteed profit.
- Always review liquidity, spreads, and risk limits before placing live orders.
- Conservative profile is enabled by default: prefers established mid-cap and large-cap companies, and rejects high-volatility names.
- Conservative profile uses stocks-first behavior and defaults to `NO_OPTION` to reduce risk.
- Unified runtime config is stored in `config/agent_config.json` (news + notifications + trading).
- `trading.real_trading_capital` is fixed capital used for quantity recommendations.
- `trading.simulation_initial_capital` is first-run simulation baseline; simulation then rolls each run.
- News score stays neutral if headline coverage is below minimum threshold.
- Engine performs post-analysis each run on the previous top picks and updates model weights/thresholds in `data/model/model_params.json`.
- Learning contract: if recommendations from ~10 minutes ago are incorrect, apply that error immediately to update model logic for the next run.
- Latest post-analysis summary is written to `data/latest/post_analysis.json` and historical records to `data/history/post_analysis_history.jsonl`.
- End-of-day summary contract: once per trading day (weekdays, after 16:00 ET), generate a day-level report with run count, P/L, win-rate snapshot, and improvement suggestions.
- Market-hours context is included each run (`market_open`, `market_session`, `next_open_et`, `next_close_et`).
- When market is closed, analysis and post-analysis use regular-session close price as the reference.
- After-hours processing is disabled by default and can be enabled explicitly with `--enable-after-hours` (or `ENABLE_AFTER_HOURS=1` in runner).
- Telegram notifications for very good setups are controlled by `config/agent_config.json` (`notifications`) and sent via Telegram bot credentials.
