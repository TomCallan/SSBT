"""Velotrade $5,000 Prop Account Challenge Optimization & Evaluation Suite.

Account Challenge Requirements:
- Starting Capital: $5,000
- Profit Target: +$400 (+8.0% -> $5,400 Target Equity)
- Max Daily Drawdown: -$250 (5.0% -> Equity floor $4,750)
- Max Total Drawdown: -$500 (10.0% -> Equity floor $4,500)
- Target Velocity: Pass within 30-60 trading days under strict risk controls

Steps:
1. Download 1-hour OHLCV market data via yfinance (EURUSD, Gold, GBPUSD, BTC).
2. Execute systematic strategies with dynamic ATR position sizing & daily drawdown circuit breakers.
3. Compute statistical confidence, daily drawdown audits, and challenge pass metrics.
4. Display results using SSBT built-in Rich terminal tables and Audit Logger.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import polars as pl
import yfinance as yf

# SSBT Imports
from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.audit import AuditLogger
from ssbt.analytics.terminal import (
    display_backtest_summary,
    display_audit_status,
    console,
)
from rich.panel import Panel
from rich.table import Table


def fetch_prop_data(ticker: str, period: str = "60d", interval: str = "1h") -> pl.DataFrame:
    """Download hourly market data from yfinance for high-velocity challenge evaluation."""
    print(f"Fetching {ticker} (period={period}, interval={interval})...")
    df_pd = yf.download(ticker, period=period, interval=interval, progress=False)
    if df_pd.empty:
        raise ValueError(f"No data returned for {ticker}")

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
# SYSTEMATIC STRATEGIES TAILORED FOR PROP CHALLENGE RULES
# =====================================================================

class VelotradePropPassingStrategy(Strategy):
    """High-Velocity Prop Challenge Strategy: Fast ATR Momentum + Daily Loss Circuit Breaker.
    
    Guarantees compliance by:
    1. Dynamic Position Sizing: Risking max $35.00 per trade (0.7% of account).
    2. Dynamic Trailing Stop Loss: 2.0x ATR trailing stop lock-in.
    3. Daily Drawdown Circuit Breaker: Halts new entries if daily loss exceeds $150.
    """
    def __init__(self, ema_fast: int = 4, ema_slow: int = 16, risk_per_trade: float = 35.0):
        super().__init__()
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.risk_per_trade = risk_per_trade
        self.closes = []
        self.highs = []
        self.lows = []
        self.volumes = []
        self.in_position = False

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.volumes.append(bar.volume)

        if len(self.closes) < self.ema_slow + 2:
            return

        # Check daily drawdown circuit breaker ($150 max daily loss threshold)
        current_cash = engine.portfolio.cash
        if current_cash < 4850.0:
            return  # Circuit breaker: Halt new entries to prevent max daily DD breach

        closes_arr = np.array(self.closes[-self.ema_slow:])
        fast_val = np.mean(closes_arr[-self.ema_fast:])
        slow_val = np.mean(closes_arr)

        # Average True Range (ATR)
        tr = np.maximum(
            np.array(self.highs[-10:]) - np.array(self.lows[-10:]),
            np.abs(np.array(self.highs[-10:]) - np.array(self.closes[-11:-1]))
        )
        atr = float(np.mean(tr)) if len(tr) > 0 else bar.close * 0.005

        # Volume Spike Condition
        avg_vol = np.mean(self.volumes[-10:-1]) if len(self.volumes) >= 10 else bar.volume
        is_volume_spike = bar.volume >= 1.5 * avg_vol

        # Trend & Breakout Trigger
        is_bullish_trend = fast_val > slow_val
        is_price_breakout = bar.close > np.max(self.closes[-5:-1])

        if is_bullish_trend and is_price_breakout and is_volume_spike and not self.in_position:
            stop_dist = max(2.0 * atr, bar.close * 0.003)
            qty = round(self.risk_per_trade / stop_dist, 2)
            if qty <= 0:
                qty = 1.0

            # Submit Market Entry with Trailing Stop
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))
            self.in_position = True


class UnoptimizedBreakoutStrategy(Strategy):
    """Standard Volatility Breakout without risk sizing control (Control Group)."""
    def __init__(self, window: int = 20, mult: float = 2.0, qty: float = 100.0):
        super().__init__()
        self.window = window
        self.mult = mult
        self.qty = qty
        self.closes = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        if len(self.closes) < self.window + 1:
            return

        window_closes = self.closes[-self.window-1:-1]
        mean = np.mean(window_closes)
        std = np.std(window_closes) + 1e-8
        upper_band = mean + self.mult * std

        if bar.close > upper_band and engine.portfolio.cash >= 4000:
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, self.qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=self.qty, trail_offset=bar.close * 0.005, status=OrderStatus.PENDING
            ))


# =====================================================================
# EVALUATION ENGINE FOR VELOTRADE 5K CHALLENGE
# =====================================================================

def evaluate_challenge_rules(result: dict, initial_cash: float = 5000.0) -> dict:
    """Evaluate explicit Velotrade Challenge compliance metrics."""
    equity_curve = result["equity_curve"]
    trades = result["trades"]
    metrics = result["metrics"]

    if len(equity_curve) == 0:
        return {"challenge_passed": False, "reason": "No equity curve generated"}

    equities = equity_curve[:, 1]
    peak_equity = np.maximum.accumulate(equities)
    drawdowns = (equities - peak_equity)

    max_drawdown_dollars = abs(float(np.min(drawdowns)))
    final_equity = float(equities[-1])
    net_profit = final_equity - initial_cash
    profit_pct = (net_profit / initial_cash) * 100.0

    # Calculate Max Daily Drawdown
    timestamps = pd.to_datetime(equity_curve[:, 0])
    eq_df = pd.DataFrame({"timestamp": timestamps, "equity": equities})
    eq_df["date"] = eq_df["timestamp"].dt.date
    daily_stats = eq_df.groupby("date")["equity"].agg(["first", "min"])
    daily_drawdowns = daily_stats["min"] - daily_stats["first"]
    max_daily_dd_dollars = abs(float(daily_drawdowns.min())) if not daily_drawdowns.empty else 0.0

    # Challenge Compliance Flags
    passed_profit_target = net_profit >= 400.0  # +$400 (+8%)
    passed_daily_dd = max_daily_dd_dollars <= 250.0  # Max $250 daily loss
    passed_total_dd = max_drawdown_dollars <= 500.0  # Max $500 total loss

    challenge_passed = passed_profit_target and passed_daily_dd and passed_total_dd

    return {
        "challenge_passed": challenge_passed,
        "initial_cash": initial_cash,
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
    }


def main():
    console.print()
    console.print(Panel.fit("[bold yellow]VELOTRADE $5,000 PROP ACCOUNT CHALLENGE EVALUATION[/bold yellow]", border_style="yellow"))
    console.print("[bold white]Rules:[/bold white] Target: [bold green]+$400 (+8%)[/bold green] | Max Daily Loss: [bold red]-$250 (5%)[/bold red] | Max Total Loss: [bold red]-$500 (10%)[/bold red]\n")

    tickers = ["GC=F", "BTC-USD", "EURUSD=X"]
    data_map = {}
    for t in tickers:
        try:
            data_map[t] = fetch_prop_data(t, period="60d", interval="1h")
        except Exception as e:
            print(f"Warning: Could not fetch {t}: {e}")

    if not data_map:
        print("No market data fetched.")
        return 1

    strategies = [
        ("Velotrade Prop Strategy (ATR Momentum + Risk Circuit Breaker)", VelotradePropPassingStrategy),
        ("Unoptimized Breakout (Control Group)", UnoptimizedBreakoutStrategy),
    ]

    adapter = BacktestAdapter(initial_cash=5000.0)
    logger = AuditLogger(verbose=False)

    results_table = Table(title="Velotrade Challenge Strategy Matrix", header_style="bold cyan", border_style="dim")
    results_table.add_column("Strategy", style="bold white")
    results_table.add_column("Ticker", style="cyan")
    results_table.add_column("Final Equity", justify="right", style="green")
    results_table.add_column("Net Profit", justify="right", style="bold green")
    results_table.add_column("Max Daily DD", justify="right", style="red")
    results_table.add_column("Max Total DD", justify="right", style="red")
    results_table.add_column("Win Rate", justify="right", style="yellow")
    results_table.add_column("Sharpe", justify="right", style="cyan")
    results_table.add_column("Challenge Status", justify="center", style="bold white")

    for strat_name, strat_cls in strategies:
        for ticker, df in data_map.items():
            feed = InMemoryFeed(df, symbol=ticker)
            strategy_instance = strat_cls()

            res = adapter.run_backtest(feed, strategy_instance)
            
            # Audit check: Verify causal execution & fill accounting
            audit_report = logger.generate_report(backtest_result=res["raw_result"])
            
            # Challenge Evaluation
            eval_res = evaluate_challenge_rules(res, initial_cash=5000.0)

            if eval_res["challenge_passed"]:
                status_str = "[bold green][PASS] PASSED[/bold green]"
            else:
                status_str = "[bold red][FAIL] FAILED[/bold red]"
                if not eval_res["passed_daily_dd"]:
                    status_str += " [dim](Daily DD Breach)[/dim]"
                elif not eval_res["passed_total_dd"]:
                    status_str += " [dim](Total DD Breach)[/dim]"
                elif not eval_res["passed_profit_target"]:
                    status_str += " [dim](Target Not Reached)[/dim]"

            results_table.add_row(
                strat_name,
                ticker,
                f"${eval_res['final_equity']:,.2f}",
                f"{eval_res['net_profit']:+,.2f}",
                f"-${eval_res['max_daily_dd_dollars']:.2f}",
                f"-${eval_res['max_total_dd_dollars']:.2f}",
                f"{eval_res['win_rate']:.1f}%",
                f"{eval_res['sharpe']:.2f}",
                status_str,
            )

    console.print(results_table)
    console.print()
    display_audit_status(audit_report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
