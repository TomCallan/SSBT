# Task 3 Report: Preset Execution Profiles & Warm Feed Cache

## Implementation Summary
Implemented preset execution fidelity profiles and a warm in-memory feed cache singleton to reduce parsing overhead and optimize backtest runtime performance.

## Key Changes
1. **`ssbt/service/profiles.py`**:
   - `ExecutionProfile(str, Enum)`: Enums for `FAST` ("fast"), `BALANCED` ("balanced"), `MAX_FIDELITY` ("max_fidelity").
   - `ProfileConfig`: Dataclass containing `safe_mode`, `enable_microstructure`, `enable_overfitting_defense`, and `enable_ipc_stream`.
   - `apply_execution_profile(request, profile)`: Validates and configures request execution settings based on preset profiles.
   - `FeedCache`: Singleton for warm feed reuse with `get_or_load(data, symbol)` and `clear()`.

2. **`ssbt/service/runner.py`**:
   - Updated `run_backtest(request, context=None, profile=None)` and `run_backtest_async(request, context=None, profile=None)` to enforce tenant security policies, apply execution profiles, utilize `FeedCache`, and output tenant artifact paths via `resolve_tenant_artifact_dir`.

3. **`ssbt/service/schemas.py` & `ssbt/service/__init__.py`**:
   - Added optional execution profile flags to `ExecutionSpec` and exported all profile/tenancy components.

4. **`ssbt/tests/test_service_profiles.py`**:
   - Added unit and integration tests covering execution profile enums, profile configuration application, invalid profile handling, `FeedCache` warm feed reuse and clear, multi-tenant `run_backtest` artifact creation, and `run_backtest_async`.

## Commit Log
- `feat(service): implement preset execution profiles and warm in-memory feed cache`

## Verification Summary
`10 passed in 0.28s` (`ssbt/tests/test_service_profiles.py`)
