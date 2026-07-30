"""Run Volatility-Adjusted Mean Reversion & StatArb Trailing Stop Sweeps & Walk-Forward Analysis."""

from __future__ import annotations
import json
import numpy as np
import polars as pl

from scripts.download_yfinance import download_yfinance_polars, build_ssbt_feed_from_yfinance
from ssbt.data.feed import InMemoryFeed
from ssbt.optimization.space import ParameterSpace, ChoiceParam
from ssbt.optimization.grid_search import GridSearchOptimizer
from ssbt.optimization.walk_forward import WalkForwardOptimizer
from ssbt.analytics.robustness import deflated_sharpe_ratio, probability_of_backtest_overfitting
from strategies_vault.volatility_mean_reversion import VolatilityAdjustedMeanReversionStrategy
from strategies_vault.statarb_pairs import StatArbPairsStrategy


def calc_max_dd(equity_curve: np.ndarray) -> tuple[float, float]:
    """Calculate absolute and percentage max drawdown from an equity curve."""
    if len(equity_curve) < 2:
        return 0.0, 0.0
    peak = np.maximum.accumulate(equity_curve)
    dd_dollars = peak - equity_curve
    dd_pct = dd_dollars / (peak + 1e-8)
    max_dd_dollars = float(np.max(dd_dollars))
    max_dd_pct = float(np.max(dd_pct)) * 100.0
    return max_dd_dollars, max_dd_pct


