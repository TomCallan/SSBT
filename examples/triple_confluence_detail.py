"""Detailed Trade Log & Equity Curve Inspection for TripleConfluenceStrategy on Gold (GC=F).

1. Fetches Gold (GC=F) 1-year OHLCV data.
2. Runs TripleConfluenceStrategy backtest.
3. Extracts and displays complete trade entry/exit timestamps, prices, holding periods, and PnLs.
4. Generates an equity curve visualization plot saved to artifacts/triple_confluence_gold_equity.png.
"""

import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
from ssbt.analytics.terminal import display_audit_status, console
from rich.panel import Panel
from rich.table import Table


def fetch_gold_data() -> tuple[pl.DataFrame, pd.DatetimeIndex]:
    """Download 1-year daily Gold futures data."""
    print("Downloading GC=F (Gold) from yfinance...")
    df_pd = yf.download("GC=F", period="1y", interval="1d", progress=False)
    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index().dropna(subset=["Close", "Volume"])
    time_col = df_pd.columns[0]
    dates = pd.to_datetime(df_pd[time_col])
    timestamps = np.arange(len(df_pd), dtype=np.int64)  # bar index sequence

    pl_df = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["GC=F"] * len(df_pd),
        "open": df_pd["Open"].values.astype(float),
        "high": df_pd["High"].values.astype(float),
        "low": df_pd["Low"].values.astype(float),
        "close": df_pd["Close"].values.astype(float),
        "volume": df_pd["Volume"].values.astype(float),
    }).sort("timestamp")

    return pl_df, dates


class TripleConfluenceStrategy(Strategy):
    """Triple Confluence Strategy on Gold."""
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


