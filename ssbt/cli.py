"""SSBT CLI entry points for human quants and AI agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ssbt.agent import get_agent_template, validate_strategy_script
from ssbt.quick import quick_backtest
from ssbt.strategy.base import load_strategy_from_source


def main() -> int:
    """Main CLI entry point for ssbt commands."""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]

    if command in ("-h", "--help", "help"):
        print_usage()
        return 0

    if command in ("run", "quick"):
        return handle_run_or_quick(sys.argv[2:])

    if command == "validate":
        return handle_validate(sys.argv[2:])

    if command == "template":
        return handle_template(sys.argv[2:])

    print(f"Unknown command: {command}", file=sys.stderr)
    print_usage()
    return 1


def print_usage() -> None:
    print("SSBT Strategy Backtesting Engine CLI:", file=sys.stderr)
    print("  ssbt run <strategy.py> <data.parquet|csv> [--symbol BTC-USD] [--json]  Run strategy backtest", file=sys.stderr)
    print("  ssbt quick <strategy.py> <data.parquet|csv> [--symbol BTC-USD]         Run 1-line strategy backtest", file=sys.stderr)
    print("  ssbt validate <strategy.py>                                            Validate strategy script AST", file=sys.stderr)
    print("  ssbt template [sma_cross|functional]                                   Generate starter strategy template", file=sys.stderr)


def handle_run_or_quick(args: list[str]) -> int:
    if len(args) < 2:
        print("Usage: ssbt run <strategy.py> <data.parquet|csv> [--symbol BTC-USD] [--json]", file=sys.stderr)
        return 1

    strat_file = args[0]
    data_file = args[1]
    json_mode = "--json" in args

    symbol = "BTC-USD"
    if "--symbol" in args:
        idx = args.index("--symbol")
        if idx + 1 < len(args):
            symbol = args[idx + 1]

    if not Path(strat_file).exists():
        print(f"Strategy file not found: {strat_file}", file=sys.stderr)
        return 1

    try:
        strat = load_strategy_from_source(strat_file)
        res = quick_backtest(strat, data=data_file, symbol=symbol, verbose=not json_mode)

        if json_mode:
            print(res.to_json(indent=2))
        else:
            print(f"\n{res}")
        return 0
    except Exception as e:
        if json_mode:
            print(json.dumps({"status": "error", "message": str(e)}, indent=2))
        else:
            print(f"Backtest execution failed: {e}", file=sys.stderr)
        return 1


def handle_validate(args: list[str]) -> int:
    if not args:
        print("Usage: ssbt validate <strategy.py>", file=sys.stderr)
        return 1

    target = Path(args[0])
    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    res = validate_strategy_script(target)
    if res["valid"]:
        print(f"[OK] Strategy script '{target}' is syntactically valid.")
        if res["strategy_class"]:
            print(f"  Detected strategy class: {res['strategy_class']}")
        for warn in res["warnings"]:
            print(f"  [Warning] {warn}")
        return 0
    else:
        print(f"[ERROR] Strategy script '{target}' failed validation:")
        for err in res["errors"]:
            print(f"  - {err}")
        return 1


def handle_template(args: list[str]) -> int:
    tmpl_type = args[0] if args else "sma_cross"
    content = get_agent_template(tmpl_type)
    print(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())