def run_volatility_statarb_pipeline(
    symbols: list[str] | None = None,
    intervals: list[str] | None = None,
    period: str = "6mo",
    initial_balance: float = 5000.0,
    max_risk_pct: float = 0.0015,
) -> dict:
    """Execute Volatility-Adjusted Mean Reversion & StatArb Pipeline with full PnL reporting.
    
    Each set receives its own isolated balance of $5,000 with a max risk of 0.15% ($7.50).
    Performs trailing stop parameter sweeps and rolling walk-forward analysis.
    """
    if symbols is None:
        symbols = ["AAPL", "MSFT", "GOOGL", "NVDA", "SPY"]
    if intervals is None:
        intervals = ["1d", "1h"]

    max_risk_dollars = initial_balance * max_risk_pct

    results = {
        "config": {
            "symbols": symbols,
            "intervals": intervals,
            "period": period,
            "initial_balance_per_set": initial_balance,
            "max_risk_pct": max_risk_pct,
            "max_risk_dollars": max_risk_dollars,
        },
        "mean_reversion_experiments": {},
        "statarb_experiments": {},
    }

    param_space = ParameterSpace([
        ChoiceParam(name="atr_mult", choices=[1.0, 1.5, 2.0, 2.5, 3.0, 3.5]),
        ChoiceParam(name="lookback", choices=[10, 20, 30]),
    ])

    print(f"\n==================================================================")
    print(f"  SSBT Volatility-Adjusted Mean Reversion & StatArb PnL Engine")
    print(f"  Balance per Set: ${initial_balance:,.2f} | Max Risk: {max_risk_pct*100:.2f}% (${max_risk_dollars:.2f})")
    print(f"==================================================================\n")

    for sym in symbols:
        for inter in intervals:
            key = f"{sym}_{inter}"
            print(f"--- Processing Instrument: {sym} ({inter}) ---")

            try:
                feed = build_ssbt_feed_from_yfinance(sym, period=period, interval=inter)
                n_bars = len(feed.df)
                if n_bars < 50:
                    print(f"Skipping {key}: Insufficient bars ({n_bars})")
                    continue

                # 1. Grid Search Parameter Sweep
                grid_search = GridSearchOptimizer(
                    strategy_cls=VolatilityAdjustedMeanReversionStrategy,
                    param_space=param_space,
                    initial_cash=initial_balance,
                )
                grid_res = grid_search.optimize(feed)

                best_trial = max(grid_res.all_trials, key=lambda x: x.get("sharpe", -999.0))
                best_is_net_pnl = float(best_trial.get("net_pnl", 0.0))
                best_is_trades = int(best_trial.get("total_trades", 0))

                # 2. Walk-Forward Rolling Analysis
                is_bars = min(120, max(30, int(n_bars * 0.6)))
                oos_bars = min(30, max(10, int(n_bars * 0.2)))

                wf_opt = WalkForwardOptimizer(
                    strategy_cls=VolatilityAdjustedMeanReversionStrategy,
                    param_space=param_space,
                    is_bars=is_bars,
                    oos_bars=oos_bars,
                    initial_cash=initial_balance,
                )
                wf_res = wf_opt.run(feed)

                # 3. Out-Of-Sample PnL Calculations
                oos_start_equity = float(wf_res.stitched_oos_equity[0])
                oos_final_equity = float(wf_res.stitched_oos_equity[-1])
                oos_net_pnl = oos_final_equity - oos_start_equity
                oos_return_pct = (oos_net_pnl / oos_start_equity) * 100.0
                max_dd_dollars, max_dd_pct = calc_max_dd(wf_res.stitched_oos_equity)

                results["mean_reversion_experiments"][key] = {
                    "symbol": sym,
                    "resolution": inter,
                    "total_bars": n_bars,
                    "initial_balance": initial_balance,
                    "best_trailing_stop_mult": grid_res.best_params.get("atr_mult"),
                    "best_lookback": grid_res.best_params.get("lookback"),
                    # In-Sample PnL
                    "best_in_sample_net_pnl_dollars": round(best_is_net_pnl, 2),
                    "best_in_sample_sharpe": round(float(grid_res.best_sharpe), 4),
                    "in_sample_total_trades": best_is_trades,
                    # Out-Of-Sample PnL Metrics
                    "oos_final_equity_dollars": round(oos_final_equity, 2),
                    "oos_net_pnl_dollars": round(oos_net_pnl, 2),
                    "oos_return_pct": round(oos_return_pct, 2),
                    "oos_max_drawdown_dollars": round(max_dd_dollars, 2),
                    "oos_max_drawdown_pct": round(max_dd_pct, 2),
                    "overall_oos_sharpe": round(float(wf_res.overall_oos_sharpe), 4),
                    "wfe_ratio": round(float(wf_res.wfe_ratio), 4),
                    "dsr_score": round(float(grid_res.dsr_score), 4),
                    "pbo_score": round(float(grid_res.pbo_score), 4),
                }

                print(f"  Best Params: {grid_res.best_params}")
                print(f"  OOS Final Equity: ${oos_final_equity:,.2f} | Net PnL: ${oos_net_pnl:+,.2f} ({oos_return_pct:+.2f}%)")
                print(f"  OOS Max Drawdown: ${max_dd_dollars:,.2f} ({max_dd_pct:.2f}%) | OOS Sharpe: {wf_res.overall_oos_sharpe:.4f}\n")

            except Exception as e:
                print(f"Error processing {key}: {e}\n")

    # Statistical Arbitrage Pair Sweeps
    print("--- Processing Statistical Arbitrage Pair Sweeps ---")
    if len(symbols) >= 2:
        pair_syms = symbols[:2]
        try:
            feed_p1 = download_yfinance_polars(pair_syms[0], period=period, interval="1d")
            feed_p2 = download_yfinance_polars(pair_syms[1], period=period, interval="1d")

            min_len = min(len(feed_p1), len(feed_p2))
            spread_df = pl.DataFrame({
                "timestamp": feed_p1["timestamp"][:min_len],
                "open": feed_p1["open"][:min_len] - feed_p2["open"][:min_len] + 100.0,
                "high": feed_p1["high"][:min_len] - feed_p2["low"][:min_len] + 100.0,
                "low": feed_p1["low"][:min_len] - feed_p2["high"][:min_len] + 100.0,
                "close": feed_p1["close"][:min_len] - feed_p2["close"][:min_len] + 100.0,
                "volume": feed_p1["volume"][:min_len],
                "symbol": f"{pair_syms[0]}_{pair_syms[1]}_SPREAD",
            })
            pair_feed = InMemoryFeed(spread_df, symbol=f"{pair_syms[0]}_{pair_syms[1]}_SPREAD")

            grid_search_pair = GridSearchOptimizer(
                strategy_cls=StatArbPairsStrategy,
                param_space=param_space,
                initial_cash=initial_balance,
            )
            pair_grid_res = grid_search_pair.optimize(pair_feed)

            wf_opt_pair = WalkForwardOptimizer(
                strategy_cls=StatArbPairsStrategy,
                param_space=param_space,
                is_bars=80,
                oos_bars=25,
                initial_cash=initial_balance,
            )
            pair_wf_res = wf_opt_pair.run(pair_feed)

            oos_start_eq = float(pair_wf_res.stitched_oos_equity[0])
            oos_end_eq = float(pair_wf_res.stitched_oos_equity[-1])
            pair_pnl = oos_end_eq - oos_start_eq
            pair_ret = (pair_pnl / oos_start_eq) * 100.0
            pair_dd_dollars, pair_dd_pct = calc_max_dd(pair_wf_res.stitched_oos_equity)

            pair_key = f"{pair_syms[0]}_{pair_syms[1]}"
            results["statarb_experiments"][pair_key] = {
                "pair": pair_key,
                "initial_balance": initial_balance,
                "best_trailing_stop_mult": pair_grid_res.best_params.get("atr_mult"),
                "best_lookback": pair_grid_res.best_params.get("lookback"),
                "oos_final_equity_dollars": round(oos_end_eq, 2),
                "oos_net_pnl_dollars": round(pair_pnl, 2),
                "oos_return_pct": round(pair_ret, 2),
                "oos_max_drawdown_dollars": round(pair_dd_dollars, 2),
                "oos_max_drawdown_pct": round(pair_dd_pct, 2),
                "overall_oos_sharpe": round(float(pair_wf_res.overall_oos_sharpe), 4),
                "wfe_ratio": round(float(pair_wf_res.wfe_ratio), 4),
                "dsr_score": round(float(pair_grid_res.dsr_score), 4),
            }

            print(f"StatArb Pair {pair_key}: Final Equity=${oos_end_eq:,.2f}, Net PnL=${pair_pnl:+,.2f} ({pair_ret:+.2f}%), OOS Sharpe={pair_wf_res.overall_oos_sharpe:.4f}\n")

        except Exception as e:
            print(f"Error processing StatArb Pair: {e}\n")

    return results


if __name__ == "__main__":
    res = run_volatility_statarb_pipeline(symbols=["AAPL", "MSFT", "SPY"], intervals=["1d", "1h"], period="6mo")
    print("=== SUMMARY OF PNL EXPERIMENTS ===")
    print(json.dumps(res, indent=2))
