from __future__ import annotations

import json
from dataclasses import dataclass

from stock_recommendation.config import AGENT_NAME, MONTHLY_OPENAI_BUDGET_USD, ai_enabled, openai_model
from stock_recommendation.tools.backtest import backtest_strategy
from stock_recommendation.tools.fundamentals import calculate_fundamentals
from stock_recommendation.tools.market_data import get_market_data, get_stable_universe
from stock_recommendation.tools.news import get_news_summary
from stock_recommendation.tools.paper_portfolio import ai_budget_remaining, record_ai_usage, update_paper_portfolio
from stock_recommendation.tools.technicals import calculate_technical_indicators


@dataclass
class Recommendation:
    symbol: str
    action: str
    score: float
    price: float
    reason: str
    risks: list[str]
    metrics: dict


def recommend_trade(symbol: str) -> Recommendation:
    data = get_market_data(symbol)
    technical = calculate_technical_indicators(data.history)
    fundamental = calculate_fundamentals(data.info)
    news = get_news_summary(data.news)
    backtest = backtest_strategy(data.history)

    stability = 0.25 if symbol in {"SPY", "QQQ", "DIA", "IWM", "VTI"} else 0.10
    liquidity = min(1.0, float(technical.get("avg_volume", 0.0)) / 10_000_000.0)
    score = (
        stability
        + 0.30 * float(technical.get("score", 0.0))
        + 0.20 * liquidity
        + 0.20 * float(fundamental.get("score", 0.0))
        + 0.10 * float(news.get("score", 0.0))
        + 0.20 * float(backtest.get("confidence", 0.0))
    )
    if score >= 0.55:
        action = "buy"
    elif score <= 0.20:
        action = "sell"
    else:
        action = "hold"
    risks = []
    if float(technical.get("rsi14", 50)) > 70:
        risks.append("overbought_rsi")
    if float(backtest.get("max_drawdown_pct", 0)) < -12:
        risks.append("historical_drawdown")
    if float(news.get("score", 0)) < 0:
        risks.append("negative_news_tone")
    reason = (
        f"score={score:.2f}; technical={technical.get('score')}; fundamental={fundamental.get('score')}; "
        f"news={news.get('score')}; backtest_confidence={backtest.get('confidence')}"
    )
    return Recommendation(
        symbol=symbol,
        action=action,
        score=round(score, 4),
        price=float(technical.get("price", 0.0)),
        reason=reason,
        risks=risks,
        metrics={"technical": technical, "fundamental": fundamental, "news": news, "backtest": backtest},
    )


def ask_openai_for_analysis(recommendations: list[Recommendation]) -> dict:
    payload = [
        {
            "symbol": r.symbol,
            "action": r.action,
            "score": r.score,
            "price": r.price,
            "reason": r.reason,
            "risks": r.risks,
        }
        for r in recommendations
    ]
    if not ai_enabled():
        return {"enabled": False, "summary": "OpenAI summary disabled. Set STOCK_RECOMMENDATION_AI=1 and OPENAI_API_KEY to enable.", "budget_usd": MONTHLY_OPENAI_BUDGET_USD}
    if ai_budget_remaining() <= 0:
        return {"enabled": False, "summary": "OpenAI monthly budget reached; skipped AI summary.", "budget_usd": MONTHLY_OPENAI_BUDGET_USD}

    prompt = (
        "You are stock_recommendation. Explain these deterministic Python stock/ETF recommendations, "
        "identify risks, and suggest strategy improvements. Do not change actions. Return concise JSON."
    )
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatOpenAI(model=openai_model(), temperature=0, max_tokens=700)
        msg = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=json.dumps(payload))])
        usage = getattr(msg, "usage_metadata", {}) or {}
        ai_usage = record_ai_usage(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0)))
        text = str(msg.content)
        try:
            parsed = json.loads(text)
            return {"enabled": True, "model": openai_model(), "usage": ai_usage, **parsed}
        except Exception:
            return {"enabled": True, "model": openai_model(), "usage": ai_usage, "summary": text[:1500]}
    except Exception as exc:
        return {"enabled": False, "summary": f"LangChain/OpenAI unavailable: {exc}", "budget_usd": MONTHLY_OPENAI_BUDGET_USD}


def run_recommendation_workflow(update_portfolio: bool = True) -> dict:
    symbols = get_stable_universe()
    recommendations = [recommend_trade(symbol) for symbol in symbols]
    recommendations.sort(key=lambda r: r.score, reverse=True)
    selected = recommendations[:3]
    ai_review = ask_openai_for_analysis(selected)
    paper_result = update_paper_portfolio([r.__dict__ for r in selected]) if update_portfolio else {"executed": []}
    return {
        "agent": AGENT_NAME,
        "workflow": [
            "collect data",
            "calculate signals",
            "run backtest",
            "ask OpenAI for analysis/summary only",
            "recommend trade",
            "paper-trade balance update",
            "log result",
        ],
        "recommendations": [r.__dict__ for r in selected],
        "ai_review": ai_review,
        "paper_portfolio": paper_result,
    }


def build_langchain_agent():
    try:
        from langchain.agents import tool
        from langchain_openai import ChatOpenAI

        @tool
        def analyze_ticker(symbol: str) -> str:
            """Analyze one ticker and return deterministic recommendation JSON."""
            return json.dumps(recommend_trade(symbol).__dict__)

        @tool
        def run_workflow() -> str:
            """Run the controlled recommendation workflow."""
            return json.dumps(run_recommendation_workflow(update_portfolio=False))

        try:
            from langchain.agents import create_agent

            return create_agent(
                model=ChatOpenAI(model=openai_model(), temperature=0),
                tools=[analyze_ticker, run_workflow],
                system_prompt="You are stock_recommendation. Use tools for calculations. Explain only; do not invent trades.",
            )
        except Exception:
            return {"model": ChatOpenAI(model=openai_model(), temperature=0), "tools": [analyze_ticker, run_workflow]}
    except Exception as exc:
        return {"error": f"LangChain unavailable: {exc}"}
