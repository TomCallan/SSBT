"""Multi-Ticker & Multi-Timeframe Strategy Matrix Evaluation Suite with Standard SSBT Visualizations.

1. Generates a unique Run ID (e.g. `run_20260728_204130`).
2. Clears previous artifacts and saves all outputs to `artifacts/<run_id>/`.
3. Evaluates TripleConfluence across tickers (Gold, Silver, Crude Oil, BTC) and timeframes (1d, 1h).
4. Generates standard SSBT charts (Matrix Heatmap, Multi-Equity Curves) and AuditLogger anti-lookahead lineage verification.
5. Emits real-time IPC execution stream (`artifacts/<run_id>/execution_stream.jsonl`).
"""

import sys
import shutil
from datetime import datetime
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
from ssbt.analytics.stream import ExecutionStreamPublisher
from ssbt.analytics.terminal import display_audit_status, console
from ssbt.experiments.charts import (
    generate_matrix_heatmap_chart,
    generate_multi_equity_curve_chart,
)
from rich.panel import Panel
from rich.table import Table


def fetch_multi_data(ticker: str, period: str, interval: str) -> pl.DataFrame:
    """Download OHLCV data from yfinance."""
    print(f"Downloading {ticker} ({interval} / {period})...")
    df_pd = yf.download(ticker, period=period, interval=interval, progress=False)
    if df_pd.empty:
        raise ValueError(f"No data for {ticker}")

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index().dropna(subset=["Close", "Volume"])
    time_col = df_pd.columns[0]
    dates = pd.to_datetime(df_pd[time_col])
    timestamps_ns = dates.astype("int64").values

    return pl.DataFrame({
        "timestamp": timestamps_ns,
        "symbol": [ticker] * len(df_pd),
        "open": df_pd["Open"].values.astype(float),
        "high": df_pd["High"].values.astype(float),
        "low": df_pd["Low"].values.astype(float),
        "close": df_pd["Close"].values.astype(float),
        "volume": df_pd["Volume"].values.astype(float),
    }).sort("timestamp")


class ContinuousTripleConfluence(Strategy):
    """Triple Confluence Strategy with recurring position reset check via `self.is_flat`."""
    def __init__(self, ema_period: int = 20, rsi_period: int = 14, risk_dollars: float = 85.0):
        super().__init__()
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []

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

        # Use self.is_flat(engine, bar.symbol) to allow continuous recurring trades!
        if bar.close > ema and 45.0 <= rsi <= 65.0 and self.is_flat(engine, bar.symbol) and engine.portfolio.cash >= 3500:
            stop_dist = max(1.8 * atr, bar.close * 0.008)
            qty = round(self.risk_dollars / stop_dist, 2)
            if qty <= 0:
                qty = 1.0

            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))


