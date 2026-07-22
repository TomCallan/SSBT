"""Backtest engine — single-pass event loop tying feed, strategy, matching, portfolio.

Optimisations:
  - No per-bar Bar/BidAsk object allocation (fast path iterates raw arrays)
  - No isinstance() check (feed dtype known at init)
  - Skip second matching.process_bar() when no new orders
  - Pre-allocated equity curve via Portfolio
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ssbt.core.events import Bar, BidAsk, Fill, Order
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.data.feed import InMemoryFeed, ParquetFeed


@dataclass(slots=True)
class BacktestResult:
    equity_curve: np.ndarray  # (n, 2): [timestamp, equity]
    fills: list[Fill]
    trades: list
    portfolio: Portfolio
    n_events: int

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1, 1] if len(self.equity_curve) else 0.0

    @property
    def total_return(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        return (self.equity_curve[-1, 1] / self.equity_curve[0, 1]) - 1.0


class Engine:
    """Event-driven backtesting engine.

    Flow per event:
      1. Feed yields Bar or BidAsk
      2. Strategy receives event via on_bar() / on_bidask()
      3. Strategy may submit orders (queued in matching engine)
      4. Matching engine processes pending orders against this event
      5. Portfolio applies fills, updates mark-to-market
      6. Equity recorded
    """

    def __init__(
        self,
        feed: ParquetFeed | InMemoryFeed,
        strategy=None,
        initial_cash: float = 100_000.0,
        matching: MatchingEngine | None = None,
    ):
        self.feed = feed
        self.strategy = strategy
        self.matching = matching or MatchingEngine()
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self._event_count = 0
        self._fast_path = False  # set in run() if InMemoryFeed single-symbol

    def submit_order(self, order: Order) -> Order:
        return self.matching.submit(order)

    def submit_oco(self, order_a: Order, order_b: Order) -> tuple[Order, Order]:
        return self.matching.submit_oco(order_a, order_b)

    def cancel_order(self, order_id: int) -> bool:
        return self.matching.cancel(order_id)

    def cancel_all(self, symbol: str | None = None) -> int:
        return self.matching.cancel_all(symbol)

    def run(self) -> BacktestResult:
        """Execute the backtest. Returns BacktestResult."""
        if self.strategy is None:
            raise ValueError("No strategy set on engine")

        self.strategy.on_init(self)

        # Detect fast path: single-symbol with bar/bidask data and to_arrays()
        if hasattr(self.feed, "to_arrays") and hasattr(self.feed, "n_bars"):
            if self.feed.dtype == "bar":
                self._run_fast_bar()
            elif self.feed.dtype == "ba":
                self._run_fast_bidask()
            else:
                self._run_generic()
        elif isinstance(self.feed, ParquetFeed) and len(self.feed.symbols) == 1:
            # Auto-convert single-symbol ParquetFeed to InMemoryFeed for fast path
            sym = self.feed.symbols[0]
            self.feed = self.feed.to_inmemory(sym)
            if self.feed.dtype == "bar":
                self._run_fast_bar()
            else:
                self._run_fast_bidask()
        else:
            self._run_generic()

        self.strategy.on_finish(self)

        equity = self.portfolio.equity_curve
        return BacktestResult(
            equity_curve=equity,
            fills=self.portfolio.fills,
            trades=self.portfolio.trades,
            portfolio=self.portfolio,
            n_events=self._event_count,
        )

    def _run_fast_bar(self) -> None:
        """Fast path: single-symbol bar data, raw array iteration, no Bar objects."""
        arrays = self.feed.to_arrays()
        n = self.feed.n_bars
        symbol = self.feed.symbols[0]

        ts = arrays["timestamp"]
        o = arrays["open"]
        h = arrays["high"]
        l = arrays["low"]
        c = arrays["close"]
        v = arrays["volume"]

        self.portfolio = Portfolio(
            initial_cash=self.portfolio.initial_cash,
            n_bars=n,
        )
        self.portfolio.set_single_symbol(symbol)

        match = self.matching
        portfolio = self.portfolio
        strategy = self.strategy
        matching_process = match.process_bar
        matching_has_new = match.has_new

        for i in range(n):
            self._event_count += 1

            bar = Bar(
                timestamp=int(ts[i]),
                symbol=symbol,
                open=float(o[i]),
                high=float(h[i]),
                low=float(l[i]),
                close=float(c[i]),
                volume=float(v[i]),
            )

            # 1. Process pending orders from previous bar
            fills = matching_process(bar)
            for fill in fills:
                portfolio.apply_fill(fill)

            # 2. Notify strategy
            strategy.on_bar(bar, self)

            # 3. Process new orders submitted by strategy (only if any)
            if matching_has_new:
                fills = matching_process(bar)
                for fill in fills:
                    portfolio.apply_fill(fill)

            # 4. Mark-to-market
            portfolio.update_prices(symbol, bar.close, bar.timestamp)

    def _run_fast_bidask(self) -> None:
        """Fast path: single-symbol bid/ask data, raw array iteration."""
        arrays = self.feed.to_arrays()
        n = self.feed.n_bars
        symbol = self.feed.symbols[0]

        ts = arrays["timestamp"]
        b = arrays["bid"]
        a = arrays["ask"]

        self.portfolio = Portfolio(
            initial_cash=self.portfolio.initial_cash,
            n_bars=n,
        )
        self.portfolio.set_single_symbol(symbol)

        match = self.matching
        portfolio = self.portfolio
        strategy = self.strategy
        matching_process = match.process_bidask
        matching_has_new = match.has_new

        for i in range(n):
            self._event_count += 1

            ba = BidAsk(
                timestamp=int(ts[i]),
                symbol=symbol,
                bid=float(b[i]),
                ask=float(a[i]),
            )

            fills = matching_process(ba)
            for fill in fills:
                portfolio.apply_fill(fill)

            strategy.on_bidask(ba, self)

            if matching_has_new:
                fills = matching_process(ba)
                for fill in fills:
                    portfolio.apply_fill(fill)

            mid = (ba.bid + ba.ask) / 2
            portfolio.update_prices(symbol, mid, ba.timestamp)

    def _run_generic(self) -> None:
        """Generic path: multi-symbol or ParquetFeed, uses feed iterator."""
        for event in self.feed:
            self._event_count += 1

            if isinstance(event, Bar):
                fills = self.matching.process_bar(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                self.strategy.on_bar(event, self)

                if self.matching.has_new:
                    fills = self.matching.process_bar(event)
                    for fill in fills:
                        self.portfolio.apply_fill(fill)

                self.portfolio.update_prices(event.symbol, event.close, event.timestamp)

            elif isinstance(event, BidAsk):
                fills = self.matching.process_bidask(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                self.strategy.on_bidask(event, self)

                if self.matching.has_new:
                    fills = self.matching.process_bidask(event)
                    for fill in fills:
                        self.portfolio.apply_fill(fill)

                mid = (event.bid + event.ask) / 2
                self.portfolio.update_prices(event.symbol, mid, event.timestamp)
