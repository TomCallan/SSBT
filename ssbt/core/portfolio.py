"""Portfolio tracker — positions, cash, equity curve, trade log (round-trips).

Optimisations:
  - Pre-allocated NumPy equity curve (no per-bar list append)
  - Single-symbol fast path (no dict lookup per bar)
  - Inlined equity calculation
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ssbt.core.events import Fill, Side, Trade


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0

    def is_flat(self) -> bool:
        return self.qty == 0.0


@dataclass(slots=True)
class _OpenFill:
    """Tracks an unfilled round-trip leg waiting to be closed."""
    order_id: int
    symbol: str
    side: Side
    qty: float
    price: float
    commission: float
    timestamp: int


class Portfolio:
    """Tracks cash, positions, equity curve, and round-trip trades.

    Equity = cash + market_value(positions).
    Mark-to-market happens on every update_prices() call (per bar/tick).
    """

    def __init__(self, initial_cash: float = 100_000.0, n_bars: int = 0):
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._trades: list[Trade] = []
        self._open_legs: dict[str, list[_OpenFill]] = {}
        self._all_fills: list[Fill] = []

        # Pre-allocated equity curve: [timestamp, equity] per bar
        self._equity_ts = np.empty(n_bars, dtype=np.int64) if n_bars else None
        self._equity_val = np.empty(n_bars, dtype=np.float64) if n_bars else None
        self._equity_idx = 0
        self._n_bars = n_bars

        # Fallback list if not pre-allocated
        self._equity_list: list[tuple[int, float]] = []

        self._last_prices: dict[str, float] = {}
        self._current_ts: int = 0

        # Single-symbol fast path
        self._single_symbol: str | None = None
        self._single_position: Position | None = None
        self._single_legs: list[_OpenFill] = []

    def set_single_symbol(self, symbol: str) -> None:
        """Enable single-symbol fast path — avoids dict lookups per bar."""
        self._single_symbol = symbol
        pos = Position(symbol=symbol)
        self._positions[symbol] = pos
        self._single_position = pos
        self._open_legs[symbol] = self._single_legs

    @property
    def positions(self) -> dict[str, Position]:
        return self._positions

    @property
    def trades(self) -> list[Trade]:
        return self._trades

    @property
    def fills(self) -> list[Fill]:
        return self._all_fills

    @property
    def equity_curve(self) -> np.ndarray:
        """Return equity curve as (n, 2) array."""
        if self._equity_val is not None and self._equity_idx > 0:
            n = self._equity_idx
            return np.column_stack((self._equity_ts[:n], self._equity_val[:n]))
        return np.array(self._equity_list, dtype=np.float64).reshape(-1, 2)

    def apply_fill(self, fill: Fill) -> None:
        """Process a fill: update cash, position, track round-trips."""
        self._all_fills.append(fill)

        # Use fast path if single-symbol
        if self._single_symbol == fill.symbol:
            pos = self._single_position
            legs = self._single_legs
        else:
            if fill.symbol not in self._positions:
                self._positions[fill.symbol] = Position(symbol=fill.symbol)
            pos = self._positions[fill.symbol]
            if fill.symbol not in self._open_legs:
                self._open_legs[fill.symbol] = []
            legs = self._open_legs[fill.symbol]

        # Cash adjustment
        notional = fill.price * fill.qty
        if fill.side == Side.BUY:
            self.cash -= notional + fill.commission
        else:
            self.cash += notional - fill.commission

        # Position update
        if fill.side == Side.BUY:
            new_qty = pos.qty + fill.qty
            if new_qty != 0:
                pos.avg_price = (pos.avg_price * pos.qty + fill.price * fill.qty) / new_qty
            pos.qty = new_qty
        else:
            pos.qty -= fill.qty

        # Round-trip tracking: match against opposite-side legs FIFO
        remaining = fill.qty
        new_legs: list[_OpenFill] = []
        pnl = 0.0
        entry_leg = None
        entry_price = 0.0
        entry_time = 0
        total_closed_qty = 0.0

        for leg in legs:
            if remaining <= 0:
                new_legs.append(leg)
                continue

            if leg.side != fill.side:
                close_qty = min(remaining, leg.qty)
                if fill.side == Side.BUY:
                    leg_pnl = (leg.price - fill.price) * close_qty
                else:
                    leg_pnl = (fill.price - leg.price) * close_qty
                pnl += leg_pnl
                remaining -= close_qty
                total_closed_qty += close_qty

                if entry_leg is None:
                    entry_leg = leg
                    entry_price = leg.price
                    entry_time = leg.timestamp

                leg.qty -= close_qty
                if leg.qty > 0:
                    new_legs.append(leg)
            else:
                new_legs.append(leg)

        if total_closed_qty > 0:
            self._trades.append(Trade(
                symbol=fill.symbol,
                entry_time=entry_time,
                exit_time=fill.timestamp,
                entry_price=entry_price,
                exit_price=fill.price,
                qty=total_closed_qty,
                side=entry_leg.side,
                pnl=pnl,
                commission=fill.commission,
            ))

        if remaining > 0:
            new_legs.append(_OpenFill(
                order_id=fill.order_id,
                symbol=fill.symbol,
                side=fill.side,
                qty=remaining,
                price=fill.price,
                commission=fill.commission,
                timestamp=fill.timestamp,
            ))

        # Update legs in place
        if self._single_symbol == fill.symbol:
            self._single_legs[:] = new_legs
        else:
            self._open_legs[fill.symbol] = new_legs

    def update_prices(self, symbol: str, price: float, timestamp: int) -> None:
        """Mark-to-market: update last known price, record equity."""
        self._last_prices[symbol] = price
        self._current_ts = timestamp

        # Inline equity calculation
        if self._single_position is not None and symbol == self._single_symbol:
            pos = self._single_position
            equity = self.cash + (pos.qty * price if pos.qty != 0 else 0.0)
        else:
            equity = self.cash
            for sym, pos in self._positions.items():
                if pos.qty != 0:
                    p = self._last_prices.get(sym, pos.avg_price)
                    equity += pos.qty * p

        # Write to pre-allocated array or fallback list
        if self._equity_val is not None and self._equity_idx < self._n_bars:
            self._equity_ts[self._equity_idx] = timestamp
            self._equity_val[self._equity_idx] = equity
            self._equity_idx += 1
        else:
            self._equity_list.append((timestamp, equity))

    def market_value(self) -> float:
        """Current total equity (cash + positions at last mark)."""
        if self._single_position is not None:
            pos = self._single_position
            price = self._last_prices.get(self._single_symbol, pos.avg_price) if self._single_symbol else pos.avg_price
            return self.cash + (pos.qty * price if pos.qty != 0 else 0.0)
        equity = self.cash
        for sym, pos in self._positions.items():
            if pos.qty != 0:
                price = self._last_prices.get(sym, pos.avg_price)
                equity += pos.qty * price
        return equity

    def unrealised_pnl(self) -> float:
        if self._single_position is not None:
            pos = self._single_position
            price = self._last_prices.get(self._single_symbol, pos.avg_price) if self._single_symbol else pos.avg_price
            return (price - pos.avg_price) * pos.qty if pos.qty != 0 else 0.0
        total = 0.0
        for sym, pos in self._positions.items():
            if pos.qty != 0:
                price = self._last_prices.get(sym, pos.avg_price)
                total += (price - pos.avg_price) * pos.qty
        return total

    def realised_pnl(self) -> float:
        return sum(t.pnl - t.commission for t in self._trades)
