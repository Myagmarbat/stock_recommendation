from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from stock_recommendation.config import DEFAULT_UNIVERSE


@dataclass
class MarketData:
    symbol: str
    history: pd.DataFrame
    info: dict
    news: list[dict]


def get_stable_universe() -> list[str]:
    return list(DEFAULT_UNIVERSE)


def get_price_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    try:
        hist = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
        if hist.empty:
            return pd.DataFrame()
        return hist.dropna(subset=["Close"]).copy()
    except Exception:
        return pd.DataFrame()


def get_market_data(symbol: str) -> MarketData:
    ticker = yf.Ticker(symbol)
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    try:
        news = ticker.news or []
    except Exception:
        news = []
    return MarketData(symbol=symbol, history=get_price_history(symbol), info=info, news=news)
