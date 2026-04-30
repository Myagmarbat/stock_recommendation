# Stock/Options Auto Scanner (Yahoo Finance)

Automated scanner that:
- Pulls top 50 symbols from Yahoo Finance market movers (default mix: 60% day gainers, 40% day losers).
- Runs fundamental, technical, and news sentiment analysis.
- Adds quarterly earnings catalyst scoring (up to about 30 days pre-earnings) and checks whether the current price setup is favorable.
- Detects broad market trend (bullish, bearish, neutral) and adapts recommendations.
- Produces top 10 picks every run.
- Stores timestamped outputs for historical analysis.
- Runs in background via Windows Task Scheduler or macOS launchd during market hours only on weekdays.
- Self-adjusts model weights and thresholds after each run based on prior pick correctness.
- Applies run-to-run feedback learning so the next run uses updated logic immediately.
- Tracks US market session status and next open/close times.
- Uses regular-session close pricing as the reference when the market is closed.
- Tracks virtual portfolio performance from fixed `capital_balance` `$10,000` while updating `simulation_balance` every run.
- Generates one end-of-day strategy summary per weekday after 4:00 PM ET with next-day improvement actions.
- Uses conservative filtering by default and prefers stocks-first behavior with `NO_OPTION`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quick Start

1. Create and activate the virtual environment.
2. Install dependencies.
3. Run one manual scan to confirm the environment works.
4. Install the platform scheduler: Windows Task Scheduler or macOS launchd.
5. Start the scheduler once if you want an immediate first run.

## Run once

```powershell
python .\stock_option_agent\agent.py --base-dir .\data --universe-count 50 --config .\config\agent_config.json
```

Daily partition example:

```powershell
$dayKey = Get-Date -Format "yyyyMMdd"
python .\stock_option_agent\agent.py --base-dir ".\data\daily\$dayKey" --universe-count 50 --config .\config\agent_config.json
```

## Run one symbol summary

```powershell
python .\stock_option_agent\agent.py --base-dir .\data --symbol AAPL --config .\config\agent_config.json
```

Output files:
- `data/latest/symbol_summary_AAPL.md`
- `data/latest/symbol_summary_AAPL.csv`
- `data/history/symbol_summary_AAPL_history.csv`
- `data/runs/<timestamp>/symbol_summary_AAPL.md`

## Set real balance (one-shot override)

```powershell
.\.venv\Scripts\Activate.ps1
$dayKey = Get-Date -Format "yyyyMMdd"
python .\stock_option_agent\agent.py --base-dir ".\data\daily\$dayKey" --set-sim-budget 10000 --config .\config\agent_config.json
```

Notes:
- Updates persistent state file: `data/portfolio/state.json`
- Resets open positions and run counters while keeping `capital_balance` fixed

After-hours handling:
- Default: disabled (regular session pricing only).
- Enable explicitly:

```powershell
python .\stock_option_agent\agent.py --base-dir .\data --universe-count 50 --config .\config\agent_config.json --enable-after-hours
```

## News tuning

- Unified config file: `config/agent_config.json`
- Supports:
  - `news`: source weights, recency, thresholds
  - `notifications`: Telegram alerts and cooldown
  - `trading`:
    - `real_trading_capital`
    - `simulation_initial_capital`
    - `stock_only`
    - `include_downtrend_symbols` and `downtrend_symbol_ratio`
    - `full_budget_deploy` and `full_deploy_target_pct`
