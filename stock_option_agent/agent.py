#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta, time as dt_time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
import shutil
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

YAHOO_SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
YAHOO_SCREENER_URL_ALT = "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
YAHOO_GAINERS_PAGE = "https://finance.yahoo.com/markets/stocks/gainers/"
DEFAULT_BASE_DIR = Path("data")
MODEL_STATE_PATH = Path("data/model/model_params.json")
AGENT_CONFIG_PATH = Path("config/agent_config.json")
US_MARKET_TZ = ZoneInfo("America/New_York")
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
US_MARKET_OPEN = dt_time(9, 30)
US_MARKET_CLOSE = dt_time(16, 0)
MIN_LEARNING_AGE_MINUTES = 10
MIN_RETURN_FOR_LABEL = 0.002
DEFAULT_ENABLE_AFTER_HOURS = False
INITIAL_CAPITAL = 10000.0
REAL_TRADING_CAPITAL = 10000.0
RISK_PER_TRADE = 0.0075
MAX_STOCK_ALLOC_PCT = 0.12
MAX_OPTION_ALLOC_PCT = 0.01
MAX_PORTFOLIO_EXPOSURE_PCT = 0.60
MAX_OPEN_POSITIONS = 8
MAX_HOLD_RUNS_STOCK = 6 * 24 * 5
MAX_HOLD_RUNS_OPTION = 6 * 24 * 3
CONSERVATIVE_PROFILE = True
MIN_MARKET_CAP = 2_000_000_000
MIN_AVG_VOLUME = 2_000_000
MIN_PRICE = 15.0
MAX_VOL20 = 0.035
MAX_BETA = 1.8

POSITIVE_WORDS = {
    "beat",
    "growth",
    "surge",
    "strong",
    "profit",
    "record",
    "upgrade",
    "expands",
    "bullish",
    "outperform",
    "raise",
    "raised",
    "buyback",
    "partnership",
    "guidance",
    "approval",
    "contract",
    "wins",
    "upside",
}
NEGATIVE_WORDS = {
    "miss",
    "fall",
    "weak",
    "lawsuit",
    "downgrade",
    "cuts",
    "bearish",
    "risk",
    "decline",
    "plunge",
    "fraud",
    "probe",
    "investigation",
    "warning",
    "bankruptcy",
    "recall",
    "cuts guidance",
    "delay",
    "default",
}

DEFAULT_SOURCE_WEIGHTS = {
    "reuters": 1.35,
    "bloomberg": 1.35,
    "wall street journal": 1.3,
    "wsj": 1.3,
    "financial times": 1.3,
    "cnbc": 1.2,
    "marketwatch": 1.15,
    "barron": 1.2,
    "yahoo finance": 1.05,
    "seeking alpha": 1.0,
    "benzinga": 0.95,
    "motley fool": 0.8,
    "sec": 1.4,
    "federal reserve": 1.2,
    "reddit": 0.45,
}

DEFAULT_NEWS_CONFIG = {
    "half_life_hours": 24.0,
    "unknown_source_weight": 1.0,
    "missing_timestamp_weight": 0.5,
    "min_recency_weight": 0.2,
    "max_recency_weight": 1.5,
    "normalization_divisor": 2.5,
    "min_headline_count": 5,
    "max_headlines_scored": 40,
    "max_headlines_per_source": 4,
    "tier_multipliers": {
        "core": 1.0,
        "secondary": 0.8,
        "speculative": 0.45,
    },
    "tier_limits": {
        "core": 24,
        "secondary": 12,
        "speculative": 6,
    },
    "source_weights": DEFAULT_SOURCE_WEIGHTS,
}

DEFAULT_NOTIFICATIONS_CONFIG = {
    "enabled": True,
    "channel": "telegram",
    "telegram_enabled": True,
    "telegram_chat_id": "",
    "good_trade_min_score": 0.75,
    "good_trade_min_rr": 1.5,
    "cooldown_minutes": 60,
    "max_alert_items": 3,
}

DEFAULT_MODEL_PARAMS = {
    "weights": {
        "fundamental": 0.4,
        "technical": 0.45,
        "news": 0.15,
    },
    "regime_bias": {
        "bullish": 0.1,
        "neutral": 0.0,
        "bearish": -0.1,
    },
    "thresholds": {
        "bullish_buy": 0.25,
        "bullish_short": -0.30,
        "bearish_buy": 0.45,
        "bearish_short": -0.15,
        "bearish_technical_short": -0.20,
        "neutral_buy": 0.35,
        "neutral_short": -0.35,
    },
    "threshold_adjustments": {
        "buy": 0.0,
        "short": 0.0,
    },
    "learning": {
        "enabled": True,
        "learning_rate": 0.025,
        "max_weight_abs": 1.2,
    },
    "meta": {
        "last_updated_utc": "",
        "updates_applied": 0,
        "last_evaluated_run_id": "",
    },
}

FALLBACK_UNIVERSE = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AMD",
    "NFLX",
    "AVGO",
    "JPM",
    "BAC",
    "XOM",
    "CVX",
    "WMT",
    "COST",
    "V",
    "MA",
    "UNH",
    "LLY",
    "HD",
    "KO",
    "PFE",
    "INTC",
    "PLTR",
    "SMCI",
    "MSTR",
    "COIN",
    "RIVN",
    "SOFI",
    "SHOP",
    "UBER",
    "DIS",
    "CRM",
    "ORCL",
    "ADBE",
    "QCOM",
    "MU",
    "PANW",
    "SNOW",
    "ABNB",
    "PYPL",
    "NKE",
    "BA",
    "GE",
    "CAT",
    "T",
    "VZ",
    "MRNA",
    "BABA",
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLE",
    "XLI",
    "XBI",
    "SMH",
    "TLT",
    "GLD",
]

STABLE_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "JPM", "V", "MA",
    "UNH", "LLY", "PG", "KO", "PEP", "XOM", "CVX", "WMT", "COST", "HD",
    "MCD", "JNJ", "MRK", "ABBV", "TMO", "CRM", "ORCL", "ADBE", "AVGO", "QCOM",
    "TXN", "NKE", "DIS", "CAT", "GE", "HON", "AMGN", "PFE", "BAC", "GS",
    "MS", "SCHW", "SPGI", "BLK", "LOW", "NEE", "DUK", "SO", "VZ", "T",
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLI", "XBI", "SMH", "TLT", "GLD",
]

DEFAULT_TRADING_CONFIG = {
    "stock_only": True,
    "allow_shorting": True,
    "real_trading_capital": 10000.0,
    "paper_initial_capital": 10000.0,
    "include_downtrend_symbols": True,
    "downtrend_symbol_ratio": 0.4,
    "full_budget_deploy": False,
    "full_deploy_target_pct": 1.0,
}

DEFAULT_AGENT_CONFIG = {
    "news": DEFAULT_NEWS_CONFIG,
    "notifications": DEFAULT_NOTIFICATIONS_CONFIG,
    "trading": DEFAULT_TRADING_CONFIG,
}


@dataclass
class AnalysisRow:
    symbol: str
    price: float
    market_regime: str
    fundamental_score: float
    technical_score: float
    news_score: float
    upcoming_earnings_days: int
    earnings_event_score: float
    market_trend_score: float
    category_trend_score: float
    total_score: float
    action_stock: str
    action_option: str
    execution_timing: str
    entry_price: float
    target_price: float
    stop_price: float
    risk_reward: float
    option_symbol_hint: str
    option_expiry: str
    option_strike: float
    prediction_1w_price: float
    prediction_1w_return_pct: float
    prediction_1m_price: float
    prediction_1m_return_pct: float
    prediction_3m_price: float
    prediction_3m_return_pct: float
    prediction_6m_price: float
    prediction_6m_return_pct: float
    prediction_1y_price: float
    prediction_1y_return_pct: float
    prediction_5y_price: float
    prediction_5y_return_pct: float
    reason: str


@dataclass
class NewsHeadline:
    title: str
    source: str
    published_ts: float


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def load_news_config(path: Path) -> dict[str, Any]:
    config = {
        **DEFAULT_NEWS_CONFIG,
        "source_weights": dict(DEFAULT_SOURCE_WEIGHTS),
    }
    if not path.exists():
        return config

    try:
        with path.open("r", encoding="utf-8") as f:
            user_cfg = json.load(f)
    except Exception:
        return config

    if not isinstance(user_cfg, dict):
        return config

    numeric_keys = {
        "half_life_hours",
        "unknown_source_weight",
        "missing_timestamp_weight",
        "min_recency_weight",
        "max_recency_weight",
        "normalization_divisor",
    }
    int_keys = {"min_headline_count", "max_headlines_scored"}

    for key in numeric_keys:
        if key in user_cfg:
            try:
                config[key] = float(user_cfg[key])
            except (TypeError, ValueError):
                pass
    for key in int_keys:
        if key in user_cfg:
            try:
                config[key] = int(user_cfg[key])
            except (TypeError, ValueError):
                pass

    source_weights = user_cfg.get("source_weights")
    if isinstance(source_weights, dict):
        merged = dict(config["source_weights"])
        for k, v in source_weights.items():
            if isinstance(k, str):
                try:
                    merged[k.lower()] = float(v)
                except (TypeError, ValueError):
                    continue
        config["source_weights"] = merged

    return config


NEWS_CONFIG: dict[str, Any] = dict(DEFAULT_NEWS_CONFIG)
NOTIFICATIONS_CONFIG: dict[str, Any] = dict(DEFAULT_NOTIFICATIONS_CONFIG)
TRADING_CONFIG: dict[str, Any] = dict(DEFAULT_TRADING_CONFIG)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_agent_config(path: Path) -> dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULT_AGENT_CONFIG))
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg = deep_merge(cfg, user)
        except Exception:
            pass
    return cfg


def default_model_params() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_MODEL_PARAMS))


def load_model_params(path: Path = MODEL_STATE_PATH) -> dict[str, Any]:
    params = default_model_params()
    if not path.exists():
        return params
    try:
        with path.open("r", encoding="utf-8") as f:
            user = json.load(f)
    except Exception:
        return params
    if not isinstance(user, dict):
        return params

    for section in ("weights", "regime_bias", "thresholds", "threshold_adjustments", "learning", "meta"):
        if isinstance(user.get(section), dict):
            params[section].update(user[section])
    return params


