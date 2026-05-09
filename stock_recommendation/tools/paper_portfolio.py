from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from stock_recommendation.config import (
    DB_PATH,
    INITIAL_PAPER_BALANCE,
    MAX_TRADES_PER_DAY,
    MONTHLY_OPENAI_BUDGET_USD,
    OPENAI_INPUT_PRICE_PER_MILLION,
    OPENAI_OUTPUT_PRICE_PER_MILLION,
    RISK_PER_TRADE,
)


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value REAL NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, symbol TEXT NOT NULL, action TEXT NOT NULL, qty INTEGER NOT NULL, price REAL NOT NULL, notional REAL NOT NULL, reason TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, qty INTEGER NOT NULL, avg_price REAL NOT NULL)"
    )
    if conn.execute("SELECT COUNT(*) FROM state").fetchone()[0] == 0:
        conn.execute("INSERT INTO state(key, value) VALUES('cash', ?)", (INITIAL_PAPER_BALANCE,))
        conn.execute("INSERT INTO state(key, value) VALUES('equity', ?)", (INITIAL_PAPER_BALANCE,))
    conn.commit()
    return conn


def get_state(db_path: Path = DB_PATH) -> dict:
    conn = _connect(db_path)
    rows = conn.execute("SELECT key, value FROM state").fetchall()
    conn.close()
    return {k: v for k, v in rows}


def get_state_value(key: str, default: float = 0.0, db_path: Path = DB_PATH) -> float:
    state = get_state(db_path)
    return float(state.get(key, default))


def set_state_value(key: str, value: float, db_path: Path = DB_PATH) -> None:
    conn = _connect(db_path)
    conn.execute(
        "INSERT INTO state(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def ai_budget_remaining(db_path: Path = DB_PATH) -> float:
    month = datetime.now(timezone.utc).strftime("%Y%m")
    usage_key = f"ai_cost_{month}"
    spent = get_state_value(usage_key, 0.0, db_path)
    return max(0.0, MONTHLY_OPENAI_BUDGET_USD - spent)


def record_ai_usage(input_tokens: int, output_tokens: int, db_path: Path = DB_PATH) -> dict:
    month = datetime.now(timezone.utc).strftime("%Y%m")
    usage_key = f"ai_cost_{month}"
    spent = get_state_value(usage_key, 0.0, db_path)
    cost = (max(0, input_tokens) / 1_000_000.0 * OPENAI_INPUT_PRICE_PER_MILLION) + (
        max(0, output_tokens) / 1_000_000.0 * OPENAI_OUTPUT_PRICE_PER_MILLION
    )
    set_state_value(usage_key, spent + cost, db_path)
    return {"month": month, "input_tokens": input_tokens, "output_tokens": output_tokens, "estimated_cost_usd": round(spent + cost, 6), "monthly_budget_usd": MONTHLY_OPENAI_BUDGET_USD}


def trades_today(conn: sqlite3.Connection) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return int(conn.execute("SELECT COUNT(*) FROM trades WHERE substr(ts, 1, 10)=?", (today,)).fetchone()[0])


def positions(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute("SELECT symbol, qty, avg_price FROM positions").fetchall()
    return {symbol: {"qty": int(qty), "avg_price": float(avg_price)} for symbol, qty, avg_price in rows}


def update_paper_portfolio(recommendations: list[dict], db_path: Path = DB_PATH) -> dict:
    conn = _connect(db_path)
    state = get_state(db_path)
    cash = float(state.get("cash", INITIAL_PAPER_BALANCE))
    executed = []
    held = positions(conn)
    remaining_slots = max(0, MAX_TRADES_PER_DAY - trades_today(conn))
    for rec in recommendations:
        if remaining_slots <= 0:
            break
        price = float(rec.get("price") or 0)
        if price <= 0:
            continue
        symbol = str(rec["symbol"])
        action = str(rec.get("action", "hold"))
        if action == "sell" and symbol in held and held[symbol]["qty"] > 0:
            qty = held[symbol]["qty"]
            notional = qty * price
            cash += notional
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "INSERT INTO trades(ts, symbol, action, qty, price, notional, reason) VALUES(?,?,?,?,?,?,?)",
                (ts, symbol, "SELL", qty, price, notional, rec.get("reason", "")),
            )
            conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
            executed.append({"symbol": symbol, "action": "SELL", "qty": qty, "price": price, "notional": round(notional, 2)})
            remaining_slots -= 1
            continue
        if action != "buy":
            continue
        risk_budget = cash * RISK_PER_TRADE
        qty = int(risk_budget // max(price * 0.03, 0.01))
        qty = max(0, min(qty, int(cash // price)))
        if qty <= 0:
            continue
        notional = qty * price
        cash -= notional
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO trades(ts, symbol, action, qty, price, notional, reason) VALUES(?,?,?,?,?,?,?)",
            (ts, symbol, "BUY", qty, price, notional, rec.get("reason", "")),
        )
        old = held.get(symbol, {"qty": 0, "avg_price": 0.0})
        new_qty = old["qty"] + qty
        new_avg = ((old["qty"] * old["avg_price"]) + notional) / max(1, new_qty)
        conn.execute(
            "INSERT INTO positions(symbol, qty, avg_price) VALUES(?,?,?) ON CONFLICT(symbol) DO UPDATE SET qty=excluded.qty, avg_price=excluded.avg_price",
            (symbol, new_qty, new_avg),
        )
        held[symbol] = {"qty": new_qty, "avg_price": new_avg}
        executed.append({"symbol": symbol, "action": "BUY", "qty": qty, "price": price, "notional": round(notional, 2)})
        remaining_slots -= 1
    marked_positions = []
    latest_price = {str(r.get("symbol")): float(r.get("price") or 0) for r in recommendations}
    equity = cash
    for symbol, pos in positions(conn).items():
        mark = latest_price.get(symbol, 0.0) or pos["avg_price"]
        value = pos["qty"] * mark
        equity += value
        marked_positions.append({"symbol": symbol, "qty": pos["qty"], "avg_price": round(pos["avg_price"], 4), "mark": round(mark, 4), "value": round(value, 2)})
    conn.execute("UPDATE state SET value=? WHERE key='cash'", (cash,))
    conn.execute("UPDATE state SET value=? WHERE key='equity'", (equity,))
    conn.commit()
    conn.close()
    return {"cash": round(cash, 2), "equity": round(equity, 2), "positions": marked_positions, "executed": executed, "max_trades_per_day": MAX_TRADES_PER_DAY}


def save_trade_log(payload: dict) -> dict:
    return payload