- Legacy per-file configs are still supported but no longer required.
- Enable after-hours in the Windows runner explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1 -EnableAfterHours
```

## Trading mode

- Config file: `config/agent_config.json` -> `trading.stock_only`
- Current default: `stock_only = true` (options disabled)
- Full deployment mode:
  - `trading.full_budget_deploy = true`
  - `trading.full_deploy_target_pct = 1.0`
  - Uses up to about 100% of current simulation equity, subject to drawdown controls and exposure headroom

## Output

- Quickest view: `data/simple/`
- Full snapshot per run: `data/runs/<timestamp>/...`
- Current recommendation: `data/latest/top10.csv` and `data/latest/top10.md`
- On-demand single-symbol summary: `data/latest/symbol_summary_<SYMBOL>.md`
- `top10.md` includes `Daily Trading Section` and `Earnings Swing Section`
- `top10.md` also includes a `Simulation Budget` section that explains:
  - fixed initial benchmark capital
  - current mark-to-market simulation equity
  - cash on hand versus current exposure
  - fresh deployable budget after exposure and drawdown controls
  - improvement actions when budget is below benchmark or drawdown controls are active
- Trade levels per pick: `entry_price`, `target_price`, `stop_price`, `risk_reward`
- Sizing per run: `stock_qty`, `stock_notional_usd`, `option_contracts`, `option_premium_est_usd`
- Persistent portfolio state across days: `data/portfolio/state.json`
- Earnings catalyst fields: `upcoming_earnings_days`, `earnings_event_score`
- Execution timing: `NOW` or `NEXT_MARKET_OPEN`
- History outputs:
  - `data/history/top10_history.csv`
  - `data/history/top10_hourly.csv`
  - `data/history/top10_daily.csv`
  - `data/history/post_analysis_history.jsonl`
  - `data/history/equity_curve.csv`
  - `data/history/trades_log.csv`
- Portfolio outputs:
  - `data/latest/portfolio_status.json`
  - `data/latest/portfolio_report.md`
  - `data/latest/alerts.json`
  - `data/latest/last_alert.txt`
- Runtime map:
  - `data/today` -> junction to the current day partition
  - `data/daily/YYYYMMDD/` -> primary partitioned storage
  - `data/model/` -> adaptive model parameters
  - `data/portfolio/` -> persistent state
  - `data/simple/` -> simplified outputs
- Daily summary outputs:
  - `data/latest/daily_summary.md`
  - `data/history/daily_summary_YYYYMMDD.md`
  - `data/history/daily_summary_state.json`

## Where To Look After A Run

- Current day outputs: `data\today\latest\`
- Per-run snapshots: `data\today\runs\`
- Current logs: `data\today\logs\`
- Simplest summary view: `data\simple\top10.md`
- Portfolio state: `data\portfolio\state.json`

Most useful files after the scheduler runs:
- `data\today\latest\top10.md`
- `data\today\latest\portfolio_report.md`
- `data\today\latest\daily_summary.md`
- `data\today\logs\run_<timestamp>.log`

## Telegram Alerts (Very Good Setups)

- Config: `config/agent_config.json` -> `notifications`
- Trigger: high-confidence setups based on score and risk/reward thresholds
- Anti-spam: cooldown and duplicate-message suppression
- Delivery backend: Telegram Bot API using:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID` or `telegram_chat_id` in config

## How Learning Works

- Every run first evaluates the previous recommendations.
- Correct versus wrong outcome is computed from the latest available price.
- Model weights and decision thresholds are updated automatically.
- Updated parameters are saved and used immediately in the current run.

## Portfolio Strategy (Low Risk)

- Capital balance: `$10,000` fixed benchmark
- Simulation balance: mark-to-market equity updated every run from simulated trades and open-position repricing
- Risk per trade: `0.75%` of equity
- Max stock allocation per position: `12%`
- Max options allocation per position: `1%`
- Max total exposure: `60%` of equity
- Max holding period:
  - stock: `5` trading days equivalent
  - option: `3` trading days equivalent

## Portfolio Strategy (Full Budget Deploy)

- Enable in `config/agent_config.json`:
  - `trading.full_budget_deploy = true`
  - `trading.full_deploy_target_pct = 1.0`
- Behavior:
  - Increases target exposure up to the configured deploy percentage
  - Distributes available cash across actionable picks each run
  - Keeps `capital_balance` fixed while `simulation_balance` reflects full-deployment P/L
  - Still limits new deployment by current cash and remaining exposure headroom

## How To Read Simulation Budget

- `Initial benchmark capital`: fixed reporting baseline, normally `$10,000`
- `Run start budget`: simulation equity at the start of the current run
- `Current equity`: cash plus marked value of open simulated positions
- `Cash on hand`: undeployed cash available before new recommendations
- `Current exposure`: capital currently tied up in open positions
- `Fresh deployable budget now`: additional capital that can still be deployed after exposure caps and drawdown controls
- `Recommended deploy (risk-capped)`: the new recommendation budget after applying both position-sizing logic and portfolio-level caps

Why it can be lower than the initial budget:
- realized losses reduce simulation equity
- unrealized losses on open positions reduce mark-to-market equity
- drawdown controls can tighten exposure and risk per trade until equity recovers

Improvement actions when budget is under pressure:
- reduce deployment to the risk-capped budget
- prioritize highest-conviction stock setups
- preserve more cash while drawdown controls are active
- pause new positions if deployable budget is too small

## Background schedulers

The project includes scheduler installers for both Windows and macOS:
- Windows: `scripts/install_task_scheduler.ps1`
- macOS: `scripts/install_launchd.sh`

Both use the platform runner script and write daily output under `data/daily/YYYYMMDD/`, with `data/today` pointing at the current day.

Quick scheduler commands:

| Platform | Install scheduler | Run now | Check status | Remove scheduler |
| --- | --- | --- | --- | --- |
| Windows | `powershell -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1` | `Start-ScheduledTask -TaskName stock_option_agent` | `Get-ScheduledTask -TaskName stock_option_agent` | `powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_task_scheduler.ps1` |
| macOS | `bash scripts/install_launchd.sh` | `launchctl kickstart -k "gui/$(id -u)/com.local.stock_option_agent"` | `launchctl list \| grep com.local.stock_option_agent` | `bash scripts/uninstall_launchd.sh` |

## Windows Task Scheduler

Recommended operating flow:

1. Install the scheduled task.
2. Start it once manually if you want an immediate first run.
3. Verify the task exists and is enabled.
4. Check `data\today\logs\` and `data\today\latest\` after the first run.
5. Disable or stop it when you need to pause background execution.

Install the scheduled task from an elevated PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1
```

Manual one-shot run through the Windows runner:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1
```

Enable after-hours in the scheduled runner:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1 -EnableAfterHours
```

Check status:

```powershell
Get-ScheduledTask -TaskName stock_option_agent
```

Check the most recent task result and runtime details:

```powershell
Get-ScheduledTaskInfo -TaskName stock_option_agent
```

Run immediately:

```powershell
Start-ScheduledTask -TaskName stock_option_agent
```

Remove job:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_task_scheduler.ps1
```

Stop the currently running task instance:

```powershell
Stop-ScheduledTask -TaskName stock_option_agent
```

Disable the background scheduler without deleting it:

```powershell
Disable-ScheduledTask -TaskName stock_option_agent
```

Re-enable the background scheduler:

```powershell
Enable-ScheduledTask -TaskName stock_option_agent
```

Common scheduler actions:
- Install or refresh the task definition:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1`
- Run one cycle immediately:
  - `Start-ScheduledTask -TaskName stock_option_agent`
- Stop the current in-progress run:
  - `Stop-ScheduledTask -TaskName stock_option_agent`
- Pause future scheduled runs:
  - `Disable-ScheduledTask -TaskName stock_option_agent`
- Resume future scheduled runs:
  - `Enable-ScheduledTask -TaskName stock_option_agent`
- Remove the task completely:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_task_scheduler.ps1`

Troubleshooting:
- If the task exists but no fresh output appears, check `data\today\logs\` first.
- If `Get-ScheduledTaskInfo` shows failures, run `powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1` manually to reproduce the issue in the foreground.
- If Python or dependencies changed, reinstall the task after confirming `.venv` is valid.
- If you want after-hours scheduling behavior, reinstall with `-EnableAfterHours`.

Default schedule behavior:
- Runs every 5 minutes from `6:30 AM` through `1:00 PM` local time
- Uses weekdays only (`MON-FRI`)
- Intended for a Windows machine set to Pacific Time to match `09:30-16:00 ET`
- Uses `scripts/run_agent.ps1`
- Writes logs under `data/daily/YYYYMMDD/logs/`
- Refreshes `data/today` as a directory junction to the current `data/daily/YYYYMMDD/` partition
- Does not auto-run after-hours or weekends unless installed with `-EnableAfterHours`

## macOS launchd

Recommended operating flow:

1. Install the launchd agent.
2. Start it once manually if you want an immediate first run.
3. Verify the launchd job is loaded.
4. Check `data/today/logs/` and `data/today/latest/` after the first run.
5. Unload the launchd job when you need to pause background execution.

Install and load the launchd job:

```bash
bash scripts/install_launchd.sh
```

Manual one-shot run through the macOS runner:

```bash
bash scripts/run_agent.sh
```

Manual one-shot run with after-hours enabled:

```bash
ENABLE_AFTER_HOURS=1 bash scripts/run_agent.sh
```

Check status:

```bash
launchctl list | grep com.local.stock_option_agent
```

Run immediately:

```bash
launchctl kickstart -k "gui/$(id -u)/com.local.stock_option_agent"
```

Remove job:

```bash
bash scripts/uninstall_launchd.sh
```

Default macOS schedule behavior:
- Runs on weekdays during the regular US market session window: `06:30` through `13:00` local time
- The current launchd installer schedules every 30 minutes in that window
- Intended for a macOS machine set to Pacific Time to match `09:30-16:00 ET`
- Uses `scripts/run_agent.sh`
- Writes per-run logs under `data/daily/YYYYMMDD/logs/`
- Refreshes `data/today` as a symlink to the current `data/daily/YYYYMMDD/` partition
- Does not auto-run on weekends

## Important

- The engine ranks opportunities; it does not guarantee profitability.
- Validate fills, bid/ask spread, and position sizing before trading live.
