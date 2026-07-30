# SSBT Sub-Project 3: Multi-Tenancy, Strategy Plugins & Execution Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build multi-tenant workspace isolation (`ssbt.service.tenancy`), security policy hooks, pip-installable strategy plugin compatibility checks (`ssbt.service.plugins`), 5-bar dry-run validation, preset execution profiles (`fast`, `balanced`, `max_fidelity`), and warm in-memory feed caching (`ssbt.service.profiles`).

**Architecture:** Extended backend service layer providing tenant namespacing, execution profile adapters, feed cache registry, and plugin compatibility hooks.

**Tech Stack:** Python 3.12, Polars, dataclasses, pytest.

## Global Constraints

- Preserve all existing 225 passing unit/integration tests without breaking low-level API contracts.
- Tenant isolation must prevent cross-tenant artifact directory leaks.
- Warm feed cache must be thread-safe.

---

### Task 1: Multi-Tenant Workspaces & Security Policy Hooks

**Files:**
- Create: `ssbt/service/tenancy.py`
- Test: `ssbt/tests/test_service_tenancy.py`

**Interfaces:**
- Produces: `TenantContext`, `resolve_tenant_artifact_dir`, `validate_tenant_policy`

- [ ] **Step 1: Write failing tests for tenancy module**

```python
# ssbt/tests/test_service_tenancy.py
from pathlib import Path
import pytest
from ssbt.service import BacktestRequest, DataSpec, StrategySpec
from ssbt.service.tenancy import TenantContext, resolve_tenant_artifact_dir, validate_tenant_policy

def test_resolve_tenant_artifact_dir():
    ctx = TenantContext(org_id="acme", user_id="alice", project_id="alpha")
    path = resolve_tenant_artifact_dir(ctx, "run_123")
    assert str(path).replace("\\", "/").endswith("artifacts/acme/alice/alpha/run_123")

def test_validate_tenant_policy_allowlist():
    ctx = TenantContext(org_id="acme")
    req = BacktestRequest(strategy=StrategySpec(name="ForbiddenStrategy"))
    with pytest.raises(Exception):
        validate_tenant_policy(req, ctx, allowlist=["AllowedStrategy"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_tenancy.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.tenancy'")

- [ ] **Step 3: Implement tenancy module**

```python
# ssbt/service/tenancy.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ssbt.service.errors import ServiceError, E_STRATEGY_INIT, E_RESOURCE_LIMIT
from ssbt.service.schemas import BacktestRequest

@dataclass
class TenantContext:
    org_id: str = "default"
    user_id: str = "default"
    project_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

def resolve_tenant_artifact_dir(context: TenantContext | None, run_id: str) -> Path:
    if context is None:
        context = TenantContext()
    return Path("artifacts") / context.org_id / context.user_id / context.project_id / run_id

