# Simple Data View

- `top10.md`: current recommendations
- `top10.csv`: current recommendations (csv)
- `portfolio_status.json`: latest balances and run P/L
- `portfolio_report.md`: human-readable portfolio report
- `daily_summary.md`: daily summary with next-day improvements
- `alerts.json`: latest alert payload
- `post_analysis.json`: latest learning/adaptation summary
- `latest_run.log`: latest run log

Generated automatically after each run.

For full scheduled-run outputs, use `data/today/latest/` and `data/today/logs/`.
AI advisor output, when enabled, is written to `data/today/latest/ai_decision.json`; monthly AI budget usage is tracked in `data/ai/usage_YYYYMM.json`.
