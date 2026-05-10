from __future__ import annotations

import os
from pathlib import Path


AGENT_NAME = "stock_recommendation"
DEFAULT_UNIVERSE = ["SPY", "QQQ", "DIA", "IWM", "VTI", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]
INITIAL_PAPER_BALANCE = 10_000.0
RISK_PER_TRADE = 0.01
MAX_TRADES_PER_DAY = 3
DEFAULT_MODEL = "gpt-5-nano"
MONTHLY_OPENAI_BUDGET_USD = float(os.getenv("STOCK_RECOMMENDATION_AI_MONTHLY_BUDGET_USD", "0.95"))
OPENAI_INPUT_PRICE_PER_MILLION = float(os.getenv("STOCK_RECOMMENDATION_OPENAI_INPUT_PRICE_PER_MILLION", "0.05"))
OPENAI_OUTPUT_PRICE_PER_MILLION = float(os.getenv("STOCK_RECOMMENDATION_OPENAI_OUTPUT_PRICE_PER_MILLION", "0.40"))
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("STOCK_RECOMMENDATION_AI_MAX_OUTPUT_TOKENS", "600"))
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = Path(os.getenv("STOCK_RECOMMENDATION_DATA_DIR", str(PROJECT_DIR / "data"))).expanduser()
DB_PATH = Path(os.getenv("STOCK_RECOMMENDATION_DB_PATH", str(DATA_DIR / "paper_trades.db"))).expanduser()


def openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def openai_model() -> str:
    return os.getenv("STOCK_RECOMMENDATION_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def ai_enabled() -> bool:
    enabled = os.getenv("STOCK_RECOMMENDATION_AI", "1").strip().lower()
    return enabled not in {"0", "false", "no", "off"} and bool(openai_api_key())