def validate_tenant_policy(
    request: BacktestRequest,
    context: TenantContext | None = None,
    allowlist: list[str] | None = None,
    max_tenant_bars: int | None = None,
) -> None:
    if allowlist is not None and request.strategy.name not in allowlist:
        raise ServiceError(
            code=E_STRATEGY_INIT,
            message=f"Strategy '{request.strategy.name}' is not in tenant allowlist: {allowlist}",
            hint="Use an approved strategy class name",
        )

    if max_tenant_bars is not None and request.limits.max_bars > max_tenant_bars:
        raise ServiceError(
            code=E_RESOURCE_LIMIT,
            message=f"Requested max_bars ({request.limits.max_bars}) exceeds tenant policy limit of {max_tenant_bars}",
            hint="Reduce ResourceLimitSpec.max_bars to comply with tenant policy",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_tenancy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/tenancy.py ssbt/tests/test_service_tenancy.py
git commit -m "feat(service): add multi-tenant workspace namespacing and policy security hooks"
```

---

### Task 2: Strategy Plugin Architecture & Dry-Run Engine

**Files:**
- Create: `ssbt/service/plugins.py`
- Test: `ssbt/tests/test_service_plugins.py`

**Interfaces:**
- Produces: `PluginManifest`, `check_plugin_compatibility`, `dry_run_strategy`

- [ ] **Step 1: Write failing tests for plugins and dry-run engine**

```python
# ssbt/tests/test_service_plugins.py
import polars as pl
from ssbt.quick import generate_synthetic_bars
from ssbt.service import StrategySpec
from ssbt.service.plugins import PluginManifest, check_plugin_compatibility, dry_run_strategy

def test_check_plugin_compatibility():
    manifest = PluginManifest(name="my_plugin", version="1.0.0", min_ssbt_version="0.1.0")
    res = check_plugin_compatibility(manifest)
    assert res["compatible"] is True

def test_dry_run_strategy():
    code = '''from ssbt import Strategy, Side
class DryStrat(Strategy):
    def on_bar(self, bar, engine):
        engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
'''
    spec = StrategySpec(name="DryStrat", code=code)
    df = generate_synthetic_bars(n_bars=10, seed=42)
    res = dry_run_strategy(spec, data_sample=df)
    assert res["dry_run_passed"] is True
    assert res["bars_processed"] == 5
    assert res["orders_submitted"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_plugins.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.plugins'")

- [ ] **Step 3: Implement plugins and dry-run validator**

```python
# ssbt/service/plugins.py
from __future__ import annotations
import importlib.util
from dataclasses import dataclass
from typing import Any
import polars as pl

import ssbt
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.quick import generate_synthetic_bars
from ssbt.service.errors import ServiceError, E_STRATEGY_INIT
from ssbt.service.schemas import StrategySpec
from ssbt.strategy.base import Strategy

@dataclass
class PluginManifest:
    name: str
    version: str
    min_ssbt_version: str = "0.1.0"
    entrypoint: str = "main"

def check_plugin_compatibility(manifest: PluginManifest) -> dict[str, Any]:
    curr_ver = getattr(ssbt, "__version__", "0.5.0")
    compatible = curr_ver >= manifest.min_ssbt_version
    return {
        "plugin_name": manifest.name,
        "plugin_version": manifest.version,
        "current_ssbt_version": curr_ver,
        "min_ssbt_version": manifest.min_ssbt_version,
        "compatible": compatible,
    }

def dry_run_strategy(
    strategy_spec: StrategySpec,
    data_sample: pl.DataFrame | None = None,
    symbol: str = "DRY_RUN",
) -> dict[str, Any]:
    if data_sample is None:
        data_sample = generate_synthetic_bars(n_bars=5, seed=42)

    sample_df = data_sample.head(5)
    if sample_df["timestamp"].dtype in (pl.Datetime, pl.Date):
        sample_df = sample_df.with_columns(pl.col("timestamp").dt.epoch("ms"))

    strat_obj = None
    if strategy_spec.code:
        try:
            mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("dry_mod", None))
            exec(strategy_spec.code, mod.__dict__)
            for val in mod.__dict__.values():
                if isinstance(val, type) and issubclass(val, Strategy) and val is not Strategy:
                    strat_obj = val(**strategy_spec.kwargs)
                    break
        except Exception as e:
            raise ServiceError(code=E_STRATEGY_INIT, message=f"Dry run compilation failed: {e}")

    if strat_obj is None:
        raise ServiceError(code=E_STRATEGY_INIT, message="Could not resolve Strategy subclass for dry run")

    feed = InMemoryFeed(sample_df, symbol=symbol)
    engine = Engine(feed=feed, strategy=strat_obj, initial_cash=100_000.0)
    res = engine.run()

    return {
        "dry_run_passed": True,
        "strategy_name": strategy_spec.name,
        "bars_processed": res.n_events,
        "orders_submitted": len(engine.matching.pending_orders) + len(res.fills),
        "fills_count": len(res.fills),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_plugins.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/plugins.py ssbt/tests/test_service_plugins.py
git commit -m "feat(service): add strategy plugin compatibility verifier and 5-bar dry-run engine"
```

---

### Task 3: Preset Execution Profiles & Warm Feed Cache

**Files:**
- Create: `ssbt/service/profiles.py`
- Modify: `ssbt/service/runner.py`
- Test: `ssbt/tests/test_service_profiles.py`

**Interfaces:**
- Produces: `ExecutionProfile`, `apply_execution_profile`, `FeedCache`

- [ ] **Step 1: Write failing tests for profiles and feed cache**

```python
# ssbt/tests/test_service_profiles.py
from ssbt.quick import generate_synthetic_bars
from ssbt.service import BacktestRequest, DataSpec, run_backtest
from ssbt.service.profiles import ExecutionProfile, apply_execution_profile, FeedCache

def test_apply_execution_profile():
    req = BacktestRequest()
    req_fast = apply_execution_profile(req, ExecutionProfile.FAST)
    assert req_fast.execution.safe_mode is False

def test_feed_cache_warm_load():
    df = generate_synthetic_bars(n_bars=30, seed=42)
    cache = FeedCache.get_instance()
    cache.clear()
    feed1 = cache.get_or_load(df, symbol="BTC")
    feed2 = cache.get_or_load(df, symbol="BTC")
    assert feed1 is feed2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_profiles.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.profiles'")

- [ ] **Step 3: Implement profiles and feed cache**

```python
# ssbt/service/profiles.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import polars as pl

from ssbt.data.feed import InMemoryFeed, ParquetFeed
from ssbt.service.schemas import BacktestRequest

class ExecutionProfile(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    MAX_FIDELITY = "max_fidelity"

@dataclass
class ProfileConfig:
    safe_mode: bool = True
    enable_microstructure: bool = False
    enable_overfitting_defense: bool = False
    enable_ipc_stream: bool = False

def apply_execution_profile(request: BacktestRequest, profile: ExecutionProfile | str) -> BacktestRequest:
    prof_enum = ExecutionProfile(profile) if isinstance(profile, str) else profile
    if prof_enum == ExecutionProfile.FAST:
        request.execution.safe_mode = False
        request.execution.impact_model = None
        request.execution.borrow_cost = 0.0
    elif prof_enum == ExecutionProfile.BALANCED:
        request.execution.safe_mode = True
        request.execution.impact_model = "square_root"
    elif prof_enum == ExecutionProfile.MAX_FIDELITY:
        request.execution.safe_mode = True
        request.execution.impact_model = "square_root"
        request.execution.borrow_cost = 0.001
    return request

class FeedCache:
    _instance: FeedCache | None = None

    def __init__(self):
        self._cache: dict[str, InMemoryFeed] = {}

    @classmethod
    def get_instance(cls) -> FeedCache:
        if cls._instance is None:
            cls._instance = FeedCache()
        return cls._instance

    def clear(self) -> None:
        self._cache.clear()

    def get_or_load(self, data: pl.DataFrame | str | Path, symbol: str) -> InMemoryFeed:
        cache_key = f"{symbol}:{id(data) if isinstance(data, pl.DataFrame) else str(data)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if isinstance(data, pl.DataFrame):
            df = data
        elif isinstance(data, (str, Path)):
            path = Path(data)
            df = pl.read_parquet(path) if path.suffix == ".parquet" else pl.read_csv(path)
        else:
            df = data

        if df["timestamp"].dtype in (pl.Datetime, pl.Date):
            df = df.with_columns(pl.col("timestamp").dt.epoch("ms"))

        feed = InMemoryFeed(df, symbol=symbol)
        self._cache[cache_key] = feed
        return feed
```

Update `run_backtest` in `ssbt/service/runner.py` to accept optional `context: TenantContext` and `profile: ExecutionProfile`, using `resolve_tenant_artifact_dir` for artifacts.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_profiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/profiles.py ssbt/service/runner.py ssbt/tests/test_service_profiles.py
git commit -m "feat(service): implement preset execution profiles and warm in-memory feed cache"
```

---

### Task 4: Package Top-Level Exports & Full Regression Verification

**Files:**
- Modify: `ssbt/service/__init__.py`
- Modify: `ssbt/__init__.py`
- Test: `ssbt/tests/` (all tests)

- [ ] **Step 1: Export sub-project 3 entrypoints in `ssbt/service/__init__.py` and `ssbt/__init__.py`**

Export: `TenantContext`, `resolve_tenant_artifact_dir`, `validate_tenant_policy`, `PluginManifest`, `check_plugin_compatibility`, `dry_run_strategy`, `ExecutionProfile`, `apply_execution_profile`, `FeedCache`.

- [ ] **Step 2: Run full pytest suite**

Run: `uv run python -m pytest ssbt/tests/ -v`
Expected: PASS (all tests passing)

- [ ] **Step 3: Commit**

```bash
git add ssbt/service/__init__.py ssbt/__init__.py
git commit -m "feat(service): export multi-tenancy plugins profiles and feed cache at top-level ssbt"
```

---

## Verification Plan

### Automated Tests
Run full test suite:
```bash
uv run python -m pytest ssbt/tests/ -v
```

### Manual Verification
Execute python inline test:
```python
import ssbt

df = ssbt.generate_synthetic_bars(n_bars=50)
ctx = ssbt.TenantContext(org_id="fintech", user_id="bob", project_id="algo1")
req = ssbt.BacktestRequest(data=ssbt.DataSpec(symbol="ETH", dataframe=df))

req = ssbt.apply_execution_profile(req, ssbt.ExecutionProfile.BALANCED)
resp = ssbt.run_backtest(req, context=ctx)
print("Response status:", resp.status)
print("Artifact dir:", resp.artifacts["output_dir"])
```
