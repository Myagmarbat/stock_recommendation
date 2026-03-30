# Daily Strategy Summary (2026-03-30 ET)

## Performance
- Runs today: `45`
- Start equity: `$10,000.00`
- End equity: `$10,958.43`
- Daily P/L: `$958.43` (9.58%)
- Realized P/L: `$0.00`
- Max open positions: `5`

## Recommendation Effectiveness
- Closed trades today: `0`
- Win rate: `N/A`
- Post-analysis statuses: `{'no_runs': 2, 'too_fresh': 37, 'no_evaluable_rows': 2, 'already_evaluated': 1, 'updated': 3}`

## How Strategy Worked
- Strategy remained low-risk, stock-only with mid/large-cap bias.
- Entries/exits were managed via target/stop/max-hold policy.

## Improvements
1. Tomorrow (2026-03-31 ET): keep risk at 0.75% per trade, but only open new positions when score and market regime agree.
2. Tomorrow (2026-03-31 ET): shorten time-in-trade review cadence and force an end-of-day exit check at 15:50 ET for stale positions.
3. Tomorrow (2026-03-31 ET): reduce too-fresh evaluations by delaying evaluation checks and prioritizing mature prior runs.