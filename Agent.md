# Agent.md

## Objective
Run a Yahoo Finance driven scanner every 5 minutes, analyze the top 50 symbols, and output top 10 opportunity picks for stocks/options with buy/sell direction and trade levels.
Track paper portfolio growth or decline from fixed `capital_balance` `$10,000` while `paper_balance` carries forward and updates on every run.

## Run Format
- Universe source: Yahoo predefined screeners `day_gainers` and `day_losers`, top 50 symbols (default 60/40 mix).
- On-demand symbol mode: `--symbol <TICKER>` produces a single-stock summary snapshot.
- Analysis layers:
  1. Fundamental score
  2. Technical score
  3. Headline/news sentiment score
  4. Market regime and market trend
  5. Category trend score
  6. Earnings catalyst score
- Recommendation fields:
  - `action_stock`: `BUY_STOCK`, `SELL_SHORT`, `HOLD`
  - `action_option`: `BUY_CALL`, `BUY_PUT`, `NO_OPTION`
  - `execution_timing`: `NOW`, `NEXT_MARKET_OPEN`
  - `entry_price`, `target_price`, `stop_price`, `risk_reward`
  - `stock_qty`, `stock_notional_usd`, `option_contracts`, `option_premium_est_usd`
  - `upcoming_earnings_days`, `earnings_event_score`
  - `strategy_bucket`: `DAILY_TRADING` or `EARNINGS_SWING`
  - `option_symbol_hint`, `option_expiry`, `option_strike`

## Storage Contract
- Daily root:
  - `data/daily/YYYYMMDD/`
  - `data/today` (junction to current day folder)
- Per run snapshot:
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/market_context.json`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/candidates.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.csv`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/top10.md`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/symbol_summary_<SYMBOL>.md`
  - `data/daily/YYYYMMDD/runs/<UTC_TIMESTAMP>/symbol_summary_<SYMBOL>.csv`
- Rolling files:
  - `data/daily/YYYYMMDD/latest/top10.csv`
  - `data/daily/YYYYMMDD/latest/top10.md`
  - `data/daily/YYYYMMDD/latest/symbol_summary_<SYMBOL>.md`
  - `data/daily/YYYYMMDD/latest/symbol_summary_<SYMBOL>.csv`
  - `data/daily/YYYYMMDD/latest/post_analysis.json`
  - `data/daily/YYYYMMDD/latest/portfolio_status.json`
  - `data/daily/YYYYMMDD/latest/portfolio_report.md`
  - `data/daily/YYYYMMDD/latest/alerts.json`
  - `data/daily/YYYYMMDD/latest/last_alert.txt`
  - `data/daily/YYYYMMDD/latest/daily_summary.md`
  - `data/daily/YYYYMMDD/latest/daily_evaluation_report.md`
- Historical files:
  - `data/daily/YYYYMMDD/history/top10_history.csv`
  - `data/daily/YYYYMMDD/history/top10_hourly.csv`
  - `data/daily/YYYYMMDD/history/top10_daily.csv`
  - `data/daily/YYYYMMDD/history/post_analysis_history.jsonl`
  - `data/daily/YYYYMMDD/history/equity_curve.csv`
  - `data/daily/YYYYMMDD/history/trades_log.csv`
  - `data/daily/YYYYMMDD/history/symbol_summary_<SYMBOL>_history.csv`
  - `data/daily/YYYYMMDD/history/daily_summary_YYYYMMDD.md`
  - `data/daily/YYYYMMDD/history/daily_evaluation_report_YYYYMMDD.md`
  - `data/daily/YYYYMMDD/history/daily_summary_state.json`
- Model state:
  - `data/daily/YYYYMMDD/model/model_params.json`
- Logs:
  - `data/daily/YYYYMMDD/logs/run_<UTC_TIMESTAMP>.log`
  - `data/daily/YYYYMMDD/logs/run_<UTC_TIMESTAMP>.stdout.log`
  - `data/daily/YYYYMMDD/logs/run_<UTC_TIMESTAMP>.stderr.log`
- Global persistent paper-budget state:
  - `data/portfolio/state.json`

