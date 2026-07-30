"""SSBT AI Agent Tooling, Schemas & Programmatic Validation Engine."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def get_experiment_schema() -> dict[str, Any]:
    """Generate JSON Schema definition for SSBT Experiment Specs and YAML configs."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "SSBTExperimentSpec",
        "type": "object",
        "required": ["version", "name", "data", "events", "outcomes"],
        "properties": {
            "version": {
                "type": "string",
                "enum": ["1.0", "1"],
                "description": "Experiment specification format version.",
            },
            "name": {
                "type": "string",
                "description": "Descriptive unique name for the exploration experiment.",
            },
            "description": {
                "type": "string",
                "description": "Optional detailed context or hypothesis statement.",
            },
            "data": {
                "type": "object",
                "required": ["symbols"],
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of ticker symbols.",
                    },
                    "path": {"type": "string", "description": "Parquet data directory or file."},
                    "resample": {"type": "string", "description": "Bar aggregation time (e.g. 5m, 1h)."},
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "params": {"type": "object"},
                    },
                },
            },
            "outcomes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "params": {"type": "object"},
                    },
                },
            },
            "audit": {
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string"},
                    "enable_signatures": {"type": "boolean"},
                },
            },
        },
    }


def validate_strategy_script(code_or_path: str | Path) -> dict[str, Any]:
    """Dry-run static AST validator for AI agents to check strategy code for syntax or lookahead issues.

    Returns:
        dict containing 'valid', 'errors', 'warnings', and 'strategy_class'.
    """
    errors: list[str] = []
    warnings: list[str] = []
    found_strategy_class: str | None = None

    # Resolve content
    code_text = ""
    if isinstance(code_or_path, Path) or (isinstance(code_or_path, str) and code_or_path.endswith(".py") and Path(code_or_path).exists()):
        try:
            code_text = Path(code_or_path).read_text(encoding="utf-8")
        except Exception as e:
            return {"valid": False, "errors": [f"Could not read strategy file: {e}"], "warnings": [], "strategy_class": None}
    else:
        code_text = str(code_or_path)

    # 1. Parse AST
    try:
        tree = ast.parse(code_text)
    except SyntaxError as e:
        return {
            "valid": False,
            "errors": [f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"],
            "warnings": [],
            "strategy_class": None,
        }

    # 2. Inspect class definitions and methods
    class_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.append(node.name)
            # Check base classes
            is_strat = any(
                (isinstance(base, ast.Name) and base.id in ("Strategy", "ssbt.Strategy"))
                or (isinstance(base, ast.Attribute) and base.attr == "Strategy")
                for base in node.bases
            )
            if is_strat or node.name.endswith("Strategy"):
                found_strategy_class = node.name
                # Check for on_bar method
                has_on_bar = any(
                    isinstance(item, ast.FunctionDef) and item.name == "on_bar"
                    for item in node.body
                )
                if not has_on_bar:
                    errors.append(f"Class '{node.name}' inherits from Strategy but does not implement 'on_bar(self, bar, engine)'.")

        # 3. Lookahead checks
        if isinstance(node, ast.Call):
            # Check for .shift(-1) or negative shifts
            if isinstance(node.func, ast.Attribute) and node.func.attr == "shift":
                for arg in node.args:
                    if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                        warnings.append("Potential anti-lookahead risk: detected negative `.shift()` in strategy AST.")
                    elif isinstance(arg, ast.Constant) and isinstance(arg.value, int) and arg.value < 0:
                        warnings.append("Potential anti-lookahead risk: detected negative `.shift()` in strategy AST.")

    if not found_strategy_class and not class_names:
        # Check if `@strategy` decorator or functional definition is present
        has_func_strat = any(
            isinstance(node, ast.FunctionDef) and any(
                (isinstance(dec, ast.Name) and dec.id in ("strategy", "ssbt.strategy"))
                or (isinstance(dec, ast.Attribute) and dec.attr == "strategy")
                for dec in node.decorator_list
            )
            for node in ast.walk(tree)
        )
        if not has_func_strat:
            warnings.append("No class inheriting from `Strategy` or decorated with `@strategy` found.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "strategy_class": found_strategy_class,
    }


def get_agent_template(template_name: str = "sma_cross") -> str:
    """Return standard code or YAML template for AI agents."""
    templates = {
        "sma_cross": '''from ssbt import Strategy, Side, Bar, Engine

class SmaCrossStrategy(Strategy):
    """Simple Moving Average Crossover Strategy."""

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.prices: list[float] = []

    def on_bar(self, bar: Bar, engine: Engine) -> None:
        self.prices.append(bar.close)
        if len(self.prices) < self.slow_period:
            return

        fast_sma = sum(self.prices[-self.fast_period:]) / self.fast_period
        slow_sma = sum(self.prices[-self.slow_period:]) / self.slow_period

        pos_qty = self.get_position_qty(engine, bar.symbol)

        if fast_sma > slow_sma and pos_qty <= 0:
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
        elif fast_sma < slow_sma and pos_qty >= 0:
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, 1.0))
''',
        "functional": '''import ssbt

@ssbt.strategy
def momentum_strategy(bar, engine):
    if bar.close > bar.open * 1.01:
        engine.submit_order(ssbt.Strategy.market_order(bar.symbol, ssbt.Side.BUY, 1.0))
''',
        "experiment_yaml": '''version: "1.0"
name: "sample_exploration"
description: "Agent-generated signal exploration"

data:
  symbols: ["BTC-USD"]

events:
  - name: "breakout"
    params:
      lookback: 20

outcomes:
  - name: "forward_returns"
    params:
      horizons: [1, 5, 10]
''',
    }
    return templates.get(template_name, templates["sma_cross"])
