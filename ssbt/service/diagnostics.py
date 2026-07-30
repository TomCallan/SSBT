from __future__ import annotations
import json
from typing import Any

from ssbt.service.errors import (
    E_DATA_SCHEMA,
    E_LOOKAHEAD,
    E_RESOURCE_LIMIT,
    E_RUN_NOT_FOUND,
    E_STRATEGY_INIT,
    ErrorSpec,
    ServiceError,
)
from ssbt.service.schemas import BacktestResponse


def explain_failure(
    target: ErrorSpec | BacktestResponse | ServiceError | Exception | str,
) -> dict[str, Any]:
    """Parse error targets and return structured diagnostic remediation dictionaries."""
    code = "E_UNKNOWN"
    message = ""
    hint: str | None = None
    details: dict[str, Any] = {}

    if isinstance(target, ErrorSpec):
        code = target.code
        message = target.message
        hint = target.hint
        details = target.details
    elif isinstance(target, BacktestResponse):
        if target.error is not None:
            code = target.error.code
            message = target.error.message
            hint = target.error.hint
            details = target.error.details
        else:
            message = f"Backtest status: {target.status}. No error specified."
    elif isinstance(target, ServiceError):
        code = target.code
        message = target.message
        hint = target.hint
        details = target.details
    elif isinstance(target, Exception):
        code = getattr(target, "code", "E_UNKNOWN")
        message = str(target)
        hint = getattr(target, "hint", None)
        details = getattr(target, "details", {})
    elif isinstance(target, str):
        if target in {
            E_DATA_SCHEMA,
            E_STRATEGY_INIT,
            E_RESOURCE_LIMIT,
            E_LOOKAHEAD,
            E_RUN_NOT_FOUND,
        }:
            code = target
            message = f"Execution failed with error code {target}."
        else:
            try:
                data = json.loads(target)
                if isinstance(data, dict):
                    code = data.get("code", "E_UNKNOWN")
                    message = data.get("message", target)
                    hint = data.get("hint")
                    details = data.get("details", {})
                else:
                    message = target
            except Exception:
                message = target

    remediations: dict[str, dict[str, str]] = {
        E_DATA_SCHEMA: {
            "summary": "Data schema validation failed due to missing required columns or invalid data types.",
            "root_cause": "The supplied Polars DataFrame or CSV/Parquet file lacks required OHLCV columns ('timestamp', 'open', 'high', 'low', 'close', 'volume') or has incompatible data types.",
            "suggested_action": "Ensure input DataFrame contains lower-case column names ['timestamp', 'open', 'high', 'low', 'close', 'volume'] with correct Datetime and Float64 dtypes.",
            "code_fix_snippet": (
                "import polars as pl\n\n"
                "# Ensure columns and data types match SSBT schema\n"
                'df = df.rename({"Date": "timestamp", "Close": "close"})\n'
                "df = df.with_columns([\n"
                '    pl.col("timestamp").str.to_datetime(),\n'
                '    pl.col("close").cast(pl.Float64)\n'
                "])"
            ),
            "default_hint": "Check column names and ensure timestamp is Datetime format.",
        },
        E_STRATEGY_INIT: {
            "summary": "Strategy initialization or execution error during script loading or instantiating.",
            "root_cause": "The strategy code contains syntax errors, invalid imports, missing required methods (on_bar), or failed during __init__ instantiation.",
            "suggested_action": "Verify that your strategy inherits from `ssbt.Strategy`, defines an `on_bar(self, engine)` method, and has valid Python syntax.",
            "code_fix_snippet": (
                "from ssbt import Strategy\n\n"
                "class MyStrategy(Strategy):\n"
                "    def __init__(self, **kwargs):\n"
                "        super().__init__(**kwargs)\n\n"
                "    def on_bar(self, engine):\n"
                "        # Implement bar logic here\n"
                "        pass"
            ),
            "default_hint": "Check strategy class syntax and constructor arguments.",
        },
        E_RESOURCE_LIMIT: {
            "summary": "Backtest execution exceeded resource limits (max bars or timeout threshold).",
            "root_cause": "The dataset bar count exceeds max_bars limit or the backtest execution time exceeded timeout_seconds.",
            "suggested_action": "Increase `limits.max_bars` or `limits.timeout_seconds` in BacktestRequest, or downsample input dataset.",
            "code_fix_snippet": (
                "from ssbt.service import BacktestRequest, ResourceLimitSpec\n\n"
                "req = BacktestRequest(\n"
                "    limits=ResourceLimitSpec(max_bars=5_000_000, timeout_seconds=120.0)\n"
                ")"
            ),
            "default_hint": "Increase timeout_seconds or max_bars limit in request.",
        },
        E_LOOKAHEAD: {
            "summary": "Anti-lookahead causality violation detected during backtesting or data alignment.",
            "root_cause": "Data points or indicator values from future timestamps were accessed prior to their point-in-time availability.",
            "suggested_action": "Use `align_multi_timeframe()` or point-in-time joins to align multi-frequency data without future leakage.",
            "code_fix_snippet": (
                "from ssbt import align_multi_timeframe\n\n"
                "# Align higher timeframe data without lookahead bias\n"
                'aligned_df = align_multi_timeframe(higher_tf_df, lower_tf_df, timestamp_col="timestamp")'
            ),
            "default_hint": "Avoid indexing future bars and use point-in-time data alignment.",
        },
        E_RUN_NOT_FOUND: {
            "summary": "Requested backtest run artifact or job ID could not be found.",
            "root_cause": "The specified `run_id` or `job_id` does not exist in the artifact directory or active job manager memory.",
            "suggested_action": "Check the `run_id` spelling or list active jobs before requesting rerun/status.",
            "code_fix_snippet": (
                "from ssbt.service import get_job_status, rerun\n\n"
                "# Verify job status before rerun\n"
                "job_info = get_job_status(job_id)\n"
                'if job_info.status == "COMPLETED":\n'
                "    res = rerun(job_info.response.run_id)"
            ),
            "default_hint": "Verify the run_id or artifact directory path.",
        },
    }

    info = remediations.get(
        code,
        {
            "summary": f"Execution failed with code: {code}",
            "root_cause": message or "An unspecified internal error occurred.",
            "suggested_action": "Inspect stack trace and execution logs for details.",
            "code_fix_snippet": f"# Diagnostic detail for code: {code}\n# Message: {message}",
            "default_hint": "Review error log and inputs.",
        },
    )

    final_hint = hint if hint is not None else info["default_hint"]

    return {
        "code": code,
        "message": message,
        "hint": final_hint,
        "summary": info["summary"],
        "root_cause": info["root_cause"],
        "suggested_action": info["suggested_action"],
        "code_fix_snippet": info["code_fix_snippet"],
    }


