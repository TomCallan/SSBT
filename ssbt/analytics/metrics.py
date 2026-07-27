"""Performance metrics — all NumPy, no pandas.

Functions accept the equity curve as a 2D array [timestamp, equity]
and/or a list of Trade objects from the portfolio.
"""

from __future__ import annotations

import numpy as np

from ssbt.core.events import Trade


def _equity_to_returns(equity_curve: np.ndarray) -> np.ndarray:
    """Convert equity curve to per-period returns."""
    equity = equity_curve[:, 1]
    if len(equity) < 2:
        return np.array([], dtype=np.float64)
    return np.diff(equity) / equity[:-1]


def max_drawdown(equity_curve: np.ndarray) -> tuple[float, int]:
    """Return (max_drawdown_pct, peak_index).

    max_drawdown_pct is always <= 0.0 (e.g. -0.15 = 15% drawdown).
    """
    equity = equity_curve[:, 1]
    if len(equity) < 2:
        return 0.0, 0

    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    idx = int(np.argmin(drawdown))
    return float(drawdown[idx]), idx


def sharpe_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio. Assumes returns are per-period."""
    if len(returns) < 2:
        return 0.0
    std = np.std(returns, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(returns) / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: np.ndarray, periods_per_year: int = 252) -> float:
    """Annualised Sortino ratio. Uses downside deviation."""
    if len(returns) < 2:
        return 0.0
    downside = returns[returns < 0]
    if len(downside) == 0:
        return 0.0
    downside_std = np.sqrt(np.mean(downside ** 2))
    if downside_std == 0:
        return 0.0
    return float(np.mean(returns) / downside_std * np.sqrt(periods_per_year))


def calmar_ratio(equity_curve: np.ndarray, periods_per_year: int = 252) -> float:
    """Calmar: annualised return / max drawdown."""
    equity = equity_curve[:, 1]
    if len(equity) < 2:
        return 0.0
    total_return = equity[-1] / equity[0] - 1.0
    n_years = len(equity) / periods_per_year
    if n_years == 0:
        return 0.0
    annual_return = (1 + total_return) ** (1 / n_years) - 1
    mdd, _ = max_drawdown(equity_curve)
    if mdd == 0:
        return 0.0
    return float(annual_return / abs(mdd))


def win_rate(trades: list[Trade]) -> float:
    """Fraction of winning trades."""
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.pnl > 0)
    return wins / len(trades)


def profit_factor(trades: list[Trade]) -> float:
    """Gross profit / gross loss."""
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return float(gross_profit / gross_loss)


def average_trade(trades: list[Trade]) -> float:
    """Average PnL per trade (net of commission)."""
    if not trades:
        return 0.0
    return float(np.mean([t.pnl - t.commission for t in trades]))


def compute_metrics(
    equity_curve: np.ndarray,
    trades: list[Trade],
    periods_per_year: int = 252,
) -> dict:
    """Compute all metrics. Returns dict of name → value."""
    returns = _equity_to_returns(equity_curve)
    mdd, mdd_idx = max_drawdown(equity_curve)
    n_trades = len(trades)

    equity = equity_curve[:, 1] if len(equity_curve) else np.array([0.0])
    total_return = float(equity[-1] / equity[0] - 1.0) if len(equity) >= 2 else 0.0

    return {
        "total_return": total_return,
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year),
        "calmar": calmar_ratio(equity_curve, periods_per_year),
        "max_drawdown": mdd,
        "n_trades": n_trades,
        "win_rate": win_rate(trades),
        "profit_factor": profit_factor(trades),
        "avg_trade": average_trade(trades),
        "final_equity": float(equity[-1]) if len(equity) else 0.0,
        "n_periods": len(equity_curve),
    }


def format_metrics(metrics: dict) -> str:
    """Pretty-print metrics dict as a string table."""
    lines = [
        f"{'Metric':<20} {'Value':>15}",
        f"{'------':<20} {'-----':>15}",
    ]
    pct_keys = {"total_return", "max_drawdown", "win_rate"}
    for key, val in metrics.items():
        if key in pct_keys:
            lines.append(f"{key:<20} {val * 100:>14.2f}%")
        elif isinstance(val, float):
            lines.append(f"{key:<20} {val:>15.4f}")
        else:
            lines.append(f"{key:<20} {val:>15}")
    return "\n".join(lines)
