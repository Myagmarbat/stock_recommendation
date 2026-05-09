# Stock/Options Auto Scanner (Yahoo Finance)

Automated scanner that:
- Pulls top 50 symbols from Yahoo Finance market movers (default mix: 60% day gainers, 40% day losers).
- Runs fundamental, technical, and news sentiment analysis.
- Adds quarterly earnings catalyst scoring (up to about 30 days pre-earnings) and checks whether the current price setup is favorable.
- Detects broad market trend (bullish, bearish, neutral) and adapts recommendations.
- Produces top 10 picks every run.
- Stores timestamped outputs for historical analysis.
- Runs in background via macOS launchd, macOS/Linux cron, or Windows Task Scheduler during market hours only on weekdays.
- Self-adjusts model weights and thresholds after each run based on prior pick correctness.
- Applies run-to-run feedback learning so the next run uses updated logic immediately.
- Tracks US market session status and next open/close times.
- Uses regular-session close pricing as the reference when the market is closed.
- Tracks paper-trading performance from fixed `capital_balance` `$10,000` while carrying the current `paper_balance` into the next run.
- Generates a post-close daily evaluation report with every recommended trade from each 5-minute run, P/L, paper budget balance, and next-day improvements.
- Uses conservative filtering by default and prefers stocks-first behavior with `NO_OPTION`.

## Setup