## Automation
- Windows runner: `scripts/run_agent.ps1`
- macOS runner: `scripts/run_agent.sh`
- Install Windows background schedule: `scripts/install_task_scheduler.ps1`
- Install macOS background schedule: `scripts/install_launchd.sh`
- Inspect Windows scheduler state: `Get-ScheduledTask -TaskName stock_option_agent`
- Inspect Windows last run result: `Get-ScheduledTaskInfo -TaskName stock_option_agent`
- Inspect macOS scheduler state: `launchctl list | grep com.local.stock_option_agent`
- Start one immediate Windows run: `Start-ScheduledTask -TaskName stock_option_agent`
- Start one immediate macOS run: `launchctl kickstart -k "gui/$(id -u)/com.local.stock_option_agent"`
- Stop active Windows run: `Stop-ScheduledTask -TaskName stock_option_agent`
- Disable Windows scheduler without deleting it: `Disable-ScheduledTask -TaskName stock_option_agent`
- Re-enable Windows scheduler: `Enable-ScheduledTask -TaskName stock_option_agent`
- Remove Windows schedule: `scripts/uninstall_task_scheduler.ps1`
- Remove macOS schedule: `scripts/uninstall_launchd.sh`
- Default schedule: weekdays, regular US market session only (`06:30-13:00 PT` / `09:30-16:00 ET`)
- No automatic weekend runs
- No automatic after-hours runs unless the Windows scheduled task is installed with `-EnableAfterHours`; macOS one-shot runs can use `ENABLE_AFTER_HOURS=1`
- First places to inspect after a scheduled run:
  - `data/today/latest/`
  - `data/today/logs/`
  - `data/simple/`
- Paper-budget override command:
  - `python stock_option_agent/agent.py --base-dir data/daily/YYYYMMDD --set-paper-budget <USD> --config config/agent_config.json`
  - Writes `data/portfolio/state.json` and resets open positions for clean resync

## Notes
- This is a systematic ranking engine, not guaranteed profit.
- Always review liquidity, spreads, and risk limits before placing live orders.
- Conservative profile is enabled by default and prefers established mid-cap and large-cap companies.
- Conservative profile uses stocks-first behavior and defaults to `NO_OPTION`.
- Unified runtime config is stored in `config/agent_config.json`.
- `trading.real_trading_capital` is fixed capital used for quantity recommendations.
- `trading.paper_initial_capital` is the fixed initial benchmark for paper-budget reporting and first-run state only.
- Persisted `data/portfolio/state.json` is the source of truth after the first run; do not reinitialize paper cash or equity from config during normal runs.
- `paper_balance` is live mark-to-market paper equity and can move below the initial benchmark after realized or unrealized losses.
- `simulation_balance`, `peak_simulation_balance`, and `--set-sim-budget` are deprecated compatibility aliases only.
- `trading.full_budget_deploy` and `trading.full_deploy_target_pct` enable aggressive full-cash deployment.
- Portfolio state uses fixed `capital_balance`, live `paper_balance`, current `cash`, and open-position exposure.
- Paper trading flow per run: load `data/portfolio/state.json`, merge duplicate lots, mark open positions, close positions on stop/target/max-hold/opposite-advice rules, then open or top up positions using only paper cash and exposure headroom.
- In generated `top10.md`, the `Paper Budget` section should be interpreted as:
  - benchmark capital: fixed reference amount
  - current equity: cash plus current marked value of open positions
  - fresh deployable budget: remaining deployable capital after exposure caps and drawdown controls
  - improvement actions: concrete recovery steps when current budget is below benchmark or exposure is too tight
- News score stays neutral if headline coverage is below the minimum threshold.
- The engine performs post-analysis each run on the previous top picks and updates model weights and thresholds.
- Latest post-analysis summary is written to `data/latest/post_analysis.json` and historical records to `data/history/post_analysis_history.jsonl`.
- End-of-day evaluation contract: once per trading day from the `13:05 PT` evaluation-only scheduled run, generate a daily evaluation report listing every recommended trade from each 5-minute run, estimated P/L, paper-trade P/L events, overall paper budget balance, and next-day improvements.
- Market-hours context is included each run through `market_open`, `market_session`, `next_open_et`, and `next_close_et`.
- When the market is closed, analysis and post-analysis use regular-session close price as the reference.
- After-hours processing is disabled by default and can be enabled with `--enable-after-hours` or by installing the Windows scheduled task with `-EnableAfterHours`.
- Telegram notifications for very good setups are controlled by `config/agent_config.json` under `notifications`.
