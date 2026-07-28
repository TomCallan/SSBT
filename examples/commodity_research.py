"""Complete Commodity Market Research Study using SSBT.

Data Ingestion: yfinance (External)
Engine: SSBT (Event Detection, Bootstrap Stats, Numba Backtest Engine)
Audit & Output: AuditLogger (Anti-Lookahead Verification) & Rich Terminal Displays
"""

import sys
import numpy as np
import pandas as pd
import polars as pl
import yfinance as yf

from ssbt.events.volume_spike import VolumeSpike
from ssbt.outcomes.forward_return import ForwardReturn
from ssbt.experiments.specs import ExperimentSpec
from ssbt.experiments.stats import compute_confidence_stats
from ssbt.strategy.base import Strategy
from ssbt.core.events import OrderType, Side, Bar, Order, OrderStatus
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.audit import AuditLogger
from ssbt.analytics.terminal import (
    display_experiment_summary,
    display_backtest_summary,
    display_audit_status,
)


def fetch_commodity_polars(ticker: str, period: str = "2y", interval: str = "1d") -> pl.DataFrame:
    """Download commodity data from yfinance and convert to SSBT-compatible Polars DataFrame."""
    print(f"Downloading {ticker} from yfinance (period={period}, interval={interval})...")
    df_pd = yf.download(ticker, period=period, interval=interval, progress=False)
    if df_pd.empty:
        raise ValueError(f"No data returned for {ticker}")

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index().dropna(subset=["Close", "Volume"])
    timestamps = (pd.to_datetime(df_pd.iloc[:, 0]).astype("int64")).values

    return pl.DataFrame({
        "timestamp": timestamps,
        "symbol": [ticker] * len(timestamps),
        "open": df_pd["Open"].values.astype(float),
        "high": df_pd["High"].values.astype(float),
        "low": df_pd["Low"].values.astype(float),
        "close": df_pd["Close"].values.astype(float),
        "volume": df_pd["Volume"].values.astype(float),
    }).sort("timestamp")


def run_event_study(commodity_data: dict[str, pl.DataFrame]):
    event_plugin = VolumeSpike()
    outcome_plugin = ForwardReturn()
    logger = AuditLogger(verbose=False)

    for ticker, df in commodity_data.items():
        events = event_plugin.compute_events(df, {"window": 20, "multiplier": 2.5})
        if events.is_empty():
            continue

        outcomes = outcome_plugin.compute_outcomes(df, events, {"horizons": [1, 5, 10, 20, 50]})
        if outcomes.is_empty():
            continue

        # Audit check: Verify causal integrity and anti-lookahead timestamp ordering
        audit_report = logger.generate_report(events=events, outcomes=outcomes)
        display_audit_status(audit_report)

        spec = ExperimentSpec.from_dict({
            "version": 1,
            "experiment": {"name": f"study_{ticker}", "type": "event_study"},
            "dataset": {"source": "yfinance", "symbol": ticker},
            "events": [{"name": "volume_spike"}],
            "outcomes": [{"name": "forward_return"}],
            "analysis": {"confidence": {"method": "bootstrap", "iterations": 1000, "ci": 0.95}}
        })
        ci_stats = compute_confidence_stats(outcomes, spec)

        result_payload = {
            "events": events,
            "outcomes": outcomes,
            "statistics": ci_stats,
        }
        display_experiment_summary(result_payload, title=f"Event Study Results: {ticker}")


class VolumeSpikeSwingStrategy(Strategy):
    def __init__(self, window: int = 20, mult: float = 2.5, trail_pct: float = 0.03, qty: float = 10.0):
        super().__init__()
        self.window = window
        self.mult = mult
        self.trail_pct = trail_pct
        self.qty = qty
        self.volumes = []
        self.closes = []
        self.in_position = False

    def on_bar(self, bar: Bar, engine) -> None:
        self.volumes.append(bar.volume)
        self.closes.append(bar.close)

        if len(self.volumes) < self.window:
            return

        vol_window = self.volumes[-self.window:-1]
        avg_vol = np.mean(vol_window) if len(vol_window) > 0 else 0.0

        is_spike = bar.volume >= self.mult * avg_vol
        is_breakout = bar.close > np.mean(self.closes[-self.window:])

        if is_spike and is_breakout and not self.in_position:
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, self.qty))
            trail_offset = bar.close * self.trail_pct
            engine.submit_order(Order(
                id=0,
                symbol=bar.symbol,
                side=Side.SELL,
                type=OrderType.TRAILING_STOP,
                qty=self.qty,
                trail_offset=trail_offset,
                status=OrderStatus.PENDING
            ))
            self.in_position = True


def run_swing_backtests(commodity_data: dict[str, pl.DataFrame]):
    adapter = BacktestAdapter(initial_cash=100_000.0)
    logger = AuditLogger(verbose=False)

    for ticker, df in commodity_data.items():
        feed = InMemoryFeed(df, symbol=ticker)
        strategy = VolumeSpikeSwingStrategy(window=20, mult=2.5, trail_pct=0.03, qty=10.0)

        res = adapter.run_backtest(feed, strategy)
        
        # Verify backtest execution causality
        audit_report = logger.generate_report(backtest_result=res["raw_result"])
        display_audit_status(audit_report)
        display_backtest_summary(res["metrics"], res["trades"])


def main():
    tickers = ["GC=F", "SI=F", "CL=F"]
    commodity_data = {}

    for ticker in tickers:
        try:
            df = fetch_commodity_polars(ticker, period="1y", interval="1d")
            commodity_data[ticker] = df
        except Exception as e:
            print(f"Warning: Could not fetch {ticker}: {e}")

    if not commodity_data:
        print("No commodity data fetched.")
        return 1

    run_event_study(commodity_data)
    run_swing_backtests(commodity_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
