from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="stock_recommendation controlled stock/ETF recommendation workflow")
    parser.add_argument("prompt", nargs="?", default="", help="Optional instruction for the stock_recommendation LLM agent.")
    parser.add_argument("--no-paper-update", action="store_true", help="Run analysis without updating the SQLite paper ledger.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    parser.add_argument("--ask-agent", action="store_true", help="Ask the stock_recommendation LLM agent instead of running the deterministic workflow directly.")
    args = parser.parse_args()

    if args.ask_agent or args.prompt:
        from stock_recommendation.config import MONTHLY_OPENAI_BUDGET_USD, ai_enabled

        if not ai_enabled():
            print(
                "OpenAI agent is enabled by default, but OPENAI_API_KEY is not set or STOCK_RECOMMENDATION_AI disables it. "
                f"Default monthly budget cap is ${MONTHLY_OPENAI_BUDGET_USD:.2f}."
            )
            return 0

        from stock_recommendation.agents.stock_recommendation import run_stock_recommendation_agent

        prompt = args.prompt or "Run the recommendation workflow and summarize the deterministic output."
        print(run_stock_recommendation_agent(prompt))
        return 0

    from stock_recommendation.agents.stock_recommendation import run_recommendation_workflow

    result = run_recommendation_workflow(update_portfolio=not args.no_paper_update)
    text = json.dumps(result, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