def main():
    # 1. Generate unique Run ID
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    base_artifacts_dir = Path("artifacts")
    
    # Clear previous artifacts folder if requested
    if base_artifacts_dir.exists():
        shutil.rmtree(base_artifacts_dir)

    run_dir = base_artifacts_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Maintain 'latest' directory copy for GUI integration convenience
    latest_dir = base_artifacts_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    console.print()
    console.print(Panel.fit(f"[bold yellow]EXECUTION RUN ID:[/bold yellow] [bold cyan]{run_id}[/bold cyan]\n[dim]Artifacts Output Directory: {run_dir.resolve()}[/dim]", border_style="yellow"))

    # Initialize Real-Time IPC Execution Stream Publisher
    stream_publisher = ExecutionStreamPublisher(log_path=run_dir / "execution_stream.jsonl")

    tickers = ["GC=F", "SI=F", "CL=F", "BTC-USD"]
    timeframe_configs = [
        ("1d", "1y"),
        ("1h", "60d"),
    ]

    adapter = BacktestAdapter(initial_cash=5000.0)
    logger = AuditLogger(verbose=False)

    matrix_rows = []
    equity_curves_dict = {}
    last_backtest_result = None

    for tf_name, period in timeframe_configs:
        for ticker in tickers:
            try:
                df = fetch_multi_data(ticker, period=period, interval=tf_name)
            except Exception as e:
                print(f"Skipping {ticker} {tf_name}: {e}")
                continue

            feed = InMemoryFeed(df, symbol=ticker)
            strategy = ContinuousTripleConfluence()

            res = adapter.run_backtest(feed, strategy)
            metrics = res["metrics"]
            trades = res["trades"]
            last_backtest_result = res["raw_result"]

            key = f"{ticker}_{tf_name}"
            equity_curves_dict[key] = res["equity_curve"]

            # Stream real-time summary event to IPC publisher for GUI integration
            stream_publisher.publish(
                event_type="STRATEGY_COMPLETED",
                timestamp=int(df["timestamp"][-1]),
                data={
                    "key": key,
                    "final_equity": res["final_equity"],
                    "sharpe": metrics.get("sharpe", 0.0),
                    "trades": trades.height if trades is not None else 0,
                }
            )

            matrix_rows.append({
                "ticker": ticker,
                "timeframe": tf_name,
                "final_equity": res["final_equity"],
                "net_profit": res["final_equity"] - 5000.0,
                "sharpe": metrics.get("sharpe", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0) * 100.0,
                "n_trades": trades.height if trades is not None else 0,
            })

    matrix_df = pl.DataFrame(matrix_rows)

    # Display Rich Terminal Results Matrix
    results_table = Table(title="Multi-Timeframe & Multi-Ticker Strategy Matrix", header_style="bold yellow", border_style="dim")
    results_table.add_column("Ticker", style="cyan")
    results_table.add_column("Timeframe", style="magenta")
    results_table.add_column("Final Equity", justify="right", style="green")
    results_table.add_column("Net Profit", justify="right", style="bold green")
    results_table.add_column("Sharpe Ratio", justify="right", style="bold cyan")
    results_table.add_column("Max Drawdown", justify="right", style="red")
    results_table.add_column("Trades Count", justify="right", style="yellow")

    for row in matrix_df.iter_rows(named=True):
        results_table.add_row(
            row["ticker"],
            row["timeframe"],
            f"${row['final_equity']:,.2f}",
            f"{row['net_profit']:+,.2f}",
            f"{row['sharpe']:.2f}",
            f"{row['max_drawdown']:.2f}%",
            str(row["n_trades"]),
        )

    console.print(results_table)
    console.print()

    # GENERATE STANDARD SSBT CHART PRODUCTS IN RUN_DIR
    matrix_chart_path = generate_matrix_heatmap_chart(
        matrix_df=matrix_df, x_col="timeframe", y_col="ticker", val_col="sharpe",
        output_dir=run_dir, name="test_matrix_plot"
    )
    console.print(f"[bold green][PASS] Generated Standard Matrix Heatmap Plot:[/bold green] [bold cyan]{run_dir / matrix_chart_path}[/bold cyan]")

    equity_chart_path = generate_multi_equity_curve_chart(
        equity_curves_dict=equity_curves_dict,
        output_dir=run_dir, name="multi_equity_curves"
    )
    console.print(f"[bold green][PASS] Generated Standard Multi-Equity Curve Plot:[/bold green] [bold cyan]{run_dir / equity_chart_path}[/bold cyan]")
    console.print(f"[bold green][PASS] Real-Time Stream Published To:[/bold green] [bold cyan]{run_dir / 'execution_stream.jsonl'}[/bold cyan]")

    # Run AuditLogger verification and save audit trail in run_dir
    audit_report = logger.generate_report(backtest_result=last_backtest_result, output_dir=run_dir)
    display_audit_status(audit_report)

    # Sync latest directory for convenience
    for item in run_dir.iterdir():
        if item.is_file():
            shutil.copy(item, latest_dir / item.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
