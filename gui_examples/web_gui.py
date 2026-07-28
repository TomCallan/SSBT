"""SSBT Interactive Real-Time Web Dashboard & Quantitative Studio.

Features:
- Control Panel: Choose Ticker, Timeframe, Cash, and Launch Live Backtests from the browser.
- Real-Time HTML5 Canvas Equity Chart: Dynamic line chart rendering account growth.
- Stream API & Metric Cards: Live Equity, Net Profit, Sharpe, Max Drawdown, and Trade Log.
"""

import json
import http.server
import socketserver
import threading
import urllib.parse
from pathlib import Path

# SSBT Engine Imports
import numpy as np
import pandas as pd
import polars as pl
import yfinance as yf

from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.stream import ExecutionStreamPublisher

PORT = 8080
STREAM_PATH = Path("artifacts/latest/execution_stream.jsonl")
LATEST_RESULT = {}

class WebTripleConfluence(Strategy):
    """Triple Confluence Strategy."""
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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSBT Interactive Web Dashboard & Real-Time Engine</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; background: #1e1e1e; padding: 15px 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .title { color: #00ffcc; font-size: 22px; font-weight: bold; }
        .toolbar { margin-top: 15px; background: #1e1e1e; padding: 15px 25px; border-radius: 8px; display: flex; gap: 20px; align-items: center; }
        label { font-weight: bold; font-size: 14px; }
        select, input, button { background: #2b2b2b; color: #fff; border: 1px solid #444; padding: 8px 14px; border-radius: 5px; font-size: 14px; }
        button { background: #0e639c; cursor: pointer; font-weight: bold; }
        button:hover { background: #1177bb; }
        .cards { display: flex; gap: 15px; margin-top: 15px; }
        .card { flex: 1; background: #1e1e1e; padding: 15px; border-radius: 8px; border: 1px solid #333; }
        .card-title { color: #888; font-size: 12px; font-weight: bold; text-transform: uppercase; }
        .card-val { font-size: 22px; font-weight: bold; margin-top: 5px; }
        .main-split { display: flex; gap: 15px; margin-top: 15px; }
        .chart-box { flex: 2; background: #1e1e1e; border-radius: 8px; padding: 15px; border: 1px solid #333; }
        .table-box { flex: 1; background: #1e1e1e; border-radius: 8px; padding: 15px; border: 1px solid #333; max-height: 400px; overflow-y: auto; }
        canvas { width: 100%; height: 320px; background: #181818; border-radius: 6px; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background: #2a2a2a; color: #00ffcc; padding: 10px; font-size: 12px; }
        td { padding: 8px; border-bottom: 1px solid #2a2a2a; font-family: monospace; font-size: 12px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">SSBT Interactive Quantitative Studio</div>
        <div id="status-tag" style="color: #4caf50; font-weight: bold;">Engine Ready</div>
    </div>

    <div class="toolbar">
        <div>
            <label>Ticker:</label>
            <select id="ticker-select">
                <option value="GC=F">Gold (GC=F)</option>
                <option value="SI=F">Silver (SI=F)</option>
                <option value="CL=F">Crude Oil (CL=F)</option>
                <option value="BTC-USD">Bitcoin (BTC-USD)</option>
                <option value="NVDA">NVIDIA (NVDA)</option>
            </select>
        </div>
        <div>
            <label>Timeframe:</label>
            <select id="tf-select">
                <option value="1d">1 Day (1d)</option>
                <option value="1h">1 Hour (1h)</option>
            </select>
        </div>
        <div>
            <label>Cash ($):</label>
            <input type="number" id="cash-input" value="5000" style="width: 90px;">
        </div>
        <button id="run-btn" onclick="runBacktest()">Run Live Strategy Test</button>
    </div>

    <div class="cards">
        <div class="card"><div class="card-title">Account Equity</div><div class="card-val" id="val-equity" style="color:#4caf50;">$5,000.00</div></div>
        <div class="card"><div class="card-title">Net Profit</div><div class="card-val" id="val-profit" style="color:#00ffcc;">+$0.00</div></div>
        <div class="card"><div class="card-title">Sharpe Ratio</div><div class="card-val" id="val-sharpe" style="color:#569cd6;">0.00</div></div>
        <div class="card"><div class="card-title">Total Trades</div><div class="card-val" id="val-trades" style="color:#e5c07b;">0</div></div>
    </div>

    <div class="main-split">
        <div class="chart-box">
            <div style="font-weight:bold; margin-bottom:10px; color:#00ffcc;">Real-Time Equity Curve Chart</div>
            <canvas id="equity-canvas"></canvas>
        </div>
        <div class="table-box">
            <div style="font-weight:bold; margin-bottom:10px; color:#569cd6;">Execution Event Stream Log</div>
            <table>
                <thead>
                    <tr><th>Event</th><th>Details</th></tr>
                </thead>
                <tbody id="stream-tbody">
                    <tr><td colspan="2" style="text-align:center; color:#666;">No active strategy execution.</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function drawCanvasChart(equities) {
            const cvs = document.getElementById('equity-canvas');
            const ctx = cvs.getContext('2d');
            cvs.width = cvs.clientWidth;
            cvs.height = cvs.clientHeight;

            const w = cvs.width;
            const h = cvs.height;
            ctx.clearRect(0, 0, w, h);

            if (!equities || equities.length < 2) return;

            const minEq = Math.min(...equities) * 0.99;
            const maxEq = Math.max(...equities) * 1.01;
            const range = maxEq - minEq || 1.0;

            // Grid lines
            ctx.strokeStyle = '#2b2b2b';
            ctx.lineWidth = 1;
            for (let i = 1; i < 5; i++) {
                const y = (h / 5) * i;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }

            // Equity line
            ctx.strokeStyle = '#00ffcc';
            ctx.lineWidth = 2.5;
            ctx.beginPath();

            equities.forEach((val, i) => {
                const x = (i / (equities.length - 1)) * (w - 20) + 10;
                const y = h - 10 - ((val - minEq) / range) * (h - 20);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        function runBacktest() {
            const btn = document.getElementById('run-btn');
            const status = document.getElementById('status-tag');
            btn.disabled = true;
            btn.innerText = 'Running Engine...';
            status.innerText = 'Fetching Data & Running Strategy...';
            status.style.color = '#ff9800';

            const ticker = document.getElementById('ticker-select').value;
            const tf = document.getElementById('tf-select').value;
            const cash = document.getElementById('cash-input').value;

            fetch(`/api/run_test?ticker=${ticker}&tf=${tf}&cash=${cash}`)
                .then(res => res.json())
                .then(data => {
                    btn.disabled = false;
                    btn.innerText = 'Run Live Strategy Test';
                    status.innerText = 'Engine Finished!';
                    status.style.color = '#4caf50';

                    document.getElementById('val-equity').innerText = '$' + data.final_equity.toLocaleString(undefined, {minimumFractionDigits:2});
                    document.getElementById('val-profit').innerText = (data.net_profit >= 0 ? '+' : '') + '$' + data.net_profit.toLocaleString(undefined, {minimumFractionDigits:2});
                    document.getElementById('val-sharpe').innerText = data.sharpe.toFixed(2);
                    document.getElementById('val-trades').innerText = data.n_trades;

                    drawCanvasChart(data.equity_curve);
                    updateStreamLog();
                })
                .catch(err => {
                    btn.disabled = false;
                    btn.innerText = 'Run Live Strategy Test';
                    status.innerText = 'Error executing backtest';
                    status.style.color = '#f44336';
                });
        }

        function updateStreamLog() {
            fetch('/api/stream')
                .then(res => res.json())
                .then(events => {
                    const tbody = document.getElementById('stream-tbody');
                    if (events.length === 0) return;
                    tbody.innerHTML = '';
                    events.forEach(evt => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `<td><b>${evt.event_type}</b></td><td>${JSON.stringify(evt.data)}</td>`;
                        tbody.appendChild(tr);
                    });
                });
        }

        setInterval(updateStreamLog, 1000);
    </script>
</body>
</html>
"""


class InteractiveDashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))

        elif path == "/api/run_test":
            ticker = query.get("ticker", ["GC=F"])[0]
            tf = query.get("tf", ["1d"])[0]
            cash = float(query.get("cash", [5000])[0])

            period = "1y" if tf == "1d" else "60d"

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
                strategy = WebTripleConfluence()
                adapter = BacktestAdapter(initial_cash=cash)

                STREAM_PATH.parent.mkdir(parents=True, exist_ok=True)
                publisher = ExecutionStreamPublisher(log_path=STREAM_PATH)

                res = adapter.run_backtest(feed, strategy)
                metrics = res["metrics"]
                trades = res["trades"]
                eq_curve = res["equity_curve"][:, 1].tolist()

                net_profit = res["final_equity"] - cash
                response_data = {
                    "final_equity": res["final_equity"],
                    "net_profit": net_profit,
                    "sharpe": metrics.get("sharpe", 0.0),
                    "n_trades": trades.height if trades is not None else 0,
                    "equity_curve": eq_curve,
                }

                publisher.publish("STRATEGY_COMPLETED", int(timestamps_ns[-1]), response_data)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

        elif path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            events = []
            if STREAM_PATH.exists():
                try:
                    with open(STREAM_PATH, "r") as f:
                        for line in f:
                            if line.strip():
                                events.append(json.loads(line.strip()))
                except Exception:
                    pass
            self.wfile.write(json.dumps(events).encode("utf-8"))
        else:
            self.send_error(404)


def main():
    socketserver.TCPServer.allow_reuse_address = True
    port = PORT
    httpd = None

    for attempt_port in range(PORT, PORT + 10):
        try:
            httpd = socketserver.TCPServer(("", attempt_port), InteractiveDashboardHTTPHandler)
            port = attempt_port
            break
        except OSError:
            continue

    if httpd is None:
        print(f"Error: Could not bind server to ports {PORT}-{PORT+9}")
        return

    print(f"SSBT Interactive Web Dashboard running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web server.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
