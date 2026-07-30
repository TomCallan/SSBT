# SSBT Sub-Project 3: Multi-Tenancy, Strategy Plugins & Execution Profiles — Design Spec

## Executive Summary
This design specification defines the architecture for **Sub-Project 3: Multi-Tenancy, Strategy Plugins & Execution Profiles** (`ssbt.service.tenancy`, `ssbt.service.plugins`, `ssbt.service.profiles`). It completes SSBT's backend platform roadmap by adding multi-tenant workspace namespacing, policy security hooks, pip-installable strategy plugin compatibility checks, dry-run strategy compilation, preset execution profiles (`fast`, `balanced`, `max_fidelity`), and warm in-memory feed caching for high-throughput parameter sweeps.

---

## 1. Subsystems & Component Architecture

```
[ BacktestRequest + TenantContext ]
                 |
                 +---> [ Tenant Policy & Workspace Resolver ]
                 |        - Validates tenant strategy allowlists
                 |        - Resolves namespaced artifacts: artifacts/{org_id}/{user_id}/{project_id}/{run_id}
                 |
                 +---> [ Strategy Plugin & Dry-Run Engine ]
                 |        - Validates plugin API version compatibility
                 |        - Dry-runs 5-bar sample execution prior to full simulation
                 |
                 +---> [ Execution Profile Preset Selector ]
                 |        - FAST: High-throughput fast-path array matching loop
                 |        - BALANCED: Microstructure latency + partial fill + PIT check
                 |        - MAX_FIDELITY: Synthetic L3 orderbook depth + DSR/PBO + IPC streaming
                 |
                 +---> [ Warm Feed Cache ]
                          - In-memory cache by parquet path / hash to eliminate redundant disk I/O
```

### Module Structure
- `ssbt/service/tenancy.py`: `TenantContext`, artifact workspace resolver, policy validation hooks.
- `ssbt/service/plugins.py`: `PluginManifest`, version compatibility checker, `dry_run_strategy()`.
- `ssbt/service/profiles.py`: `ExecutionProfile` enum (`FAST`, `BALANCED`, `MAX_FIDELITY`), profile configurations, `FeedCache` warm feed registry.

---

## 2. Detailed Component Specifications

### 2.1 Multi-Tenant Workspaces & Security Policy (`ssbt/service/tenancy.py`)
- `TenantContext`:
  - `org_id: str = "default"`
  - `user_id: str = "default"`
  - `project_id: str = "default"`
  - `metadata: dict[str, Any] = field(default_factory=dict)`
- `resolve_tenant_artifact_dir(context: TenantContext, run_id: str) -> Path`:
  Constructs namespaced output directory `artifacts/{org_id}/{user_id}/{project_id}/{run_id}/`.
- `validate_tenant_policy(request: BacktestRequest, context: TenantContext, allowlist: list[str] | None = None) -> None`:
  Enforces strategy class allowlist or tenant bar count ceilings. Raises `ServiceError(code=E_RESOURCE_LIMIT)` or `E_STRATEGY_INIT` on policy violation.

### 2.2 Strategy Plugins & Dry-Run Validator (`ssbt/service/plugins.py`)
- `PluginManifest`:
  - `name: str`
  - `version: str`
  - `min_ssbt_version: str`
  - `entrypoint: str`
- `check_plugin_compatibility(manifest: PluginManifest) -> dict[str, Any]`:
  Verifies SSBT engine version compatibility against plugin manifest bounds.
- `dry_run_strategy(strategy_spec: StrategySpec, data_sample: pl.DataFrame | None = None) -> dict[str, Any]`:
  Instantiates strategy, executes a 5-bar dry run, records order submissions, and confirms zero lookahead syntax errors without launching a full backtest run.

### 2.3 Preset Execution Profiles & Feed Cache (`ssbt/service/profiles.py`)
- `ExecutionProfile`: Enum (`FAST`, `BALANCED`, `MAX_FIDELITY`).
- `ProfileConfig`: Dataclass containing flags for microstructure impact models, L3 depth quote reconstruction, causality audit logging, and DSR/PBO overfitting defense.
- `apply_execution_profile(request: BacktestRequest, profile: ExecutionProfile | str) -> BacktestRequest`:
  Applies profile presets to request execution and audit settings.
- `FeedCache`:
  - `get_or_load(parquet_path_or_df: str | Path | pl.DataFrame, symbol: str) -> InMemoryFeed`:
    Caches loaded `InMemoryFeed` instances in memory, avoiding redundant file reads across repeated tenant backtests or grid sweeps.

---

## 3. Verification & Testing Plan

1. **Multi-Tenancy Tests (`ssbt/tests/test_service_tenancy.py`)**:
   - `test_resolve_tenant_artifact_dir()`: Asserts correct nested directory paths.
   - `test_validate_tenant_policy()`: Verifies strategy allowlist enforcement and policy error handling.
2. **Plugins & Dry-Run Tests (`ssbt/tests/test_service_plugins.py`)**:
   - `test_check_plugin_compatibility()`: Asserts version compatibility check logic.
   - `test_dry_run_strategy()`: Verifies 5-bar sample execution and order collection.
3. **Profiles & Feed Cache Tests (`ssbt/tests/test_service_profiles.py`)**:
   - `test_apply_execution_profile()`: Verifies FAST, BALANCED, and MAX_FIDELITY presets.
   - `test_feed_cache_warm_load()`: Asserts cached feed reuse and performance gain.
4. **Full Suite Regression**:
   - Execute full pytest suite to verify zero regressions across all SSBT subsystems.