def main():
    console.print()
    console.print(Panel.fit("[bold green]TRIPLE CONFLUENCE STRATEGY — DETAILED TRADE & EQUITY INSPECTION[/bold green]", border_style="green"))

    df, dates = fetch_gold_data()
    feed = InMemoryFeed(df, symbol="GC=F")
    strategy = TripleConfluenceStrategy()

    adapter = BacktestAdapter(initial_cash=5000.0)
    result = adapter.run_backtest(feed, strategy)

    metrics = result["metrics"]
    trades_df = result["trades"]
    equity_curve = result["equity_curve"]

    # Render Summary Panel
    console.print(f"[bold white]Starting Balance:[/bold white] $5,000.00  |  [bold white]Final Equity:[/bold white] [bold green]${result['final_equity']:,.2f}[/bold green]")
    console.print(f"[bold white]Net Profit:[/bold white] [bold green]+${result['final_equity'] - 5000:,.2f} (+{(result['final_equity']/5000 - 1)*100:.2f}%)[/bold green]")
    console.print(f"[bold white]Sharpe Ratio:[/bold white] [bold cyan]{metrics['sharpe']:.2f}[/bold cyan]  |  [bold white]Max Drawdown:[/bold white] [bold red]{metrics['max_drawdown']*100:.2f}%[/bold red]")
    console.print()

    # RENDER COMPLETE TRADE ENTRIES & EXITS TABLE
    if trades_df is not None and not trades_df.is_empty():
        trade_table = Table(title="Complete Trade Entries & Exits Log", header_style="bold yellow", border_style="dim")
        trade_table.add_column("Trade #", justify="right", style="cyan")
        trade_table.add_column("Symbol", style="cyan")
        trade_table.add_column("Side", style="white")
        trade_table.add_column("Entry Date", style="white")
        trade_table.add_column("Exit Date", style="white")
        trade_table.add_column("Entry Price", justify="right", style="white")
        trade_table.add_column("Exit Price", justify="right", style="white")
        trade_table.add_column("Quantity", justify="right", style="yellow")
        trade_table.add_column("PnL ($)", justify="right", style="bold green")
        trade_table.add_column("PnL (%)", justify="right", style="bold green")

        for idx, row in enumerate(trades_df.iter_rows(named=True), 1):
            entry_idx = int(row["entry_time"])
            exit_idx = int(row["exit_time"])
            entry_dt = dates[min(entry_idx, len(dates)-1)].strftime("%Y-%m-%d")
            exit_dt = dates[min(exit_idx, len(dates)-1)].strftime("%Y-%m-%d")

            pnl_val = row.get("pnl", 0.0)
            pnl_pct = row.get("pnl_pct", 0.0) * 100.0
            color = "green" if pnl_val >= 0 else "red"

            trade_table.add_row(
                str(idx),
                str(row.get("symbol", "GC=F")),
                str(row.get("side", "BUY")),
                entry_dt,
                exit_dt,
                f"${row.get('entry_price', 0.0):,.2f}",
                f"${row.get('exit_price', 0.0):,.2f}",
                f"{row.get('qty', 0.0):.2f}",
                f"[{color}]+${pnl_val:,.2f}[/{color}]",
                f"[{color}]+{pnl_pct:.2f}%[/{color}]",
            )
        console.print(trade_table)

    # RENDER EQUITY CURVE STEP-BY-STEP SNAPSHOT TABLE
    if len(equity_curve) > 0:
        eq_values = equity_curve[:, 1]
        
        eq_table = Table(title="Equity Curve Snapshots Across Trading Days", header_style="bold blue", border_style="dim")
        eq_table.add_column("Bar #", justify="right", style="cyan")
        eq_table.add_column("Date", style="white")
        eq_table.add_column("Account Equity ($)", justify="right", style="bold green")
        eq_table.add_column("Drawdown ($)", justify="right", style="red")

        peak = eq_values[0]
        step_indices = np.linspace(0, len(eq_values) - 1, min(10, len(eq_values)), dtype=int)
        
        for idx in step_indices:
            dt_str = dates[min(idx, len(dates)-1)].strftime("%Y-%m-%d")
            val = eq_values[idx]
            peak = max(peak, val)
            dd = val - peak
            eq_table.add_row(
                str(idx + 1),
                dt_str,
                f"${val:,.2f}",
                f"-${abs(dd):,.2f}",
            )
        console.print()
        console.print(eq_table)

    # GENERATE PLOT VISUALIZATION
    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / "triple_confluence_gold_equity.png"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    equities = equity_curve[:, 1]
    plot_dates = dates[:len(equities)]
    ax1.plot(plot_dates, equities, color="green", linewidth=2, label="Account Equity ($)")
    ax1.axhline(5000.0, color="gray", linestyle="--", alpha=0.7, label="Initial Capital ($5,000)")
    ax1.axhline(5400.0, color="gold", linestyle="--", linewidth=1.5, label="Velotrade Target ($5,400)")
    
    # Mark Trade Entry & Exit points on Equity Curve
    for row in trades_df.iter_rows(named=True):
        e_idx = min(int(row["entry_time"]), len(plot_dates)-1)
        x_idx = min(int(row["exit_time"]), len(plot_dates)-1)
        entry_t = plot_dates[e_idx]
        exit_t = plot_dates[x_idx]
        ax1.scatter(entry_t, 5000.0, color="blue", marker="^", s=100, label="Trade Entry")
        ax1.scatter(exit_t, 5000.0 + row["pnl"], color="green", marker="v", s=100, label="Trade Exit")

    ax1.set_ylabel("Equity ($)")
    ax1.set_title("Triple Confluence Strategy — Gold (GC=F) Equity Curve & Trades")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Plot 2: Drawdown
    peaks = np.maximum.accumulate(equities)
    dds = (equities - peaks)
    ax2.fill_between(plot_dates, dds, 0, color="red", alpha=0.3, label="Drawdown ($)")
    ax2.set_ylabel("Drawdown ($)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(chart_path, dpi=150)
    plt.close(fig)

    console.print()
    console.print(f"[bold green][PASS] Saved Equity Curve Chart to:[/bold green] [bold cyan]{chart_path.resolve()}[/bold cyan]")

    # Run Audit Logger verification
    logger = AuditLogger(verbose=False)
    report = logger.generate_report(backtest_result=result["raw_result"], output_dir=output_dir)
    display_audit_status(report)


if __name__ == "__main__":
    sys.exit(main())
