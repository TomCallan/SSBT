"""Unit tests for SSBT universal plot and autoplot engine."""

import pytest
import numpy as np
import polars as pl
import ssbt
from ssbt.analytics.plots import plot, autoplot


def test_plot_dataframe(tmp_path):
    df = pl.DataFrame({
        "timestamp": [1000, 2000],
        "close": [100.0, 105.0],
    })
    res = plot(df, title="Test DataFrame Plot", save_path=str(tmp_path / "test_df_plot.png"))
    assert res is None  # Saved to file


def test_plot_array(tmp_path):
    arr = np.array([100.0, 102.0, 101.0, 105.0])
    res = plot(arr, title="Test Array Plot", save_path=str(tmp_path / "test_arr_plot.png"))
    assert res is None


def test_autoplot_decorator():
    @autoplot
    def generate_data():
        return np.array([10.0, 20.0, 30.0])

    res = generate_data()
    assert len(res) == 3
