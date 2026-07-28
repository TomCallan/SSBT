"""Statistical overfitting defense suite for SSBT.

Implements:
1. Deflated Sharpe Ratio (DSR): Adjusts observed Sharpe ratio for multiple testing, data length, skewness, and kurtosis.
2. Probability of Backtest Overfitting (PBO): Estimates the likelihood of in-sample overfitting leading to out-of-sample underperformance.
3. Monte Carlo Trade Resampling: Bootstraps trade sequence permutations to compute non-parametric confidence intervals for equity growth and drawdowns.
"""

from __future__ import annotations

import math
import numpy as np
from typing import Sequence, Any


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (CDF)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Standard normal percent point function (quantile / inverse CDF)."""
    if p <= 0.0:
        return -5.0
    if p >= 1.0:
        return 5.0
    # Rational approximation for inverse normal CDF (Wichura algorithm approximation)
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        val = q * (((((((2.5090809287301226727e1 * r + 3.3430575583588128105e2) * r + 6.7265770927008700853e2) * r + 4.5921953931549871457e2) * r + 1.3731693765509461125e2) * r + 1.9715903935665180570e1) * r + 1.3314173525810645288e0) * r + 3.3871328727963666080e-2) / (((((((5.2264952788528545610e1 * r + 2.8729085735721942670e2) * r + 3.9307895800092710610e2) * r + 2.1213794301586595867e2) * r + 5.3941960214247511077e1) * r + 6.8718108834014049330e0) * r + 4.2313330701600911252e-1) * r + 1.0)
    else:
        r = p if q < 0.0 else 1.0 - p
        r = math.sqrt(-math.log(r))
        if r <= 5.0:
            r = r - 1.6
            val = (((((((7.7454501427857140700e-4 * r + 2.2723844989269184580e-2) * r + 2.4178072517745061170e-1) * r + 1.2704582524523683820e0) * r + 3.6421455248356045470e0) * r + 5.7611074092871670840e0) * r + 4.6957535306975400040e0) * r + 1.5970156304071598440e0) / (((((((2.0178058163585040600e-4 * r + 1.3463866165432696660e-2) * r + 1.6361663852033735160e-1) * r + 9.5161049966779439200e-1) * r + 2.9234859039233071370e0) * r + 4.9080962254559075050e0) * r + 4.0955938538048325330e0) * r + 1.0)
        else:
            r = r - 5.0
            val = (((((((2.0103343992922881326e-7 * r + 2.7115555687434875782e-5) * r + 1.2426609473880784386e-3) * r + 2.6532189526576123093e-2) * r + 2.9656057182850489123e-1) * r + 1.7848265399172913376e0) * r + 5.4637849111641143699e0) * r + 6.6579046435011037772e0) / (((((((2.0442631033899397856e-8 * r + 1.4215117583164458887e-5) * r + 1.8463183175100546818e-3) * r + 7.8686913114561325910e-2) * r + 1.4875361290850614852e0) * r + 1.3692988092273580531e1) * r + 5.9983220955584944547e1) * r + 1.0)
        if q < 0.0:
            val = -val
    return val


def deflated_sharpe_ratio(
    observed_sharpe: float,
    var_sharpes: float,
    n_trials: int,
    returns_len: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Calculate Deflated Sharpe Ratio (DSR) (Bailey & Lopez de Prado, 2014).
    
    Adjusts observed Sharpe ratio for:
    - Multiple testing / trial count (n_trials)
    - Variance of Sharpe ratios across trials (var_sharpes)
    - Sample size / return series length (returns_len)
    - Non-normality (skewness and kurtosis)

    Returns:
        Probability (0.0 to 1.0) that observed Sharpe ratio is truly positive and skill-based.
    """
    if returns_len < 2 or n_trials < 1 or var_sharpes <= 0:
        return 0.5 if observed_sharpe > 0 else 0.0

    # Euler-Mascheroni constant
    em_gamma = np.euler_gamma

    # Expected maximum Sharpe ratio under the null hypothesis of zero skill
    z1 = _norm_ppf(1.0 - 1.0 / n_trials)
    z2 = _norm_ppf(1.0 - 1.0 / (n_trials * np.e))
    e_max_sharpe = np.sqrt(var_sharpes) * ((1.0 - em_gamma) * z1 + em_gamma * z2)

    # Standard error of the Sharpe ratio accounting for non-normality
    sr_std = np.sqrt(
        (1.0 + (0.5 * observed_sharpe**2) - (skew * observed_sharpe) + (((kurtosis - 3.0) / 4.0) * observed_sharpe**2))
        / (returns_len - 1.0)
    )

    if sr_std <= 0:
        return 0.5

    dsr_stat = (observed_sharpe - e_max_sharpe) / sr_std
    return float(_norm_cdf(dsr_stat))