macOS Terminal (`zsh`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional local environment file for scheduled runs:

```bash
cp .env.example .env
```

Then edit `.env` with local secrets such as `OPENAI_API_KEY`. The Unix runner loads `.env` automatically so launchd and cron jobs can see the same values as manual runs.

Do not use `.\.venv\Scripts\Activate.ps1` in macOS Terminal. That path is for Windows PowerShell. On macOS, the activation script is `.venv/bin/activate`.

To confirm the virtual environment is active in macOS Terminal:

```bash
command -v python3
python3 --version
```

The Python path should point into this project, for example:

```text
/Users/mdorjtse/workspace/stock_analyzer/.venv/bin/python3
```

If `which python` prints `python: aliased to python3`, that is a shell alias and does not mean activation failed. Use `command -v python3` instead.

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quick Start

1. Create and activate the virtual environment.
2. Install dependencies.
3. Run one manual scan to confirm the environment works.
4. Optional: copy `.env.example` to `.env` and add local keys.
5. Install the platform scheduler: macOS launchd, macOS/Linux cron, or Windows Task Scheduler.
6. Start the scheduler once if you want an immediate first run.

## Run once

macOS:

```bash
python stock_option_agent/agent.py --base-dir ./data --universe-count 50 --config ./config/agent_config.json
```

Windows:

```powershell
python .\stock_option_agent\agent.py --base-dir .\data --universe-count 50 --config .\config\agent_config.json
```

Daily partition example on macOS:

```bash
day_key="$(date +%Y%m%d)"
python stock_option_agent/agent.py --base-dir "./data/daily/$day_key" --universe-count 50 --config ./config/agent_config.json
```

Daily partition example on Windows:

```powershell
$dayKey = Get-Date -Format "yyyyMMdd"
python .\stock_option_agent\agent.py --base-dir ".\data\daily\$dayKey" --universe-count 50 --config .\config\agent_config.json
```

## Run one symbol summary

macOS:

```bash
python stock_option_agent/agent.py --base-dir ./data --symbol AAPL --config ./config/agent_config.json
```

Windows:

```powershell
python .\stock_option_agent\agent.py --base-dir .\data --symbol AAPL --config .\config\agent_config.json
```

Output files:
- `data/today/latest/symbol_summary_AAPL.md`
- `data/today/latest/symbol_summary_AAPL.csv`
- `data/today/history/symbol_summary_AAPL_history.csv`
- `data/today/runs/<timestamp>/symbol_summary_AAPL.md`

## Set paper budget (one-shot override)

macOS:

```bash
source .venv/bin/activate
day_key="$(date +%Y%m%d)"
python stock_option_agent/agent.py --base-dir "./data/daily/$day_key" --set-paper-budget 10000 --config ./config/agent_config.json
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
$dayKey = Get-Date -Format "yyyyMMdd"
python .\stock_option_agent\agent.py --base-dir ".\data\daily\$dayKey" --set-paper-budget 10000 --config .\config\agent_config.json
```

Notes:
- Updates persistent paper-trading state file: `data/portfolio/state.json`
- Resets open positions and run counters while keeping `capital_balance` fixed
- Deprecated aliases still accepted for compatibility: `--set-sim-budget`, `--set-real-balance`

After-hours handling:
- Default: disabled (regular session pricing only).
- Enable explicitly:

macOS:

```bash
python stock_option_agent/agent.py --base-dir ./data --universe-count 50 --config ./config/agent_config.json --enable-after-hours
```

Windows:

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
    - `paper_initial_capital`
    - `stock_only`
    - `include_downtrend_symbols` and `downtrend_symbol_ratio`
    - `full_budget_deploy` and `full_deploy_target_pct`
- Legacy per-file configs are still supported but no longer required.
- Deprecated config aliases still load when present: `simulation_initial_capital`, `initial_capital`.
- `paper_initial_capital` is used only to seed the first portfolio state. After that, `data/portfolio/state.json` is the source of truth and the paper balance changes through simulated buys, sells, and mark-to-market P/L.
Enable after-hours in the platform runner explicitly:

```bash
ENABLE_AFTER_HOURS=1 bash scripts/run_agent.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1 -EnableAfterHours
```

## Trading mode

- Config file: `config/agent_config.json` -> `trading.stock_only`
- Current default: `stock_only = true` (options disabled)
- Full deployment mode:
  - `trading.full_budget_deploy = true`
  - `trading.full_deploy_target_pct = 1.0`
  - Uses up to about 100% of current paper equity, subject to drawdown controls and exposure headroom

## Optional LangChain AI advisor

The scanner can optionally call a LangChain-backed AI advisor after the deterministic top picks are built.
This is disabled by default and is cost-capped in `config/agent_config.json` under `ai`.
The default provider is OpenAI through `langchain-openai`, with `framework` set to `langchain`.

The AI layer is an advisor, not the primary trading engine. Python computes the candidates, sizing, stops, targets, and budget controls first. The LangChain advisor reviews that structured payload and returns JSON review fields. In the default `advisory` mode, those fields are written into reports without changing trade actions.

Recommended low-cost setup:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
```

Then set:

```json
"ai": {
  "enabled": true,
  "provider": "openai",
  "framework": "langchain",
  "model": "gpt-5-nano",
  "api_key_env": "OPENAI_API_KEY",
  "monthly_budget_usd": 5.0,
  "review_top_n": 5,
  "max_runs_per_day": 6,
  "decision_mode": "advisory"
}
```

AI outputs:
- `data/today/latest/ai_decision.json`
- `data/today/ai/decision_<timestamp>.json`
- `data/ai/usage_YYYYMM.json`
- `data/today/latest/ai_daily_improvement.json` after the daily evaluation run

The default `advisory` mode adds AI review fields and report sections without changing the scanner's trade actions.
Use `decision_mode` other than `advisory` only after paper-testing, because then AI `HOLD` decisions can downgrade a candidate before alerts and paper-trading updates.
Cost control is enforced with `monthly_budget_usd`, `max_runs_per_day`, and `review_top_n`.

Different agent profiles can use different config files. Create profile files by copying the base config:

```bash
cp config/agent_config.json config/agent_config.conservative.json
cp config/agent_config.json config/agent_config.aggressive.json
```

Then run a selected profile:

```bash
python stock_option_agent/agent.py --config ./config/agent_config.json
python stock_option_agent/agent.py --config ./config/agent_config.conservative.json
python stock_option_agent/agent.py --config ./config/agent_config.aggressive.json
```

Each profile can set its own `ai.model`, `ai.api_key_env`, budget, review size, and `decision_mode`. Scheduler scripts use `AGENT_CONFIG_PATH`, so cron or launchd can point at a different agent profile without changing code:

```bash
AGENT_CONFIG_PATH="$PWD/config/agent_config.conservative.json" bash scripts/run_agent.sh
```

Current implementation note: the LangChain integration uses `ChatOpenAI` for structured JSON review calls. It is LangChain-backed and config-driven, but it is not yet a tool-calling LangChain `AgentExecutor`.

## stock_recommendation

The new `stock_recommendation/` package is a controlled workflow for stable stock/ETF recommendations:

```text
stock_recommendation
  -> collect data
  -> calculate signals
  -> run backtest
  -> ask LangChain/OpenAI for analysis/summary only
  -> recommend trade
  -> paper-trade balance update
  -> log result
```

First scope:
- Universe: `SPY`, `QQQ`, `DIA`, `IWM`, `VTI`, `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`
- Actions: `buy`, `sell`, `hold`
- No shorting yet
- Paper balance: `$10,000`
- Risk per trade: max `1%`
- Max trades/day: `3`
- Storage: SQLite at `stock_recommendation/data/paper_trades.db`

Run:

```bash
python -m stock_recommendation.main
```

Run without changing the paper ledger:

```bash
python -m stock_recommendation.main --no-paper-update
```

Enable OpenAI summary/review only:

```bash
export OPENAI_API_KEY="sk-..."
export STOCK_RECOMMENDATION_AI=1
export STOCK_RECOMMENDATION_MODEL="gpt-4.1-mini"
```

The LLM does not freely decide trades. Python computes the recommendation score from stability, trend, liquidity, fundamentals, news sentiment, and backtest confidence. OpenAI only explains the recommendation, identifies risks, and suggests strategy improvements.

## Output

- Quickest view: `data/simple/`
- Full snapshot per run: `data/today/runs/<timestamp>/...`
- Current recommendation: `data/today/latest/top10.csv` and `data/today/latest/top10.md`
- On-demand single-symbol summary: `data/today/latest/symbol_summary_<SYMBOL>.md`
- `top10.md` includes `Daily Trading Section` and `Earnings Swing Section`
- `top10.md` also includes a `Paper Budget` section that explains:
  - fixed initial benchmark capital
  - current mark-to-market paper equity
  - cash on hand versus current exposure
  - fresh deployable budget after exposure and drawdown controls
  - improvement actions when budget is below benchmark or drawdown controls are active
- Trade levels per pick: `entry_price`, `target_price`, `stop_price`, `risk_reward`
- Sizing per run: `stock_qty`, `stock_notional_usd`, `option_contracts`, `option_premium_est_usd`
- Persistent portfolio state across days: `data/portfolio/state.json`
- Earnings catalyst fields: `upcoming_earnings_days`, `earnings_event_score`
- Execution timing: `NOW` or `NEXT_MARKET_OPEN`
- History outputs:
  - `data/today/history/top10_history.csv`
  - `data/today/history/top10_hourly.csv`
  - `data/today/history/top10_daily.csv`
  - `data/today/history/post_analysis_history.jsonl`
  - `data/today/history/equity_curve.csv`
  - `data/today/history/trades_log.csv`
- Portfolio outputs:
  - `data/today/latest/portfolio_status.json`
  - `data/today/latest/portfolio_report.md`
  - `data/today/latest/alerts.json`
  - `data/today/latest/last_alert.txt`
- Runtime map:
  - `data/today` -> junction on Windows or symlink on macOS to the current day partition
  - `data/daily/YYYYMMDD/` -> primary partitioned storage
  - `data/model/` -> adaptive model parameters
  - `data/portfolio/` -> persistent paper-trading state
  - `data/simple/` -> simplified outputs
- Daily summary outputs:
  - `data/today/latest/daily_summary.md`
  - `data/today/latest/daily_evaluation_report.md`
  - `data/today/history/daily_summary_YYYYMMDD.md`
  - `data/today/history/daily_evaluation_report_YYYYMMDD.md`
  - `data/today/history/daily_summary_state.json`

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
- Paper balance: mark-to-market equity updated every run from paper trades and open-position repricing
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
  - Keeps `capital_balance` fixed while `paper_balance` reflects full-deployment P/L
  - Still limits new deployment by current cash and remaining exposure headroom

## How To Read Paper Budget

- The paper budget is a persistent paper-trading account.
- Each run starts from `data/portfolio/state.json`, marks existing paper positions to the latest available price, closes positions when stop/target/max-hold/opposite-advice rules trigger, then opens new paper positions only with remaining cash and exposure headroom.
- The fixed benchmark capital is only a reporting baseline; purchases and sells use the carried-forward paper cash and open-position value from prior runs and prior days.
- `Initial benchmark capital`: fixed reporting baseline, normally `$10,000`
- `Run start budget`: paper equity at the start of the current run
- `Current equity`: cash plus marked value of open paper positions
- `Cash on hand`: undeployed cash available before new recommendations
- `Current exposure`: capital currently tied up in open positions
- `Fresh deployable budget now`: additional capital that can still be deployed after exposure caps and drawdown controls
- `Recommended deploy (risk-capped)`: the new recommendation budget after applying both position-sizing logic and portfolio-level caps

Why it can be lower than the initial budget:
- realized losses reduce paper equity
- unrealized losses on open positions reduce mark-to-market equity
- drawdown controls can tighten exposure and risk per trade until equity recovers

Improvement actions when budget is under pressure:
- reduce deployment to the risk-capped budget
- prioritize highest-conviction stock setups
- preserve more cash while drawdown controls are active
- pause new positions if deployable budget is too small

## Background schedulers

The project includes separate scheduler installers:
- macOS: `scripts/install_launchd.sh`
- macOS/Linux cron: `scripts/install_cron.sh`
- Windows: `scripts/install_task_scheduler.ps1`

Both use the platform runner script and write daily output under `data/daily/YYYYMMDD/`, with `data/today` pointing at the current day.

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
- Runs every 5 minutes from `6:30 AM` through `1:00 PM` local time
- Runs one evaluation-only pass at `1:05 PM` local time to assess every recommendation from the day's 5-minute runs, write P/L, paper balance, and next-day improvements
- Uses weekdays only (`MON-FRI`)
- Intended for a macOS machine set to Pacific Time to match `09:30-16:00 ET`
- Uses `scripts/run_agent.sh`
- Writes per-run logs under `data/daily/YYYYMMDD/logs/`
- Refreshes `data/today` as a symlink to the current `data/daily/YYYYMMDD/` partition
- The runner exits without analysis outside weekday `06:30 <= time < 13:00 PT`, except the `13:00 <= time < 13:15 PT` final evaluation-only window
- Does not auto-run after-hours or weekends unless run with `ENABLE_AFTER_HOURS=1`

## macOS/Linux cron

Use cron when you want a portable Unix scheduler instead of macOS launchd.

Install managed cron entries:

```bash
bash scripts/install_cron.sh
```

View installed entries:

```bash
crontab -l
```

Manual one-shot run through the Unix runner:

```bash
bash scripts/run_agent.sh
```

Remove only the managed project cron entries:

```bash
bash scripts/uninstall_cron.sh
```

Default cron schedule behavior:
- Runs weekdays every 5 minutes from `6:30 AM` through `1:00 PM` local machine time
- Runs one evaluation-only pass at `1:05 PM` local machine time
- Uses `scripts/run_agent.sh`
- The runner still checks `America/Los_Angeles` time and exits without analysis outside weekday `06:30 <= time < 13:00 PT`, except the `13:00 <= time < 13:15 PT` final evaluation-only window
- For US market hours, keep the machine timezone set to Pacific Time or prefer launchd/systemd timers with explicit timezone handling

## AI schedule and cost

With the default AI config in `config/agent_config.json`, AI is disabled unless `ai.enabled` is set to `true` and `OPENAI_API_KEY` is present.

When enabled:
- A regular scan can make at most one AI advisor call after the deterministic top picks are built.
- The final `1:05 PM` daily evaluation can make one additional AI improvement call when `daily_improvement_enabled` is `true`.
- `max_runs_per_day` defaults to `6`, so the scanner will stop making AI calls after 6 successful AI calls in a UTC day even though cron/launchd continues running the deterministic scanner every 5 minutes.
- `monthly_budget_usd` defaults to `$5.00`; once tracked estimated spend reaches that value, later AI calls are skipped.
- Cost is estimated from actual token usage and the configured prices: `input_price_per_million = 0.05`, `output_price_per_million = 0.40`.

The 06:30-13:00 weekday schedule creates about 78 regular scan opportunities per trading day, plus one evaluation pass. With defaults, AI usage is capped to 6 calls/day, not 79 calls/day. At the configured `gpt-5-nano` rates, 6 small JSON review calls per trading day should normally remain below `$5/month`; the hard budget cap prevents the app from continuing AI calls after the configured monthly budget is reached.

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1 -Force
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

Troubleshooting:
- If the task exists but no fresh output appears, check `data\today\logs\` first.
- If `Get-ScheduledTaskInfo` shows failures, run `powershell -ExecutionPolicy Bypass -File .\scripts\run_agent.ps1 -Force` manually to reproduce the issue in the foreground.
- If Python or dependencies changed, reinstall the task after confirming `.venv` is valid.
- If you want after-hours scheduling behavior, reinstall with `-EnableAfterHours`.

Default Windows schedule behavior:
- Runs every 5 minutes from `6:30 AM` through `1:00 PM` local time
- Runs one evaluation-only pass at `1:05 PM` local time to assess every recommendation from the day's 5-minute runs, write P/L, paper balance, and next-day improvements
- Uses weekdays only (`MON-FRI`)
- Intended for a Windows machine set to Pacific Time to match `09:30-16:00 ET`
- Uses `scripts/run_agent.ps1`
- Writes logs under `data/daily/YYYYMMDD/logs/`
- Refreshes `data/today` as a directory junction to the current `data/daily/YYYYMMDD/` partition
- The runner exits without analysis outside weekday `06:30 <= time < 13:00 PT`, except the `13:00 <= time < 13:15 PT` final evaluation-only window
- Does not auto-run after-hours or weekends unless installed with `-EnableAfterHours`

## Important

- The engine ranks opportunities; it does not guarantee profitability.
- Validate fills, bid/ask spread, and position sizing before trading live.
