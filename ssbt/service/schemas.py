from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from typing import Any
from ssbt.service.errors import ErrorSpec


@dataclass
class StrategySpec:
    name: str = "Strategy"
    code: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class DataSpec:
    symbol: str = "ASSET"
    dataframe: Any | None = None
    parquet_path: str | None = None
    resample: str | None = None


@dataclass
class ExecutionSpec:
    initial_cash: float = 100_000.0
    impact_model: str | None = None
    borrow_cost: float = 0.0
    safe_mode: bool = True
    enable_microstructure: bool = False
    enable_overfitting_defense: bool = False
    enable_ipc_stream: bool = False
    profile: str | None = None



@dataclass
class ResourceLimitSpec:
    max_bars: int = 1_000_000
    timeout_seconds: float = 60.0


@dataclass
class BacktestRequest:
    version: str = "1.0"
    run_id: str | None = None
    strategy: StrategySpec = field(default_factory=StrategySpec)
    data: DataSpec = field(default_factory=DataSpec)
    execution: ExecutionSpec = field(default_factory=ExecutionSpec)
    limits: ResourceLimitSpec = field(default_factory=ResourceLimitSpec)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


@dataclass
class BacktestResponse:
    status: str
    run_id: str
    config_hash: str
    summary: dict[str, Any] = field(default_factory=dict)
    equity_curve: list[list[float]] = field(default_factory=list)
    fills: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    error: ErrorSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
