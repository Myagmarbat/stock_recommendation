# Stock Analysis Skill

## Purpose
Generate top picks from Yahoo Finance data using a low-risk, stock-first process that works for both up and down market conditions.

## Inputs
- Universe source: Yahoo screener (`day_gainers`) top 50 symbols.
- Market context: SPY/QQQ trend and momentum.
- Symbol data: OHLCV history, company fundamentals, headline/news feed, options chain.
- Risk preference: focus on established mid-cap and large-cap companies; avoid high-volatility names.

## Workflow
1. Retrieve top 50 symbols from Yahoo gainers.
2. Determine market regime:
   - `bullish` when medium trend and 20-day momentum are positive.
   - `bearish` when trend and momentum are negative.
   - `neutral` otherwise.
3. For each symbol compute:
   - Fundamental score: PE, profit margin, ROE, revenue growth, debt-to-equity.
   - Technical score: SMA20/SMA50/SMA200 trend, RSI(14), 20-day momentum, volatility penalty.
   - News sentiment score from recent headlines.
   - Market trend score (broad index/regime support).
   - Category trend score (sector/macro proxies such as oil/energy context).
   - Earnings catalyst score (upcoming quarterly result up to ~30 days out).
4. Combine scores in required analysis order:
   1. Fundamental
   2. Technical
   3. News
   4. Market trend
   5. Category trend
5. Choose recommendation by regime-aware logic:
   - Stock: `BUY_STOCK`, `SELL_SHORT`, or `HOLD`
   - Option: `BUY_CALL`, `BUY_PUT`, or `NO_OPTION`
   - Default profile: `stock_only=true` so `action_option=NO_OPTION`.
   - Earnings rule: if fundamentals/technical/news plus quarterly outlook and current price setup are supportive, allow pre-earnings buy bias (up to ~30 days).
6. Select nearest practical option contract (expiry/strike/contract symbol hint) when option action is buy.
7. Add trade levels for each actionable pick:
   - `entry_price` (buy at / short at)
   - `target_price` (sell at / cover at)
   - `stop_price`
   - `risk_reward`
8. Output top 10 ranked picks for next-week opportunity focus.
9. Post-analysis learning loop (every run):
   - Evaluate previous run recommendations (~10 minutes earlier) as correct/incorrect using latest available price.
   - If recommendation was incorrect, adjust model weights/thresholds.
   - Persist adapted parameters for the next run.
10. Daily summary loop (once after market close on weekdays):
   - Produce day-level gain/loss, run-count, recommendation effectiveness, and improvement notes.
11. On-demand symbol summary mode:
   - Accept a single symbol input and output one focused recommendation summary with full score breakdown and trade levels.

## Output Format
Per symbol include:
- `symbol`
- `price`
- `market_regime`
- `fundamental_score`
- `technical_score`
- `news_score`
- `total_score`
- `action_stock`
- `action_option`
- `execution_timing` (`NOW` or `NEXT_MARKET_OPEN`)
- `entry_price`
- `target_price`
- `stop_price`
- `risk_reward`
- `option_symbol_hint`
- `option_expiry`
- `option_strike`
- `reason`
- `trade_type`
- `stock_instruction`
- `option_instruction`
- `brief_reason`

For symbol mode also persist:
- `data/latest/symbol_summary_<SYMBOL>.md`
- `data/latest/symbol_summary_<SYMBOL>.csv`
- `data/history/symbol_summary_<SYMBOL>_history.csv`

## Risk/Quality Rules
- If live market data is unavailable, do not crash: return last valid snapshot with stale note.
- Treat outputs as ranking guidance, not guaranteed profitability.
- Favor liquid stocks and avoid illiquid/high-volatility names.
- Use market-hours awareness to control timing:
  - include market state (`market_open`, `market_session`, `next_open_et`, `next_close_et`)
  - if market is closed, mark execution timing as `NEXT_MARKET_OPEN`.
- Default automation behavior: do not trade after-hours/weekends; allow manual run when needed.