def save_model_params(params: dict[str, Any], path: Path = MODEL_STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(params, f, indent=2)


def compute_total_score(fund: float, tech: float, news: float, regime: str, params: dict[str, Any]) -> float:
    w = params.get("weights", {})
    reg = params.get("regime_bias", {})
    return (
        safe_float(w.get("fundamental"), 0.4) * fund
        + safe_float(w.get("technical"), 0.45) * tech
        + safe_float(w.get("news"), 0.15) * news
        + safe_float(reg.get(regime), 0.0)
    )


def market_hours_context(now_dt: datetime | None = None) -> dict[str, Any]:
    current_utc = now_dt or now_utc()
    now_et = current_utc.astimezone(US_MARKET_TZ)
    now_pt = current_utc.astimezone(PACIFIC_TZ)
    weekday = now_et.weekday()  # Mon=0
    is_weekday = weekday < 5
    open_dt = now_et.replace(hour=US_MARKET_OPEN.hour, minute=US_MARKET_OPEN.minute, second=0, microsecond=0)
    close_dt = now_et.replace(hour=US_MARKET_CLOSE.hour, minute=US_MARKET_CLOSE.minute, second=0, microsecond=0)
    market_open = is_weekday and open_dt <= now_et <= close_dt

    if market_open:
        session = "regular"
        next_open_et = open_dt + timedelta(days=1)
        while next_open_et.weekday() >= 5:
            next_open_et += timedelta(days=1)
        next_open_et = next_open_et.replace(hour=US_MARKET_OPEN.hour, minute=US_MARKET_OPEN.minute, second=0, microsecond=0)
        next_close_et = close_dt
    else:
        if is_weekday and now_et < open_dt:
            session = "pre_market"
            next_open_et = open_dt
        else:
            session = "after_hours" if is_weekday else "weekend"
            next_open_et = now_et + timedelta(days=1)
            while next_open_et.weekday() >= 5:
                next_open_et += timedelta(days=1)
            next_open_et = next_open_et.replace(hour=US_MARKET_OPEN.hour, minute=US_MARKET_OPEN.minute, second=0, microsecond=0)
        next_close_et = next_open_et.replace(hour=US_MARKET_CLOSE.hour, minute=US_MARKET_CLOSE.minute)

    mins_to_open = int((next_open_et - now_et).total_seconds() // 60)
    mins_to_close = int((next_close_et - now_et).total_seconds() // 60)
    next_open_pt = next_open_et.astimezone(PACIFIC_TZ)
    next_close_pt = next_close_et.astimezone(PACIFIC_TZ)
    return {
        "market_open": market_open,
        "market_session": session,
        "market_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "market_time_pt": now_pt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "next_open_et": next_open_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "next_close_et": next_close_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "next_open_pt": next_open_pt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "next_close_pt": next_close_pt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "minutes_to_open": max(mins_to_open, 0),
        "minutes_to_close": max(mins_to_close, 0),
        "holiday_calendar_applied": False,
    }


def previous_trading_day_et(now_dt: datetime | None = None) -> str:
    now_et = (now_dt or now_utc()).astimezone(US_MARKET_TZ)
    d = now_et.date()
    # If market is open in ET regular hours, previous completed close is prior weekday.
    if now_et.weekday() < 5 and now_et.time() >= US_MARKET_CLOSE:
        ref = d
    else:
        ref = d - timedelta(days=1)
    while ref.weekday() >= 5:
        ref = ref - timedelta(days=1)
    return ref.strftime("%Y-%m-%d")


def previous_trading_day_pt(now_dt: datetime | None = None) -> str:
    now_pt = (now_dt or now_utc()).astimezone(PACIFIC_TZ)
    return previous_trading_day_et(now_pt.astimezone(timezone.utc))


def post_analyze_and_adapt(base_dir: Path, params: dict[str, Any], enable_after_hours: bool) -> dict[str, Any]:
    if not params.get("learning", {}).get("enabled", True):
        return {"status": "disabled"}
    mkt = market_hours_context()

    runs_dir = base_dir / "runs"
    if not runs_dir.exists():
        return {"status": "no_runs"}
    run_ids: list[str] = []
    for p in runs_dir.iterdir():
        if not p.is_dir():
            continue
        mc = p / "market_context.json"
        t10 = p / "top10.csv"
        if not (mc.exists() and t10.exists()):
            continue
        try:
            ctx = json.loads(mc.read_text(encoding="utf-8"))
            if str(ctx.get("regime", "")) == "stale_snapshot":
                continue
        except Exception:
            continue
        run_ids.append(p.name)
    run_ids = sorted(run_ids)
    if not run_ids:
        return {"status": "no_evaluable_runs"}

    last_run_id = run_ids[-1]
    meta = params.get("meta", {})
    if str(meta.get("last_evaluated_run_id", "")) == last_run_id:
        return {"status": "already_evaluated", "evaluated_run_id": last_run_id}

    try:
        run_dt = datetime.strptime(last_run_id, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        age_min = int((now_utc() - run_dt).total_seconds() // 60)
    except Exception:
        age_min = 10**9
    if age_min < MIN_LEARNING_AGE_MINUTES:
        return {"status": "too_fresh", "evaluated_run_id": last_run_id, "age_minutes": age_min}

    last_run = runs_dir / last_run_id
    top10_path = last_run / "top10.csv"
    if not top10_path.exists():
        return {"status": "missing_top10"}

    try:
        prior = pd.read_csv(top10_path)
    except Exception:
        return {"status": "read_error"}
    if prior.empty:
        return {"status": "empty_top10"}

    lr = safe_float(params.get("learning", {}).get("learning_rate"), 0.025)
    max_abs = safe_float(params.get("learning", {}).get("max_weight_abs"), 1.2)
    weights = params.get("weights", {})
    thresholds = params.get("threshold_adjustments", {})

    evaluated = 0
    correct = 0
    buy_total = 0
    buy_correct = 0
    short_total = 0
    short_correct = 0

    market_open_now = bool(mkt.get("market_open"))
    if not market_open_now:
        reference_mode = "market_close"
    else:
        reference_mode = "extended_or_intraday" if enable_after_hours else "regular_session_only"
    for row in prior.to_dict(orient="records"):
        action = str(row.get("action_stock", ""))
        if action not in {"BUY_STOCK", "SELL_SHORT"}:
            continue
        symbol = str(row.get("symbol", ""))
        rec_price = safe_float(row.get("price"), 0.0)
        if not symbol or rec_price <= 0:
            continue
        try:
            if not market_open_now:
                hist = yf.Ticker(symbol).history(period="5d", interval="1d")
            else:
                hist = yf.Ticker(symbol).history(period="1d", interval="1m", prepost=enable_after_hours)
                if hist.empty:
                    hist = yf.Ticker(symbol).history(period="5d", interval="1d")
                    reference_mode = "last_regular_close"
            if hist.empty:
                continue
            now_price = safe_float(hist["Close"].iloc[-1], 0.0)
            if now_price <= 0:
                continue
        except Exception:
            continue

        ret = (now_price / rec_price) - 1
        # Ignore micro-noise; require at least 20 bps move to label.
        if abs(ret) < MIN_RETURN_FOR_LABEL:
            continue
        y = 1.0 if ret > 0 else -1.0
        target = 1.0 if action == "BUY_STOCK" else -1.0
        is_correct = (y == target)
        evaluated += 1
        correct += 1 if is_correct else 0

        if action == "BUY_STOCK":
            buy_total += 1
            buy_correct += 1 if is_correct else 0
        else:
            short_total += 1
            short_correct += 1 if is_correct else 0

        fund = safe_float(row.get("fundamental_score"))
        tech = safe_float(row.get("technical_score"))
        news = safe_float(row.get("news_score"))
        regime = str(row.get("market_regime", "neutral"))

        pred_score = compute_total_score(fund, tech, news, regime, params)
        pred = max(-1.0, min(1.0, pred_score))
        err = y - pred

        weights["fundamental"] = clamp(safe_float(weights.get("fundamental"), 0.4) + lr * err * fund, -max_abs, max_abs)
        weights["technical"] = clamp(safe_float(weights.get("technical"), 0.45) + lr * err * tech, -max_abs, max_abs)
        weights["news"] = clamp(safe_float(weights.get("news"), 0.15) + lr * err * news, -max_abs, max_abs)

    if buy_total >= 2:
        buy_acc = buy_correct / buy_total
        if buy_acc < 0.5:
            thresholds["buy"] = clamp(safe_float(thresholds.get("buy"), 0.0) + 0.02, -0.3, 0.3)
        elif buy_acc > 0.65:
            thresholds["buy"] = clamp(safe_float(thresholds.get("buy"), 0.0) - 0.01, -0.3, 0.3)

    if short_total >= 2:
        short_acc = short_correct / short_total
        if short_acc < 0.5:
            thresholds["short"] = clamp(safe_float(thresholds.get("short"), 0.0) - 0.02, -0.3, 0.3)
        elif short_acc > 0.65:
            thresholds["short"] = clamp(safe_float(thresholds.get("short"), 0.0) + 0.01, -0.3, 0.3)

    if evaluated == 0:
        params.setdefault("meta", {})
        params["meta"]["last_updated_utc"] = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        params["meta"]["last_evaluated_run_id"] = last_run_id
        save_model_params(params)
        return {
            "status": "no_evaluable_rows",
            "evaluated_run_id": last_run_id,
            "market_session": mkt.get("market_session"),
            "price_reference_mode": reference_mode,
        }

    params["weights"] = weights
    params["threshold_adjustments"] = thresholds
    params.setdefault("meta", {})
    params["meta"]["last_updated_utc"] = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    params["meta"]["updates_applied"] = int(params["meta"].get("updates_applied", 0)) + 1
    params["meta"]["last_evaluated_run_id"] = last_run_id

    save_model_params(params)
    return {
        "status": "updated",
        "evaluated_run_id": last_run_id,
        "market_session": mkt.get("market_session"),
        "price_reference_mode": reference_mode,
        "evaluated": evaluated,
        "correct": correct,
        "accuracy": round(correct / evaluated, 4),
        "buy_accuracy": round(buy_correct / buy_total, 4) if buy_total else None,
        "short_accuracy": round(short_correct / short_total, 4) if short_total else None,
        "weights": {
            "fundamental": round(safe_float(weights.get("fundamental"), 0.0), 4),
            "technical": round(safe_float(weights.get("technical"), 0.0), 4),
            "news": round(safe_float(weights.get("news"), 0.0), 4),
        },
        "threshold_adjustments": {
            "buy": round(safe_float(thresholds.get("buy"), 0.0), 4),
            "short": round(safe_float(thresholds.get("short"), 0.0), 4),
        },
    }


def save_post_analysis(base_dir: Path, summary: dict[str, Any]) -> None:
    history_dir = base_dir / "history"
    latest_dir = base_dir / "latest"
    history_dir.mkdir(parents=True, exist_ok=True)
    latest_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        **summary,
    }
    with (latest_dir / "post_analysis.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with (history_dir / "post_analysis_history.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def fetch_screener_symbols(scr_id: str, count: int = 50) -> list[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    params = {
        "formatted": "false",
        "scrIds": scr_id,
        "count": str(count),
        "start": "0",
    }

    for base_url in (YAHOO_SCREENER_URL, YAHOO_SCREENER_URL_ALT):
        for attempt in range(3):
            try:
                r = requests.get(base_url, params=params, headers=headers, timeout=20)
                if r.status_code == 429:
                    time.sleep(1.5 + attempt + random.random())
                    continue
                r.raise_for_status()
                data = r.json()
                quotes = data["finance"]["result"][0]["quotes"]
                out = []
                for q in quotes:
                    sym = q.get("symbol")
                    if sym and isinstance(sym, str):
                        out.append(sym.upper())
                out = filter_equity_symbols(out)
                if out:
                    return out[:count]
            except Exception:
                time.sleep(1 + random.random())

    return []


def fetch_top_gainers(count: int = 50) -> list[str]:
    out = fetch_screener_symbols("day_gainers", count)
    if out:
        return merge_with_fallback(out, count)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        page = requests.get(YAHOO_GAINERS_PAGE, headers=headers, timeout=20)
        page.raise_for_status()
        html = page.text
        parsed = re.findall(r'"symbol":"([A-Z.\\-]{1,12})"', html)
        if parsed:
            unique = list(dict.fromkeys(parsed))
            unique = filter_equity_symbols(unique)
            if unique:
                return merge_with_fallback(unique, count)
    except Exception:
        pass

    return fallback_top_movers(count)


def fetch_market_movers(count: int = 50, include_downtrend: bool = True, downtrend_ratio: float = 0.4) -> list[str]:
    if not include_downtrend:
        return fetch_top_gainers(count)

    ratio = clamp(safe_float(downtrend_ratio, 0.4), 0.2, 0.8)
    losers_n = max(1, int(round(count * ratio)))
    gainers_n = max(1, count - losers_n)

    gainers = fetch_screener_symbols("day_gainers", gainers_n)
    losers = fetch_screener_symbols("day_losers", losers_n)
    combined = filter_equity_symbols((gainers or []) + (losers or []))
    if combined:
        return merge_with_fallback(combined, count)
    return fetch_top_gainers(count)


def filter_equity_symbols(symbols: list[str]) -> list[str]:
    out = []
    for sym in symbols:
        if not sym:
            continue
        if "-" in sym or "^" in sym or "=" in sym or "/" in sym:
            continue
        if len(sym) > 6:
            continue
        out.append(sym)
    return list(dict.fromkeys(out))


def merge_with_fallback(symbols: list[str], count: int) -> list[str]:
    if len(symbols) >= count:
        return symbols[:count]
    missing = count - len(symbols)
    fallback = [s for s in fallback_top_movers(count + 20) if s not in symbols]
    return (symbols + fallback[:missing])[:count]


def fallback_top_movers(count: int) -> list[str]:
    scores: list[tuple[str, float]] = []
    for sym in FALLBACK_UNIVERSE:
        try:
            hist = yf.Ticker(sym).history(period="1mo", interval="1d")
            if len(hist) < 6:
                continue
            c = hist["Close"]
            ret5 = (c.iloc[-1] / c.iloc[-6]) - 1
            scores.append((sym, float(ret5)))
        except Exception:
            continue
    scores.sort(key=lambda x: x[1], reverse=True)
    return [sym for sym, _ in scores[:count]]


def market_regime() -> tuple[str, dict[str, float]]:
    try:
        spy = yf.Ticker("SPY").history(period="1y", interval="1d")
        qqq = yf.Ticker("QQQ").history(period="1y", interval="1d")
    except Exception:
        return "neutral", {"market_data_error": 1.0}
    if len(spy) < 210 or len(qqq) < 210:
        return "neutral", {"market_data_error": 1.0}

    def regime_for(df: pd.DataFrame) -> tuple[float, float]:
        close = df["Close"]
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        ret20 = (close.iloc[-1] / close.iloc[-20]) - 1
        trend = 1.0 if sma50 > sma200 else -1.0
        return trend, ret20

    t1, r1 = regime_for(spy)
    t2, r2 = regime_for(qqq)
    regime_score = (t1 + t2) / 2 + (r1 + r2)
    if regime_score > 0.4:
        regime = "bullish"
    elif regime_score < -0.4:
        regime = "bearish"
    else:
        regime = "neutral"
    return regime, {"spy_20d_return": r1, "qqq_20d_return": r2, "regime_score": regime_score}


def market_trend_score(regime: str, ctx: dict[str, Any]) -> float:
    base = {"bullish": 0.6, "neutral": 0.0, "bearish": -0.6}.get(regime, 0.0)
    spy_ret = safe_float(ctx.get("spy_20d_return"), 0.0)
    qqq_ret = safe_float(ctx.get("qqq_20d_return"), 0.0)
    momentum = clamp((spy_ret + qqq_ret) / 0.12, -1, 1)
    return round(clamp(0.6 * base + 0.4 * momentum, -1, 1), 4)


def next_earnings_days(ticker: yf.Ticker, info: dict[str, Any]) -> int:
    now_ts = now_utc().timestamp()
    candidates: list[float] = []

    for k in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd"):
        v = safe_float(info.get(k), 0.0)
        if v > now_ts:
            candidates.append(v)

    try:
        cal = ticker.calendar
        if cal is not None:
            if isinstance(cal, pd.DataFrame):
                for v in cal.to_numpy().flatten().tolist():
                    try:
                        dt = pd.to_datetime(v, utc=True)
                        if pd.notna(dt):
                            ts = float(dt.timestamp())
                            if ts > now_ts:
                                candidates.append(ts)
                    except Exception:
                        continue
            elif isinstance(cal, dict):
                for v in cal.values():
                    try:
                        dt = pd.to_datetime(v, utc=True)
                        if pd.notna(dt):
                            ts = float(dt.timestamp())
                            if ts > now_ts:
                                candidates.append(ts)
                    except Exception:
                        continue
    except Exception:
        pass

    try:
        ed = ticker.earnings_dates
        if isinstance(ed, pd.DataFrame) and not ed.empty:
            for idx in ed.index.tolist()[:8]:
                try:
                    dt = pd.to_datetime(idx, utc=True)
                    if pd.notna(dt):
                        ts = float(dt.timestamp())
                        if ts > now_ts:
                            candidates.append(ts)
                except Exception:
                    continue
    except Exception:
        pass

    if not candidates:
        return -1
    next_ts = min(candidates)
    return max(0, int((next_ts - now_ts) // 86400))


def earnings_outlook_score(info: dict[str, Any]) -> float:
    eg = safe_float(info.get("earningsQuarterlyGrowth"), safe_float(info.get("earningsGrowth"), 0.0))
    rg = safe_float(info.get("revenueGrowth"), 0.0)
    rec = safe_float(info.get("recommendationMean"), 3.0)  # 1(best) .. 5(worst)
    eg_c = clamp((eg + 0.05) / 0.25, 0.0, 1.0)
    rg_c = clamp((rg + 0.03) / 0.18, 0.0, 1.0)
    rec_c = clamp((3.2 - rec) / 1.8, 0.0, 1.0)
    return round(clamp(0.45 * eg_c + 0.30 * rg_c + 0.25 * rec_c, 0.0, 1.0), 4)


def price_setup_score(hist: pd.DataFrame, price: float) -> float:
    if len(hist) < 60 or price <= 0:
        return 0.0
    close = hist["Close"]
    sma20 = safe_float(close.rolling(20).mean().iloc[-1], price)
    sma50 = safe_float(close.rolling(50).mean().iloc[-1], price)
    rsi14 = rsi(close, 14)
    trend_c = 1.0 if price >= sma50 else 0.2
    # Favor reasonable entry zones (not deeply oversold/overbought).
    rsi_c = 1.0 - clamp(abs(rsi14 - 55.0) / 30.0, 0.0, 1.0)
    dist20 = abs(price - sma20) / max(1e-6, sma20)
    meanrev_c = 1.0 - clamp(dist20 / 0.12, 0.0, 1.0)
    return round(clamp(0.45 * trend_c + 0.30 * rsi_c + 0.25 * meanrev_c, 0.0, 1.0), 4)


def earnings_event_score(
    days_to_earnings: int,
    fund: float,
    tech: float,
    news: float,
    regime: str,
    outlook_score: float,
    price_score: float,
) -> float:
    # Pre-earnings accumulation window: up to 30 days before event, weighted by proximity and quality.
    if days_to_earnings < 0:
        return 0.0
    if days_to_earnings <= 1:
        return 0.0
    if days_to_earnings > 30:
        return 0.0

    fund_c = clamp((fund + 0.2) / 0.8, 0.0, 1.0)
    tech_c = clamp((tech + 0.2) / 0.8, 0.0, 1.0)
    news_c = clamp((news + 0.08) / 0.24, 0.0, 1.0)
    quality = clamp(
        0.20 * fund_c + 0.20 * tech_c + 0.10 * news_c + 0.30 * outlook_score + 0.20 * price_score,
        0.0,
        1.0,
    )
    proximity = clamp((30 - days_to_earnings) / 28.0, 0.0, 1.0)
    regime_factor = 0.55 if regime == "bearish" else 1.0
    return round(clamp(quality * (0.55 + 0.45 * proximity) * regime_factor, 0.0, 1.0), 4)


def build_category_context() -> dict[str, float]:
    # Sector ETFs + macro proxies for world/oil backdrop.
    symbols = {
        "Technology": "XLK",
        "Financial Services": "XLF",
        "Financial": "XLF",
        "Healthcare": "XLV",
        "Consumer Defensive": "XLP",
        "Consumer Cyclical": "XLY",
        "Industrials": "XLI",
        "Utilities": "XLU",
        "Real Estate": "XLRE",
        "Energy": "XLE",
        "Basic Materials": "XLB",
        "Communication Services": "XLC",
        "world": "VT",
        "oil": "USO",
    }
    out: dict[str, float] = {}
    for key, ticker in symbols.items():
        try:
            h = yf.Ticker(ticker).history(period="2mo", interval="1d")
            if len(h) >= 21:
                c = h["Close"]
                out[key] = safe_float((c.iloc[-1] / c.iloc[-20]) - 1, 0.0)
            else:
                out[key] = 0.0
        except Exception:
            out[key] = 0.0
    return out


def category_trend_score(info: dict[str, Any], category_ctx: dict[str, float]) -> float:
    sector = str(info.get("sector", "")).strip()
    sector_ret = safe_float(category_ctx.get(sector), 0.0)
    world_ret = safe_float(category_ctx.get("world"), 0.0)
    oil_ret = safe_float(category_ctx.get("oil"), 0.0)
    oil_component = oil_ret if sector == "Energy" else 0.0
    raw = 0.65 * sector_ret + 0.25 * world_ret + 0.10 * oil_component
    return round(clamp(raw / 0.08, -1, 1), 4)


def is_etf_like(info: dict[str, Any]) -> bool:
    quote_type = str(info.get("quoteType", "")).strip().upper()
    fund_family = str(info.get("fundFamily", "")).strip()
    return quote_type == "ETF" or bool(fund_family)


def fundamental_score(info: dict[str, Any]) -> tuple[float, str]:
    if is_etf_like(info):
        return 0.0, "ETF_fundamentals_n/a"
    pe = safe_float(info.get("trailingPE"), 40)
    margin = safe_float(info.get("profitMargins"))
    roe = safe_float(info.get("returnOnEquity"))
    rev_growth = safe_float(info.get("revenueGrowth"))
    debt_to_equity = safe_float(info.get("debtToEquity"), 200)

    pe_score = clamp((30 - pe) / 30, -1, 1)
    margin_score = clamp(margin / 0.25, -1, 1)
    roe_score = clamp(roe / 0.3, -1, 1)
    growth_score = clamp(rev_growth / 0.3, -1, 1)
    debt_score = clamp((100 - debt_to_equity) / 100, -1, 1)

    total = 0.2 * pe_score + 0.2 * margin_score + 0.2 * roe_score + 0.25 * growth_score + 0.15 * debt_score
    reason = (
        f"PE={pe:.1f}, margin={margin:.2f}, ROE={roe:.2f}, "
        f"rev_growth={rev_growth:.2f}, debt_to_equity={debt_to_equity:.1f}"
    )
    return total, reason


def rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    values = 100 - (100 / (1 + rs))
    out = values.iloc[-1]
    return float(out) if pd.notna(out) else 50.0


def technical_score(hist: pd.DataFrame) -> tuple[float, str]:
    if len(hist) < 210:
        return 0.0, "insufficient_history"
    close = hist["Close"]
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    mom20 = (close.iloc[-1] / close.iloc[-20]) - 1
    rsi14 = rsi(close, 14)
    vol = close.pct_change().rolling(20).std().iloc[-1]

    trend = clamp((sma20 - sma50) / sma50 * 10, -1, 1) + clamp((sma50 - sma200) / sma200 * 8, -1, 1)
    momentum = clamp(mom20 / 0.2, -1, 1)
    rsi_component = clamp((rsi14 - 50) / 25, -1, 1)
    volatility_penalty = clamp(vol / 0.05, 0, 2)
    total = 0.4 * trend + 0.35 * momentum + 0.25 * rsi_component - 0.1 * volatility_penalty
    reason = (
        f"sma20={sma20:.2f}, sma50={sma50:.2f}, sma200={sma200:.2f}, "
        f"mom20={mom20:.2%}, rsi14={rsi14:.1f}, vol20={vol:.2%}"
    )
    return total, reason


def vol20(hist: pd.DataFrame) -> float:
    try:
        return safe_float(hist["Close"].pct_change().rolling(20).std().iloc[-1], 0.0)
    except Exception:
        return 0.0


def conservative_gate(symbol: str, info: dict[str, Any], hist: pd.DataFrame, price: float) -> tuple[bool, str]:
    if not CONSERVATIVE_PROFILE:
        return True, "profile_off"
    market_cap = safe_float(info.get("marketCap"), 0.0)
    if is_etf_like(info) and market_cap <= 0:
        market_cap = safe_float(info.get("totalAssets"), 0.0)
    avg_vol = safe_float(info.get("averageVolume"), 0.0)
    beta = abs(safe_float(info.get("beta"), 1.0))
    v20 = vol20(hist)
    checks = {
        "mcap": market_cap >= MIN_MARKET_CAP,
        "avg_vol": avg_vol >= MIN_AVG_VOLUME,
        "price": price >= MIN_PRICE,
        "vol20": v20 <= MAX_VOL20 if v20 > 0 else True,
        "beta": beta <= MAX_BETA if beta > 0 else True,
    }
    ok = all(checks.values())
    # Weekend/off-hours resilience: if metadata is unavailable but symbol is in stable universe,
    # allow analysis using historical price/volume behavior instead of rejecting all rows.
    if (market_cap <= 0 or avg_vol <= 0) and symbol in STABLE_UNIVERSE and len(hist) >= 200 and price >= MIN_PRICE:
        if (v20 <= MAX_VOL20 if v20 > 0 else True) and (beta <= MAX_BETA if beta > 0 else True):
            return True, "gate_fallback(stable_symbol_missing_info)"
    reason = (
        f"gate(mcap={market_cap:.0f},avg_vol={avg_vol:.0f},price={price:.2f},"
        f"vol20={v20:.2%},beta={beta:.2f})"
    )
    return ok, reason


def conservative_option_allowed(
    total: float, stock_action: str, market_cap: float, v20: float, beta: float, regime: str
) -> bool:
    if stock_action not in {"BUY_STOCK", "SELL_SHORT"}:
        return False
    if market_cap < 100_000_000_000:
        return False
    if v20 > 0.025 or beta > 1.4:
        return False
    if regime == "bearish":
        return total <= -0.95
    return total >= 0.9


def news_sentiment(symbol: str, news_items: list[dict[str, Any]]) -> tuple[float, str]:
    headlines: list[NewsHeadline] = []
    for item in news_items[:20]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        publisher = str(item.get("publisher") or item.get("provider") or "unknown")
        publish_time = safe_float(item.get("providerPublishTime"))
        headlines.append(NewsHeadline(title=title, source=publisher, published_ts=publish_time))

    web_headlines = fetch_web_news_headlines(symbol, limit=20)
    headlines.extend(web_headlines)
    return score_headline_sentiment(headlines)


def build_news_feed_urls(symbol: str) -> list[str]:
    q_symbol = quote_plus(symbol)
    q_stock = quote_plus(f"{symbol} stock")
    q_filings_transcripts = quote_plus(
        f"{symbol} (8-K OR 10-Q OR 10-K OR earnings call transcript OR investor presentation)"
    )
    q_macro = quote_plus(
        "FOMC OR Federal Reserve OR CPI OR PCE OR Nonfarm Payrolls OR unemployment rate OR treasury yield"
    )
    q_niche = quote_plus(f"{symbol} stock sentiment")
    return [
        # Core feeds
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={q_symbol}&region=US&lang=en-US",
        f"https://news.google.com/rss/search?q={q_stock}&hl=en-US&gl=US&ceid=US:en",
        # SEC/filings + earnings transcripts (core fundamental signal)
        f"https://news.google.com/rss/search?q={q_filings_transcripts}&hl=en-US&gl=US&ceid=US:en",
        # Macro/economic calendar-like events (secondary context signal)
        f"https://news.google.com/rss/search?q={q_macro}&hl=en-US&gl=US&ceid=US:en",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        # Niche sentiment (speculative / low weight by config)
        f"https://www.reddit.com/search.rss?q={q_niche}&sort=new&t=day",
    ]


def fetch_web_news_headlines(symbol: str, limit: int = 20) -> list[NewsHeadline]:
    if not symbol:
        return []
    urls = build_news_feed_urls(symbol)
    headlines: list[NewsHeadline] = []
    for url in urls:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            root = ET.fromstring(r.text)
            for item in root.findall(".//item"):
                title_el = item.find("title")
                if title_el is None or title_el.text is None:
                    continue
                title = title_el.text.strip()
                if not title:
                    continue
                source = "unknown"
                source_el = item.find("source")
                if source_el is not None and source_el.text:
                    source = source_el.text.strip()
                elif "news.google.com" in url and " - " in title:
                    source = title.rsplit(" - ", 1)[-1].strip()
                elif "federalreserve.gov" in url:
                    source = "Federal Reserve"
                elif "reddit.com" in url:
                    source = "Reddit"
                pub_ts = parse_rss_pubdate(item.findtext("pubDate", default=""))
                headlines.append(NewsHeadline(title=title, source=source, published_ts=pub_ts))
        except Exception:
            continue
    deduped: list[NewsHeadline] = []
    seen: set[str] = set()
    for h in headlines:
        key = normalize_headline(h.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    return deduped[:limit]


def source_tier(source: str) -> str:
    s = (source or "").lower()
    core_keys = (
        "reuters",
        "bloomberg",
        "wall street journal",
        "wsj",
        "financial times",
        "cnbc",
        "marketwatch",
        "barron",
        "yahoo finance",
        "sec",
        "federal reserve",
    )
    secondary_keys = (
        "seeking alpha",
        "benzinga",
        "motley fool",
        "investing.com",
    )
    speculative_keys = (
        "reddit",
        "stocktwits",
        "x.com",
        "twitter",
    )
    if any(k in s for k in speculative_keys):
        return "speculative"
    if any(k in s for k in core_keys):
        return "core"
    if any(k in s for k in secondary_keys):
        return "secondary"
    return "secondary"


def parse_rss_pubdate(value: str) -> float:
    if not value:
        return 0.0
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def normalize_headline(title: str) -> str:
    t = title.lower().strip()
    return re.sub(r"\s+", " ", t)


def source_weight(source: str) -> float:
    s = (source or "").lower()
    source_weights = NEWS_CONFIG.get("source_weights", DEFAULT_SOURCE_WEIGHTS)
    for key, weight in source_weights.items():
        if key in s:
            return weight
    return safe_float(NEWS_CONFIG.get("unknown_source_weight"), 1.0)


def recency_weight(published_ts: float, now_ts: float) -> float:
    if published_ts <= 0:
        return safe_float(NEWS_CONFIG.get("missing_timestamp_weight"), 0.5)
    age_hours = max(0.0, (now_ts - published_ts) / 3600)
    half_life = max(1.0, safe_float(NEWS_CONFIG.get("half_life_hours"), 24.0))
    decay = 0.5 ** (age_hours / half_life)
    min_w = safe_float(NEWS_CONFIG.get("min_recency_weight"), 0.2)
    max_w = safe_float(NEWS_CONFIG.get("max_recency_weight"), 1.5)
    return clamp(decay, min_w, max_w)


def score_headline_sentiment(headlines: list[NewsHeadline]) -> tuple[float, str]:
    if not headlines:
        return 0.0, "no_recent_news"
    min_count = max(1, int(NEWS_CONFIG.get("min_headline_count", 5)))
    if len(headlines) < min_count:
        return 0.0, f"insufficient_headlines={len(headlines)}/{min_count}"

    weighted_score = 0.0
    total_weight = 0.0
    checked = 0
    now_ts = now_utc().timestamp()
    max_scored = max(1, int(NEWS_CONFIG.get("max_headlines_scored", 40)))
    max_per_source = max(1, int(NEWS_CONFIG.get("max_headlines_per_source", 4)))
    tier_multipliers = NEWS_CONFIG.get("tier_multipliers", {"core": 1.0, "secondary": 0.8, "speculative": 0.45})
    tier_limits_cfg = NEWS_CONFIG.get("tier_limits", {"core": 24, "secondary": 12, "speculative": 6})
    source_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    for headline in headlines[:max_scored]:
        source_key = (headline.source or "unknown").lower()
        if source_counts.get(source_key, 0) >= max_per_source:
            continue
        tier = source_tier(headline.source)
        tier_limit = max(1, int(safe_float(tier_limits_cfg.get(tier), 8)))
        if tier_counts.get(tier, 0) >= tier_limit:
            continue
        t = headline.title.lower()
        p = sum(1 for w in POSITIVE_WORDS if w in t)
        n = sum(1 for w in NEGATIVE_WORDS if w in t)
        base = p - n
        tier_mul = safe_float(tier_multipliers.get(tier), 1.0)
        w = source_weight(headline.source) * tier_mul * recency_weight(headline.published_ts, now_ts)
        weighted_score += base * w
        total_weight += w
        checked += 1
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    if checked == 0 or total_weight <= 0:
        return 0.0, "no_parsable_headlines"
    raw = weighted_score / total_weight
    divisor = max(0.1, safe_float(NEWS_CONFIG.get("normalization_divisor"), 2.5))
    normalized = clamp(raw / divisor, -1, 1)
    return normalized, f"headline_sentiment={raw:.2f} weighted from {checked} headlines tiers={tier_counts}"


def pick_option_candidate(ticker: yf.Ticker, action_option: str, underlying_price: float) -> tuple[str, str, float]:
    if action_option not in {"BUY_CALL", "BUY_PUT"}:
        return "", "", 0.0
    try:
        expirations = list(ticker.options)
        if not expirations:
            return "", "", 0.0
        exp = expirations[0]
        chain = ticker.option_chain(exp)
        table = chain.calls if action_option == "BUY_CALL" else chain.puts
        if table.empty:
            return "", exp, 0.0
        table = table.copy()
        table["distance"] = (table["strike"] - underlying_price).abs()
        table = table.sort_values(["distance", "openInterest", "volume"], ascending=[True, False, False])
        row = table.iloc[0]
        contract_symbol = str(row.get("contractSymbol", ""))
        strike = safe_float(row.get("strike"))
        return contract_symbol, exp, strike
    except Exception:
        return "", "", 0.0


def decide_actions(regime: str, total: float, technical: float, params: dict[str, Any]) -> tuple[str, str]:
    th = params.get("thresholds", {})
    adj = params.get("threshold_adjustments", {})
    buy_adj = safe_float(adj.get("buy"), 0.0)
    short_adj = safe_float(adj.get("short"), 0.0)
    allow_shorting = bool(TRADING_CONFIG.get("allow_shorting", True))

    if regime == "bullish":
        bullish_buy = safe_float(th.get("bullish_buy"), 0.25) + buy_adj
        bullish_short = safe_float(th.get("bullish_short"), -0.30) + short_adj
        if total >= bullish_buy:
            return "BUY_STOCK", "NO_OPTION" if (CONSERVATIVE_PROFILE or TRADING_CONFIG.get("stock_only", True)) else "BUY_CALL"
        if allow_shorting:
            if (not CONSERVATIVE_PROFILE) and total <= bullish_short:
                return "SELL_SHORT", "BUY_PUT"
            if CONSERVATIVE_PROFILE and total <= min(bullish_short, -0.55) and technical <= -0.35:
                return "SELL_SHORT", "NO_OPTION" if TRADING_CONFIG.get("stock_only", True) else "BUY_PUT"
        return "HOLD", "NO_OPTION"

    if regime == "bearish":
        bearish_buy = safe_float(th.get("bearish_buy"), 0.45) + buy_adj
        bearish_short = safe_float(th.get("bearish_short"), -0.15) + short_adj
        bearish_tech_short = safe_float(th.get("bearish_technical_short"), -0.2)
        if allow_shorting:
            if ((not CONSERVATIVE_PROFILE) and (total <= bearish_short or technical < bearish_tech_short)) or (
                CONSERVATIVE_PROFILE and (total <= min(bearish_short, -0.25) or technical < min(bearish_tech_short, -0.35))
            ):
                return "SELL_SHORT", "NO_OPTION" if (CONSERVATIVE_PROFILE or TRADING_CONFIG.get("stock_only", True)) else "BUY_PUT"
        if total >= bearish_buy:
            return "BUY_STOCK", "NO_OPTION" if (CONSERVATIVE_PROFILE or TRADING_CONFIG.get("stock_only", True)) else "BUY_CALL"
        return "HOLD", "NO_OPTION"

    neutral_buy = safe_float(th.get("neutral_buy"), 0.35) + buy_adj
    neutral_short = safe_float(th.get("neutral_short"), -0.35) + short_adj
    if total >= neutral_buy:
        return "BUY_STOCK", "NO_OPTION" if (CONSERVATIVE_PROFILE or TRADING_CONFIG.get("stock_only", True)) else "BUY_CALL"
    if allow_shorting:
        if (not CONSERVATIVE_PROFILE) and total <= neutral_short:
            return "SELL_SHORT", "BUY_PUT"
        if CONSERVATIVE_PROFILE and total <= min(neutral_short, -0.45) and technical <= -0.30:
            return "SELL_SHORT", "NO_OPTION" if TRADING_CONFIG.get("stock_only", True) else "BUY_PUT"
    return "HOLD", "NO_OPTION"


def trade_levels(hist: pd.DataFrame, price: float, action_stock: str) -> tuple[float, float, float, float]:
    if action_stock not in {"BUY_STOCK", "SELL_SHORT"}:
        return 0.0, 0.0, 0.0, 0.0
    atr = 0.0
    try:
        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = safe_float(tr.rolling(14).mean().iloc[-1], 0.0)
    except Exception:
        atr = 0.0
    if atr <= 0:
        vol20 = safe_float(hist["Close"].pct_change().rolling(20).std().iloc[-1], 0.02)
        atr = max(price * vol20, price * 0.01)

    if action_stock == "BUY_STOCK":
        entry = price * 0.997
        stop = entry - 1.2 * atr
        target = entry + 2.0 * atr
    else:
        entry = price * 1.003
        stop = entry + 1.2 * atr
        target = entry - 2.0 * atr

    risk = abs(entry - stop)
    reward = abs(target - entry)
    rr = reward / risk if risk > 0 else 0.0
    return round(entry, 4), round(target, 4), round(stop, 4), round(rr, 3)


PREDICTION_HORIZONS: tuple[tuple[str, int], ...] = (
    ("1w", 5),
    ("1m", 21),
    ("3m", 63),
    ("6m", 126),
    ("1y", 252),
    ("5y", 1260),
)


def annualized_return(close: pd.Series, trading_days: int) -> float | None:
    clean = close.dropna()
    if len(clean) <= max(2, trading_days // 3):
        return None
    lookback = min(trading_days, len(clean) - 1)
    start = safe_float(clean.iloc[-lookback - 1], 0.0)
    end = safe_float(clean.iloc[-1], 0.0)
    if start <= 0 or end <= 0:
        return None
    period_return = (end / start) - 1.0
    annualized = (1.0 + period_return) ** (252.0 / lookback) - 1.0
    return clamp(annualized, -0.75, 1.25)


def forecast_price_horizons(
    hist: pd.DataFrame,
    price: float,
    fund: float,
    tech: float,
    news: float,
    total: float,
    regime: str,
) -> dict[str, float]:
    empty = {}
    for label, _days in PREDICTION_HORIZONS:
        empty[f"prediction_{label}_price"] = 0.0
        empty[f"prediction_{label}_return_pct"] = 0.0
    if price <= 0 or hist.empty or "Close" not in hist.columns:
        return empty

    close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
    if len(close) < 20:
        return empty

    weighted_components: list[tuple[float, float]] = []
    for days, weight in ((21, 0.20), (63, 0.20), (126, 0.20), (252, 0.25), (1260, 0.15)):
        annual = annualized_return(close, days)
        if annual is not None:
            weighted_components.append((annual, weight))

    if weighted_components:
        weight_sum = sum(w for _v, w in weighted_components)
        historical_annual = sum(v * w for v, w in weighted_components) / max(weight_sum, 0.01)
    else:
        historical_annual = 0.0

    daily_vol = safe_float(close.pct_change().rolling(63).std().iloc[-1], 0.0)
    vol_penalty = clamp(daily_vol * (252.0 ** 0.5) * 0.15, 0.0, 0.18)
    score_tilt = 0.10 * fund + 0.12 * tech + 0.06 * news + 0.08 * total
    regime_tilt = 0.04 if regime == "bullish" else -0.04 if regime == "bearish" else 0.0
    expected_annual = clamp(historical_annual + score_tilt + regime_tilt - vol_penalty, -0.55, 0.75)
    long_term_anchor = clamp(historical_annual * 0.45 + score_tilt * 0.50 + regime_tilt, -0.20, 0.35)

    out: dict[str, float] = {}
    for label, days in PREDICTION_HORIZONS:
        years = days / 252.0
        if days <= 63:
            horizon_annual = expected_annual
        elif days <= 252:
            horizon_annual = expected_annual * 0.70 + long_term_anchor * 0.30
        else:
            horizon_annual = expected_annual * 0.35 + long_term_anchor * 0.65
        predicted = price * ((1.0 + max(horizon_annual, -0.95)) ** years)
        return_pct = ((predicted / price) - 1.0) * 100.0
        out[f"prediction_{label}_price"] = round(predicted, 4)
        out[f"prediction_{label}_return_pct"] = round(return_pct, 2)
    return out


def latest_trade_price(ticker: yf.Ticker, daily_hist: pd.DataFrame, enable_after_hours: bool, market_open: bool) -> float:
    # When market is closed, anchor to regular close.
    if not market_open:
        return safe_float(daily_hist["Close"].iloc[-1], 0.0)
    # During market session, prefer intraday print. Extended-hours is optional.
    try:
        intraday = ticker.history(period="1d", interval="1m", prepost=enable_after_hours, auto_adjust=False)
        if not intraday.empty:
            p = safe_float(intraday["Close"].iloc[-1], 0.0)
            if p > 0:
                return p
    except Exception:
        pass
    return safe_float(daily_hist["Close"].iloc[-1], 0.0)


def safe_ticker_info(ticker: yf.Ticker) -> dict[str, Any]:
    try:
        info = ticker.info or {}
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}


def safe_ticker_news(ticker: yf.Ticker) -> list[dict[str, Any]]:
    try:
        news_items = ticker.news or []
        return news_items if isinstance(news_items, list) else []
    except Exception:
        return []


def analyze_symbol(
    symbol: str,
    regime: str,
    params: dict[str, Any],
    market_open: bool,
    enable_after_hours: bool,
    mkt_score: float,
    category_ctx: dict[str, float],
) -> AnalysisRow | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", interval="1d", auto_adjust=False)
        if hist.empty:
            return None
        price = latest_trade_price(ticker, hist, enable_after_hours, market_open)
        info = safe_ticker_info(ticker)
        news_items = safe_ticker_news(ticker)
        gate_ok, gate_reason = conservative_gate(symbol, info, hist, price)
        if not gate_ok:
            return None

        fund, fund_reason = fundamental_score(info)
        tech, tech_reason = technical_score(hist)
        news, news_reason = news_sentiment(symbol, news_items)
        earnings_days = next_earnings_days(ticker, info)
        outlook_score = earnings_outlook_score(info)
        price_score = price_setup_score(hist, price)
        earn_score = earnings_event_score(earnings_days, fund, tech, news, regime, outlook_score, price_score)
        cat_score = category_trend_score(info, category_ctx)

        base_total = compute_total_score(fund, tech, news, regime, params)
        total = base_total + 0.12 * mkt_score + 0.08 * cat_score + 0.10 * earn_score

        stock_action, option_action = decide_actions(regime, total, tech, params)
        mcap = safe_float(info.get("marketCap"), 0.0)
        beta = abs(safe_float(info.get("beta"), 1.0))
        v20 = vol20(hist)
        if TRADING_CONFIG.get("stock_only", True):
            option_action = "NO_OPTION"
        elif CONSERVATIVE_PROFILE and not conservative_option_allowed(total, stock_action, mcap, v20, beta, regime):
            option_action = "NO_OPTION"
        if gate_ok and stock_action == "HOLD" and regime != "bearish" and 2 <= earnings_days <= 30:
            near_earnings_ok = earnings_days <= 10 and earn_score >= 0.55
            far_earnings_ok = earnings_days > 10 and earn_score >= 0.72
            if (near_earnings_ok or far_earnings_ok) and outlook_score >= 0.45 and price_score >= 0.45:
                stock_action = "BUY_STOCK"
                option_action = "NO_OPTION"
        entry_price, target_price, stop_price, rr = trade_levels(hist, price, stock_action)
        option_symbol, option_expiry, option_strike = pick_option_candidate(ticker, option_action, price)
        execution_timing = "NOW" if market_open else "NEXT_MARKET_OPEN"
        predictions = forecast_price_horizons(hist, price, fund, tech, news, total, regime)

        reason = " | ".join(
            [
                gate_reason,
                fund_reason,
                tech_reason,
                news_reason,
                f"earnings_days={earnings_days}, earnings_event_score={earn_score:.2f}, earnings_outlook_score={outlook_score:.2f}, price_setup_score={price_score:.2f}",
            ]
        )
        return AnalysisRow(
            symbol=symbol,
            price=round(price, 4),
            market_regime=regime,
            fundamental_score=round(fund, 4),
            technical_score=round(tech, 4),
            news_score=round(news, 4),
            upcoming_earnings_days=earnings_days,
            earnings_event_score=round(earn_score, 4),
            market_trend_score=round(mkt_score, 4),
            category_trend_score=round(cat_score, 4),
            total_score=round(total, 4),
            action_stock=stock_action,
            action_option=option_action,
            execution_timing=execution_timing,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            risk_reward=rr,
            option_symbol_hint=option_symbol,
            option_expiry=option_expiry,
            option_strike=round(option_strike, 4),
            prediction_1w_price=predictions["prediction_1w_price"],
            prediction_1w_return_pct=predictions["prediction_1w_return_pct"],
            prediction_1m_price=predictions["prediction_1m_price"],
            prediction_1m_return_pct=predictions["prediction_1m_return_pct"],
            prediction_3m_price=predictions["prediction_3m_price"],
            prediction_3m_return_pct=predictions["prediction_3m_return_pct"],
            prediction_6m_price=predictions["prediction_6m_price"],
            prediction_6m_return_pct=predictions["prediction_6m_return_pct"],
            prediction_1y_price=predictions["prediction_1y_price"],
            prediction_1y_return_pct=predictions["prediction_1y_return_pct"],
            prediction_5y_price=predictions["prediction_5y_price"],
            prediction_5y_return_pct=predictions["prediction_5y_return_pct"],
            reason=reason,
        )
    except Exception:
        return None


def ensure_dirs(base_dir: Path) -> dict[str, Path]:
    base_dir.mkdir(parents=True, exist_ok=True)
    runs = base_dir / "runs"
    history = base_dir / "history"
    portfolio = base_dir / "portfolio"
    runs.mkdir(parents=True, exist_ok=True)
    history.mkdir(parents=True, exist_ok=True)
    portfolio.mkdir(parents=True, exist_ok=True)
    return {"runs": runs, "history": history, "portfolio": portfolio}


def find_last_available_snapshot(base_dir: Path) -> tuple[Path | None, Path | None]:
    # Prefer current base latest first.
    current_csv = base_dir / "latest" / "top10.csv"
    current_md = base_dir / "latest" / "top10.md"
    if current_csv.exists():
        return current_csv, (current_md if current_md.exists() else None)

    # Then search sibling daily folders for the latest available snapshot.
    # Expected layout: data/daily/YYYYMMDD/
    parent = base_dir.parent
    if not parent.exists():
        return None, None
    candidates: list[Path] = []
    for p in parent.iterdir():
        if not p.is_dir():
            continue
        latest_csv = p / "latest" / "top10.csv"
        if latest_csv.exists():
            candidates.append(latest_csv)
    if not candidates:
        return None, None
    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
    csv_path = candidates[0]
    md_path = csv_path.parent / "top10.md"
    return csv_path, (md_path if md_path.exists() else None)


def data_root_dir(base_dir: Path) -> Path:
    # Common layouts:
    # - data/daily/YYYYMMDD -> data
    # - data                 -> data
    if base_dir.name == "data":
        return base_dir
    if base_dir.parent.name == "daily":
        return base_dir.parent.parent
    if base_dir.parent.name == "data":
        return base_dir.parent
    return base_dir


def portfolio_state_path(base_dir: Path) -> Path:
    return data_root_dir(base_dir) / "portfolio" / "state.json"


def refresh_simple_view(base_dir: Path, run_ts: str) -> None:
    root = data_root_dir(base_dir)
    simple_dir = root / "simple"
    latest_dir = base_dir / "latest"
    logs_dir = base_dir / "logs"
    simple_dir.mkdir(parents=True, exist_ok=True)

    copies = [
        ("top10.md", "top10.md"),
        ("top10.csv", "top10.csv"),
        ("candidates.csv", "candidates.csv"),
        ("portfolio_status.json", "portfolio_status.json"),
        ("portfolio_report.md", "portfolio_report.md"),
        ("daily_summary.md", "daily_summary.md"),
        ("alerts.json", "alerts.json"),
        ("post_analysis.json", "post_analysis.json"),
    ]
    for src_name, dst_name in copies:
        src = latest_dir / src_name
        if src.exists():
            shutil.copy2(src, simple_dir / dst_name)

    latest_log = None
    if logs_dir.exists():
        logs = sorted(logs_dir.glob("run_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            latest_log = logs[0]
            shutil.copy2(latest_log, simple_dir / "latest_run.log")

    summary = {
        "timestamp_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_ts,
        "source_base_dir": str(base_dir),
        "source_latest_dir": str(latest_dir),
        "latest_log": str(latest_log) if latest_log else "",
        "note": "Simple view with key files only.",
    }
    (simple_dir / "README.md").write_text(
        "\n".join(
            [
                "# Simple Data View",
                "",
                "- `top10.md`: current recommendations",
                "- `top10.csv`: current recommendations (csv)",
                "- `portfolio_status.json`: latest balances and run P/L",
                "- `portfolio_report.md`: human-readable portfolio report",
                "- `daily_summary.md`: daily summary with next-day improvements",
                "- `alerts.json`: latest alert payload",
                "- `post_analysis.json`: latest learning/adaptation summary",
                "- `latest_run.log`: latest run log",
                "",
                "Generated automatically after each run.",
            ]
        ),
        encoding="utf-8",
    )
    (simple_dir / "status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def portfolio_default_state() -> dict[str, Any]:
    return {
        "capital_balance": INITIAL_CAPITAL,
        "cash": INITIAL_CAPITAL,
        "paper_balance": INITIAL_CAPITAL,
        "peak_paper_balance": INITIAL_CAPITAL,
        "simulation_balance": INITIAL_CAPITAL,
        "peak_simulation_balance": INITIAL_CAPITAL,
        "run_count": 0,
        "open_positions": [],
        "closed_positions_count": 0,
        "last_updated_utc": "",
    }


def load_portfolio_state(base_dir: Path) -> dict[str, Any]:
    path = portfolio_state_path(base_dir)
    if not path.exists():
        # Legacy daily state fallback/migration path.
        legacy = base_dir / "portfolio" / "state.json"
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    out = portfolio_default_state()
                    out.update(data)
                    if "capital_balance" not in data:
                        out["capital_balance"] = safe_float(data.get("initial_capital"), INITIAL_CAPITAL)
                    if "simulation_balance" not in data:
                        out["simulation_balance"] = safe_float(data.get("equity"), safe_float(out.get("cash"), INITIAL_CAPITAL))
                    if "paper_balance" not in data:
                        out["paper_balance"] = safe_float(out.get("simulation_balance"), safe_float(out.get("cash"), INITIAL_CAPITAL))
                    if "cash" not in data:
                        out["cash"] = safe_float(out.get("paper_balance"), safe_float(out.get("simulation_balance"), INITIAL_CAPITAL))
                    if "peak_simulation_balance" not in data:
                        out["peak_simulation_balance"] = max(
                            safe_float(out.get("simulation_balance"), INITIAL_CAPITAL),
                            safe_float(out.get("capital_balance"), INITIAL_CAPITAL),
                        )
                    if "peak_paper_balance" not in data:
                        out["peak_paper_balance"] = safe_float(out.get("peak_simulation_balance"), safe_float(out.get("paper_balance"), INITIAL_CAPITAL))
                    out["initial_capital"] = safe_float(out.get("capital_balance"), INITIAL_CAPITAL)
                    out["equity"] = safe_float(out.get("paper_balance"), safe_float(out.get("cash"), INITIAL_CAPITAL))
                    if not isinstance(out.get("open_positions"), list):
                        out["open_positions"] = []
                    return out
            except Exception:
                pass
        return portfolio_default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return portfolio_default_state()
    if not isinstance(data, dict):
        return portfolio_default_state()
    out = portfolio_default_state()
    out.update(data)
    # Backward compatibility for legacy keys.
    if "capital_balance" not in data:
        out["capital_balance"] = safe_float(data.get("initial_capital"), INITIAL_CAPITAL)
    if "simulation_balance" not in data:
        out["simulation_balance"] = safe_float(data.get("equity"), safe_float(out.get("cash"), INITIAL_CAPITAL))
    if "paper_balance" not in data:
        out["paper_balance"] = safe_float(out.get("simulation_balance"), safe_float(data.get("equity"), safe_float(out.get("cash"), INITIAL_CAPITAL)))
    if "cash" not in data:
        out["cash"] = safe_float(out.get("paper_balance"), safe_float(out.get("simulation_balance"), safe_float(data.get("equity"), INITIAL_CAPITAL)))
    if "peak_simulation_balance" not in data:
        out["peak_simulation_balance"] = max(
            safe_float(out.get("simulation_balance"), INITIAL_CAPITAL),
            safe_float(out.get("capital_balance"), INITIAL_CAPITAL),
        )
    if "peak_paper_balance" not in data:
        out["peak_paper_balance"] = safe_float(out.get("peak_simulation_balance"), safe_float(out.get("paper_balance"), INITIAL_CAPITAL))
    # Keep legacy simulation keys mirrored to the newer paper-trading keys.
    out["simulation_balance"] = safe_float(out.get("paper_balance"), safe_float(out.get("simulation_balance"), INITIAL_CAPITAL))
    out["peak_simulation_balance"] = safe_float(out.get("peak_paper_balance"), safe_float(out.get("peak_simulation_balance"), INITIAL_CAPITAL))
    # Keep aliases in memory for older call sites that may still read them.
    out["initial_capital"] = safe_float(out.get("capital_balance"), INITIAL_CAPITAL)
    out["equity"] = safe_float(out.get("paper_balance"), safe_float(out.get("cash"), INITIAL_CAPITAL))
    if not isinstance(out.get("open_positions"), list):
        out["open_positions"] = []
    return out


def save_portfolio_state(base_dir: Path, state: dict[str, Any]) -> None:
    path = portfolio_state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def set_paper_budget(base_dir: Path, balance: float) -> dict[str, Any]:
    b = max(0.0, round(float(balance), 4))
    state = load_portfolio_state(base_dir)
    # Keep capital_balance as fixed reporting baseline; reset only live paper-trading balance.
    state["capital_balance"] = INITIAL_CAPITAL
    state["cash"] = b
    state["paper_balance"] = b
    state["peak_paper_balance"] = b
    state["simulation_balance"] = b
    state["peak_simulation_balance"] = b
    # Backward-compatible aliases.
    state["initial_capital"] = state["capital_balance"]
    state["equity"] = state["paper_balance"]
    state["run_count"] = 0
    state["open_positions"] = []
    state["closed_positions_count"] = 0
    state["last_updated_utc"] = now_utc().strftime("%Y%m%d_%H%M%S")
    save_portfolio_state(base_dir, state)
    return state


def set_simulation_budget(base_dir: Path, balance: float) -> dict[str, Any]:
    return set_paper_budget(base_dir, balance)


def fetch_symbol_price(symbol: str, enable_after_hours: bool) -> float:
    try:
        t = yf.Ticker(symbol)
        intraday = t.history(period="1d", interval="1m", prepost=enable_after_hours, auto_adjust=False)
        if not intraday.empty:
            p = safe_float(intraday["Close"].iloc[-1], 0.0)
            if p > 0:
                return p
        daily = t.history(period="5d", interval="1d", auto_adjust=False)
        if not daily.empty:
            p = safe_float(daily["Close"].iloc[-1], 0.0)
            if p > 0:
                return p
    except Exception:
        return 0.0
    return 0.0


def mark_position_value(position: dict[str, Any], current_price: float) -> float:
    entry_price = max(0.0001, safe_float(position.get("entry_underlying_price"), 0.0))
    alloc = max(0.0, safe_float(position.get("capital_allocated"), 0.0))
    direction = 1.0 if str(position.get("direction")) == "LONG" else -1.0
    leverage = max(1.0, safe_float(position.get("leverage"), 1.0))
    ret = (current_price / entry_price) - 1.0
    gross = 1.0 + (direction * leverage * ret)
    return round(max(0.0, alloc * gross), 4)


def normalize_open_positions(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in positions:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol", "")).strip().upper()
        instrument = str(raw.get("instrument", "STOCK")).strip().upper()
        direction = str(raw.get("direction", "LONG")).strip().upper()
        if not symbol:
            continue
        pos = dict(raw)
        pos["symbol"] = symbol
        pos["instrument"] = instrument
        pos["direction"] = direction
        alloc = max(0.0, safe_float(pos.get("capital_allocated"), 0.0))
        if alloc <= 0:
            continue
        key = (symbol, instrument, direction)
        if key not in merged:
            merged[key] = pos
            continue

        existing = merged[key]
        existing_alloc = max(0.0, safe_float(existing.get("capital_allocated"), 0.0))
        total_alloc = existing_alloc + alloc
        if total_alloc <= 0:
            continue

        for field in ("entry_underlying_price", "stop_price", "target_price"):
            existing_value = safe_float(existing.get(field), 0.0)
            new_value = safe_float(pos.get(field), 0.0)
            if existing_value > 0 and new_value > 0:
                existing[field] = round(((existing_value * existing_alloc) + (new_value * alloc)) / total_alloc, 4)
            elif new_value > 0:
                existing[field] = round(new_value, 4)

        existing["capital_allocated"] = round(total_alloc, 4)
        existing["opened_run"] = min(int(existing.get("opened_run", 0) or 0), int(pos.get("opened_run", 0) or 0))
        existing["hold_runs"] = max(int(existing.get("hold_runs", 0) or 0), int(pos.get("hold_runs", 0) or 0))
        existing["entry_score"] = max(safe_float(existing.get("entry_score"), 0.0), safe_float(pos.get("entry_score"), 0.0))
        if pos.get("last_price"):
            existing["last_price"] = pos.get("last_price")
        if pos.get("last_value"):
            existing["last_value"] = pos.get("last_value")
    return list(merged.values())


def position_price_for_mark(position: dict[str, Any], enable_after_hours: bool) -> tuple[float, str]:
    symbol = str(position.get("symbol", ""))
    current_price = fetch_symbol_price(symbol, enable_after_hours)
    if current_price > 0:
        return current_price, "live"
    last_price = safe_float(position.get("last_price"), 0.0)
    if last_price > 0:
        return last_price, "last"
    entry_price = safe_float(position.get("entry_underlying_price"), 0.0)
    if entry_price > 0:
        return entry_price, "entry_fallback"
    return 0.0, "unavailable"


def refresh_position_mark(position: dict[str, Any], price: float, price_source: str) -> float:
    value = mark_position_value(position, price)
    position["last_price"] = round(price, 4)
    position["last_value"] = round(value, 4)
    position["last_price_source"] = price_source
    position["last_marked_utc"] = now_utc().strftime("%Y%m%d_%H%M%S")
    return value


def add_to_position(position: dict[str, Any], add_alloc: float, add_price: float, run_count: int) -> None:
    old_alloc = max(0.0, safe_float(position.get("capital_allocated"), 0.0))
    add_alloc = max(0.0, safe_float(add_alloc, 0.0))
    total_alloc = old_alloc + add_alloc
    if add_alloc <= 0 or total_alloc <= 0 or add_price <= 0:
        return
    old_entry = safe_float(position.get("entry_underlying_price"), add_price)
    position["entry_underlying_price"] = round(((old_entry * old_alloc) + (add_price * add_alloc)) / total_alloc, 4)
    position["capital_allocated"] = round(total_alloc, 4)
    position["last_price"] = round(add_price, 4)
    position["last_value"] = round(mark_position_value(position, add_price), 4)
    position["last_topup_run"] = run_count


def should_close_position(position: dict[str, Any], current_price: float) -> tuple[bool, str]:
    direction = str(position.get("direction", "LONG"))
    stop = safe_float(position.get("stop_price"), 0.0)
    target = safe_float(position.get("target_price"), 0.0)
    hold_runs = int(position.get("hold_runs", 0))
    instrument = str(position.get("instrument", "STOCK"))
    max_hold = MAX_HOLD_RUNS_OPTION if instrument == "OPTION" else MAX_HOLD_RUNS_STOCK
    if hold_runs >= max_hold:
        return True, "max_hold"
    if direction == "LONG":
        if stop > 0 and current_price <= stop:
            return True, "stop"
        if target > 0 and current_price >= target:
            return True, "target"
    else:
        if stop > 0 and current_price >= stop:
            return True, "stop"
        if target > 0 and current_price <= target:
            return True, "target"
    return False, ""


def advice_close_reason(position: dict[str, Any], advice: dict[str, Any] | None) -> str:
    if not advice:
        return ""
    direction = str(position.get("direction", "LONG"))
    instrument = str(position.get("instrument", "STOCK"))
    if instrument == "STOCK":
        action = str(advice.get("action_stock", "HOLD"))
        if direction == "LONG" and action == "SELL_SHORT":
            return "advice_sell_or_short"
        if direction == "SHORT" and action == "BUY_STOCK":
            return "advice_buy_to_cover"
    elif instrument == "OPTION":
        action = str(advice.get("action_option", "NO_OPTION"))
        if direction == "LONG" and action == "BUY_PUT":
            return "advice_buy_put"
        if direction == "SHORT" and action == "BUY_CALL":
            return "advice_buy_call"
    return ""


def build_budget_controls(
    current_equity: float,
    simulation_baseline: float,
    peak_equity: float,
    full_deploy: bool,
    full_deploy_target_pct: float,
) -> dict[str, float | int | str]:
    eq = max(0.0, safe_float(current_equity, INITIAL_CAPITAL))
    baseline = max(1.0, safe_float(simulation_baseline, INITIAL_CAPITAL))
    peak = max(baseline, safe_float(peak_equity, baseline), eq)
    drawdown_pct = max(0.0, (peak - eq) / peak * 100.0)
    growth_vs_baseline_pct = ((eq / baseline) - 1.0) * 100.0 if baseline > 0 else 0.0
    base_target_exposure = clamp(
        safe_float(full_deploy_target_pct, 1.0) if full_deploy else MAX_PORTFOLIO_EXPOSURE_PCT,
        MAX_PORTFOLIO_EXPOSURE_PCT if full_deploy else 0.25,
        1.0 if full_deploy else MAX_PORTFOLIO_EXPOSURE_PCT,
    )

    regime = "normal"
    risk_scale = 1.0
    exposure_scale = 1.0
    max_open_scale = 1.0
    if drawdown_pct >= 20:
        regime = "capital_preservation"
        risk_scale = 0.45
        exposure_scale = 0.50
        max_open_scale = 0.50
    elif drawdown_pct >= 15:
        regime = "protective"
        risk_scale = 0.60
        exposure_scale = 0.65
        max_open_scale = 0.65
    elif drawdown_pct >= 10:
        regime = "defensive"
        risk_scale = 0.75
        exposure_scale = 0.80
        max_open_scale = 0.75
    elif drawdown_pct >= 5:
        regime = "cautious"
        risk_scale = 0.90
        exposure_scale = 0.90
        max_open_scale = 0.90

    effective_risk_per_trade_pct = RISK_PER_TRADE * risk_scale
    effective_max_stock_alloc_pct = MAX_STOCK_ALLOC_PCT * exposure_scale
    effective_max_option_alloc_pct = MAX_OPTION_ALLOC_PCT * risk_scale
    min_target = 0.35 if full_deploy else 0.20
    effective_target_exposure_pct = clamp(base_target_exposure * exposure_scale, min_target, base_target_exposure)
    base_open_positions = 20 if full_deploy else MAX_OPEN_POSITIONS
    effective_max_open_positions = max(3, int(round(base_open_positions * max_open_scale)))
    reserve_cash_pct = max(0.0, 1.0 - effective_target_exposure_pct)

    return {
        "regime": regime,
        "baseline_equity": round(baseline, 4),
        "peak_equity": round(peak, 4),
        "drawdown_pct": round(drawdown_pct, 4),
        "growth_vs_baseline_pct": round(growth_vs_baseline_pct, 4),
        "effective_risk_per_trade_pct": round(effective_risk_per_trade_pct * 100.0, 4),
        "effective_max_stock_alloc_pct": round(effective_max_stock_alloc_pct * 100.0, 4),
        "effective_max_option_alloc_pct": round(effective_max_option_alloc_pct * 100.0, 4),
        "effective_target_exposure_pct": round(effective_target_exposure_pct * 100.0, 4),
        "effective_max_open_positions": effective_max_open_positions,
        "reserve_cash_pct": round(reserve_cash_pct * 100.0, 4),
    }


def append_equity_curve(base_dir: Path, row: dict[str, Any]) -> None:
    path = base_dir / "history" / "equity_curve.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def append_trade_events(base_dir: Path, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    path = base_dir / "history" / "trades_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(events[0].keys()))
        if write_header:
            writer.writeheader()
        writer.writerows(events)


def should_generate_daily_summary(now_et: datetime) -> bool:
    # Generate after the regular scheduled scan window has ended.
    now_pt = now_et.astimezone(PACIFIC_TZ)
    return now_pt.weekday() < 5 and now_pt.hour >= 13


def load_daily_summary_state(base_dir: Path) -> dict[str, Any]:
    path = base_dir / "history" / "daily_summary_state.json"
    if not path.exists():
        return {"last_date_et": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"last_date_et": ""}


def save_daily_summary_state(base_dir: Path, state: dict[str, Any]) -> None:
    path = base_dir / "history" / "daily_summary_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def to_pt_date_str(ts_utc: str) -> str:
    try:
        dt = datetime.strptime(ts_utc, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc).astimezone(PACIFIC_TZ)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def format_run_ts_pt(ts_utc: str) -> str:
    try:
        dt = datetime.strptime(ts_utc, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc).astimezone(PACIFIC_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_utc


def format_iso_utc_to_pt(ts_utc: str) -> str:
    try:
        dt = datetime.strptime(ts_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(PACIFIC_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ts_utc


def generate_daily_summary(base_dir: Path, run_ts: str, force: bool = False) -> None:
    now_et = now_utc().astimezone(US_MARKET_TZ)
    now_pt = now_utc().astimezone(PACIFIC_TZ)
    if not force and not should_generate_daily_summary(now_et):
        return
    today_pt = now_pt.strftime("%Y-%m-%d")
    state = load_daily_summary_state(base_dir)
    if state.get("last_date_pt") == today_pt or state.get("last_date_et") == today_pt:
        return

    eq_path = base_dir / "history" / "equity_curve.csv"
    trades_path = base_dir / "history" / "trades_log.csv"
    post_path = base_dir / "history" / "post_analysis_history.jsonl"
    if not eq_path.exists():
        return

    try:
        eq = pd.read_csv(eq_path)
    except Exception:
        return
    if eq.empty or "timestamp_utc" not in eq.columns:
        return
    eq["date_pt"] = eq["timestamp_utc"].astype(str).map(to_pt_date_str)
    day_eq = eq[eq["date_pt"] == today_pt].copy()
    if day_eq.empty:
        return

    start_equity = safe_float(day_eq.iloc[0].get("start_equity"), 0.0)
    end_equity = safe_float(day_eq.iloc[-1].get("end_equity"), 0.0)
    day_pnl = end_equity - start_equity
    day_ret = (day_pnl / start_equity * 100) if start_equity > 0 else 0.0
    max_open = int(pd.to_numeric(day_eq.get("open_positions", 0), errors="coerce").fillna(0).max())
    runs_count = len(day_eq)

    realized = 0.0
    closes_count = 0
    win_rate = None
    if trades_path.exists():
        try:
            td = pd.read_csv(trades_path)
            if not td.empty and "timestamp_utc" in td.columns:
                td["date_pt"] = td["timestamp_utc"].astype(str).map(to_pt_date_str)
                day_td = td[td["date_pt"] == today_pt].copy()
                closes = day_td[day_td.get("event", "") == "CLOSE"] if "event" in day_td.columns else pd.DataFrame()
                if not closes.empty:
                    pnl_series = pd.to_numeric(closes.get("pnl", 0), errors="coerce").fillna(0)
                    realized = float(pnl_series.sum())
                    closes_count = len(closes)
                    win_rate = float((pnl_series > 0).sum() / len(pnl_series))
        except Exception:
            pass

    post_status_counts: dict[str, int] = {}
    if post_path.exists():
        try:
            for line in post_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                ts = str(obj.get("timestamp_utc", ""))
                if not ts:
                    continue
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(PACIFIC_TZ)
                    if dt.strftime("%Y-%m-%d") != today_pt:
                        continue
                except Exception:
                    continue
                s = str(obj.get("status", "unknown"))
                post_status_counts[s] = post_status_counts.get(s, 0) + 1
        except Exception:
            pass

    next_trading_day = now_et + timedelta(days=1)
    while next_trading_day.weekday() >= 5:
        next_trading_day += timedelta(days=1)
    next_day_label = next_trading_day.astimezone(PACIFIC_TZ).strftime("%Y-%m-%d")

    improvements: list[str] = []

    if day_pnl < 0 or (win_rate is not None and win_rate < 0.5):
        improvements.append(
            f"Tomorrow ({next_day_label} PT): tighten entries by raising buy threshold by +0.02 and cap new risk to 0.60% per trade until accuracy improves."
        )
    else:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): keep risk at 0.75% per trade, but only open new positions when score and market regime agree."
        )

    if closes_count == 0:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): shorten time-in-trade review cadence and force an end-of-day exit check at 12:50 PT for stale positions."
        )
    elif win_rate is not None and win_rate < 0.5:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): tighten stop discipline by trimming loser hold time and requiring stronger follow-through after entry."
        )
    else:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): keep current exit logic and review any stop-outs for slippage before next session."
        )

    total_post = sum(post_status_counts.values())
    too_fresh_count = int(post_status_counts.get("too_fresh", 0))
    if total_post == 0:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): ensure post-analysis snapshots are captured during market hours to maintain learning signal quality."
        )
    elif too_fresh_count / max(total_post, 1) >= 0.5:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): reduce too-fresh evaluations by delaying evaluation checks and prioritizing mature prior runs."
        )
    else:
        improvements.append(
            f"Tomorrow ({next_day_label} PT): maintain current learning cadence and monitor post-analysis accuracy drift run-to-run."
        )

    lines = [
        f"# Daily Strategy Summary ({today_pt} PT)",
        "",
        "## Performance",
        f"- Runs today: `{runs_count}`",
        f"- Start equity: `${start_equity:,.2f}`",
        f"- End equity: `${end_equity:,.2f}`",
        f"- Daily P/L: `${day_pnl:,.2f}` ({day_ret:.2f}%)",
        f"- Realized P/L: `${realized:,.2f}`",
        f"- Max open positions: `{max_open}`",
        "",
        "## Recommendation Effectiveness",
        f"- Closed trades today: `{closes_count}`",
        f"- Win rate: `{(win_rate * 100):.2f}%`" if win_rate is not None else "- Win rate: `N/A`",
        f"- Post-analysis statuses: `{post_status_counts}`",
        "",
        "## How Strategy Worked",
        "- Strategy remained low-risk, stock-only with mid/large-cap bias.",
        "- Entries/exits were managed via target/stop/max-hold policy.",
        "",
        "## Improvements",
    ]
    for idx, item in enumerate(improvements, start=1):
        lines.append(f"{idx}. {item}")

    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "daily_summary.md").write_text("\n".join(lines), encoding="utf-8")

    hist_path = base_dir / "history" / f"daily_summary_{today_pt.replace('-', '')}.md"
    hist_path.write_text("\n".join(lines), encoding="utf-8")

    state["last_date_pt"] = today_pt
    state["last_date_et"] = today_pt
    state["last_generated_run_ts"] = run_ts
    save_daily_summary_state(base_dir, state)


def build_daily_evaluation_report(base_dir: Path, run_ts: str) -> Path:
    now_pt = now_utc().astimezone(PACIFIC_TZ)
    today_pt = now_pt.strftime("%Y-%m-%d")
    latest_dir = base_dir / "latest"
    history_dir = base_dir / "history"
    latest_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)

    top_path = history_dir / "top10_history.csv"
    eq_path = history_dir / "equity_curve.csv"
    trades_path = history_dir / "trades_log.csv"
    report_path = latest_dir / "daily_evaluation_report.md"

    if not top_path.exists():
        lines = [
            f"# Daily Trade Evaluation ({today_pt} PT)",
            "",
            "No recommendation history was found for today.",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    try:
        recs = pd.read_csv(top_path)
    except Exception:
        recs = pd.DataFrame()
    if recs.empty or "timestamp_utc" not in recs.columns:
        lines = [
            f"# Daily Trade Evaluation ({today_pt} PT)",
            "",
            "Recommendation history was empty or unreadable.",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    recs["date_pt"] = recs["timestamp_utc"].astype(str).map(to_pt_date_str)
    day_recs = recs[recs["date_pt"] == today_pt].copy()
    if day_recs.empty:
        lines = [
            f"# Daily Trade Evaluation ({today_pt} PT)",
            "",
            "No recommendations were recorded for today.",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    day_recs["time_pt"] = day_recs["timestamp_utc"].astype(str).map(format_run_ts_pt)
    for col in ("price", "entry_price", "total_score", "stock_qty", "rank"):
        if col in day_recs.columns:
            day_recs[col] = pd.to_numeric(day_recs[col], errors="coerce").fillna(0)
    latest_prices = (
        day_recs.sort_values("timestamp_utc")
        .groupby("symbol")["price"]
        .last()
        .to_dict()
        if "symbol" in day_recs.columns and "price" in day_recs.columns
        else {}
    )

    day_recs["end_price_for_day"] = day_recs["symbol"].map(latest_prices).fillna(day_recs.get("price", 0))

    def recommendation_pnl(row: pd.Series) -> float:
        action = str(row.get("action_stock", ""))
        qty = int(safe_float(row.get("stock_qty"), 0.0))
        entry = safe_float(row.get("entry_price"), safe_float(row.get("price"), 0.0))
        end_price = safe_float(row.get("end_price_for_day"), entry)
        if qty <= 0 or entry <= 0:
            return 0.0
        if action == "SELL_SHORT":
            return (entry - end_price) * qty
        if action == "BUY_STOCK":
            return (end_price - entry) * qty
        return 0.0

    day_recs["estimated_day_pnl"] = day_recs.apply(recommendation_pnl, axis=1)

    trade_summary: dict[tuple[str, str], dict[str, float | str]] = {}
    realized_pnl = 0.0
    opens_count = 0
    closes_count = 0
    if trades_path.exists():
        try:
            trades = pd.read_csv(trades_path)
            if not trades.empty and "timestamp_utc" in trades.columns:
                trades["date_pt"] = trades["timestamp_utc"].astype(str).map(to_pt_date_str)
                day_trades = trades[trades["date_pt"] == today_pt].copy()
                for _idx, trade in day_trades.iterrows():
                    event = str(trade.get("event", ""))
                    symbol = str(trade.get("symbol", ""))
                    ts = str(trade.get("timestamp_utc", ""))
                    key = (ts, symbol)
                    item = trade_summary.setdefault(
                        key,
                        {"events": "", "allocated": 0.0, "value": 0.0, "pnl": 0.0},
                    )
                    item["events"] = ",".join([p for p in [str(item.get("events", "")), event] if p])
                    item["allocated"] = safe_float(item.get("allocated"), 0.0) + safe_float(trade.get("capital_allocated"), 0.0)
                    item["value"] = safe_float(item.get("value"), 0.0) + safe_float(trade.get("value"), 0.0)
                    item["pnl"] = safe_float(item.get("pnl"), 0.0) + safe_float(trade.get("pnl"), 0.0)
                    if event == "OPEN":
                        opens_count += 1
                    if event == "CLOSE":
                        closes_count += 1
                        realized_pnl += safe_float(trade.get("pnl"), 0.0)
        except Exception:
            pass

    start_equity = 0.0
    end_equity = 0.0
    cash = 0.0
    open_positions = 0
    day_pnl = 0.0
    if eq_path.exists():
        try:
            eq = pd.read_csv(eq_path)
            if not eq.empty and "timestamp_utc" in eq.columns:
                eq["date_pt"] = eq["timestamp_utc"].astype(str).map(to_pt_date_str)
                day_eq = eq[eq["date_pt"] == today_pt].copy()
                if not day_eq.empty:
                    start_equity = safe_float(day_eq.iloc[0].get("start_equity"), 0.0)
                    end_equity = safe_float(day_eq.iloc[-1].get("end_equity"), 0.0)
                    cash = safe_float(day_eq.iloc[-1].get("cash"), 0.0)
                    open_positions = int(safe_float(day_eq.iloc[-1].get("open_positions"), 0.0))
                    day_pnl = end_equity - start_equity
        except Exception:
            pass

    daily_summary_path = latest_dir / "daily_summary.md"
    improvements: list[str] = []
    if daily_summary_path.exists():
        capture = False
        for line in daily_summary_path.read_text(encoding="utf-8").splitlines():
            if line.strip() == "## Improvements":
                capture = True
                continue
            if capture and line.startswith("## "):
                break
            if capture and line.strip():
                improvements.append(line)

    actionable = day_recs[day_recs.get("action_stock", "") != "HOLD"] if "action_stock" in day_recs.columns else day_recs
    estimated_total = float(pd.to_numeric(actionable.get("estimated_day_pnl", 0), errors="coerce").fillna(0).sum())
    runs_count = int(day_recs["timestamp_utc"].nunique())

    lines = [
        f"# Daily Trade Evaluation ({today_pt} PT)",
        "",
        "## Paper Budget",
        f"- Start paper balance: `${start_equity:,.2f}`",
        f"- End paper balance: `${end_equity:,.2f}`",
        f"- Daily paper P/L: `${day_pnl:,.2f}`",
        f"- Cash: `${cash:,.2f}`",
        f"- Open positions after evaluation: `{open_positions}`",
        f"- Realized paper-trade P/L today: `${realized_pnl:,.2f}`",
        "",
        "## Recommendation Coverage",
        f"- Five-minute recommendation runs reviewed: `{runs_count}`",
        f"- Recommended rows reviewed: `{len(day_recs)}`",
        f"- Paper opens today: `{opens_count}`",
        f"- Paper closes today: `{closes_count}`",
        f"- Estimated mark-to-last-seen P/L across actionable recommendations: `${estimated_total:,.2f}`",
        "",
        "## Improvements Applied For Tomorrow",
    ]
    if improvements:
        lines.extend(improvements)
    else:
        lines.append("1. No daily improvement actions were generated because the daily summary had insufficient data.")

    lines.extend(
        [
            "",
            "## All Recommended Trades",
            "| Time PT | Rank | Symbol | Action | Qty | Entry | Last Seen | Est. P/L | Score | Paper Event | Paper P/L |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|---|---:|",
        ]
    )

    display_cols = [
        "timestamp_utc",
        "time_pt",
        "rank",
        "symbol",
        "action_stock",
        "stock_qty",
        "entry_price",
        "end_price_for_day",
        "estimated_day_pnl",
        "total_score",
    ]
    for _idx, row in day_recs.sort_values(["timestamp_utc", "rank"]).iterrows():
        key = (str(row.get("timestamp_utc", "")), str(row.get("symbol", "")))
        trade = trade_summary.get(key, {})
        paper_event = str(trade.get("events", ""))
        paper_pnl = safe_float(trade.get("pnl"), 0.0)
        values = {col: row.get(col, "") for col in display_cols}
        lines.append(
            f"| {values['time_pt']} | {int(safe_float(values['rank'], 0))} | {values['symbol']} | "
            f"{values['action_stock']} | {int(safe_float(values['stock_qty'], 0))} | "
            f"${safe_float(values['entry_price'], 0):,.2f} | ${safe_float(values['end_price_for_day'], 0):,.2f} | "
            f"${safe_float(values['estimated_day_pnl'], 0):,.2f} | {safe_float(values['total_score'], 0):.3f} | "
            f"{paper_event or '-'} | ${paper_pnl:,.2f} |"
        )

    report_text = "\n".join(lines)
    report_path.write_text(report_text, encoding="utf-8")
    hist_path = history_dir / f"daily_evaluation_report_{today_pt.replace('-', '')}.md"
    hist_path.write_text(report_text, encoding="utf-8")
    return report_path


def write_portfolio_report(base_dir: Path, summary: dict[str, Any], open_positions: list[dict[str, Any]], enable_after_hours: bool) -> None:
    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Portfolio Report",
        "",
        f"Timestamp (PT): `{format_iso_utc_to_pt(str(summary.get('timestamp_utc', '')))}`",
        f"Start Equity: `${safe_float(summary.get('start_equity')):,.2f}`",
        f"Paper Balance: `${safe_float(summary.get('paper_balance'), safe_float(summary.get('simulation_balance'), safe_float(summary.get('end_equity')))):,.2f}`",
        f"Peak Equity: `${safe_float(summary.get('peak_equity')):,.2f}`",
        f"Drawdown From Peak: `{safe_float(summary.get('drawdown_pct')):.2f}%`",
        f"Benchmark Capital (fixed): `${safe_float(summary.get('capital_balance'), safe_float(summary.get('initial_capital'))):,.2f}`",
        f"Run P/L: `${safe_float(summary.get('run_pnl')):,.2f}` ({safe_float(summary.get('run_return_pct')):.2f}%)",
        f"Total Return: `{safe_float(summary.get('total_return_pct')):.2f}%`",
        f"Cash: `${safe_float(summary.get('cash')):,.2f}`",
        f"Open Positions: `{int(summary.get('open_positions', 0))}`",
        f"New Events This Run: `{int(summary.get('new_events', 0))}`",
        f"Budget Regime: `{summary.get('budget_controls', {}).get('regime', 'normal')}`",
        f"Target Exposure Cap: `{safe_float(summary.get('budget_controls', {}).get('effective_target_exposure_pct')):.2f}%`",
        f"Risk Per Trade: `{safe_float(summary.get('budget_controls', {}).get('effective_risk_per_trade_pct')):.4f}%`",
        "",
    ]

    position_rows = []
    for p in open_positions:
        symbol = str(p.get("symbol", ""))
        if not symbol:
            continue
        px = fetch_symbol_price(symbol, enable_after_hours)
        if px <= 0:
            px = safe_float(p.get("entry_underlying_price"), 0.0)
        alloc = safe_float(p.get("capital_allocated"), 0.0)
        value = mark_position_value(p, px)
        pnl = value - alloc
        ret_pct = (pnl / alloc * 100) if alloc > 0 else 0.0
        position_rows.append(
            {
                "symbol": symbol,
                "instrument": str(p.get("instrument", "")),
                "direction": str(p.get("direction", "")),
                "entry": safe_float(p.get("entry_underlying_price"), 0.0),
                "last": px,
                "allocated": alloc,
                "value": value,
                "pnl": pnl,
                "ret_pct": ret_pct,
                "target": safe_float(p.get("target_price"), 0.0),
                "stop": safe_float(p.get("stop_price"), 0.0),
                "hold_runs": int(p.get("hold_runs", 0)),
            }
        )

    realized = 0.0
    trades_path = base_dir / "history" / "trades_log.csv"
    if trades_path.exists():
        try:
            tdf = pd.read_csv(trades_path)
            if not tdf.empty and "event" in tdf.columns and "pnl" in tdf.columns:
                closes = tdf[tdf["event"] == "CLOSE"]
                realized = float(pd.to_numeric(closes["pnl"], errors="coerce").fillna(0).sum())
        except Exception:
            realized = 0.0

    unrealized = sum(r["pnl"] for r in position_rows)
    lines.extend(
        [
            "## P&L Breakdown",
            f"- Realized P&L: `${realized:,.2f}`",
            f"- Unrealized P&L: `${unrealized:,.2f}`",
            "",
        ]
    )

    if position_rows:
        by_pnl_desc = sorted(position_rows, key=lambda x: x["pnl"], reverse=True)
        winners = by_pnl_desc[:3]
        losers = sorted(position_rows, key=lambda x: x["pnl"])[:3]

        lines.extend(
            [
                "## Top Winners (Open)",
                "| Symbol | Instr | Dir | P&L | Return % |",
                "|---|---|---|---:|---:|",
            ]
        )
        for r in winners:
            lines.append(
                f"| {r['symbol']} | {r['instrument']} | {r['direction']} | ${r['pnl']:.2f} | {r['ret_pct']:.2f}% |"
            )

        lines.extend(
            [
                "",
                "## Top Losers (Open)",
                "| Symbol | Instr | Dir | P&L | Return % |",
                "|---|---|---|---:|---:|",
            ]
        )
        for r in losers:
            lines.append(
                f"| {r['symbol']} | {r['instrument']} | {r['direction']} | ${r['pnl']:.2f} | {r['ret_pct']:.2f}% |"
            )

        lines.extend(
            [
                "",
                "## Open Positions",
                "| Symbol | Instr | Dir | Entry | Last | Allocated | Value | P&L | Target | Stop | Hold Runs |",
                "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for r in sorted(position_rows, key=lambda x: x["symbol"]):
            lines.append(
                f"| {r['symbol']} | {r['instrument']} | {r['direction']} | {r['entry']:.2f} | {r['last']:.2f} | "
                f"${r['allocated']:.2f} | ${r['value']:.2f} | ${r['pnl']:.2f} | {r['target']:.2f} | {r['stop']:.2f} | {r['hold_runs']} |"
            )
    else:
        lines.extend(["## Open Positions", "No open positions.", ""])

    (latest_dir / "portfolio_report.md").write_text("\n".join(lines), encoding="utf-8")


def load_notification_state(base_dir: Path) -> dict[str, Any]:
    path = base_dir / "notifications" / "state.json"
    if not path.exists():
        return {"last_alert_ts_utc": "", "last_alert_hash": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"last_alert_ts_utc": "", "last_alert_hash": ""}


def save_notification_state(base_dir: Path, state: dict[str, Any]) -> None:
    path = base_dir / "notifications" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def should_alert(now_ts: datetime, state: dict[str, Any], cooldown_minutes: int, message_hash: str) -> bool:
    if message_hash and message_hash == str(state.get("last_alert_hash", "")):
        return False
    last_ts = str(state.get("last_alert_ts_utc", ""))
    if not last_ts:
        return True
    try:
        dt = datetime.strptime(last_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return True
    age_min = (now_ts - dt).total_seconds() / 60
    return age_min >= max(1, cooldown_minutes)


def send_telegram_message(message: str, chat_id: str) -> tuple[bool, str]:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = (chat_id or os.getenv("TELEGRAM_CHAT_ID", "")).strip()
    if not (bot_token and chat):
        return False, "missing_telegram_env"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={
                "chat_id": chat,
                "text": message,
                "disable_web_page_preview": "true",
            },
            timeout=20,
        )
        if 200 <= r.status_code < 300:
            return True, "sent"
        return False, f"telegram_http_{r.status_code}"
    except Exception as exc:
        return False, f"telegram_error:{exc}"


def process_notifications(base_dir: Path, ts: str, top10: pd.DataFrame, market_ctx: dict[str, Any]) -> dict[str, Any]:
    cfg = NOTIFICATIONS_CONFIG
    out = {
        "timestamp_utc": ts,
        "enabled": bool(cfg.get("enabled", True)),
        "channel": str(cfg.get("channel", "telegram")),
        "telegram_enabled": bool(cfg.get("telegram_enabled", True)),
        "sent": False,
        "reason": "",
        "telegram_chat_id": str(cfg.get("telegram_chat_id", "")),
        "items": [],
    }
    if not out["enabled"]:
        out["reason"] = "disabled"
        return out
    if top10.empty:
        out["reason"] = "empty_top10"
        return out

    min_score = safe_float(cfg.get("good_trade_min_score"), 0.75)
    min_rr = safe_float(cfg.get("good_trade_min_rr"), 1.5)
    max_items = max(1, int(cfg.get("max_alert_items", 3)))
    qualifying = []
    for _, row in top10.iterrows():
        score = safe_float(row.get("total_score"), 0.0)
        rr = safe_float(row.get("risk_reward"), 0.0)
        stock_action = str(row.get("action_stock", ""))
        option_action = str(row.get("action_option", ""))
        bullish = stock_action == "BUY_STOCK" and option_action in {"BUY_CALL", "NO_OPTION"} and score >= min_score and rr >= min_rr
        bearish = stock_action == "SELL_SHORT" and option_action in {"BUY_PUT", "NO_OPTION"} and score <= -min_score and rr >= min_rr
        if bullish or bearish:
            qualifying.append(
                {
                    "symbol": str(row.get("symbol", "")),
                    "score": round(score, 3),
                    "stock_action": stock_action,
                    "option_action": option_action,
                    "entry": round(safe_float(row.get("entry_price"), 0.0), 2),
                    "target": round(safe_float(row.get("target_price"), 0.0), 2),
                    "stop": round(safe_float(row.get("stop_price"), 0.0), 2),
                    "rr": round(rr, 2),
                }
            )
    qualifying = qualifying[:max_items]
    out["items"] = qualifying
    if not qualifying:
        out["reason"] = "no_very_good_trade"
        return out

    lines = [
        f"ALERT {market_ctx.get('market_session','')} | Very good setups",
    ]
    for q in qualifying:
        lines.append(
            f"{q['symbol']} {q['stock_action']}/{q['option_action']} "
            f"entry {q['entry']} target {q['target']} stop {q['stop']} rr {q['rr']} score {q['score']}"
        )
    body = " | ".join(lines)
    msg_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    now_ts = now_utc()
    state = load_notification_state(base_dir)
    cooldown = int(cfg.get("cooldown_minutes", 60))
    if not should_alert(now_ts, state, cooldown, msg_hash):
        out["reason"] = "cooldown_or_duplicate"
        return out

    if out.get("channel") != "telegram":
        out["reason"] = "unsupported_channel"
        return out

    if not out["telegram_enabled"]:
        out["reason"] = "telegram_disabled"
        return out

    ok, reason = send_telegram_message(body, str(cfg.get("telegram_chat_id", "")))
    out["sent"] = ok
    out["reason"] = reason
    if ok:
        state["last_alert_ts_utc"] = now_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        state["last_alert_hash"] = msg_hash
        save_notification_state(base_dir, state)

    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "last_alert.txt").write_text(body, encoding="utf-8")
    return out


def build_new_position(
    row: dict[str, Any],
    equity: float,
    cash: float,
    run_count: int,
    instrument: str,
    budget_controls: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    symbol = str(row.get("symbol", ""))
    if not symbol:
        return None
    controls = budget_controls or {}
    stock_alloc_pct = safe_float(controls.get("effective_max_stock_alloc_pct"), MAX_STOCK_ALLOC_PCT * 100.0) / 100.0
    option_alloc_pct = safe_float(controls.get("effective_max_option_alloc_pct"), MAX_OPTION_ALLOC_PCT * 100.0) / 100.0
    risk_per_trade_pct = safe_float(controls.get("effective_risk_per_trade_pct"), RISK_PER_TRADE * 100.0) / 100.0
    action_stock = str(row.get("action_stock", ""))
    action_option = str(row.get("action_option", ""))
    if instrument == "STOCK":
        if action_stock not in {"BUY_STOCK", "SELL_SHORT"}:
            return None
        direction = "LONG" if action_stock == "BUY_STOCK" else "SHORT"
        leverage = 1.0
        alloc_cap = equity * stock_alloc_pct
    else:
        if action_option not in {"BUY_CALL", "BUY_PUT"}:
            return None
        direction = "LONG" if action_option == "BUY_CALL" else "SHORT"
        leverage = 4.0
        alloc_cap = equity * option_alloc_pct

    entry = safe_float(row.get("entry_price"), 0.0)
    stop = safe_float(row.get("stop_price"), 0.0)
    target = safe_float(row.get("target_price"), 0.0)
    if entry <= 0:
        return None
    stop_dist_ratio = abs(entry - stop) / entry if stop > 0 else 0.02
    risk_budget = max(0.0, equity * risk_per_trade_pct)
    capital_by_risk = risk_budget / max(0.0001, stop_dist_ratio * leverage)
    alloc = min(alloc_cap, capital_by_risk, max(0.0, cash))
    if alloc < 100:
        return None

    return {
        "id": f"{symbol}_{instrument}_{run_count}",
        "symbol": symbol,
        "instrument": instrument,
        "direction": direction,
        "leverage": leverage,
        "capital_allocated": round(alloc, 4),
        "entry_underlying_price": round(entry, 4),
        "stop_price": round(stop, 4),
        "target_price": round(target, 4),
        "opened_run": run_count,
        "hold_runs": 0,
        "entry_score": safe_float(row.get("total_score"), 0.0),
    }


def update_portfolio(
    base_dir: Path,
    top10: pd.DataFrame,
    run_ts: str,
    enable_after_hours: bool,
    advice_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    state = load_portfolio_state(base_dir)
    # capital_balance is a fixed benchmark (e.g., 10000) and should not drift run-to-run.
    base_capital = INITIAL_CAPITAL
    start_equity = safe_float(state.get("paper_balance"), safe_float(state.get("simulation_balance"), safe_float(state.get("equity"), base_capital)))
    cash = safe_float(state.get("cash"), base_capital)
    run_count = int(state.get("run_count", 0)) + 1
    open_positions: list[dict[str, Any]] = normalize_open_positions(list(state.get("open_positions", [])))
    candidate_rows = top10.to_dict(orient="records")
    advice_rows = (advice_df if advice_df is not None else top10).to_dict(orient="records")
    advice_by_symbol = {str(r.get("symbol", "")): r for r in advice_rows if str(r.get("symbol", ""))}

    events: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    open_value = 0.0

    for pos in open_positions:
        symbol = str(pos.get("symbol", ""))
        current_price, price_source = position_price_for_mark(pos, enable_after_hours)
        pos["hold_runs"] = int(pos.get("hold_runs", 0)) + 1
        if current_price <= 0:
            still_open.append(pos)
            continue

        value = refresh_position_mark(pos, current_price, price_source)
        close_now, reason = should_close_position(pos, current_price)
        if close_now and price_source != "live":
            reason = f"{reason}_{price_source}"
        if not close_now:
            reason = advice_close_reason(pos, advice_by_symbol.get(symbol))
            close_now = bool(reason)
        if close_now:
            cash += value
            pnl = value - safe_float(pos.get("capital_allocated"), 0.0)
            events.append(
                {
                    "timestamp_utc": run_ts,
                    "event": "CLOSE",
                    "symbol": symbol,
                    "instrument": pos.get("instrument"),
                    "direction": pos.get("direction"),
                    "entry_price": pos.get("entry_underlying_price"),
                    "exit_price": round(current_price, 4),
                    "capital_allocated": pos.get("capital_allocated"),
                    "value": round(value, 4),
                    "pnl": round(pnl, 4),
                    "reason": reason,
                    "hold_runs": pos.get("hold_runs"),
                }
            )
            state["closed_positions_count"] = int(state.get("closed_positions_count", 0)) + 1
        else:
            open_value += value
            still_open.append(pos)

    open_positions = still_open
    equity = cash + open_value
    full_deploy = bool(TRADING_CONFIG.get("full_budget_deploy", False))
    deploy_target_pct = clamp(safe_float(TRADING_CONFIG.get("full_deploy_target_pct"), 1.0), 0.6, 1.0)
    peak_equity = max(safe_float(state.get("peak_paper_balance"), safe_float(state.get("peak_simulation_balance"), start_equity)), start_equity, equity)
    budget_controls = build_budget_controls(start_equity, base_capital, peak_equity, full_deploy, deploy_target_pct)
    target_exposure_pct = safe_float(budget_controls.get("effective_target_exposure_pct"), MAX_PORTFOLIO_EXPOSURE_PCT * 100.0) / 100.0
    max_open_positions = int(budget_controls.get("effective_max_open_positions", 20 if full_deploy else MAX_OPEN_POSITIONS))
    current_exposure_cap = equity * target_exposure_pct

    used_symbols = {str(p.get("symbol")) for p in open_positions}
    if full_deploy:
        actionable = [
            r
            for r in candidate_rows
            if str(r.get("action_stock", "")) in {"BUY_STOCK", "SELL_SHORT"}
        ]
        remaining_slots = len(actionable)
        for row in actionable:
            if len(open_positions) >= max_open_positions or cash < 100:
                break
            symbol = str(row.get("symbol", ""))
            if not symbol:
                remaining_slots = max(0, remaining_slots - 1)
                continue
            if symbol in used_symbols:
                remaining_slots = max(0, remaining_slots - 1)
                continue
            open_value = sum(
                mark_position_value(
                    p,
                    position_price_for_mark(p, enable_after_hours)[0],
                )
                for p in open_positions
            )
            if open_value >= current_exposure_cap:
                break
            pos = build_new_position(row, equity, cash, run_count, "STOCK", budget_controls)
            remaining_slots = max(0, remaining_slots - 1)
            if pos is None:
                continue
            # Distribute cash across remaining actionable picks to approach full deployment.
            slots_divisor = max(1, remaining_slots + 1)
            planned_alloc = cash / slots_divisor
            room = max(0.0, current_exposure_cap - open_value)
            alloc = min(max(100.0, planned_alloc), cash, room)
            if alloc < 100:
                continue
            pos["capital_allocated"] = round(alloc, 4)
            cash -= alloc
            open_positions.append(pos)
            used_symbols.add(symbol)
            events.append(
                {
                    "timestamp_utc": run_ts,
                    "event": "OPEN",
                    "symbol": symbol,
                    "instrument": pos.get("instrument"),
                    "direction": pos.get("direction"),
                    "entry_price": pos.get("entry_underlying_price"),
                    "exit_price": "",
                    "capital_allocated": pos.get("capital_allocated"),
                    "value": pos.get("capital_allocated"),
                    "pnl": 0.0,
                    "reason": "signal_open_full_budget",
                    "hold_runs": 0,
                }
            )
        # If there is remaining cash, top up existing stock positions to approach full deployment.
        if cash >= 100 and open_positions:
            stock_targets = [p for p in open_positions if str(p.get("instrument", "")) == "STOCK"]
            remaining_targets = len(stock_targets)
            for idx, pos0 in enumerate(stock_targets, start=1):
                if cash < 100:
                    break
                remaining_targets = max(1, remaining_targets)
                open_value = sum(
                    mark_position_value(
                        p,
                        position_price_for_mark(p, enable_after_hours)[0],
                    )
                    for p in open_positions
                )
                room = max(0.0, current_exposure_cap - open_value)
                if room < 100:
                    break
                alloc = min(cash / remaining_targets, cash, room)
                if alloc < 100:
                    remaining_targets -= 1
                    continue
                symbol = str(pos0.get("symbol", ""))
                px, price_source = position_price_for_mark(pos0, enable_after_hours)
                if px <= 0:
                    remaining_targets -= 1
                    continue
                add_to_position(pos0, alloc, px, run_count)
                cash -= alloc
                events.append(
                    {
                        "timestamp_utc": run_ts,
                        "event": "OPEN",
                        "symbol": symbol,
                        "instrument": "STOCK",
                        "direction": pos0.get("direction"),
                        "entry_price": pos0.get("entry_underlying_price"),
                        "exit_price": "",
                        "capital_allocated": round(alloc, 4),
                        "value": round(alloc, 4),
                        "pnl": 0.0,
                        "reason": "signal_open_full_budget_topup",
                        "hold_runs": 0,
                    }
                )
                remaining_targets -= 1
    else:
        # Prefer stock trades for low-risk profile, then small options sleeve.
        for instrument in ("STOCK", "OPTION"):
            for row in candidate_rows:
                if len(open_positions) >= max_open_positions:
                    break
                symbol = str(row.get("symbol", ""))
                if not symbol or symbol in used_symbols:
                    continue
                open_value = sum(
                    mark_position_value(p, position_price_for_mark(p, enable_after_hours)[0])
                    for p in open_positions
                )
                if open_value >= current_exposure_cap:
                    break
                pos = build_new_position(row, equity, cash, run_count, instrument, budget_controls)
                if pos is None:
                    continue
                alloc = safe_float(pos.get("capital_allocated"), 0.0)
                if open_value + alloc > current_exposure_cap:
                    continue
                cash -= alloc
                open_positions.append(pos)
                used_symbols.add(symbol)
                events.append(
                    {
                        "timestamp_utc": run_ts,
                        "event": "OPEN",
                        "symbol": symbol,
                        "instrument": pos.get("instrument"),
                        "direction": pos.get("direction"),
                        "entry_price": pos.get("entry_underlying_price"),
                        "exit_price": "",
                        "capital_allocated": pos.get("capital_allocated"),
                        "value": pos.get("capital_allocated"),
                        "pnl": 0.0,
                        "reason": "signal_open",
                        "hold_runs": 0,
                    }
                )

    # Re-mark open positions for ending equity.
    end_open_value = 0.0
    for p in open_positions:
        px, price_source = position_price_for_mark(p, enable_after_hours)
        if px <= 0:
            continue
        end_open_value += refresh_position_mark(p, px, price_source)
    end_equity = cash + end_open_value

    run_pnl = end_equity - start_equity
    run_return = (run_pnl / start_equity) if start_equity > 0 else 0.0
    total_return = (end_equity / base_capital - 1.0) if base_capital > 0 else 0.0
    state["peak_paper_balance"] = round(max(peak_equity, end_equity), 4)
    state["peak_simulation_balance"] = state["peak_paper_balance"]
    budget_controls = build_budget_controls(end_equity, base_capital, state["peak_paper_balance"], full_deploy, deploy_target_pct)

    state["capital_balance"] = base_capital
    state["cash"] = round(cash, 4)
    state["paper_balance"] = round(end_equity, 4)
    state["simulation_balance"] = round(end_equity, 4)
    # Backward-compatible aliases.
    state["initial_capital"] = state["capital_balance"]
    state["equity"] = state["paper_balance"]
    state["run_count"] = run_count
    state["open_positions"] = open_positions
    state["last_updated_utc"] = run_ts
    save_portfolio_state(base_dir, state)

    append_trade_events(base_dir, events)
    append_equity_curve(
        base_dir,
        {
            "timestamp_utc": run_ts,
            "run_count": run_count,
            "start_equity": round(start_equity, 4),
            "end_equity": round(end_equity, 4),
            "run_pnl": round(run_pnl, 4),
            "run_return_pct": round(run_return * 100, 4),
            "total_return_pct": round(total_return * 100, 4),
            "cash": round(cash, 4),
            "open_positions": len(open_positions),
            "peak_equity": round(safe_float(state.get("peak_paper_balance"), end_equity), 4),
            "drawdown_pct": round(safe_float(budget_controls.get("drawdown_pct"), 0.0), 4),
            "closed_positions_count": int(state.get("closed_positions_count", 0)),
        },
    )

    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp_utc": run_ts,
        "capital_balance": base_capital,
        "real_trading_capital": REAL_TRADING_CAPITAL,
        "start_equity": round(start_equity, 4),
        "paper_balance": round(end_equity, 4),
        "simulation_balance": round(end_equity, 4),
        "run_pnl": round(run_pnl, 4),
        "run_return_pct": round(run_return * 100, 4),
        "total_return_pct": round(total_return * 100, 4),
        "cash": round(cash, 4),
        "current_exposure": round(end_open_value, 4),
        "peak_equity": round(safe_float(state.get("peak_paper_balance"), end_equity), 4),
        "drawdown_pct": round(safe_float(budget_controls.get("drawdown_pct"), 0.0), 4),
        "open_positions": len(open_positions),
        "new_events": len(events),
        "risk_profile": "LOW_RISK_HIGH_LEVEL",
        "risk_limits": {
            "risk_per_trade_pct": safe_float(budget_controls.get("effective_risk_per_trade_pct"), RISK_PER_TRADE * 100),
            "max_stock_alloc_pct": safe_float(budget_controls.get("effective_max_stock_alloc_pct"), MAX_STOCK_ALLOC_PCT * 100),
            "max_option_alloc_pct": safe_float(budget_controls.get("effective_max_option_alloc_pct"), MAX_OPTION_ALLOC_PCT * 100),
            "max_portfolio_exposure_pct": safe_float(budget_controls.get("effective_target_exposure_pct"), target_exposure_pct * 100),
            "max_open_positions": int(budget_controls.get("effective_max_open_positions", max_open_positions)),
            "full_budget_deploy": full_deploy,
        },
        "budget_controls": budget_controls,
    }
    # Backward-compatible aliases for existing consumers.
    summary["initial_capital"] = summary["capital_balance"]
    summary["end_equity"] = summary["paper_balance"]
    (latest_dir / "portfolio_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_portfolio_report(base_dir, summary, open_positions, enable_after_hours)
    return summary


def sizing_equity_from_summary(summary: dict[str, Any]) -> float:
    return max(
        0.0,
        safe_float(
            summary.get("paper_balance"),
            safe_float(
                summary.get("simulation_balance"),
            safe_float(summary.get("end_equity"), safe_float(summary.get("start_equity"), INITIAL_CAPITAL)),
            ),
        ),
    )


def save_run(base_dir: Path, rows: list[AnalysisRow], market_ctx: dict[str, Any]) -> Path:
    dirs = ensure_dirs(base_dir)
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    run_dir = dirs["runs"] / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    with (run_dir / "market_context.json").open("w", encoding="utf-8") as f:
        json.dump(market_ctx, f, indent=2)

    all_df = pd.DataFrame([asdict(r) for r in rows]).sort_values("total_score", ascending=False)
    all_df = add_instruction_columns(all_df)
    all_df.to_csv(run_dir / "candidates.csv", index=False)

    actionable = all_df[all_df["action_stock"].isin(["BUY_STOCK", "SELL_SHORT"])].copy()
    if not actionable.empty:
        actionable["edge_score"] = actionable.apply(
            lambda r: safe_float(r.get("total_score"), 0.0)
            if str(r.get("action_stock", "")) == "BUY_STOCK"
            else -safe_float(r.get("total_score"), 0.0),
            axis=1,
        )
        top10 = actionable.sort_values("edge_score", ascending=False).head(10).drop(columns=["edge_score"], errors="ignore")
        if len(top10) < 10:
            fill = all_df.loc[~all_df["symbol"].isin(set(top10["symbol"]))].head(10 - len(top10))
            top10 = pd.concat([top10, fill], ignore_index=True)
    else:
        top10 = all_df.head(10).copy()
    alert_summary = process_notifications(base_dir, ts, top10, market_ctx)
    (run_dir / "alerts.json").write_text(json.dumps(alert_summary, indent=2), encoding="utf-8")
    portfolio_summary = update_portfolio(
        base_dir,
        top10,
        ts,
        bool(market_ctx.get("enable_after_hours", False)),
        all_df,
    )
    (run_dir / "portfolio_summary.json").write_text(json.dumps(portfolio_summary, indent=2), encoding="utf-8")
    sizing_equity = sizing_equity_from_summary(portfolio_summary)
    budget_controls = dict(portfolio_summary.get("budget_controls", {}))
    top10 = add_sizing_columns(top10, sizing_equity, budget_controls)
    top10 = add_instruction_columns(top10)
    top10.to_csv(run_dir / "top10.csv", index=False)
    budget_plan = build_budget_plan(
        top10,
        safe_float(portfolio_summary.get("start_equity"), sizing_equity),
        safe_float(portfolio_summary.get("paper_balance"), safe_float(portfolio_summary.get("simulation_balance"), safe_float(portfolio_summary.get("end_equity"), sizing_equity))),
        safe_float(portfolio_summary.get("capital_balance"), safe_float(portfolio_summary.get("initial_capital"), INITIAL_CAPITAL)),
        budget_controls,
        safe_float(portfolio_summary.get("cash"), 0.0),
        safe_float(portfolio_summary.get("current_exposure"), 0.0),
    )

    md_lines = [
        f"# Top 10 Picks ({format_run_ts_pt(ts)})",
        "",
        f"Market regime: **{market_ctx.get('regime', 'unknown')}**",
        f"Market session: **{market_ctx.get('market_session', 'unknown')}** "
        f"(`open={market_ctx.get('market_open', False)}`; PT {market_ctx.get('market_time_pt', '')})",
        f"Price reference: `{market_ctx.get('price_reference_mode', '')}` "
        f"(close date PT: {market_ctx.get('price_reference_close_date_pt', '')})",
        "",
        "## Portfolio",
        f"- Start equity this run: `${portfolio_summary.get('start_equity', 0):,.2f}`",
        f"- Benchmark capital (fixed): `${safe_float(portfolio_summary.get('capital_balance'), safe_float(portfolio_summary.get('initial_capital'), 0)):,.2f}`",
        f"- Real trading capital (fixed): `${portfolio_summary.get('real_trading_capital', 0):,.2f}`",
        f"- Paper balance: `${safe_float(portfolio_summary.get('paper_balance'), safe_float(portfolio_summary.get('simulation_balance'), safe_float(portfolio_summary.get('end_equity'), 0))):,.2f}`",
        f"- Run P/L: `${portfolio_summary.get('run_pnl', 0):,.2f}` "
        f"({portfolio_summary.get('run_return_pct', 0):.2f}%)",
        f"- Total return: `{portfolio_summary.get('total_return_pct', 0):.2f}%`",
        f"- Open positions: `{portfolio_summary.get('open_positions', 0)}`",
        "",
        "## Paper Budget",
        f"- Initial benchmark capital (fixed): `${budget_plan.get('initial_baseline', 0):,.2f}`",
        f"- Run start budget (from previous run): `${budget_plan.get('run_start_budget', 0):,.2f}`",
        f"- Current equity: `${budget_plan.get('current_equity', 0):,.2f}`",
        f"- Change vs initial benchmark: `${budget_plan.get('delta_vs_initial', 0):,.2f}`",
        f"- Change vs run start: `${budget_plan.get('delta_vs_run_start', 0):,.2f}`",
        f"- Cash on hand: `${budget_plan.get('cash_on_hand', 0):,.2f}`",
        f"- Current exposure: `${budget_plan.get('current_exposure', 0):,.2f}`",
        f"- Peak equity: `${budget_plan.get('peak_equity', 0):,.2f}`",
        f"- Drawdown from peak: `{budget_plan.get('drawdown_pct', 0):.2f}%`",
        f"- Budget regime: `{budget_plan.get('budget_regime', 'normal')}`",
        f"- Target exposure cap: `{budget_plan.get('target_exposure_pct', 0):.2f}%`",
        f"- Risk per trade: `{budget_plan.get('risk_per_trade_pct', 0):.4f}%`",
        f"- Remaining exposure headroom: `${budget_plan.get('exposure_headroom', 0):,.2f}`",
        f"- Fresh deployable budget now: `${budget_plan.get('deployable_budget', 0):,.2f}`",
        f"- Recommended deploy (raw): `${budget_plan.get('uncapped_recommended', 0):,.2f}`",
        f"- Recommended deploy (risk-capped): `${budget_plan.get('capped_recommended', 0):,.2f}`",
        f"- Reserve cash after plan: `${budget_plan.get('reserve_after_plan', 0):,.2f}`",
        f"- Why this can be below the initial budget: {budget_plan.get('budget_explanation', '')}",
        "",
        "## Alerts",
        f"- Channel: `{alert_summary.get('channel', '')}`",
        f"- Notification sent: `{alert_summary.get('sent', False)}`",
        f"- Alert reason: `{alert_summary.get('reason', '')}`",
        f"- Alert candidates: `{len(alert_summary.get('items', []))}`",
        "",
        "| Rank | Symbol | Strategy | Price | Score | Stock Qty | Option Ctr | E Days | E Score | Stock Action | Option Action | Exec | Option Hint | Entry | Target | Stop | R:R | Why |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for idx, row in top10.reset_index(drop=True).iterrows():
        md_lines.append(
            f"| {idx+1} | {row['symbol']} | {row.get('strategy_bucket','DAILY_TRADING')} | {row['price']:.2f} | {row['total_score']:.3f} | "
            f"{int(safe_float(row.get('stock_qty'), 0))} | {int(safe_float(row.get('option_contracts'), 0))} | "
            f"{int(safe_float(row.get('upcoming_earnings_days'), -1))} | {safe_float(row.get('earnings_event_score'), 0.0):.2f} | "
            f"{row['action_stock']} | {row['action_option']} | {row['execution_timing']} | {row['option_symbol_hint']} | "
            f"{row['entry_price']:.2f} | {row['target_price']:.2f} | {row['stop_price']:.2f} | {row['risk_reward']:.2f} | "
            f"{row['brief_reason']} |"
        )
    md_lines.extend(
        [
            "",
            "## Clear Action Plan",
        ]
    )
    for idx, row in top10.reset_index(drop=True).iterrows():
        md_lines.append(
            f"{idx+1}. {row['symbol']} ({row['trade_type']}, {row.get('strategy_bucket','DAILY_TRADING')}) | {row['stock_instruction']} | {row['option_instruction']} | {row['brief_reason']}"
        )
    if budget_plan.get("rows"):
        md_lines.extend(["", "## Budget By Pick"])
        for idx, b in enumerate(budget_plan["rows"], start=1):
            md_lines.append(
                f"{idx}. {b['symbol']} | {b['action_stock']} | shares={b['stock_qty']} | contracts={b['option_contracts']} | budget=${b['budget_usd']:.2f}"
            )
    actions = budget_plan.get("improvement_actions", [])
    if actions:
        md_lines.extend(["", "## Improvement Actions"])
        for idx, action in enumerate(actions, start=1):
            md_lines.append(f"{idx}. {action}")
    md_lines.extend(["", "## Daily Trading Section"])
    daily_focus = top10[top10["strategy_bucket"] == "DAILY_TRADING"].head(10).reset_index(drop=True)
    if daily_focus.empty:
        md_lines.append("- No daily-trading focus names in current top picks.")
    else:
        for idx, row in daily_focus.iterrows():
            md_lines.append(
                f"{idx+1}. {row['symbol']} | {row['stock_instruction']} | score={safe_float(row.get('total_score'), 0.0):.2f}"
            )
    md_lines.extend(["", "## Earnings Swing Section"])
    earnings_focus = (
        top10[top10["strategy_bucket"] == "EARNINGS_SWING"]
        .sort_values(["earnings_event_score", "total_score"], ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    if earnings_focus.empty:
        md_lines.append("- No earnings-swing setups (2-30 day pre-earnings window) in current top picks.")
    else:
        for idx, row in earnings_focus.iterrows():
            md_lines.append(
                f"{idx+1}. {row['symbol']} | earnings in {int(safe_float(row.get('upcoming_earnings_days'), -1))}d | "
                f"{row['stock_instruction']} | e_score={safe_float(row.get('earnings_event_score'), 0.0):.2f} | total={safe_float(row.get('total_score'), 0.0):.2f}"
            )
    (run_dir / "top10.md").write_text("\n".join(md_lines), encoding="utf-8")

    append_history(dirs["history"] / "top10_history.csv", ts, top10)
    now_local = datetime.now()
    if now_local.minute == 0:
        append_history(dirs["history"] / "top10_hourly.csv", ts, top10)
    if now_local.hour == 16 and now_local.minute <= 10:
        append_history(dirs["history"] / "top10_daily.csv", ts, top10)

    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(latest_dir / "candidates.csv", index=False)
    top10.to_csv(latest_dir / "top10.csv", index=False)
    (latest_dir / "alerts.json").write_text(json.dumps(alert_summary, indent=2), encoding="utf-8")
    (latest_dir / "top10.md").write_text("\n".join(md_lines), encoding="utf-8")

    generate_daily_summary(base_dir, ts)
    refresh_simple_view(base_dir, ts)
    return run_dir


def append_history(path: Path, timestamp: str, top10: pd.DataFrame) -> None:
    rows = []
    for rank, row in enumerate(top10.reset_index(drop=True).to_dict(orient="records"), start=1):
        rows.append({"timestamp_utc": timestamp, "rank": rank, **row})

    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def write_market_closed_status(base_dir: Path, mkt: dict[str, Any]) -> None:
    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp_utc": now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "skipped_market_closed",
        **mkt,
    }
    (latest_dir / "market_status.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def render_stock_instruction(row: pd.Series) -> str:
    action = str(row.get("action_stock", "HOLD"))
    qty = int(safe_float(row.get("stock_qty"), 0))
    entry = safe_float(row.get("entry_price"), 0.0)
    target = safe_float(row.get("target_price"), 0.0)
    stop = safe_float(row.get("stop_price"), 0.0)
    if action == "BUY_STOCK":
        return f"BUY {qty} SHARES @ {entry:.2f}, SELL @ {target:.2f}, STOP @ {stop:.2f}"
    if action == "SELL_SHORT":
        return f"SHORT {qty} SHARES @ {entry:.2f}, COVER @ {target:.2f}, STOP @ {stop:.2f}"
    return "HOLD STOCK (NO TRADE)"


def render_option_instruction(row: pd.Series) -> str:
    action = str(row.get("action_option", "NO_OPTION"))
    contracts = int(safe_float(row.get("option_contracts"), 0))
    hint = str(row.get("option_symbol_hint", "")).strip()
    expiry = str(row.get("option_expiry", "")).strip()
    strike = safe_float(row.get("option_strike"), 0.0)
    if action == "BUY_CALL":
        detail = hint if hint else f"CALL strike {strike:.2f} exp {expiry}"
        return f"BUY {contracts} CALL CONTRACT(S): {detail}"
    if action == "BUY_PUT":
        detail = hint if hint else f"PUT strike {strike:.2f} exp {expiry}"
        return f"BUY {contracts} PUT CONTRACT(S): {detail}"
    return "NO OPTIONS TRADE"


def estimate_position_sizes(row: pd.Series, equity: float, budget_controls: dict[str, Any] | None = None) -> tuple[int, float, int, float]:
    controls = budget_controls or {}
    action_stock = str(row.get("action_stock", "HOLD"))
    action_option = str(row.get("action_option", "NO_OPTION"))
    entry = safe_float(row.get("entry_price"), 0.0)
    stop = safe_float(row.get("stop_price"), 0.0)
    if equity <= 0 or entry <= 0:
        return 0, 0.0, 0, 0.0

    risk_per_trade_pct = safe_float(controls.get("effective_risk_per_trade_pct"), RISK_PER_TRADE * 100.0) / 100.0
    stock_alloc_pct = safe_float(controls.get("effective_max_stock_alloc_pct"), MAX_STOCK_ALLOC_PCT * 100.0) / 100.0
    option_alloc_pct = safe_float(controls.get("effective_max_option_alloc_pct"), MAX_OPTION_ALLOC_PCT * 100.0) / 100.0
    risk_budget = max(0.0, equity * risk_per_trade_pct)
    stock_alloc_cap = max(0.0, equity * stock_alloc_pct)
    option_alloc_cap = max(0.0, equity * option_alloc_pct)

    stock_qty = 0
    stock_notional = 0.0
    if action_stock in {"BUY_STOCK", "SELL_SHORT"}:
        risk_per_share = max(abs(entry - stop), max(0.005 * entry, 0.01))
        qty_by_risk = int(risk_budget // risk_per_share)
        qty_by_alloc = int(stock_alloc_cap // entry)
        stock_qty = max(0, min(qty_by_risk, qty_by_alloc))
        stock_notional = round(stock_qty * entry, 2)

    option_contracts = 0
    option_notional = 0.0
    if action_option in {"BUY_CALL", "BUY_PUT"}:
        # Premium proxy for sizing when live option premium is unavailable.
        premium_per_share = max(0.5, entry * 0.02)
        premium_per_contract = premium_per_share * 100.0
        contracts_by_alloc = int(option_alloc_cap // premium_per_contract)
        contracts_by_risk = int(risk_budget // max(premium_per_contract * 0.6, 1.0))
        option_contracts = max(0, min(contracts_by_alloc, contracts_by_risk))
        option_notional = round(option_contracts * premium_per_contract, 2)

    return stock_qty, stock_notional, option_contracts, option_notional


def add_sizing_columns(df: pd.DataFrame, equity: float, budget_controls: dict[str, Any] | None = None) -> pd.DataFrame:
    out = df.copy()
    sized = out.apply(lambda r: estimate_position_sizes(r, equity, budget_controls), axis=1)
    out["stock_qty"] = sized.map(lambda x: x[0])
    out["stock_notional_usd"] = sized.map(lambda x: x[1])
    out["option_contracts"] = sized.map(lambda x: x[2])
    out["option_premium_est_usd"] = sized.map(lambda x: x[3])
    out["recommended_budget_usd"] = (
        pd.to_numeric(out["stock_notional_usd"], errors="coerce").fillna(0.0)
        + pd.to_numeric(out["option_premium_est_usd"], errors="coerce").fillna(0.0)
    ).round(2)
    return out


def build_budget_plan(
    top10: pd.DataFrame,
    run_start_equity: float,
    current_equity: float,
    simulation_baseline: float,
    budget_controls: dict[str, Any] | None = None,
    current_cash: float | None = None,
    current_exposure: float | None = None,
) -> dict[str, Any]:
    start_eq = max(0.0, safe_float(run_start_equity, INITIAL_CAPITAL))
    eq = max(0.0, safe_float(current_equity, start_eq))
    baseline = max(0.0, safe_float(simulation_baseline, INITIAL_CAPITAL))
    controls = budget_controls or {}
    target_exposure_pct = safe_float(controls.get("effective_target_exposure_pct"), MAX_PORTFOLIO_EXPOSURE_PCT * 100.0) / 100.0
    budget_cap = eq * target_exposure_pct
    cash = max(0.0, safe_float(current_cash, eq))
    exposure = max(0.0, safe_float(current_exposure, max(0.0, eq - cash)))
    exposure_headroom = max(0.0, budget_cap - exposure)
    deployable_budget = min(cash, exposure_headroom)
    delta_vs_initial = eq - baseline
    delta_vs_run_start = eq - start_eq
    budget_status = "at_or_above_initial"
    if delta_vs_initial < 0:
        budget_status = "below_initial"
    elif delta_vs_initial > 0:
        budget_status = "above_initial"
    explanation_parts = [
        "Paper balance is marked to market each run.",
        "Closed-trade losses and unrealized losses on open positions reduce equity.",
    ]
    if delta_vs_initial < 0:
        explanation_parts.append("That is why current budget can be lower than the fixed initial benchmark.")
    if safe_float(controls.get("drawdown_pct"), 0.0) > 0:
        explanation_parts.append("Drawdown controls also reduce fresh deployment and risk until equity recovers.")
    budget_explanation = " ".join(explanation_parts)
    improvement_actions: list[str] = []
    if delta_vs_initial < 0 or str(controls.get("regime", "normal")) != "normal":
        improvement_actions.append("Reduce new deployment to the risk-capped budget instead of the raw recommendation.")
        improvement_actions.append("Prioritize only the highest-conviction stock setups until equity recovers.")
    if safe_float(controls.get("drawdown_pct"), 0.0) >= 5.0:
        improvement_actions.append("Preserve more cash and avoid using the full exposure cap while drawdown remains active.")
    if exposure > budget_cap:
        improvement_actions.append("Do not add new positions until existing exposure falls back under the target exposure cap.")
    if deployable_budget < 100.0:
        improvement_actions.append("Pause opening small new positions; wait for positions to close, improve, or for cash to rebuild.")
    if not improvement_actions:
        improvement_actions.append("Budget is healthy; continue normal sizing and deployment rules.")
    if top10.empty:
        return {
            "initial_baseline": baseline,
            "run_start_budget": start_eq,
            "current_equity": eq,
            "delta_vs_initial": delta_vs_initial,
            "delta_vs_run_start": delta_vs_run_start,
            "budget_regime": str(controls.get("regime", "normal")),
            "peak_equity": safe_float(controls.get("peak_equity"), eq),
            "drawdown_pct": safe_float(controls.get("drawdown_pct"), 0.0),
            "target_exposure_pct": round(target_exposure_pct * 100.0, 2),
            "risk_per_trade_pct": safe_float(controls.get("effective_risk_per_trade_pct"), RISK_PER_TRADE * 100.0),
            "cash_on_hand": round(cash, 2),
            "current_exposure": round(exposure, 2),
            "exposure_headroom": round(exposure_headroom, 2),
            "deployable_budget": round(deployable_budget, 2),
            "uncapped_recommended": 0.0,
            "capped_recommended": 0.0,
            "reserve_after_plan": round(cash, 2),
            "budget_status": budget_status,
            "budget_explanation": budget_explanation,
            "improvement_actions": improvement_actions,
            "rows": [],
        }
    work = top10.copy()
    work["recommended_budget_usd"] = pd.to_numeric(work.get("recommended_budget_usd", 0.0), errors="coerce").fillna(0.0)
    actionable = work[work["recommended_budget_usd"] > 0].copy()
    uncapped = float(actionable["recommended_budget_usd"].sum()) if not actionable.empty else 0.0
    capped = min(uncapped, deployable_budget)
    reserve = max(0.0, cash - capped)
    rows = []
    if not actionable.empty:
        for _, r in actionable.head(10).iterrows():
            rows.append(
                {
                    "symbol": str(r.get("symbol", "")),
                    "action_stock": str(r.get("action_stock", "")),
                    "stock_qty": int(safe_float(r.get("stock_qty"), 0)),
                    "option_contracts": int(safe_float(r.get("option_contracts"), 0)),
                    "budget_usd": round(safe_float(r.get("recommended_budget_usd"), 0.0), 2),
                }
            )
    return {
        "initial_baseline": round(baseline, 2),
        "run_start_budget": round(start_eq, 2),
        "current_equity": round(eq, 2),
        "delta_vs_initial": round(delta_vs_initial, 2),
        "delta_vs_run_start": round(delta_vs_run_start, 2),
        "budget_regime": str(controls.get("regime", "normal")),
        "peak_equity": round(safe_float(controls.get("peak_equity"), eq), 2),
        "drawdown_pct": round(safe_float(controls.get("drawdown_pct"), 0.0), 2),
        "target_exposure_pct": round(target_exposure_pct * 100.0, 2),
        "risk_per_trade_pct": round(safe_float(controls.get("effective_risk_per_trade_pct"), RISK_PER_TRADE * 100.0), 4),
        "cash_on_hand": round(cash, 2),
        "current_exposure": round(exposure, 2),
        "exposure_headroom": round(exposure_headroom, 2),
        "deployable_budget": round(deployable_budget, 2),
        "uncapped_recommended": round(uncapped, 2),
        "capped_recommended": round(capped, 2),
        "reserve_after_plan": round(reserve, 2),
        "budget_status": budget_status,
        "budget_explanation": budget_explanation,
        "improvement_actions": improvement_actions,
        "rows": rows,
    }


def add_instruction_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trade_type"] = out.apply(
        lambda r: (
            "STOCK_AND_OPTIONS"
            if str(r.get("action_stock")) in {"BUY_STOCK", "SELL_SHORT"} and str(r.get("action_option")) in {"BUY_CALL", "BUY_PUT"}
            else "STOCK_ONLY"
            if str(r.get("action_stock")) in {"BUY_STOCK", "SELL_SHORT"}
            else "OPTIONS_ONLY"
            if str(r.get("action_option")) in {"BUY_CALL", "BUY_PUT"}
            else "NO_TRADE"
        ),
        axis=1,
    )
    out["stock_instruction"] = out.apply(render_stock_instruction, axis=1)
    out["option_instruction"] = out.apply(render_option_instruction, axis=1)
    out["brief_reason"] = out.apply(render_brief_reason, axis=1)
    out["strategy_bucket"] = out.apply(classify_strategy_bucket, axis=1)
    return out


def classify_strategy_bucket(row: pd.Series) -> str:
    action = str(row.get("action_stock", "HOLD"))
    days = int(safe_float(row.get("upcoming_earnings_days"), -1))
    e_score = safe_float(row.get("earnings_event_score"), 0.0)
    if action == "BUY_STOCK" and 2 <= days <= 30 and e_score >= 0.55:
        return "EARNINGS_SWING"
    return "DAILY_TRADING"


def render_brief_reason(row: pd.Series) -> str:
    fund = safe_float(row.get("fundamental_score"), 0.0)
    tech = safe_float(row.get("technical_score"), 0.0)
    news = safe_float(row.get("news_score"), 0.0)
    total = safe_float(row.get("total_score"), 0.0)
    stock_action = str(row.get("action_stock", "HOLD"))
    regime = str(row.get("market_regime", ""))
    mkt = safe_float(row.get("market_trend_score"), 0.0)
    cat = safe_float(row.get("category_trend_score"), 0.0)
    earn_days = int(safe_float(row.get("upcoming_earnings_days"), -1))
    earn_score = safe_float(row.get("earnings_event_score"), 0.0)

    parts = []
    if tech >= 0.4:
        parts.append("strong technical trend")
    elif tech <= -0.4:
        parts.append("weak technical trend")

    if fund >= 0.2:
        parts.append("solid fundamentals")
    elif fund <= -0.2:
        parts.append("weak fundamentals")

    if news >= 0.08:
        parts.append("positive news tone")
    elif news <= -0.08:
        parts.append("negative news tone")
    if mkt >= 0.3:
        parts.append("market trend supportive")
    elif mkt <= -0.3:
        parts.append("market trend weak")
    if cat >= 0.3:
        parts.append("category trend supportive")
    elif cat <= -0.3:
        parts.append("category trend weak")
    if 2 <= earn_days <= 8 and earn_score >= 0.4:
        parts.append(f"earnings catalyst in {earn_days}d")

    if stock_action == "BUY_STOCK":
        direction = "bullish setup"
    elif stock_action == "SELL_SHORT":
        direction = "bearish setup"
    else:
        direction = "mixed setup"

    if not parts:
        parts.append("balanced signals")

    return f"{direction}; {', '.join(parts)} (score {total:.2f}, regime {regime})"


def run_once(base_dir: Path, universe_count: int, enable_after_hours: bool) -> Path:
    params = load_model_params()
    adaptation_summary = post_analyze_and_adapt(base_dir, params, enable_after_hours)
    save_post_analysis(base_dir, adaptation_summary)
    mkt = market_hours_context()
    if str(mkt.get("market_session", "")) == "weekend":
        symbols = STABLE_UNIVERSE[: max(10, universe_count)]
    else:
        symbols = fetch_market_movers(
            universe_count,
            bool(TRADING_CONFIG.get("include_downtrend_symbols", True)),
            safe_float(TRADING_CONFIG.get("downtrend_symbol_ratio", 0.4), 0.4),
        )
    regime, ctx = market_regime()
    mkt_score = market_trend_score(regime, ctx)
    category_ctx = build_category_context()
    market_ctx = {
        "regime": regime,
        **ctx,
        **mkt,
        "universe_count": len(symbols),
        "model_params_file": str(MODEL_STATE_PATH),
        "enable_after_hours": bool(enable_after_hours),
        "analysis_order": [
            "fundamental",
            "technical",
            "news",
            "market_trend",
            "category_trend",
        ],
        "price_reference_mode": "last_regular_close" if not bool(mkt.get("market_open")) else "intraday_last_trade",
        "price_reference_close_date_pt": previous_trading_day_pt(),
        "weekend_reference": "previous_trading_day_close" if str(mkt.get("market_session", "")) == "weekend" else "",
        "earnings_catalyst": {
            "enabled": True,
            "window_days": [2, 30],
            "note": "buy bias before earnings when outlook and current price setup are supportive",
        },
        "market_trend_score": mkt_score,
        "category_context": category_ctx,
        "model_weights": params.get("weights", {}),
        "threshold_adjustments": params.get("threshold_adjustments", {}),
        "post_analysis": adaptation_summary,
    }

    rows: list[AnalysisRow] = []
    analyzed_symbols: set[str] = set()
    for sym in symbols:
        analyzed_symbols.add(sym)
        out = analyze_symbol(
            sym,
            regime,
            params,
            bool(mkt.get("market_open")),
            enable_after_hours,
            mkt_score,
            category_ctx,
        )
        if out:
            rows.append(out)

    if len(rows) < 10:
        for sym in STABLE_UNIVERSE:
            if sym in analyzed_symbols:
                continue
            out = analyze_symbol(
                sym,
                regime,
                params,
                bool(mkt.get("market_open")),
                enable_after_hours,
                mkt_score,
                category_ctx,
            )
            if out:
                rows.append(out)
            if len(rows) >= max(10, universe_count):
                break

    if not rows:
        raise RuntimeError("No analyzable symbols were returned. Try again later.")

    return save_run(base_dir, rows, market_ctx)


def analyze_single_symbol(
    symbol: str,
    regime: str,
    params: dict[str, Any],
    market_open: bool,
    enable_after_hours: bool,
    mkt_score: float,
    category_ctx: dict[str, float],
) -> tuple[AnalysisRow | None, dict[str, Any]]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5y", interval="1d", auto_adjust=False)
        if hist.empty:
            return None, {"status": "no_history"}
        price = latest_trade_price(ticker, hist, enable_after_hours, market_open)
        info = safe_ticker_info(ticker)
        news_items = safe_ticker_news(ticker)

        gate_ok, gate_reason = conservative_gate(symbol, info, hist, price)
        fund, fund_reason = fundamental_score(info)
        tech, tech_reason = technical_score(hist)
        news, news_reason = news_sentiment(symbol, news_items)
        earnings_days = next_earnings_days(ticker, info)
        outlook_score = earnings_outlook_score(info)
        price_score = price_setup_score(hist, price)
        earn_score = earnings_event_score(earnings_days, fund, tech, news, regime, outlook_score, price_score)
        cat_score = category_trend_score(info, category_ctx)
        base_total = compute_total_score(fund, tech, news, regime, params)
        total = base_total + 0.12 * mkt_score + 0.08 * cat_score + 0.10 * earn_score
        stock_action, option_action = decide_actions(regime, total, tech, params)

        mcap = safe_float(info.get("marketCap"), 0.0)
        beta = abs(safe_float(info.get("beta"), 1.0))
        v20 = vol20(hist)
        if TRADING_CONFIG.get("stock_only", True):
            option_action = "NO_OPTION"
        elif CONSERVATIVE_PROFILE and not conservative_option_allowed(total, stock_action, mcap, v20, beta, regime):
            option_action = "NO_OPTION"
        if gate_ok and stock_action == "HOLD" and regime != "bearish" and 2 <= earnings_days <= 30:
            near_earnings_ok = earnings_days <= 10 and earn_score >= 0.55
            far_earnings_ok = earnings_days > 10 and earn_score >= 0.72
            if (near_earnings_ok or far_earnings_ok) and outlook_score >= 0.45 and price_score >= 0.45:
                stock_action = "BUY_STOCK"
                option_action = "NO_OPTION"
        if not gate_ok:
            stock_action = "HOLD"
            option_action = "NO_OPTION"

        entry_price, target_price, stop_price, rr = trade_levels(hist, price, stock_action)
        option_symbol, option_expiry, option_strike = pick_option_candidate(ticker, option_action, price)
        execution_timing = "NOW" if market_open else "NEXT_MARKET_OPEN"
        predictions = forecast_price_horizons(hist, price, fund, tech, news, total, regime)
        reason = " | ".join(
            [
                gate_reason,
                fund_reason,
                tech_reason,
                news_reason,
                f"earnings_days={earnings_days}, earnings_event_score={earn_score:.2f}, earnings_outlook_score={outlook_score:.2f}, price_setup_score={price_score:.2f}",
            ]
        )
        if not gate_ok:
            reason = f"{reason} | conservative_filter=reject"

        row = AnalysisRow(
            symbol=symbol,
            price=round(price, 4),
            market_regime=regime,
            fundamental_score=round(fund, 4),
            technical_score=round(tech, 4),
            news_score=round(news, 4),
            upcoming_earnings_days=earnings_days,
            earnings_event_score=round(earn_score, 4),
            market_trend_score=round(mkt_score, 4),
            category_trend_score=round(cat_score, 4),
            total_score=round(total, 4),
            action_stock=stock_action,
            action_option=option_action,
            execution_timing=execution_timing,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            risk_reward=rr,
            option_symbol_hint=option_symbol,
            option_expiry=option_expiry,
            option_strike=round(option_strike, 4),
            prediction_1w_price=predictions["prediction_1w_price"],
            prediction_1w_return_pct=predictions["prediction_1w_return_pct"],
            prediction_1m_price=predictions["prediction_1m_price"],
            prediction_1m_return_pct=predictions["prediction_1m_return_pct"],
            prediction_3m_price=predictions["prediction_3m_price"],
            prediction_3m_return_pct=predictions["prediction_3m_return_pct"],
            prediction_6m_price=predictions["prediction_6m_price"],
            prediction_6m_return_pct=predictions["prediction_6m_return_pct"],
            prediction_1y_price=predictions["prediction_1y_price"],
            prediction_1y_return_pct=predictions["prediction_1y_return_pct"],
            prediction_5y_price=predictions["prediction_5y_price"],
            prediction_5y_return_pct=predictions["prediction_5y_return_pct"],
            reason=reason,
        )
        status = "ok" if gate_ok else "filtered_by_conservative_gate"
        return row, {"status": status}
    except Exception as exc:
        return None, {"status": "error", "error": str(exc)}


def save_symbol_summary(
    base_dir: Path,
    symbol: str,
    ts: str,
    row: AnalysisRow | None,
    market_ctx: dict[str, Any],
    summary_meta: dict[str, Any],
) -> Path:
    dirs = ensure_dirs(base_dir)
    run_dir = dirs["runs"] / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Symbol Summary: {symbol} ({format_run_ts_pt(ts)})",
        "",
        f"Status: `{summary_meta.get('status', 'unknown')}`",
        f"Market regime: **{market_ctx.get('regime', 'unknown')}**",
        f"Market session: **{market_ctx.get('market_session', 'unknown')}** "
        f"(`open={market_ctx.get('market_open', False)}`; PT {market_ctx.get('market_time_pt', '')})",
        "",
        "Analysis order: `fundamental -> technical -> news -> market_trend -> category_trend`",
        "",
    ]

    if row is not None:
        df = add_instruction_columns(pd.DataFrame([asdict(row)]))
        sim_state = load_portfolio_state(base_dir)
        sim_equity = safe_float(sim_state.get("paper_balance"), safe_float(sim_state.get("simulation_balance"), safe_float(sim_state.get("equity"), INITIAL_CAPITAL)))
        peak_equity = max(safe_float(sim_state.get("peak_paper_balance"), safe_float(sim_state.get("peak_simulation_balance"), sim_equity)), sim_equity)
        full_deploy = bool(TRADING_CONFIG.get("full_budget_deploy", False))
        deploy_target_pct = clamp(safe_float(TRADING_CONFIG.get("full_deploy_target_pct"), 1.0), 0.6, 1.0)
        budget_controls = build_budget_controls(sim_equity, INITIAL_CAPITAL, peak_equity, full_deploy, deploy_target_pct)
        df = add_sizing_columns(df, sim_equity, budget_controls)
        df = add_instruction_columns(df)
        single_budget = build_budget_plan(
            df,
            sim_equity,
            sim_equity,
            INITIAL_CAPITAL,
            budget_controls,
            safe_float(sim_state.get("cash"), sim_equity),
            max(0.0, sim_equity - safe_float(sim_state.get("cash"), sim_equity)),
        )
        rec = df.iloc[0]
        lines.extend(
            [
                "## Recommendation",
                f"- Symbol: `{rec['symbol']}`",
                f"- Trade type: `{rec['trade_type']}`",
                f"- Strategy bucket: `{rec.get('strategy_bucket', 'DAILY_TRADING')}`",
                f"- Stock action: `{rec['action_stock']}`",
                f"- Option action: `{rec['action_option']}`",
                f"- Stock quantity: `{int(safe_float(rec.get('stock_qty'), 0))}`",
                f"- Option contracts: `{int(safe_float(rec.get('option_contracts'), 0))}`",
                f"- Execution timing: `{rec['execution_timing']}`",
                f"- Stock instruction: `{rec['stock_instruction']}`",
                f"- Option instruction: `{rec['option_instruction']}`",
                f"- Entry/Target/Stop: `{rec['entry_price']:.2f} / {rec['target_price']:.2f} / {rec['stop_price']:.2f}`",
                f"- Risk/Reward: `{rec['risk_reward']:.2f}`",
                "",
                "## Price Predictions",
                "| Horizon | Predicted Price | Return |",
                "|---|---:|---:|",
                f"| 1 week | `${safe_float(rec.get('prediction_1w_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_1w_return_pct'), 0.0):.2f}%` |",
                f"| 1 month | `${safe_float(rec.get('prediction_1m_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_1m_return_pct'), 0.0):.2f}%` |",
                f"| 3 months | `${safe_float(rec.get('prediction_3m_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_3m_return_pct'), 0.0):.2f}%` |",
                f"| 6 months | `${safe_float(rec.get('prediction_6m_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_6m_return_pct'), 0.0):.2f}%` |",
                f"| 1 year | `${safe_float(rec.get('prediction_1y_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_1y_return_pct'), 0.0):.2f}%` |",
                f"| 5 years | `${safe_float(rec.get('prediction_5y_price'), 0.0):.2f}` | `{safe_float(rec.get('prediction_5y_return_pct'), 0.0):.2f}%` |",
                "",
                "## Paper Budget",
                f"- Initial benchmark capital (fixed): `${single_budget.get('initial_baseline', 0):,.2f}`",
                f"- Run start budget: `${single_budget.get('run_start_budget', 0):,.2f}`",
                f"- Current equity: `${single_budget.get('current_equity', 0):,.2f}`",
                f"- Change vs initial benchmark: `${single_budget.get('delta_vs_initial', 0):,.2f}`",
                f"- Change vs run start: `${single_budget.get('delta_vs_run_start', 0):,.2f}`",
                f"- Peak equity: `${single_budget.get('peak_equity', 0):,.2f}`",
                f"- Drawdown from peak: `{single_budget.get('drawdown_pct', 0):.2f}%`",
                f"- Budget regime: `{single_budget.get('budget_regime', 'normal')}`",
                f"- Target exposure cap: `{single_budget.get('target_exposure_pct', 0):.2f}%`",
                f"- Risk per trade: `{single_budget.get('risk_per_trade_pct', 0):.4f}%`",
                f"- Real trading capital (fixed): `${REAL_TRADING_CAPITAL:,.2f}`",
                f"- Cash on hand: `${single_budget.get('cash_on_hand', 0):,.2f}`",
                f"- Current exposure: `${single_budget.get('current_exposure', 0):,.2f}`",
                f"- Fresh deployable budget now: `${single_budget.get('deployable_budget', 0):,.2f}`",
                f"- This pick budget: `${safe_float(rec.get('recommended_budget_usd'), 0.0):,.2f}`",
                f"- Reserve after this pick (risk-capped): `${single_budget.get('reserve_after_plan', 0):,.2f}`",
                f"- Why this can be below the initial budget: {single_budget.get('budget_explanation', '')}",
                "",
                "## Scores",
                f"- Fundamental: `{rec['fundamental_score']:.4f}`",
                f"- Technical: `{rec['technical_score']:.4f}`",
                f"- News: `{rec['news_score']:.4f}`",
                f"- Upcoming earnings (days): `{int(safe_float(rec.get('upcoming_earnings_days'), -1))}`",
                f"- Earnings event score: `{safe_float(rec.get('earnings_event_score'), 0.0):.4f}`",
                f"- Market trend: `{rec['market_trend_score']:.4f}`",
                f"- Category trend: `{rec['category_trend_score']:.4f}`",
                f"- Total: `{rec['total_score']:.4f}`",
                "",
                "## Summary",
                f"- {rec['brief_reason']}",
                "",
                "## Raw Reason",
                f"- {rec['reason']}",
            ]
        )
        rec_df = pd.DataFrame([rec.to_dict()])
        rec_df.to_csv(run_dir / f"symbol_summary_{symbol}.csv", index=False)
        rec_df.to_csv(latest_dir / f"symbol_summary_{symbol}.csv", index=False)
        hist_path = dirs["history"] / f"symbol_summary_{symbol}_history.csv"
        append_header = not hist_path.exists()
        row_dict = {"timestamp_utc": ts, **rec.to_dict()}
        with hist_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row_dict.keys()))
            if append_header:
                writer.writeheader()
            writer.writerow(row_dict)
    else:
        lines.extend(
            [
                "## Recommendation",
                "- No summary could be generated for this symbol in the current run.",
                f"- Details: `{summary_meta}`",
            ]
        )

    md = "\n".join(lines)
    run_path = run_dir / f"symbol_summary_{symbol}.md"
    latest_path = latest_dir / f"symbol_summary_{symbol}.md"
    run_path.write_text(md, encoding="utf-8")
    latest_path.write_text(md, encoding="utf-8")
    return run_path


def run_symbol_summary(base_dir: Path, symbol: str, enable_after_hours: bool) -> Path:
    params = load_model_params()
    regime, ctx = market_regime()
    mkt_score = market_trend_score(regime, ctx)
    category_ctx = build_category_context()
    mkt = market_hours_context()
    market_ctx = {
        "regime": regime,
        **ctx,
        **mkt,
        "enable_after_hours": bool(enable_after_hours),
        "analysis_order": [
            "fundamental",
            "technical",
            "news",
            "market_trend",
            "category_trend",
        ],
        "market_trend_score": mkt_score,
        "category_context": category_ctx,
        "model_weights": params.get("weights", {}),
        "threshold_adjustments": params.get("threshold_adjustments", {}),
    }
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    row, meta = analyze_single_symbol(
        symbol=symbol,
        regime=regime,
        params=params,
        market_open=bool(mkt.get("market_open")),
        enable_after_hours=enable_after_hours,
        mkt_score=mkt_score,
        category_ctx=category_ctx,
    )
    return save_symbol_summary(base_dir, symbol, ts, row, market_ctx, meta)


def write_stale_snapshot(base_dir: Path, error_message: str) -> Path:
    dirs = ensure_dirs(base_dir)
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    run_dir = dirs["runs"] / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    mkt = market_hours_context()

    latest_csv, latest_md = find_last_available_snapshot(base_dir)
    if latest_csv and latest_csv.exists():
        shutil.copy2(latest_csv, run_dir / "top10.csv")
    else:
        pd.DataFrame(
            columns=[
                "symbol",
                "price",
                "market_regime",
                "fundamental_score",
                "technical_score",
                "news_score",
                "upcoming_earnings_days",
                "earnings_event_score",
                "market_trend_score",
                "category_trend_score",
                "total_score",
                "action_stock",
                "action_option",
                "execution_timing",
                "entry_price",
                "target_price",
                "stop_price",
                "risk_reward",
                "option_symbol_hint",
                "option_expiry",
                "option_strike",
                "reason",
            ]
        ).to_csv(run_dir / "top10.csv", index=False)

    try:
        stale_top10 = pd.read_csv(run_dir / "top10.csv")
    except Exception:
        stale_top10 = pd.DataFrame()
    stale_changed = False
    if not stale_top10.empty:
        if "upcoming_earnings_days" not in stale_top10.columns:
            stale_top10["upcoming_earnings_days"] = -1
            stale_changed = True
        if "earnings_event_score" not in stale_top10.columns:
            stale_top10["earnings_event_score"] = 0.0
            stale_changed = True
        if "market_trend_score" not in stale_top10.columns:
            stale_top10["market_trend_score"] = 0.0
            stale_changed = True
        if "category_trend_score" not in stale_top10.columns:
            stale_top10["category_trend_score"] = 0.0
            stale_changed = True
    required_cols = {"trade_type", "stock_instruction", "option_instruction", "brief_reason", "strategy_bucket"}
    if not stale_top10.empty and not required_cols.issubset(set(stale_top10.columns)):
        stale_top10 = add_instruction_columns(stale_top10)
        stale_changed = True
    if not stale_top10.empty and stale_changed:
        stale_top10.to_csv(run_dir / "top10.csv", index=False)
        latest_dir = base_dir / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        stale_top10.to_csv(latest_dir / "top10.csv", index=False)
    alert_summary = process_notifications(
        base_dir,
        ts,
        stale_top10.head(10) if not stale_top10.empty else stale_top10,
        {"market_session": mkt.get("market_session", "unknown")},
    )
    (run_dir / "alerts.json").write_text(json.dumps(alert_summary, indent=2), encoding="utf-8")
    portfolio_summary = update_portfolio(base_dir, stale_top10, ts, DEFAULT_ENABLE_AFTER_HOURS)
    (run_dir / "portfolio_summary.json").write_text(json.dumps(portfolio_summary, indent=2), encoding="utf-8")
    budget_controls = dict(portfolio_summary.get("budget_controls", {}))
    if not stale_top10.empty:
        stale_top10 = add_sizing_columns(stale_top10, sizing_equity_from_summary(portfolio_summary), budget_controls)
        stale_top10 = add_instruction_columns(stale_top10)
        stale_top10.to_csv(run_dir / "top10.csv", index=False)
        latest_dir = base_dir / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        stale_top10.to_csv(latest_dir / "top10.csv", index=False)
    budget_plan = build_budget_plan(
        stale_top10,
        safe_float(portfolio_summary.get("start_equity"), INITIAL_CAPITAL),
        safe_float(portfolio_summary.get("paper_balance"), safe_float(portfolio_summary.get("simulation_balance"), safe_float(portfolio_summary.get("end_equity"), INITIAL_CAPITAL))),
        safe_float(portfolio_summary.get("capital_balance"), safe_float(portfolio_summary.get("initial_capital"), INITIAL_CAPITAL)),
        budget_controls,
        safe_float(portfolio_summary.get("cash"), 0.0),
        safe_float(portfolio_summary.get("current_exposure"), 0.0),
    )

    latest_candidates = base_dir / "latest" / "candidates.csv"
    if latest_candidates.exists():
        shutil.copy2(latest_candidates, run_dir / "candidates.csv")
    else:
        pd.DataFrame().to_csv(run_dir / "candidates.csv", index=False)

    note = [
        f"# Top 10 Picks ({format_run_ts_pt(ts)})",
        "",
        "Market regime: **stale_snapshot**",
        f"Market session: **{mkt.get('market_session', 'unknown')}** "
        f"(`open={mkt.get('market_open', False)}`; PT {mkt.get('market_time_pt', '')})",
        f"Price reference: `last_regular_close` (close date PT: {previous_trading_day_pt()})",
        "",
        "## Portfolio",
        f"- Start equity this run: `${portfolio_summary.get('start_equity', 0):,.2f}`",
        f"- Benchmark capital (fixed): `${safe_float(portfolio_summary.get('capital_balance'), safe_float(portfolio_summary.get('initial_capital'), 0)):,.2f}`",
        f"- Real trading capital (fixed): `${portfolio_summary.get('real_trading_capital', 0):,.2f}`",
        f"- Paper balance: `${safe_float(portfolio_summary.get('paper_balance'), safe_float(portfolio_summary.get('simulation_balance'), safe_float(portfolio_summary.get('end_equity'), 0))):,.2f}`",
        f"- Run P/L: `${portfolio_summary.get('run_pnl', 0):,.2f}` "
        f"({portfolio_summary.get('run_return_pct', 0):.2f}%)",
        f"- Total return: `{portfolio_summary.get('total_return_pct', 0):.2f}%`",
        f"- Open positions: `{portfolio_summary.get('open_positions', 0)}`",
        "",
        "## Paper Budget",
        f"- Initial benchmark capital (fixed): `${budget_plan.get('initial_baseline', 0):,.2f}`",
        f"- Run start budget (from previous run): `${budget_plan.get('run_start_budget', 0):,.2f}`",
        f"- Current equity: `${budget_plan.get('current_equity', 0):,.2f}`",
        f"- Change vs initial benchmark: `${budget_plan.get('delta_vs_initial', 0):,.2f}`",
        f"- Change vs run start: `${budget_plan.get('delta_vs_run_start', 0):,.2f}`",
        f"- Cash on hand: `${budget_plan.get('cash_on_hand', 0):,.2f}`",
        f"- Current exposure: `${budget_plan.get('current_exposure', 0):,.2f}`",
        f"- Peak equity: `${budget_plan.get('peak_equity', 0):,.2f}`",
        f"- Drawdown from peak: `{budget_plan.get('drawdown_pct', 0):.2f}%`",
        f"- Budget regime: `{budget_plan.get('budget_regime', 'normal')}`",
        f"- Target exposure cap: `{budget_plan.get('target_exposure_pct', 0):.2f}%`",
        f"- Risk per trade: `{budget_plan.get('risk_per_trade_pct', 0):.4f}%`",
        f"- Remaining exposure headroom: `${budget_plan.get('exposure_headroom', 0):,.2f}`",
        f"- Fresh deployable budget now: `${budget_plan.get('deployable_budget', 0):,.2f}`",
        f"- Recommended deploy (raw): `${budget_plan.get('uncapped_recommended', 0):,.2f}`",
        f"- Recommended deploy (risk-capped): `${budget_plan.get('capped_recommended', 0):,.2f}`",
        f"- Reserve cash after plan: `${budget_plan.get('reserve_after_plan', 0):,.2f}`",
        f"- Why this can be below the initial budget: {budget_plan.get('budget_explanation', '')}",
        "",
        "## Alerts",
        f"- Channel: `{alert_summary.get('channel', '')}`",
        f"- Notification sent: `{alert_summary.get('sent', False)}`",
        f"- Alert reason: `{alert_summary.get('reason', '')}`",
        f"- Alert candidates: `{len(alert_summary.get('items', []))}`",
        "",
        "Latest run used previous recommendations because live data fetch failed.",
        "",
        f"Error: `{error_message}`",
    ]
    if not stale_top10.empty:
        note.extend(["", "## Clear Action Plan"])
        for idx, row in stale_top10.head(10).reset_index(drop=True).iterrows():
            trade_type = row.get("trade_type", "UNKNOWN")
            strategy_bucket = row.get("strategy_bucket", "DAILY_TRADING")
            stock_instruction = row.get("stock_instruction", "")
            option_instruction = row.get("option_instruction", "")
            brief_reason = row.get("brief_reason", "")
            note.append(
                f"{idx+1}. {row.get('symbol','')} ({trade_type}, {strategy_bucket}) | {stock_instruction} | {option_instruction} | {brief_reason}"
            )
        if budget_plan.get("rows"):
            note.extend(["", "## Budget By Pick"])
            for idx, b in enumerate(budget_plan["rows"], start=1):
                note.append(
                    f"{idx}. {b['symbol']} | {b['action_stock']} | shares={b['stock_qty']} | contracts={b['option_contracts']} | budget=${b['budget_usd']:.2f}"
                )
    actions = budget_plan.get("improvement_actions", [])
    if actions:
        note.extend(["", "## Improvement Actions"])
        for idx, action in enumerate(actions, start=1):
            note.append(f"{idx}. {action}")
    (run_dir / "top10.md").write_text("\n".join(note), encoding="utf-8")
    if latest_md and latest_md.exists():
        shutil.copy2(latest_md, base_dir / "latest" / "top10_prev.md")
    (base_dir / "latest" / "top10.md").write_text("\n".join(note), encoding="utf-8")
    (base_dir / "latest" / "alerts.json").write_text(json.dumps(alert_summary, indent=2), encoding="utf-8")

    status = {
        "timestamp_utc": ts,
        "status": "stale_snapshot",
        "error": error_message,
        "market_open": mkt.get("market_open"),
        "market_session": mkt.get("market_session"),
        "next_open_et": mkt.get("next_open_et"),
        "next_close_et": mkt.get("next_close_et"),
        "model_params_file": str(MODEL_STATE_PATH),
        "model_meta": load_model_params().get("meta", {}),
    }
    market_context = {
        "regime": "stale_snapshot",
        "market_open": mkt.get("market_open"),
        "market_session": mkt.get("market_session"),
        "price_reference_mode": "last_regular_close",
        "price_reference_close_date_pt": previous_trading_day_pt(),
        "weekend_reference": "previous_trading_day_close" if str(mkt.get("market_session", "")) == "weekend" else "",
        "next_open_et": mkt.get("next_open_et"),
        "next_close_et": mkt.get("next_close_et"),
        "error": error_message,
        "post_analysis": json.loads((base_dir / "latest" / "post_analysis.json").read_text(encoding="utf-8"))
        if (base_dir / "latest" / "post_analysis.json").exists()
        else {},
    }
    with (run_dir / "market_context.json").open("w", encoding="utf-8") as f:
        json.dump(market_context, f, indent=2)
    with (run_dir / "status.json").open("w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    generate_daily_summary(base_dir, ts)
    refresh_simple_view(base_dir, ts)
    return run_dir


def run_daily_evaluation_only(base_dir: Path) -> Path:
    ts = now_utc().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / "runs" / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    latest_dir = base_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    generate_daily_summary(base_dir, ts, force=True)
    report_path = build_daily_evaluation_report(base_dir, ts)
    mkt = market_hours_context()
    status = {
        "timestamp_utc": ts,
        "status": "daily_evaluation_only",
        "market_open": mkt.get("market_open"),
        "market_session": mkt.get("market_session"),
        "daily_summary": str(latest_dir / "daily_summary.md"),
        "daily_evaluation_report": str(report_path),
    }
    market_context = {
        "regime": "daily_evaluation_only",
        "market_open": mkt.get("market_open"),
        "market_session": mkt.get("market_session"),
        "price_reference_mode": "last_regular_close",
        "price_reference_close_date_pt": previous_trading_day_pt(),
        "next_open_et": mkt.get("next_open_et"),
        "next_close_et": mkt.get("next_close_et"),
    }
    (run_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (run_dir / "market_context.json").write_text(json.dumps(market_context, indent=2), encoding="utf-8")
    refresh_simple_view(base_dir, ts)
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Yahoo-based stock/options analysis")
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR), help="Output folder for run snapshots")
    parser.add_argument("--universe-count", type=int, default=50, help="Number of top market movers (gainers+losers) to analyze")
    parser.add_argument("--symbol", default="", help="Single stock symbol summary mode (e.g., AAPL).")
    parser.add_argument(
        "--config",
        default=str(AGENT_CONFIG_PATH),
        help="Unified JSON config path (news/notifications/trading).",
    )
    parser.add_argument(
        "--enable-after-hours",
        action="store_true",
        default=DEFAULT_ENABLE_AFTER_HOURS,
        help="Enable after-hours/extended-hours pricing for analysis and post-analysis learning.",
    )
    parser.add_argument(
        "--daily-evaluation-only",
        action="store_true",
        help="Generate the end-of-day improvement summary without producing a new recommendation scan.",
    )
    parser.add_argument(
        "--set-real-balance",
        type=float,
        default=None,
        help="Deprecated alias for --set-paper-budget.",
    )
    parser.add_argument(
        "--set-paper-budget",
        type=float,
        default=None,
        help="One-shot: reset persistent paper budget state and exit.",
    )
    parser.add_argument(
        "--set-sim-budget",
        type=float,
        default=None,
        help="Deprecated alias for --set-paper-budget.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global NEWS_CONFIG, TRADING_CONFIG, INITIAL_CAPITAL, REAL_TRADING_CAPITAL
    global NOTIFICATIONS_CONFIG
    unified = load_agent_config(Path(args.config))
    NEWS_CONFIG = dict(unified.get("news", DEFAULT_NEWS_CONFIG))
    NOTIFICATIONS_CONFIG = dict(unified.get("notifications", DEFAULT_NOTIFICATIONS_CONFIG))
    TRADING_CONFIG = dict(unified.get("trading", DEFAULT_TRADING_CONFIG))
    # Backward compatibility for older config keys.
    sim_cap = safe_float(
        TRADING_CONFIG.get(
            "paper_initial_capital",
            TRADING_CONFIG.get("simulation_initial_capital", TRADING_CONFIG.get("initial_capital", 10000.0)),
        ),
        10000.0,
    )
    real_cap = safe_float(TRADING_CONFIG.get("real_trading_capital", 10000.0), 10000.0)
    if sim_cap > 0:
        INITIAL_CAPITAL = sim_cap
    if real_cap > 0:
        REAL_TRADING_CAPITAL = real_cap
    # Ensure adaptive model state exists on disk for traceability.
    save_model_params(load_model_params())
    base_dir = Path(args.base_dir)
    paper_budget_override = (
        args.set_paper_budget
        if args.set_paper_budget is not None
        else args.set_sim_budget
        if args.set_sim_budget is not None
        else args.set_real_balance
    )
    if paper_budget_override is not None:
        state = set_paper_budget(base_dir, float(paper_budget_override))
        print(
            "Paper budget updated. "
            f"capital_balance={safe_float(state.get('capital_balance'), safe_float(state.get('initial_capital'), 0)):.2f} "
            f"cash={safe_float(state.get('cash'), 0):.2f} "
            f"paper_balance={safe_float(state.get('paper_balance'), safe_float(state.get('simulation_balance'), safe_float(state.get('equity'), 0))):.2f} "
            f"real_trading_capital={REAL_TRADING_CAPITAL:.2f} "
            f"state_file={portfolio_state_path(base_dir)}"
        )
        return 0
    if bool(args.daily_evaluation_only):
        run_dir = run_daily_evaluation_only(base_dir)
        print(f"Daily evaluation completed. Results: {run_dir}")
        return 0
    symbol = str(args.symbol or "").strip().upper()
    try:
        if symbol:
            summary_path = run_symbol_summary(base_dir, symbol, bool(args.enable_after_hours))
            print(f"Symbol summary completed. Result: {summary_path}")
        else:
            run_dir = run_once(base_dir, args.universe_count, bool(args.enable_after_hours))
            print(f"Run completed. Results: {run_dir}")
    except Exception as exc:
        if symbol:
            print(f"Symbol summary failed: {exc}")
            return 1
        run_dir = write_stale_snapshot(base_dir, str(exc))
        print(f"Run completed with stale snapshot. Results: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
