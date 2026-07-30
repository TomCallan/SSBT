"""Unit and integration tests for real-time LiveStreamFeed (WebSocket / REST ingestion)."""

import time
import threading
from pathlib import Path
import pytest

from ssbt import Engine, Strategy, Side, OrderStatus, LiveStreamFeed


class LiveTestStrategy(Strategy):
    def on_init(self, engine: Engine) -> None:
        self.bars_received = 0
        self.bids_received = 0
        self.ticks_received = 0

    def on_bar(self, bar, engine: Engine) -> None:
        self.bars_received += 1
        if self.bars_received == 1 and self.is_flat(engine, bar.symbol):
            order = self.market_order(bar.symbol, Side.BUY, qty=10)
            engine.submit_order(order)

    def on_bidask(self, bidask, engine: Engine) -> None:
        self.bids_received += 1
        if self.bids_received == 1 and self.is_flat(engine, bidask.symbol):
            order = self.market_order(bidask.symbol, Side.BUY, qty=5)
            engine.submit_order(order)

    def on_tick(self, tick, engine: Engine) -> None:
        self.ticks_received += 1


def test_live_stream_feed_bar_push():
    feed = LiveStreamFeed(symbols="BTCUSD", timeout=0.2)

    # Push sample bars
    feed.push_bar(timestamp=1000, symbol="BTCUSD", open=50000, high=50100, low=49900, close=50050, volume=1.5)
    feed.push_bar(timestamp=1001, symbol="BTCUSD", open=50050, high=50200, low=50000, close=50150, volume=2.0)
    feed.stop()

    strategy = LiveTestStrategy()
    engine = Engine(feed=feed, strategy=strategy, initial_cash=100_000.0)
    result = engine.run()

    assert strategy.bars_received == 2
    assert result.n_events == 2
    assert len(result.fills) > 0


def test_live_stream_feed_threaded_push():
    feed = LiveStreamFeed(symbols="ETHUSD", timeout=0.1)

    def producer():
        time.sleep(0.05)
        feed.push_bidask(timestamp=2000, symbol="ETHUSD", bid=3000.0, ask=3000.50)
        time.sleep(0.05)
        feed.push_bidask(timestamp=2001, symbol="ETHUSD", bid=3001.0, ask=3001.50)
        time.sleep(0.05)
        feed.stop()

    thread = threading.Thread(target=producer)
    thread.start()

    strategy = LiveTestStrategy()
    engine = Engine(feed=feed, strategy=strategy, initial_cash=50_000.0)
    result = engine.run()

    thread.join()

    assert strategy.bids_received == 2
    assert result.n_events == 2
    assert len(result.fills) == 1
    assert result.fills[0].symbol == "ETHUSD"


def test_live_stream_feed_push_tick():
    feed = LiveStreamFeed(symbols="AAPL", timeout=0.1)

    feed.push_tick(timestamp=3000, symbol="AAPL", price=150.0, volume=100.0)
    feed.push_tick(timestamp=3001, symbol="AAPL", price=151.0, volume=200.0)
    feed.stop()

    strategy = LiveTestStrategy()
    engine = Engine(feed=feed, strategy=strategy, initial_cash=10_000.0)
    result = engine.run()

    assert strategy.ticks_received == 2
    assert result.n_events == 2
