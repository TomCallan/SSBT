"""Backtest engine — single-pass event loop tying feed, strategy, matching, portfolio.

Usage:
    feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
    strategy = MyStrategy()
    engine = Engine(feed, strategy)
    results = engine.run()
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ssbt.core.events import Bar, BidAsk, Fill, Order
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.data.feed import ParquetFeed


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
        feed: ParquetFeed,
        strategy=None,  # Avoid circular import; type hint as 'Strategy' in __init__.py
        initial_cash: float = 100_000.0,
        matching: MatchingEngine | None = None,
    ):
        self.feed = feed
        self.strategy = strategy
        self.matching = matching or MatchingEngine()
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self._event_count = 0

    def submit_order(self, order: Order) -> Order:
        """Delegate: submit order to matching engine."""
        return self.matching.submit(order)

    def run(self) -> BacktestResult:
        """Execute the backtest. Returns BacktestResult."""
        if self.strategy is None:
            raise ValueError("No strategy set on engine")

        # Let strategy precompute on full data
        self.strategy.on_init(self)

        for event in self.feed:
            self._event_count += 1

            # 1. Process pending orders against this event FIRST
            #    (orders submitted on previous event fill on this one)
            if isinstance(event, Bar):
                fills = self.matching.process_bar(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                # 2. Notify strategy
                self.strategy.on_bar(event, self)

                # 3. Process orders submitted by strategy this tick
                fills = self.matching.process_bar(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                # 4. Mark-to-market
                self.portfolio.update_prices(event.symbol, event.close, event.timestamp)

            elif isinstance(event, BidAsk):
                fills = self.matching.process_bidask(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                self.strategy.on_bidask(event, self)

                fills = self.matching.process_bidask(event)
                for fill in fills:
                    self.portfolio.apply_fill(fill)

                mid = (event.bid + event.ask) / 2
                self.portfolio.update_prices(event.symbol, mid, event.timestamp)

        self.strategy.on_finish(self)

        equity = np.array(self.portfolio.equity_curve, dtype=np.float64).reshape(-1, 2)
        return BacktestResult(
            equity_curve=equity,
            fills=self.portfolio.fills,
            trades=self.portfolio.trades,
            portfolio=self.portfolio,
            n_events=self._event_count,
        )