def probability_of_backtest_overfitting(returns_matrix: np.ndarray, n_splits: int = 16) -> float:
    """Estimate Probability of Backtest Overfitting (PBO) across a parameter sweep matrix.
    
    Splits returns matrix into N sub-matrices, comparing in-sample best strategy
    against out-of-sample rank distribution.

    Returns:
        PBO probability between 0.0 and 1.0 (PBO > 0.5 indicates high overfitting risk).
    """
    if returns_matrix.ndim != 2 or returns_matrix.shape[0] < 20 or returns_matrix.shape[1] < 2:
        return 0.0

    T, N = returns_matrix.shape
    half_T = T // 2

    overfit_count = 0
    total_permutations = 50

    rng = np.random.default_rng(42)
    indices = np.arange(T)

    for _ in range(total_permutations):
        is_idx = rng.choice(indices, size=half_T, replace=False)
        oos_idx = np.setdiff1d(indices, is_idx)

        is_returns = returns_matrix[is_idx, :]
        oos_returns = returns_matrix[oos_idx, :]

        is_sharpes = np.mean(is_returns, axis=0) / (np.std(is_returns, axis=0) + 1e-8)
        best_is_strategy = int(np.argmax(is_sharpes))

        oos_sharpes = np.mean(oos_returns, axis=0) / (np.std(oos_returns, axis=0) + 1e-8)
        median_oos_sharpe = np.median(oos_sharpes)

        if oos_sharpes[best_is_strategy] < median_oos_sharpe:
            overfit_count += 1

    return float(overfit_count / total_permutations)


def monte_carlo_trade_permutation(
    trade_pnls: Sequence[float],
    initial_cash: float = 5000.0,
    n_iterations: int = 1000,
    seed: int = 42,
) -> dict[str, float]:
    """Perform Monte Carlo trade sequence resampling to estimate confidence bounds on equity growth and drawdowns."""
    if len(trade_pnls) == 0:
        return {
            "median_final_equity": initial_cash,
            "ci_95_lower": initial_cash,
            "ci_95_upper": initial_cash,
            "max_dd_95": 0.0,
        }

    pnls_arr = np.array(trade_pnls, dtype=np.float64)
    rng = np.random.default_rng(seed)

    final_equities = np.empty(n_iterations, dtype=np.float64)
    max_dds = np.empty(n_iterations, dtype=np.float64)

    for i in range(n_iterations):
        resampled_pnls = rng.choice(pnls_arr, size=len(pnls_arr), replace=True)
        eq_curve = initial_cash + np.cumsum(resampled_pnls)
        final_equities[i] = eq_curve[-1]

        peak = np.maximum.accumulate(np.insert(eq_curve, 0, initial_cash))
        dd = (eq_curve - peak[1:]) / peak[1:]
        max_dds[i] = float(np.min(dd)) if len(dd) > 0 else 0.0

    return {
        "median_final_equity": float(np.median(final_equities)),
        "ci_95_lower": float(np.percentile(final_equities, 2.5)),
        "ci_95_upper": float(np.percentile(final_equities, 97.5)),
        "max_dd_95": float(np.percentile(max_dds, 5.0)),
    }
