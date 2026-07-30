from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssbt.service.errors import E_RUN_NOT_FOUND, ServiceError


def rerun(run_id_or_dir: str) -> dict[str, Any]:
    """Locate and load saved artifact payload from a backtest run.

    Args:
        run_id_or_dir: Run ID (e.g. 'run_123') or explicit artifact directory path.

    Returns:
        dict containing loaded artifact contents (request, response, audit_report, etc.)

    Raises:
        ServiceError: With E_RUN_NOT_FOUND if artifact directory or JSON files missing.
    """
    candidate = Path(run_id_or_dir)
    if candidate.is_dir():
        artifact_dir = candidate
    else:
        candidate_artifacts = Path("artifacts") / run_id_or_dir
        if candidate_artifacts.is_dir():
            artifact_dir = candidate_artifacts
        else:
            raise ServiceError(
                code=E_RUN_NOT_FOUND,
                message=f"Run artifact directory not found for '{run_id_or_dir}'",
                hint="Check run_id or artifact directory path",
                details={"run_id_or_dir": run_id_or_dir},
            )

    payload: dict[str, Any] = {
        "run_id": artifact_dir.name,
        "artifact_dir": str(artifact_dir),
    }

    req_file = artifact_dir / "request.json"
    if req_file.exists():
        with req_file.open("r", encoding="utf-8") as f:
            payload["request"] = json.load(f)

    resp_file = artifact_dir / "response.json"
    if resp_file.exists():
        with resp_file.open("r", encoding="utf-8") as f:
            payload["response"] = json.load(f)

    audit_file = artifact_dir / "audit_report.json"
    if audit_file.exists():
        with audit_file.open("r", encoding="utf-8") as f:
            payload["audit_report"] = json.load(f)

    env_file = artifact_dir / "environment_snapshot.json"
    if env_file.exists():
        with env_file.open("r", encoding="utf-8") as f:
            payload["environment_snapshot"] = json.load(f)

    if not any(k in payload for k in ("request", "response", "audit_report")):
        raise ServiceError(
            code=E_RUN_NOT_FOUND,
            message=f"No valid run artifact JSON files found in '{artifact_dir}'",
            hint="Ensure directory contains request.json, response.json, or audit_report.json",
            details={"artifact_dir": str(artifact_dir)},
        )

    return payload


def _extract_metrics(payload: dict[str, Any]) -> dict[str, float | int]:
    """Extract metrics summary, fills count, and trades count from rerun payload."""
    summary: dict[str, Any] = {}
    fills: list[Any] = []
    trades: list[Any] = []

    if "response" in payload and isinstance(payload["response"], dict):
        resp = payload["response"]
        summary = resp.get("summary", {})
        fills = resp.get("fills", [])
        trades = resp.get("trades", [])
    elif "audit_report" in payload and isinstance(payload["audit_report"], dict):
        audit = payload["audit_report"]
        summary = audit.get("summary", {})
        fills = audit.get("fills", [])
        trades = audit.get("trades", [])
    else:
        summary = payload.get("summary", {})
        fills = payload.get("fills", [])
        trades = payload.get("trades", [])

    total_return = float(summary.get("total_return", summary.get("cumulative_return", 0.0)))
    sharpe = float(summary.get("sharpe", summary.get("sharpe_ratio", 0.0)))
    max_drawdown = float(summary.get("max_drawdown", summary.get("max_drawdown_pct", 0.0)))

    n_fills = summary.get("n_fills")
    if n_fills is None:
        n_fills = len(fills)
    else:
        n_fills = int(n_fills)

    n_trades = summary.get("n_trades")
    if n_trades is None:
        n_trades = len(trades)
    else:
        n_trades = int(n_trades)

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "n_fills": n_fills,
        "n_trades": n_trades,
    }


def compare(run_id_a: str, run_id_b: str) -> dict[str, Any]:
    """Compare performance metrics between two backtest runs.

    Args:
        run_id_a: First run ID or artifact directory path.
        run_id_b: Second run ID or artifact directory path.

    Returns:
        Structured comparison report dictionary containing metrics_a, metrics_b, and deltas.
    """
    payload_a = rerun(run_id_a)
    payload_b = rerun(run_id_b)

    metrics_a = _extract_metrics(payload_a)
    metrics_b = _extract_metrics(payload_b)

    deltas = {
        "total_return": metrics_b["total_return"] - metrics_a["total_return"],
        "sharpe": metrics_b["sharpe"] - metrics_a["sharpe"],
        "max_drawdown": metrics_b["max_drawdown"] - metrics_a["max_drawdown"],
        "n_fills": metrics_b["n_fills"] - metrics_a["n_fills"],
        "n_trades": metrics_b["n_trades"] - metrics_a["n_trades"],
    }

    return {
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "deltas": deltas,
    }
