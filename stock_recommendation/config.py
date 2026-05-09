from __future__ import annotations

import os
from pathlib import Path


AGENT_NAME = "stock_recommendation"
DEFAULT_UNIVERSE = ["SPY", "QQQ", "DIA", "IWM", "VTI", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
INITIAL_PAPER_BALANCE = 10_000.0
RISK_PER_TRADE = 0.01
MAX_TRADES_PER_DAY = 3
DEFAULT_MODEL = "gpt-4.1-mini"
MONTHLY_OPENAI_BUDGET_USD = 5.0
OPENAI_INPUT_PRICE_PER_MILLION = 0.40
OPENAI_OUTPUT_PRICE_PER_MILLION = 1.60
DB_PATH = Path(__file__).resolve().parent / "data" / "paper_trades.db"


def openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def openai_model() -> str:
    return os.getenv("STOCK_RECOMMENDATION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def ai_enabled() -> bool:
    return os.getenv("STOCK_RECOMMENDATION_AI", "0").strip() == "1" and bool(openai_api_key())
