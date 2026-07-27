"""SSBT CLI entry points."""

from __future__ import annotations

import sys
from pathlib import Path

from ssbt.experiments.runner import run_experiment, RunnerError


def main() -> int:
    """Main CLI entry point for ssbt-run."""
    if len(sys.argv) < 2:
        print("Usage: ssbt-run <config.yaml>", file=sys.stderr)
        print("       ssbt <command> [args...]", file=sys.stderr)
        return 1

    command = sys.argv[1]

    if command == "run":
        if len(sys.argv) < 3:
            print("Usage: ssbt run <config.yaml>", file=sys.stderr)
            return 1
        config_path = sys.argv[2]
        if not Path(config_path).exists():
            print(f"Config file not found: {config_path}", file=sys.stderr)
            return 1
        try:
            result = run_experiment(config_path)
            print(f"Experiment completed. Events: {result['events'].height}, Outcomes: {result['outcomes'].height}")
            print(f"Artifacts written to: {result['output_dir']}")
            return 0
        except RunnerError as e:
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

    print(f"Unknown command: {command}", file=sys.stderr)
    print("Available commands: run", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())