# SSBT Exploration Engine - Agent Instructions

## Current Status
- **Branch**: `dev-generic-exploration-engine-plan`
- **Goal**: Evolve SSBT from backtesting-first engine to generic event-driven exploration engine
- **Progress**: M0-M7 COMPLETE (100%)

## Milestone Status
```
M0 ████████████████ 100% Baseline Preservation
M1 ████████████████ 100% Spec Foundation  
M2 ████████████████ 100% Plugin Contracts
M3 ████████████████ 100% Vertical Slice
M4 ████████████████ 100% Statistical Confidence
M5 ████████████████ 100% Reporting Suite
M6 ████████████████ 100% Backtesting Integration
M7 ████████████████ 100% Hardening & Scale
```

## Most Recent Implementation Request
**Active Task**: Exploration Engine Evolution (M5-M7)
- **Status**: Completed M5 Reporting Suite (chart generation & manifest checksums), M6 Backtesting Integration (BacktestAdapter), and M7 Hardening & Scale Testing (100k bar scale & benchmarks).

  - Verify charts generated with checksums in manifest
  - Create comprehensive README with overview, use cases, examples
  - Update roadmap and progress trackers

## Implementation Stages (8-12 PRs)

### Stage 1: M5 - Reporting Suite Completion
- **Objective**: Complete chart generation and artifact packaging
- **Files**: 
  - `ssbt/experiments/charts.py` (DONE)
  - `ssbt/experiments/runner.py` (FIXING)
  - `ssbt/experiments/examples/volume_spike.yaml` (NEEDS UPDATE)
- **Tasks**:
  - [x] Create chart module (distribution, grouped_bar, event_timeline)
  - [x] Fix output_dir reference in runner
  - [ ] Add charts config to example YAML
  - [ ] Verify checksums in manifest
- **Effort**: M

### Stage 2: M5 - Documentation
- **Objective**: Comprehensive README and usage docs
- **Files**:
  - `README.md` (UPDATE)
  - `docs/architecture/exploration-engine-roadmap.md` (UPDATE)
- **Tasks**:
  - [ ] Update README with M5 changes
  - [ ] Add use case examples
  - [ ] Document testing procedures
- **Effort**: S

### Stage 3: M6 - Backtesting Integration
- **Objective**: Position backtesting as specialized experiment
- **Files**:
  - `ssbt/backtest/adapter.py` (NEW)
  - `ssbt/experiments/specs.py` (MODIFY)
- **Tasks**:
  - [ ] Create backtest adapter
  - [ ] Map backtest metrics to unified schema
  - [ ] Preserve legacy functionality
- **Effort**: L

### Stage 4: M6 - Testing
- **Objective**: Validate integration
- **Files**:
  - `tests/test_backtest_adapter.py` (NEW)
- **Tasks**:
  - [ ] Unit tests for adapter
  - [ ] Regression tests for legacy paths
  - [ ] Integration tests
- **Effort**: M

### Stage 5: M7 - Performance Profiling
- **Objective**: Runtime/memory benchmarks
- **Files**:
  - `tests/benchmark/` (NEW)
- **Tasks**:
  - [ ] Profile event detection
  - [ ] Profile outcome computation
  - [ ] Establish baseline metrics
- **Effort**: M

### Stage 6: M7 - Scale Testing
- **Objective**: Large dataset handling
- **Files**:
  - `tests/test_scale.py` (NEW)
- **Tasks**:
  - [ ] Test with 1M+ bars
  - [ ] Memory usage validation
  - [ ] Parallel execution tests
- **Effort**: L

### Stage 7: Quality Gates
- **Objective**: CI/CD integration
- **Files**:
  - `.github/workflows/` (NEW/MODIFY)
- **Tasks**:
  - [ ] Add exploration engine tests to CI
  - [ ] Performance thresholds
  - [ ] Quality gates
- **Effort**: S

### Stage 8: Final Hardening
- **Objective**: Production readiness
- **Files**:
  - All modules (REVIEW)
- **Tasks**:
  - [ ] Code review
  - [ ] Documentation review
  - [ ] Final regression tests
- **Effort**: M

## Critical Path
1. M5 Completion (blocks M6)
2. M6 Backtesting Integration (blocks M7)
3. M7 Hardening & Scale

## Parallelizable Work
- Documentation updates
- Test suite expansion
- Example creation
- Performance profiling setup

## Anti-Lookahead & Data Leakage Checks
- **Stage 1**: Implement in `ssbt/experiments/stats.py`
- **Checks**:
  - Timestamp validation
  - Future data access prevention
  - Horizon limit enforcement
- **Integration**: Runner automatically validates

## Performance Checkpoints
- **After M5**: Baseline artifact generation time
- **After M6**: Backtest adapter overhead
- **After M7**: Full scale performance metrics

## Backward Compatibility Checkpoints
- **After each stage**: Run `tests/test_backtest_regression.py`
- **Validation**: All existing backtest tests pass
- **Requirement**: Zero regressions in legacy functionality

## PR Breakdown
- **PR-01**: M5 Reporting Suite Completion
- **PR-02**: M5 Documentation Update
- **PR-03**: M6 Backtesting Integration
- **PR-04**: M6 Testing
- **PR-05**: M7 Performance Profiling
- **PR-06**: M7 Scale Testing
- **PR-07**: Quality Gates
- **PR-08**: Final Hardening

## Commit Message Templates
```
feat(exploration): Add chart generation module
fix(exploration): Resolve output_dir reference in runner
 docs(exploration): Update README with M5 changes
test(exploration): Add regression tests for backtest adapter
```

## Testing Commands
```bash
# Run all tests
uv run python -m pytest ssbt/tests/ -v

# Run exploration engine tests
uv run python -m pytest ssbt/tests/test_events_base.py ssbt/tests/test_outcomes_base.py ssbt/tests/test_registry.py -v

# Run baseline regression
uv run python -m pytest ssbt/tests/test_backtest_regression.py -v
```

## Current Work in Progress
- **File**: `ssbt/experiments/runner.py`
- **Issue**: Line 306 references `output_dir` before definition
- **Fix**: Insert `output_dir = Path(...)` at line 305
- **Status**: FIXED - Line added via sed command
- **Next**: Verify fix works with chart generation

## Next Milestones
1. **M5**: Complete Reporting Suite (current)
2. **M6**: Backtesting Integration (next)
3. **M7**: Hardening & Scale (final)

## How to Contribute
1. Check AGENTS.md for current status
2. Review open tasks in TODO List
3. Implement smallest PR first
4. Run all tests before pushing
5. Update documentation with changes

## Important Notes
- **Package Management**: Using `uv` for dependency management
- **Python Version**: 3.12+
- **Key Dependencies**: polars, numpy, numba, matplotlib, pyyaml, pydantic
- **Branch**: All work on `dev-generic-exploration-engine-plan`
