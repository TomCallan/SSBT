"""SSBT CLI entry points for humans and AI agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ssbt.agent import get_agent_template, get_experiment_schema, validate_strategy_script
from ssbt.experiments.loader import load_experiment
from ssbt.experiments.runner import RunnerError, run_experiment


def main() -> int:
    """Main CLI entry point for ssbt commands."""
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]

    if command in ("-h", "--help", "help"):
        print_usage()
        return 0

    if command == "run":
        return handle_run(sys.argv[2:])

    if command == "schema":
        return handle_schema(sys.argv[2:])

    if command == "validate":
        return handle_validate(sys.argv[2:])

    if command == "template":
        return handle_template(sys.argv[2:])

    if command == "quick":
        return handle_quick(sys.argv[2:])

    print(f"Unknown command: {command}", file=sys.stderr)
    print_usage()
    return 1


def print_usage() -> None:
    print("SSBT CLI Tooling & Ergonomic Commands:", file=sys.stderr)
    print("  ssbt run <config.yaml> [--json]        Run exploration experiment", file=sys.stderr)
    print("  ssbt schema [--out schema.json]        Emit JSON Schema for experiment specs", file=sys.stderr)
    print("  ssbt validate <script.py|config.yaml>  Validate strategy script or spec", file=sys.stderr)
    print("  ssbt template [sma_cross|yaml]         Generate starter template", file=sys.stderr)
    print("  ssbt quick <script.py> <data.parquet>  Run 1-line strategy backtest", file=sys.stderr)


def handle_run(args: list[str]) -> int:
    if not args:
        print("Usage: ssbt run <config.yaml> [--json]", file=sys.stderr)
        return 1

    config_path = args[0]
    json_mode = "--json" in args

    if not Path(config_path).exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        result = run_experiment(config_path)
        if json_mode:
            output = {
                "status": "success",
                "experiment_name": result["spec"].name,
                "events_count": result["events"].height,
                "outcomes_count": result["outcomes"].height,
                "output_dir": str(result["output_dir"]),
            }
            print(json.dumps(output, indent=2))
        else:
            print(f"Experiment completed. Events: {result['events'].height}, Outcomes: {result['outcomes'].height}")
            print(f"Artifacts written to: {result['output_dir']}")
        return 0
    except RunnerError as e:
        if json_mode:
            err_dict = {
                "status": "error",
                "message": str(e),
                "errors": [{"path": err.path, "message": err.message, "suggestion": err.suggestion} for err in (e.errors or [])],
            }
            print(json.dumps(err_dict, indent=2))
        else:
            print(f"Experiment failed: {e}", file=sys.stderr)
            if e.errors:
                for err in e.errors:
                    print(f"  - {err.path}: {err.message}", file=sys.stderr)
                    if err.suggestion:
                        print(f"    Suggestion: {err.suggestion}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def handle_schema(args: list[str]) -> int:
    schema = get_experiment_schema()
    output_json = json.dumps(schema, indent=2)

    out_file = None
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_file = args[idx + 1]

    if out_file:
        Path(out_file).write_text(output_json, encoding="utf-8")
        print(f"Schema written to: {out_file}")
    else:
        print(output_json)
    return 0


def handle_validate(args: list[str]) -> int:
    if not args:
        print("Usage: ssbt validate <script.py|config.yaml>", file=sys.stderr)
        return 1

    target = Path(args[0])
    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    if target.suffix in (".yaml", ".yml"):
        try:
            load_experiment(str(target))
            print(f"✓ Experiment spec '{target}' is valid!")
            return 0
        except Exception as e:
            print(f"✗ Invalid experiment spec: {e}", file=sys.stderr)
            return 1

    res = validate_strategy_script(target)
    if res["valid"]:
        print(f"✓ Strategy script '{target}' is syntactically valid!")
        if res["strategy_class"]:
            print(f"  Detected strategy class: {res['strategy_class']}")
        for warn in res["warnings"]:
            print(f"  [Warning] {warn}")
        return 0
    else:
        print(f"✗ Strategy script '{target}' failed validation:")
        for err in res["errors"]:
            print(f"  - {err}")
        return 1


def handle_template(args: list[str]) -> int:
    tmpl_type = args[0] if args else "sma_cross"
    content = get_agent_template(tmpl_type)
    print(content)
    return 0


def handle_quick(args: list[str]) -> int:
    if len(args) < 2:
        print("Usage: ssbt quick <strategy.py> <data.parquet|csv> [--symbol BTC-USD]", file=sys.stderr)
        return 1

    strat_file = args[0]
    data_file = args[1]
    symbol = "BTC-USD"
    if "--symbol" in args:
        idx = args.index("--symbol")
        if idx + 1 < len(args):
            symbol = args[idx + 1]

    from ssbt.quick import quick_backtest, generate_synthetic_bars

    try:
        # Load strategy module
        import importlib.util
        spec = importlib.util.spec_from_file_location("user_strategy", strat_file)
        if spec is None or spec.loader is None:
            print(f"Could not load python file: {strat_file}", file=sys.stderr)
            return 1
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Strategy subclass or function
        from ssbt.strategy.base import Strategy
        strat_obj = None
        for item in dir(module):
            val = getattr(module, item)
            if isinstance(val, type) and issubclass(val, Strategy) and val is not Strategy:
                strat_obj = val()
                break

        if strat_obj is None:
            print("No Strategy subclass found in file.", file=sys.stderr)
            return 1

        res = quick_backtest(strat_obj, data=data_file, symbol=symbol, verbose=True)
        print(f"\n{res}")
        return 0
    except Exception as e:
        print(f"Quick backtest failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())