from __future__ import annotations


def _float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def calculate_fundamentals(info: dict) -> dict:
    quote_type = str(info.get("quoteType", "")).upper()
    if quote_type == "ETF" or info.get("fundFamily"):
        assets = _float(info.get("totalAssets"), 0.0)
        return {"score": 0.2 if assets > 1_000_000_000 else 0.0, "quote_type": quote_type, "reason": "ETF liquidity/asset proxy"}

    pe = _float(info.get("trailingPE"), 40.0)
    margin = _float(info.get("profitMargins"), 0.0)
    revenue_growth = _float(info.get("revenueGrowth"), 0.0)
    debt_to_equity = _float(info.get("debtToEquity"), 200.0)
    market_cap = _float(info.get("marketCap"), 0.0)

    score = (
        0.25 * _clamp((35 - pe) / 35)
        + 0.25 * _clamp(margin / 0.25)
        + 0.25 * _clamp(revenue_growth / 0.25)
        + 0.15 * _clamp((150 - debt_to_equity) / 150)
        + 0.10 * _clamp(market_cap / 250_000_000_000)
    )
    return {
        "score": round(score, 4),
        "quote_type": quote_type,
        "market_cap": market_cap,
        "reason": f"pe={pe:.1f}, margin={margin:.2f}, revenue_growth={revenue_growth:.2f}, debt_to_equity={debt_to_equity:.1f}",
    }

