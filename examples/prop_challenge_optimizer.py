"""Velotrade 5k Challenge Strategy Optimizer.

Tests single-asset and multi-asset portfolio strategies across 1h & 1d datasets
to achieve solid profit (+8% / +$400 target) and high Sharpe ratio (> 1.5)
without relying on high-frequency trading (HFT).
"""

import sys
import numpy as np
import pandas as pd
import polars as pl
import yfinance as yf

from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.audit import AuditLogger
from ssbt.analytics.terminal import display_audit_status, console
from rich.panel import Panel
from rich.table import Table


def fetch_data(ticker: str, period: str = "1y", interval: str = "1d") -> pl.DataFrame:
    """Fetch market data from yfinance."""
    print(f"Fetching {ticker} (period={period}, interval={interval})...")
    df_pd = yf.download(ticker, period=period, interval=interval, progress=False)
    if df_pd.empty:
        raise ValueError(f"No data for {ticker}")

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index().dropna(subset=["Close", "Volume"])
    time_col = df_pd.columns[0]
    timestamps = (pd.to_datetime(df_pd[time_col]).astype("int64")).values

    return pl.DataFrame({
        "timestamp": timestamps,
        "symbol": [ticker] * len(timestamps),
        "open": df_pd["Open"].values.astype(float),
        "high": df_pd["High"].values.astype(float),
        "low": df_pd["Low"].values.astype(float),
        "close": df_pd["Close"].values.astype(float),
        "volume": df_pd["Volume"].values.astype(float),
    }).sort("timestamp")


# =====================================================================
# MULTI-TIME FRAME TREND & BREAKOUT PORTFOLIO STRATEGY
# =====================================================================

class MultiTimeframeTrendStrategy(Strategy):
    """Multi-Timeframe Trend & Volatility Breakout Strategy.
    
    1. Filter: EMA(10) > EMA(30) trend filter.
    2. Entry Trigger: Breakout above highest high of past 10 bars.
    3. Position Sizing: Risk 1.5% ($75) per trade using ATR trailing stop.
    """
    def __init__(self, fast_period: int = 10, slow_period: int = 30, risk_dollars: float = 75.0):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []
        self.in_position = False

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < self.slow_period + 2:
            return

        closes_arr = np.array(self.closes[-self.slow_period:])
        fast_ema = np.mean(closes_arr[-self.fast_period:])
        slow_ema = np.mean(closes_arr)

        tr = np.maximum(
            np.array(self.highs[-10:]) - np.array(self.lows[-10:]),
            np.abs(np.array(self.highs[-10:]) - np.array(self.closes[-11:-1]))
        )
        atr = float(np.mean(tr)) if len(tr) > 0 else bar.close * 0.01

        is_uptrend = fast_ema > slow_ema
        is_breakout = bar.close > np.max(self.highs[-6:-1])

        if is_uptrend and is_breakout and not self.in_position and engine.portfolio.cash >= 3500:
            stop_dist = max(1.8 * atr, bar.close * 0.008)
            qty = round(self.risk_dollars / stop_dist, 2)
            if qty <= 0:
                qty = 1.0

            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))
            self.in_position = True


class TripleConfluenceStrategy(Strategy):
    """Triple Confluence Strategy: EMA Trend + RSI Confirmation + ATR Trailing Lock."""
    def __init__(self, ema_period: int = 20, rsi_period: int = 14, risk_dollars: float = 85.0):
        super().__init__()
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []
        self.in_position = False

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < self.ema_period + 2:
            return

        ema = np.mean(self.closes[-self.ema_period:])
        
        diffs = np.diff(self.closes[-self.rsi_period-1:])
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        rs = np.mean(gains) / (np.mean(losses) + 1e-8)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        tr = np.maximum(
            np.array(self.highs[-10:]) - np.array(self.lows[-10:]),
            np.abs(np.array(self.highs[-10:]) - np.array(self.closes[-11:-1]))
        )
        atr = float(np.mean(tr)) if len(tr) > 0 else bar.close * 0.01

        if bar.close > ema and 45.0 <= rsi <= 65.0 and not self.in_position and engine.portfolio.cash >= 3500:
            stop_dist = max(2.0 * atr, bar.close * 0.01)
            qty = round(self.risk_dollars / stop_dist, 2)
            if qty <= 0:
                qty = 1.0

            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))
            self.in_position = True


# =====================================================================
# EVALUATION & CHALLENGE AUDIT
# =====================================================================

