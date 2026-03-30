# Data Folder Map

Use this first:
- `data/simple/` -> simplest view (auto-refreshed each run).

Recommended files in `data/simple/`:
- `top10.md` / `top10.csv`: latest recommendations.
- `portfolio_status.json`: latest `capital_balance` and `simulation_balance`.
- `portfolio_report.md`: readable portfolio report.
- `daily_summary.md`: day summary + next-day improvements.
- `latest_run.log`: latest run log.

What each top-level folder means:
- `data/today` -> symlink to today’s partition under `data/daily/YYYYMMDD/`.
- `data/daily/` -> partitioned storage by day (primary runtime layout).
- `data/model/` -> adaptive model parameters.
- `data/portfolio/` -> persistent simulation state.
- `data/simple/` -> simplified, curated output view.

Legacy/compatibility folders (still written for continuity):
- `data/latest/`
- `data/history/`
- `data/runs/`
- `data/logs/`

If you only want one place to check after each run, use:
- `data/simple/top10.md`
