"""Multi-symbol backtesting engine with dynamic portfolio allocation."""

from __future__ import annotations

import numpy as np

from ssbt.core.engine import BacktestResult, Engine
from ssbt.core.events import Bar, BidAsk, Fill, Order, OrderType, OrderStatus, Side
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.data.feed import InMemoryFeed, ParquetFeed
from ssbt.portfolio.allocation import AllocationFn, equal_weight


class MultiSymbolEngine:
    """Multi-symbol backtest engine with dynamic portfolio allocation.

    Flow per bar:
      1. Merge all symbol feeds by timestamp
      2. Per event: call strategy.on_bar() for that symbol
      3. Every rebalance_freq bars: call allocation_fn, rebalance to target weights
      4. Portfolio tracks all positions, equity = cash + sum(position_value)
    """

    def __init__(
        self,
        feeds: dict[str, ParquetFeed | InMemoryFeed],
        strategy=None,
        allocation_fn: AllocationFn = equal_weight,
        initial_cash: float = 100_000.0,
        rebalance_freq: int = 1,
        commission_bps: float = 1.0,
    ):
        self.feeds = feeds
        self.strategy = strategy
        self.allocation_fn = allocation_fn
        self.rebalance_freq = rebalance_freq
        self.commission_bps = commission_bps
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.matching = MatchingEngine()
        self._event_count = 0

        # Convert all feeds to InMemoryFeed for fast array access
        self._inmemory_feeds: dict[str, InMemoryFeed] = {}
        for sym, feed in feeds.items():
            if isinstance(feed, InMemoryFeed):
                self._inmemory_feeds[sym] = feed
            elif isinstance(feed, ParquetFeed):
                self._inmemory_feeds[sym] = feed.to_inmemory(sym)

    def submit_order(self, order: Order) -> Order:
        return self.matching.submit(order)

    def submit_oco(self, order_a: Order, order_b: Order):
        return self.matching.submit_oco(order_a, order_b)

    def cancel_order(self, order_id: int) -> bool:
        return self.matching.cancel(order_id)

    def run(self) -> BacktestResult:
        if self.strategy is None:
            raise ValueError("No strategy set")

        # Get all symbols and their arrays
        symbols = list(self._inmemory_feeds.keys())
        n_symbols = len(symbols)

        # Extract arrays per symbol
        symbol_arrays: dict[str, dict] = {}
        for sym in symbols:
            feed = self._inmemory_feeds[sym]
            symbol_arrays[sym] = feed.to_arrays()

        # Merge by timestamp — build sorted index
        # Collect (timestamp, symbol, bar_index) tuples
        all_events: list[tuple[int, str, int]] = []
        for sym in symbols:
            arr = symbol_arrays[sym]
            ts = arr["timestamp"]
            for i in range(len(ts)):
                all_events.append((int(ts[i]), sym, i))
        all_events.sort(key=lambda x: x[0])

        n_events = len(all_events)

        # Estimate total bars for equity pre-allocation
        self.portfolio = Portfolio(initial_cash=self.portfolio.initial_cash, n_bars=n_events)

        # Strategy init
        self.strategy.on_init(self)

        # Track last bar per symbol for allocation
        latest_bars: dict[str, Bar] = {}
        latest_prices: dict[str, float] = {}
        bar_count = 0

        # Pre-allocate Bar objects (one per symbol, reused)
        bar_cache: dict[str, Bar] = {
            sym: Bar(timestamp=0, symbol=sym, open=0, high=0, low=0, close=0, volume=0)
            for sym in symbols
        }

        prev_ts = None

        for ts, sym, idx in all_events:
            self._event_count += 1

            # Check if we've moved to a new timestamp
            if prev_ts is not None and ts != prev_ts:
                # New bar boundary — check rebalance
                bar_count += 1
                if bar_count % self.rebalance_freq == 0 and latest_bars:
                    weights = self.allocation_fn(latest_bars, ts)
                    fills = self.portfolio.rebalance(
                        weights, latest_prices, ts, self.commission_bps
                    )

            prev_ts = ts

            # Get bar data
            arr = symbol_arrays[sym]
            bar = bar_cache[sym]
            bar.timestamp = ts
            bar.open = float(arr["open"][idx])
            bar.high = float(arr["high"][idx])
            bar.low = float(arr["low"][idx])
            bar.close = float(arr["close"][idx])
            bar.volume = float(arr["volume"][idx])

            # Process pending orders for this symbol
            fills = self.matching.process_bar(bar)
            for fill in fills:
                self.portfolio.apply_fill(fill)

            # Notify strategy
            self.strategy.on_bar(bar, self)

            # Process new orders
            if self.matching.has_new:
                fills = self.matching.process_bar(bar)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

            # Update latest bar/price
            latest_bars[sym] = Bar(
                timestamp=bar.timestamp, symbol=bar.symbol,
                open=bar.open, high=bar.high, low=bar.low,
                close=bar.close, volume=bar.volume,
            )
            latest_prices[sym] = bar.close

            # Mark-to-market
            self.portfolio.update_prices(sym, bar.close, ts)

        # Final rebalance
        if latest_bars:
            weights = self.allocation_fn(latest_bars, prev_ts or 0)
            self.portfolio.rebalance(weights, latest_prices, prev_ts or 0, self.commission_bps)

        self.strategy.on_finish(self)

        equity = self.portfolio.equity_curve
        return BacktestResult(
            equity_curve=equity,
            fills=self.portfolio.fills,
            trades=self.portfolio.trades,
            portfolio=self.portfolio,
            n_events=self._event_count,
        )

    @property
    def symbols(self) -> list[str]:
        return list(self._inmemory_feeds.keys())

    def get_dataframe(self, symbol: str | None = None):
        if symbol is None:
            return {s: f.get_dataframe() for s, f in self._inmemory_feeds.items()}
        return self._inmemory_feeds[symbol].get_dataframe()
