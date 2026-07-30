"""Unit tests for SSBT Quickstart Ergonomics, Synthetic Bar Generator, and AI Agent Tooling."""

import json
from pathlib import Path
import polars as pl
import pytest

import ssbt
from ssbt.quick import quick_backtest, generate_synthetic_bars, strategy, QuickResult
from ssbt.agent import validate_strategy_script, get_agent_template
from ssbt.cli import main as cli_main


def test_generate_synthetic_bars():
    df = generate_synthetic_bars(n_bars=500, start_price=100.0, seed=123)
    assert isinstance(df, pl.DataFrame)
    assert df.height == 500
    assert set(df.columns) == {"timestamp", "open", "high", "low", "close", "volume"}
    assert (df["high"] >= df["low"]).all()


def test_quick_backtest_with_functional_strategy():
    data = generate_synthetic_bars(n_bars=100, seed=42)

    @strategy
    def momentum_strat(bar, engine):
        if bar.close > bar.open:
            engine.submit_order(ssbt.Strategy.market_order(bar.symbol, ssbt.Side.BUY, 1.0))
        elif bar.close < bar.open:
            engine.submit_order(ssbt.Strategy.market_order(bar.symbol, ssbt.Side.SELL, 1.0))

    result = quick_backtest(momentum_strat, data, symbol="ETH-USD", initial_cash=50_000.0)

    assert isinstance(result, QuickResult)
    assert result.symbol == "ETH-USD"
    assert result.n_events == 100
    assert isinstance(result.total_return, float)

    res_dict = result.to_dict()
    assert res_dict["symbol"] == "ETH-USD"
    assert "metrics" in res_dict

    res_json = result.to_json()
    assert "ETH-USD" in res_json


def test_quick_backtest_with_strategy_class():
    data = generate_synthetic_bars(n_bars=50, seed=42)

    class BuyHoldStrategy(ssbt.Strategy):
        def on_bar(self, bar, engine):
            if self.is_flat(engine, bar.symbol):
                engine.submit_order(self.market_order(bar.symbol, ssbt.Side.BUY, 10.0))

    result = quick_backtest(BuyHoldStrategy, data, symbol="AAPL")
    assert result.n_events == 50
    assert len(result.fills) > 0




def test_validate_strategy_script(tmp_path):
    valid_code = '''from ssbt import Strategy, Side, Bar, Engine

class MyStrategy(Strategy):
    def on_bar(self, bar: Bar, engine: Engine):
        pass
'''
    res = validate_strategy_script(valid_code)
    assert res["valid"] is True
    assert res["strategy_class"] == "MyStrategy"
    assert len(res["errors"]) == 0

    invalid_code = '''from ssbt import Strategy

class BrokenStrategy(Strategy):
    pass
'''
    res_broken = validate_strategy_script(invalid_code)
    assert res_broken["valid"] is False
    assert len(res_broken["errors"]) == 1

    lookahead_code = '''import polars as pl
df.shift(-1)
'''
    res_lookahead = validate_strategy_script(lookahead_code)
    assert len(res_lookahead["warnings"]) >= 1


def test_get_agent_template():
    tmpl = get_agent_template("sma_cross")
    assert "class SmaCrossStrategy" in tmpl
    assert "on_bar" in tmpl


def test_cli_commands(monkeypatch, capsys, tmp_path):
    # Test `ssbt template`
    monkeypatch.setattr("sys.argv", ["ssbt", "template", "sma_cross"])
    ret = cli_main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "SmaCrossStrategy" in captured.out

    # Test `ssbt validate`
    strat_file = tmp_path / "test_strat.py"
    strat_file.write_text(get_agent_template("sma_cross"), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["ssbt", "validate", str(strat_file)])
    ret = cli_main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "syntactically valid" in captured.out