def get_agent_tool_spec(provider: str = "openai") -> list[dict[str, Any]]:
    """Return tool calling specifications for SSBT service APIs."""
    norm_provider = provider.lower()
    if norm_provider not in {"openai", "anthropic"}:
        raise ValueError(
            f"Unsupported LLM tool spec provider: '{provider}'. Supported providers: 'openai', 'anthropic'."
        )

    tools = [
        {
            "name": "run_backtest",
            "description": "Execute an SSBT backtest run with specified strategy, data, execution parameters, and limits.",
            "schema": {
                "type": "object",
                "properties": {
                    "request": {
                        "type": "object",
                        "description": "Backtest request containing strategy, data, execution, and limits specifications.",
                    }
                },
                "required": ["request"],
            },
        },
        {
            "name": "explain_failure",
            "description": "Analyze a backtest failure or error code and return actionable remediation diagnostics.",
            "schema": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Error code, error message, or backtest response JSON to diagnose.",
                    }
                },
                "required": ["target"],
            },
        },
        {
            "name": "rerun",
            "description": "Rerun a previous backtest run deterministically using its run_id or artifact directory path.",
            "schema": {
                "type": "object",
                "properties": {
                    "run_id_or_dir": {
                        "type": "string",
                        "description": "Run ID or directory path of the backtest artifact to rerun.",
                    }
                },
                "required": ["run_id_or_dir"],
            },
        },
        {
            "name": "compare",
            "description": "Compare two backtest runs to verify deterministic output equivalence.",
            "schema": {
                "type": "object",
                "properties": {
                    "run_a": {
                        "type": "string",
                        "description": "First run ID or artifact directory path.",
                    },
                    "run_b": {
                        "type": "string",
                        "description": "Second run ID or artifact directory path.",
                    },
                },
                "required": ["run_a", "run_b"],
            },
        },
    ]

    result: list[dict[str, Any]] = []
    for tool in tools:
        if norm_provider == "openai":
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["schema"],
                    },
                }
            )
        elif norm_provider == "anthropic":
            result.append(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["schema"],
                }
            )

    return result
