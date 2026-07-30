from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import polars as pl

from ssbt.data.feed import InMemoryFeed
from ssbt.service.schemas import BacktestRequest


class ExecutionProfile(str, Enum):
    """Preset execution fidelity profiles for SSBT backtest execution."""
    FAST = "fast"
    BALANCED = "balanced"
    MAX_FIDELITY = "max_fidelity"


@dataclass
class ProfileConfig:
    """Configuration flags associated with a specific execution profile."""
    safe_mode: bool = True
    enable_microstructure: bool = False
    enable_overfitting_defense: bool = False
    enable_ipc_stream: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILE_CONFIGS: dict[ExecutionProfile, ProfileConfig] = {
    ExecutionProfile.FAST: ProfileConfig(
        safe_mode=True,
        enable_microstructure=False,
        enable_overfitting_defense=False,
        enable_ipc_stream=False,
    ),
    ExecutionProfile.BALANCED: ProfileConfig(
        safe_mode=True,
        enable_microstructure=True,
        enable_overfitting_defense=False,
        enable_ipc_stream=False,
    ),
    ExecutionProfile.MAX_FIDELITY: ProfileConfig(
        safe_mode=True,
        enable_microstructure=True,
        enable_overfitting_defense=True,
        enable_ipc_stream=True,
    ),
}


def apply_execution_profile(
    request: BacktestRequest, profile: ExecutionProfile | str
) -> BacktestRequest:
    """Apply execution profile configuration settings to a BacktestRequest."""
    if isinstance(profile, str):
        try:
            profile = ExecutionProfile(profile.lower())
        except ValueError:
            valid_profiles = [p.value for p in ExecutionProfile]
            raise ValueError(
                f"Invalid execution profile '{profile}'. Must be one of {valid_profiles}"
            )

    cfg = PROFILE_CONFIGS[profile]
    request.execution.safe_mode = cfg.safe_mode
    request.execution.enable_microstructure = cfg.enable_microstructure
    request.execution.enable_overfitting_defense = cfg.enable_overfitting_defense
    request.execution.enable_ipc_stream = cfg.enable_ipc_stream
    request.execution.profile = profile.value

    if cfg.enable_microstructure and not request.execution.impact_model:
        request.execution.impact_model = "square_root"

    return request


class FeedCache:
    """Singleton cache for warm in-memory market data feeds.

    Reuses pre-parsed InMemoryFeed instances across backtest runs to reduce read and parsing overhead.
    """
    _instance: FeedCache | None = None

    def __new__(cls) -> FeedCache:
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._cache = {}
            cls._instance = instance
        return cls._instance

    def _make_key(self, data: pl.DataFrame | str | Path, symbol: str) -> tuple[Any, ...]:
        if isinstance(data, (str, Path)):
            p = Path(data).resolve()
            mtime = p.stat().st_mtime if p.exists() else 0
            return ("file", str(p), mtime, symbol)
        elif isinstance(data, pl.DataFrame):
            return ("df", id(data), data.shape, symbol)
        elif type(data).__module__.startswith("pandas"):
            return ("pandas", id(data), symbol)
        elif hasattr(data, "to_polars"):
            return ("custom_df", id(data), symbol)
        return ("other", id(data), symbol)

    def _get_or_load_impl(self, data: pl.DataFrame | str | Path, symbol: str = "ASSET") -> InMemoryFeed:
        cache_key = self._make_key(data, symbol)
        if cache_key in self._cache:
            return self._cache[cache_key]

        df: pl.DataFrame
        if isinstance(data, (str, Path)):
            p_path = Path(data)
            if not p_path.exists():
                raise FileNotFoundError(f"Data file not found: {p_path}")
            if p_path.suffix.lower() == ".parquet":
                df = pl.read_parquet(p_path)
            elif p_path.suffix.lower() in (".csv", ".txt"):
                df = pl.read_csv(p_path)
            else:
                try:
                    df = pl.read_parquet(p_path)
                except Exception:
                    df = pl.read_csv(p_path)
        elif isinstance(data, pl.DataFrame):
            df = data
        elif type(data).__module__.startswith("pandas"):
            df = pl.from_pandas(data)
        elif hasattr(data, "to_polars"):
            df = data.to_polars()
        else:
            raise TypeError(f"Unsupported data type for FeedCache: {type(data)}")

        if "timestamp" in df.columns:
            dtype = df["timestamp"].dtype
            if isinstance(dtype, (pl.Datetime, pl.Date)) or dtype in (pl.Datetime, pl.Date):
                df = df.with_columns(pl.col("timestamp").dt.epoch("ms"))

        feed = InMemoryFeed(df, symbol=symbol)
        self._cache[cache_key] = feed
        return feed

    @classmethod
    def get_or_load(cls, data: pl.DataFrame | str | Path, symbol: str = "ASSET") -> InMemoryFeed:
        instance = cls()
        return instance._get_or_load_impl(data, symbol=symbol)

    @classmethod
    def clear(cls) -> None:
        if cls._instance is not None:
            cls._instance._cache.clear()
