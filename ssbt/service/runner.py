from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

import ssbt
from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.service.errors import (
    E_DATA_SCHEMA,
    E_RESOURCE_LIMIT,
    E_STRATEGY_INIT,
    ServiceError,
)
from ssbt.service.observability import StageTimer, TraceLogger
from ssbt.service.schemas import (
    BacktestRequest,
    BacktestResponse,
    StrategySpec,
)


def _object_to_dict(obj: Any) -> dict[str, Any]:
    if is_dataclass(obj):
        res = asdict(obj)
        for k, v in list(res.items()):
            if isinstance(v, Enum):
                res[k] = v.value
        return res
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        res = {}
        for k, v in obj.__dict__.items():
            if k.startswith("_"):
                continue
            res[k] = v.value if isinstance(v, Enum) else v
        return res
    return dict(obj)


def _compute_config_hash(req: BacktestRequest) -> str:
    """Compute SHA-256 hash over BacktestRequest parameters."""
    d = req.to_dict()
    if "data" in d and isinstance(d["data"], dict) and d["data"].get("dataframe") is not None:
        df = d["data"]["dataframe"]
        if hasattr(df, "shape"):
            d["data"]["dataframe"] = f"DataFrame({df.shape})"
        else:
            d["data"]["dataframe"] = str(type(df))
    raw = json.dumps(d, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _instantiate_strategy(spec: StrategySpec) -> ssbt.Strategy:
    if spec.code:
        namespace: dict[str, Any] = {
            "Strategy": ssbt.Strategy,
            "Side": ssbt.Side,
            "Order": ssbt.Order,
            "OrderType": ssbt.OrderType,
            "OrderStatus": ssbt.OrderStatus,
            "Bar": ssbt.Bar,
            "BidAsk": ssbt.BidAsk,
            "Engine": ssbt.Engine,
            "pl": pl,
            "np": np,
        }
        try:
            exec(spec.code, namespace)
        except Exception as e:
            raise ServiceError(
                code=E_STRATEGY_INIT,
                message=f"Failed to compile strategy code: {e}",
                hint="Check strategy Python code syntax and imports",
                details={"error": str(e)},
            ) from e

        strat_cls = None
        if (
            spec.name
            and spec.name in namespace
            and isinstance(namespace[spec.name], type)
            and issubclass(namespace[spec.name], ssbt.Strategy)
            and namespace[spec.name] is not ssbt.Strategy
        ):
            strat_cls = namespace[spec.name]
        else:
            for k, v in namespace.items():
                if isinstance(v, type) and issubclass(v, ssbt.Strategy) and v is not ssbt.Strategy:
                    strat_cls = v
                    break

        if strat_cls is None:
            raise ServiceError(
                code=E_STRATEGY_INIT,
                message=f"No subclass of Strategy found in provided code (spec name: '{spec.name}')",
                hint="Ensure your strategy code defines a class inheriting from Strategy",
            )

        try:
            kwargs = spec.kwargs or {}
            return strat_cls(**kwargs)
        except Exception as e:
            raise ServiceError(
                code=E_STRATEGY_INIT,
                message=f"Failed to instantiate strategy '{strat_cls.__name__}': {e}",
                hint="Verify strategy kwargs match __init__ signature",
                details={"error": str(e)},
            ) from e
    else:
        if spec.name and hasattr(ssbt, spec.name):
            cls = getattr(ssbt, spec.name)
            if isinstance(cls, type) and issubclass(cls, ssbt.Strategy) and cls is not ssbt.Strategy:
                return cls(**(spec.kwargs or {}))
        if spec.name == "Strategy" or not spec.name:
            class DefaultStrategy(ssbt.Strategy):
                def on_bar(self, bar: ssbt.Bar, engine: ssbt.Engine) -> None:
                    pass
            return DefaultStrategy()
        raise ServiceError(
            code=E_STRATEGY_INIT,
            message=f"Strategy code missing for custom strategy '{spec.name}'",
            hint="Provide strategy code string in StrategySpec.code",
        )


def run_backtest(request: BacktestRequest) -> BacktestResponse:
    """Execute synchronous backtest service workflow."""
    with StageTimer() as total_timer:
        run_id = request.run_id or f"run_{uuid.uuid4().hex[:12]}"
        config_hash = _compute_config_hash(request)
        logger = TraceLogger(run_id=run_id)
        logger.log("info", "backtest_start", config_hash=config_hash)

        # 1. Validate data input
        with StageTimer() as data_prep_timer:
            if request.data.dataframe is None and request.data.parquet_path is None:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_DATA_SCHEMA,
                        message="Data source missing: neither dataframe nor parquet_path provided",
                        hint="Provide a valid Polars/Pandas DataFrame or parquet_path in DataSpec",
                    ).to_spec(),
                )

            df: pl.DataFrame | None = None
            if request.data.parquet_path is not None:
                p_path = Path(request.data.parquet_path)
                if not p_path.exists():
                    return BacktestResponse(
                        status="failed",
                        run_id=run_id,
                        config_hash=config_hash,
                        error=ServiceError(
                            code=E_DATA_SCHEMA,
                            message=f"Parquet file not found: {p_path}",
                            hint="Ensure parquet_path points to an existing file",
                        ).to_spec(),
                    )
                try:
                    df = pl.read_parquet(p_path)
                except Exception as e:
                    return BacktestResponse(
                        status="failed",
                        run_id=run_id,
                        config_hash=config_hash,
                        error=ServiceError(
                            code=E_DATA_SCHEMA,
                            message=f"Failed to read Parquet file: {e}",
                            hint="Check file integrity and format",
                            details={"error": str(e)},
                        ).to_spec(),
                    )
            elif request.data.dataframe is not None:
                raw_df = request.data.dataframe
                try:
                    if isinstance(raw_df, pl.DataFrame):
                        df = raw_df
                    elif type(raw_df).__module__.startswith("pandas"):
                        df = pl.from_pandas(raw_df)
                    elif isinstance(raw_df, dict):
                        df = pl.DataFrame(raw_df)
                    elif hasattr(raw_df, "to_polars"):
                        df = raw_df.to_polars()
                    else:
                        return BacktestResponse(
                            status="failed",
                            run_id=run_id,
                            config_hash=config_hash,
                            error=ServiceError(
                                code=E_DATA_SCHEMA,
                                message=f"Unsupported dataframe type: {type(raw_df)}",
                                hint="Pass a Polars DataFrame, Pandas DataFrame, or dict",
                            ).to_spec(),
                        )
                except Exception as e:
                    return BacktestResponse(
                        status="failed",
                        run_id=run_id,
                        config_hash=config_hash,
                        error=ServiceError(
                            code=E_DATA_SCHEMA,
                            message=f"Failed to convert dataframe to Polars: {e}",
                            hint="Check dataframe content and structure",
                            details={"error": str(e)},
                        ).to_spec(),
                    )

            if df is None or df.is_empty():
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_DATA_SCHEMA,
                        message="Provided data is empty (0 rows)",
                        hint="Provide a dataset containing at least 1 row of market data",
                    ).to_spec(),
                )

            # Convert timestamp column to int epoch milliseconds if datetime/date
            if "timestamp" in df.columns:
                dtype = df["timestamp"].dtype
                if isinstance(dtype, (pl.Datetime, pl.Date)) or dtype in (pl.Datetime, pl.Date):
                    df = df.with_columns(pl.col("timestamp").dt.epoch("ms"))

            symbol = request.data.symbol or "ASSET"
            try:
                feed = InMemoryFeed(df, symbol=symbol)
            except Exception as e:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_DATA_SCHEMA,
                        message=f"Invalid market data schema: {e}",
                        hint="Ensure DataFrame contains timestamp, open, high, low, close, volume (or timestamp, bid, ask)",
                        details={"error": str(e)},
                    ).to_spec(),
                )
        data_prep_ms = data_prep_timer.elapsed_ms()

        # 2. Enforce limits
        if request.limits and request.limits.max_bars > 0:
            if feed.n_bars > request.limits.max_bars:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_RESOURCE_LIMIT,
                        message=f"Dataset bar count ({feed.n_bars}) exceeds max_bars limit ({request.limits.max_bars})",
                        hint="Increase ResourceLimitSpec.max_bars or truncate input data",
                        details={"n_bars": feed.n_bars, "max_bars": request.limits.max_bars},
                    ).to_spec(),
                )

        # 3. Strategy setup
        with StageTimer() as strategy_init_timer:
            try:
                strat = _instantiate_strategy(request.strategy)
            except ServiceError as se:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=se.to_spec(),
                )
            except Exception as e:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_STRATEGY_INIT,
                        message=f"Strategy initialization failed: {e}",
                        hint="Verify strategy syntax and instantiation kwargs",
                        details={"error": str(e)},
                    ).to_spec(),
                )
        strategy_init_ms = strategy_init_timer.elapsed_ms()

        # 4. Execute engine run
        with StageTimer() as engine_run_timer:
            try:
                engine = Engine(
                    feed=feed,
                    strategy=strat,
                    initial_cash=request.execution.initial_cash,
                )
                res = engine.run()
            except Exception as e:
                return BacktestResponse(
                    status="failed",
                    run_id=run_id,
                    config_hash=config_hash,
                    error=ServiceError(
                        code=E_STRATEGY_INIT,
                        message=f"Backtest engine execution error: {e}",
                        hint="Check strategy runtime logic in on_bar/on_bidask",
                        details={"error": str(e)},
                    ).to_spec(),
                )
        engine_run_ms = engine_run_timer.elapsed_ms()

        # 5. Compute metrics
        with StageTimer() as metrics_timer:
            metrics = compute_metrics(res.equity_curve, res.trades)
        metrics_ms = metrics_timer.elapsed_ms()

        # 6. Artifact creation
        artifact_dir = Path("artifacts") / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        request_file = artifact_dir / "request.json"
        request_file.write_text(request.to_json(indent=2), encoding="utf-8")

        artifacts_map: dict[str, str] = {
            "request": str(request_file),
        }

        try:
            from ssbt.experiments.reproducibility import capture_environment_snapshot

            snap_path = artifact_dir / "environment_snapshot.json"
            snapshot = capture_environment_snapshot(config=request.to_dict())
            snap_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
            artifacts_map["environment_snapshot"] = str(snap_path)
        except Exception:
            pass

        total_ms = total_timer.elapsed_ms()
        timing_ms = {
            "data_prep_ms": data_prep_ms,
            "strategy_init_ms": strategy_init_ms,
            "engine_run_ms": engine_run_ms,
            "metrics_ms": metrics_ms,
            "total_ms": total_ms,
        }
        logger.log("info", "backtest_complete", timing_ms=timing_ms)

        response = BacktestResponse(
            status="success",
            run_id=run_id,
            config_hash=config_hash,
            summary=metrics,
            equity_curve=res.equity_curve.tolist() if len(res.equity_curve) > 0 else [],
            fills=[_object_to_dict(f) for f in res.fills],
            trades=[_object_to_dict(t) for t in res.trades],
            audit={
                "n_events": res.n_events,
                "symbol": symbol,
                "timing_ms": timing_ms,
            },
            artifacts=artifacts_map,
            error=None,
        )

        response_file = artifact_dir / "response.json"
        response_file.write_text(response.to_json(indent=2), encoding="utf-8")
        response.artifacts["response"] = str(response_file)

        return response


async def run_backtest_async(request: BacktestRequest) -> BacktestResponse:
    """Execute asynchronous backtest service workflow in an executor thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_backtest, request)

