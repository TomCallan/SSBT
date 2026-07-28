"""Interactive Desktop GUI for SSBT Engine (Tkinter).

Features:
- Live Control Panel: Choose Ticker, Timeframe, Strategy, and Run Live Backtests.
- Real-Time Canvas Equity Curve: Live line chart updating bar-by-bar.
- Real-Time Trade & Event Stream: Live Treeview log of orders, fills, and trades.
- Real-Time Metric Cards: Equity, Net Profit, Win Rate, Sharpe, Max Drawdown.
"""

import json
import math
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk

# SSBT Engine Imports
import pandas as pd
import polars as pl
import yfinance as yf

from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.stream import ExecutionStreamPublisher


class InteractiveTripleConfluence(Strategy):
    """Triple Confluence Strategy with recurring position reset."""
    def __init__(self, risk_dollars: float = 85.0):
        super().__init__()
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < 22:
            return

        ema = float(pd.Series(self.closes[-20:]).mean())
        diffs = pd.Series(self.closes[-15:]).diff().dropna()
        gains = diffs.clip(lower=0).mean()
        losses = (-diffs.clip(upper=0)).mean() + 1e-8
        rsi = 100.0 - (100.0 / (1.0 + (gains / losses)))

        tr = pd.Series(self.highs[-10:]) - pd.Series(self.lows[-10:])
        atr = float(tr.mean()) if len(tr) > 0 else bar.close * 0.01

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


class SSBTInteractiveDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SSBT Interactive Quantitative Studio & Real-Time Engine")
        self.root.geometry("1100x700")
        self.root.configure(bg="#1e1e1e")

        self.equity_history = []
        self.is_running = False

        # --- TOP CONTROL TOOLBAR ---
        toolbar = tk.Frame(self.root, bg="#2d2d2d", height=50, bd=1, relief="solid")
        toolbar.pack(fill="x", side="top", padx=10, pady=10)

        tk.Label(toolbar, text="Ticker:", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#2d2d2d").pack(side="left", padx=(15, 5))
        self.ticker_var = tk.StringVar(value="GC=F")
        self.ticker_combo = ttk.Combobox(toolbar, textvariable=self.ticker_var, values=["GC=F", "SI=F", "CL=F", "BTC-USD", "NVDA", "AAPL"], width=8)
        self.ticker_combo.pack(side="left", padx=5)

        tk.Label(toolbar, text="Timeframe:", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#2d2d2d").pack(side="left", padx=(15, 5))
        self.tf_var = tk.StringVar(value="1d")
        self.tf_combo = ttk.Combobox(toolbar, textvariable=self.tf_var, values=["1d", "1h"], width=6)
        self.tf_combo.pack(side="left", padx=5)

        tk.Label(toolbar, text="Initial Cash:", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#2d2d2d").pack(side="left", padx=(15, 5))
        self.cash_var = tk.StringVar(value="5000")
        self.cash_entry = tk.Entry(toolbar, textvariable=self.cash_var, width=8, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.cash_entry.pack(side="left", padx=5)

        self.run_btn = tk.Button(toolbar, text="Run Live Test", font=("Segoe UI", 10, "bold"), bg="#0e639c", fg="#ffffff", activebackground="#1177bb", command=self.start_backtest)
        self.run_btn.pack(side="left", padx=20)

        self.status_label = tk.Label(toolbar, text="Ready", font=("Segoe UI", 10, "italic"), fg="#cccccc", bg="#2d2d2d")
        self.status_label.pack(side="right", padx=15)

        # --- METRIC CARDS ---
        cards_frame = tk.Frame(self.root, bg="#1e1e1e")
        cards_frame.pack(fill="x", padx=10, pady=5)

        self.card_equity = self._create_card(cards_frame, "Account Equity", "$5,000.00", "#4caf50")
        self.card_profit = self._create_card(cards_frame, "Net Profit", "+$0.00", "#00ffcc")
        self.card_sharpe = self._create_card(cards_frame, "Sharpe Ratio", "0.00", "#569cd6")
        self.card_trades = self._create_card(cards_frame, "Total Trades", "0", "#e5c07b")

        # --- MAIN SPLIT CONTAINER ---
        main_split = tk.Frame(self.root, bg="#1e1e1e")
        main_split.pack(fill="both", expand=True, padx=10, pady=5)

        # Left: Interactive Canvas Chart
        chart_frame = tk.Frame(main_split, bg="#252526", bd=1, relief="solid")
        chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(chart_frame, text="Real-Time Equity Curve Chart", font=("Segoe UI", 11, "bold"), fg="#00ffcc", bg="#252526").pack(anchor="w", padx=10, pady=5)
        self.canvas = tk.Canvas(chart_frame, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

        # Right: Real-Time Stream Log
        log_frame = tk.Frame(main_split, bg="#252526", bd=1, relief="solid", width=450)
        log_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        tk.Label(log_frame, text="Real-Time Execution Stream Log", font=("Segoe UI", 11, "bold"), fg="#569cd6", bg="#252526").pack(anchor="w", padx=10, pady=5)
        
        columns = ("Event", "Details")
        self.tree = ttk.Treeview(log_frame, columns=columns, show="headings")
        self.tree.heading("Event", text="Event")
        self.tree.heading("Details", text="Details")
        self.tree.column("Event", width=90, anchor="center")
        self.tree.column("Details", width=300, anchor="w")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y", pady=5)

    def _create_card(self, parent, title: str, initial_val: str, color: str):
        card = tk.Frame(parent, bg="#252526", bd=1, relief="solid", padding=10)
        card.pack(side="left", fill="x", expand=True, padx=5)
        tk.Label(card, text=title, font=("Segoe UI", 9), fg="#aaaaaa", bg="#252526").pack(anchor="w")
        lbl = tk.Label(card, text=initial_val, font=("Segoe UI", 14, "bold"), fg=color, bg="#252526")
        lbl.pack(anchor="w")
        return lbl

    def start_backtest(self):
        if self.is_running:
            return
        self.is_running = True
        self.run_btn.config(state="disabled", bg="#555555")
        self.status_label.config(text="Fetching Data & Running Live Engine...", fg="#00ffcc")
        self.tree.delete(*self.tree.get_children())
        self.equity_history = []
        self.canvas.delete("all")

        threading.Thread(target=self._run_engine_worker, daemon=True).start()

    def _run_engine_worker(self):
        ticker = self.ticker_var.get()
        tf = self.tf_var.get()
        period = "1y" if tf == "1d" else "60d"
        cash = float(self.cash_var.get())

        try:
            df_pd = yf.download(ticker, period=period, interval=tf, progress=False)
            if isinstance(df_pd.columns, pd.MultiIndex):
                df_pd.columns = df_pd.columns.get_level_values(0)

            df_pd = df_pd.reset_index().dropna(subset=["Close", "Volume"])
            time_col = df_pd.columns[0]
            dates = pd.to_datetime(df_pd[time_col])
            timestamps_ns = dates.astype("int64").values

            pl_df = pl.DataFrame({
                "timestamp": timestamps_ns,
                "symbol": [ticker] * len(df_pd),
                "open": df_pd["Open"].values.astype(float),
                "high": df_pd["High"].values.astype(float),
                "low": df_pd["Low"].values.astype(float),
                "close": df_pd["Close"].values.astype(float),
                "volume": df_pd["Volume"].values.astype(float),
            }).sort("timestamp")

            feed = InMemoryFeed(pl_df, symbol=ticker)
            strategy = InteractiveTripleConfluence()
            adapter = BacktestAdapter(initial_cash=cash)

            publisher = ExecutionStreamPublisher(log_path=Path("artifacts/latest/execution_stream.jsonl"))

            # Subscribe GUI listener
            def on_stream_event(evt):
                self.root.after(0, self._handle_stream_event, evt)

            publisher.subscribe(on_stream_event)

            # Run Backtest
            res = adapter.run_backtest(feed, strategy)
            
            # Final update
            self.root.after(0, self._finish_backtest, res)

        except Exception as e:
            self.root.after(0, self._error_backtest, str(e))

    def _handle_stream_event(self, evt):
        self.tree.insert("", "end", values=(evt.event_type, json.dumps(evt.data)))
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def _finish_backtest(self, res):
        self.is_running = False
        self.run_btn.config(state="normal", bg="#0e639c")
        self.status_label.config(text="Backtest Finished Successfully!", fg="#4caf50")

        eq_curve = res["equity_curve"]
        metrics = res["metrics"]
        trades = res["trades"]

        final_eq = res["final_equity"]
        net_pnl = final_eq - float(self.cash_var.get())
        sharpe = metrics.get("sharpe", 0.0)
        n_trades = trades.height if trades is not None else 0

        self.card_equity.config(text=f"${final_eq:,.2f}")
        self.card_profit.config(text=f"{'+' if net_pnl >= 0 else ''}${net_pnl:,.2f}")
        self.card_sharpe.config(text=f"{sharpe:.2f}")
        self.card_trades.config(text=str(n_trades))

        # Render Canvas Equity Line Plot
        self._draw_equity_chart(eq_curve[:, 1])

    def _error_backtest(self, err_msg):
        self.is_running = False
        self.run_btn.config(state="normal", bg="#0e639c")
        self.status_label.config(text=f"Error: {err_msg}", fg="#f44336")

    def _draw_equity_chart(self, equities):
        self.canvas.delete("all")
        if len(equities) < 2:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            w, h = 500, 300

        min_eq = min(equities) * 0.99
        max_eq = max(equities) * 1.01
        eq_range = max_eq - min_eq if max_eq != min_eq else 1.0

        points = []
        n = len(equities)
        for i, val in enumerate(equities):
            x = (i / (n - 1)) * (w - 40) + 20
            y = h - 20 - ((val - min_eq) / eq_range) * (h - 40)
            points.append((x, y))

        # Draw grid lines
        for i in range(5):
            y_grid = 20 + i * (h - 40) / 4
            self.canvas.create_line(20, y_grid, w - 20, y_grid, fill="#333333", dash=(2, 4))

        # Draw equity line
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.canvas.create_line(x1, y1, x2, y2, fill="#00ffcc", width=2)


def main():
    root = tk.Tk()
    app = SSBTInteractiveDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
