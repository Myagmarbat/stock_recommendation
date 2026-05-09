from __future__ import annotations

import pandas as pd


def backtest_strategy(history: pd.DataFrame) -> dict:
    if history.empty or len(history) < 80:
        return {"confidence": 0.0, "return_pct": 0.0, "win_rate": 0.0, "reason": "insufficient_history"}
    close = history["Close"].copy()
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    signal = (sma20 > sma50).astype(int).shift(1).fillna(0)
    daily_ret = close.pct_change().fillna(0)
    strat_ret = signal * daily_ret
    total_return = float((1.0 + strat_ret).prod() - 1.0)
    active_days = strat_ret[signal > 0]
    win_rate = float((active_days > 0).mean()) if len(active_days) else 0.0
    drawdown = float(((1.0 + strat_ret).cumprod() / (1.0 + strat_ret).cumprod().cummax() - 1.0).min())
    confidence = max(0.0, min(1.0, 0.45 * min(max(total_return, 0.0), 0.4) / 0.4 + 0.35 * win_rate + 0.20 * max(0.0, 1.0 + drawdown)))
    return {
        "confidence": round(confidence, 4),
        "return_pct": round(total_return * 100.0, 2),
        "win_rate": round(win_rate, 4),
        "max_drawdown_pct": round(drawdown * 100.0, 2),
        "reason": f"sma20/sma50 backtest return={total_return:.2%}, win_rate={win_rate:.2%}, max_drawdown={drawdown:.2%}",
    }