def evaluate_challenge(result: dict, initial_cash: float = 5000.0) -> dict:
    equity_curve = result["equity_curve"]
    trades = result["trades"]
    metrics = result["metrics"]

    if len(equity_curve) == 0:
        return {"challenge_passed": False}

    equities = equity_curve[:, 1]
    peak_equity = np.maximum.accumulate(equities)
    drawdowns = (equities - peak_equity)

    max_drawdown_dollars = abs(float(np.min(drawdowns)))
    final_equity = float(equities[-1])
    net_profit = final_equity - initial_cash
    profit_pct = (net_profit / initial_cash) * 100.0

    timestamps = pd.to_datetime(equity_curve[:, 0])
    eq_df = pd.DataFrame({"timestamp": timestamps, "equity": equities})
    eq_df["date"] = eq_df["timestamp"].dt.date
    daily_stats = eq_df.groupby("date")["equity"].agg(["first", "min"])
    daily_drawdowns = daily_stats["min"] - daily_stats["first"]
    max_daily_dd_dollars = abs(float(daily_drawdowns.min())) if not daily_drawdowns.empty else 0.0

    passed_profit_target = net_profit >= 400.0  # +$400 (+8%)
    passed_daily_dd = max_daily_dd_dollars <= 250.0  # Max $250 daily loss
    passed_total_dd = max_drawdown_dollars <= 500.0  # Max $500 total loss

    challenge_passed = passed_profit_target and passed_daily_dd and passed_total_dd

    return {
        "challenge_passed": challenge_passed,
        "final_equity": final_equity,
        "net_profit": net_profit,
        "profit_pct": profit_pct,
        "max_daily_dd_dollars": max_daily_dd_dollars,
        "max_total_dd_dollars": max_drawdown_dollars,
        "passed_profit_target": passed_profit_target,
        "passed_daily_dd": passed_daily_dd,
        "passed_total_dd": passed_total_dd,
        "n_trades": trades.height if trades is not None else 0,
        "win_rate": metrics.get("win_rate", 0.0) * 100.0,
        "sharpe": metrics.get("sharpe", 0.0),
        "sortino": metrics.get("sortino", 0.0),
    }


def main():
    console.print()
    console.print(Panel.fit("[bold yellow]PROP STRATEGY OPTIMIZER — VELOTRADE 5K ACCOUNT[/bold yellow]", border_style="yellow"))

    # Test high-trending instruments (Gold, NVDA, AAPL, BTC, Silver)
    assets = ["GC=F", "NVDA", "AAPL", "SI=F", "CL=F"]
    datasets = {}
    for a in assets:
        try:
            datasets[a] = fetch_data(a, period="1y", interval="1d")
        except Exception as e:
            print(f"Warning: Could not fetch {a}: {e}")

    strategies = [
        ("Multi-Timeframe Trend", MultiTimeframeTrendStrategy),
        ("Triple Confluence", TripleConfluenceStrategy),
    ]

    adapter = BacktestAdapter(initial_cash=5000.0)
    logger = AuditLogger(verbose=False)

    table = Table(title="Velotrade 5k Optimization Results Matrix", header_style="bold cyan", border_style="dim")
    table.add_column("Strategy", style="bold white")
    table.add_column("Ticker", style="cyan")
    table.add_column("Final Equity", justify="right", style="green")
    table.add_column("Net Profit", justify="right", style="bold green")
    table.add_column("Max Daily DD", justify="right", style="red")
    table.add_column("Max Total DD", justify="right", style="red")
    table.add_column("Win Rate", justify="right", style="yellow")
    table.add_column("Sharpe", justify="right", style="bold cyan")
    table.add_column("Sortino", justify="right", style="bold cyan")
    table.add_column("Challenge Status", justify="center", style="bold white")

    passed_count = 0

    for name, strat_cls in strategies:
        for ticker, df in datasets.items():
            feed = InMemoryFeed(df, symbol=ticker)
            strat = strat_cls()

            res = adapter.run_backtest(feed, strat)
            audit_report = logger.generate_report(backtest_result=res["raw_result"])
            eval_res = evaluate_challenge(res, initial_cash=5000.0)

            if eval_res["challenge_passed"]:
                status_str = "[bold green][PASS] PASSED[/bold green]"
                passed_count += 1
            else:
                status_str = "[bold red][FAIL] FAILED[/bold red]"
                if not eval_res["passed_daily_dd"]:
                    status_str += " [dim](Daily DD)[/dim]"
                elif not eval_res["passed_total_dd"]:
                    status_str += " [dim](Total DD)[/dim]"
                elif not eval_res["passed_profit_target"]:
                    status_str += " [dim](Target Not Reached)[/dim]"

            table.add_row(
                name,
                ticker,
                f"${eval_res['final_equity']:,.2f}",
                f"{eval_res['net_profit']:+,.2f}",
                f"-${eval_res['max_daily_dd_dollars']:.2f}",
                f"-${eval_res['max_total_dd_dollars']:.2f}",
                f"{eval_res['win_rate']:.1f}%",
                f"{eval_res['sharpe']:.2f}",
                f"{eval_res['sortino']:.2f}",
                status_str,
            )

    console.print(table)
    console.print()
    console.print(f"[bold white]Total Passing Strategies Found:[/bold white] [bold green]{passed_count}[/bold green]")
    display_audit_status(audit_report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
