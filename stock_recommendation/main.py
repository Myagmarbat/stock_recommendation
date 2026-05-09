from __future__ import annotations

import argparse
import json
from pathlib import Path

from stock_recommendation.agents.stock_recommendation import run_recommendation_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="stock_recommendation controlled stock/ETF recommendation workflow")
    parser.add_argument("--no-paper-update", action="store_true", help="Run analysis without updating the SQLite paper ledger.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

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

