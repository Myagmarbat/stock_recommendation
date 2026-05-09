from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    values = 100 - (100 / (1 + rs))
    out = values.iloc[-1]
    return float(out) if pd.notna(out) else 50.0


def calculate_technical_indicators(history: pd.DataFrame) -> dict:
    if history.empty or len(history) < 60:
        return {"score": 0.0, "reason": "insufficient_history"}
    close = history["Close"]
    volume = history["Volume"] if "Volume" in history else pd.Series(dtype=float)
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    price = float(close.iloc[-1])
    momentum20 = float((close.iloc[-1] / close.iloc[-20]) - 1.0)
    rsi14 = rsi(close)
    vol20 = float(close.pct_change().rolling(20).std().iloc[-1])
    avg_volume = float(volume.tail(20).mean()) if not volume.empty else 0.0

    trend_score = 1.0 if price > sma20 > sma50 else 0.4 if price > sma50 else -0.4
    momentum_score = max(-1.0, min(1.0, momentum20 / 0.08))
    rsi_score = 0.6 if 45 <= rsi14 <= 68 else -0.2 if rsi14 > 75 else 0.0
    volatility_penalty = min(0.5, vol20 / 0.06)
    score = max(-1.0, min(1.0, 0.45 * trend_score + 0.35 * momentum_score + 0.20 * rsi_score - volatility_penalty))
    return {
        "score": round(score, 4),
        "price": round(price, 4),
        "sma20": round(sma20, 4),
        "sma50": round(sma50, 4),
        "momentum20": round(momentum20, 4),
        "rsi14": round(rsi14, 2),
        "vol20": round(vol20, 4),
        "avg_volume": round(avg_volume, 2),
        "reason": f"price={price:.2f}, sma20={sma20:.2f}, sma50={sma50:.2f}, mom20={momentum20:.2%}, rsi={rsi14:.1f}",
    }

