from pathlib import Path
import pytest

from ssbt.service.errors import E_RESOURCE_LIMIT, E_STRATEGY_INIT, ServiceError
from ssbt.service.schemas import BacktestRequest, ResourceLimitSpec, StrategySpec
from ssbt.service.tenancy import TenantContext, resolve_tenant_artifact_dir, validate_tenant_policy


def test_resolve_tenant_artifact_dir_with_context():
    ctx = TenantContext(org_id="acme", user_id="alice", project_id="alpha")
    path = resolve_tenant_artifact_dir(ctx, "run_123")
    expected = Path("artifacts") / "acme" / "alice" / "alpha" / "run_123"
    assert path == expected


def test_resolve_tenant_artifact_dir_default_context():
    path = resolve_tenant_artifact_dir(None, "run_456")
    expected = Path("artifacts") / "default" / "default" / "default" / "run_456"
    assert path == expected


def test_validate_tenant_policy_allowlist_pass():
    ctx = TenantContext(org_id="acme")
    req = BacktestRequest(strategy=StrategySpec(name="AllowedStrategy"))
    validate_tenant_policy(req, ctx, allowlist=["AllowedStrategy", "OtherStrategy"])


def test_validate_tenant_policy_allowlist_fail():
    ctx = TenantContext(org_id="acme")
    req = BacktestRequest(strategy=StrategySpec(name="ForbiddenStrategy"))
    with pytest.raises(ServiceError) as exc_info:
        validate_tenant_policy(req, ctx, allowlist=["AllowedStrategy"])
    assert exc_info.value.code == E_STRATEGY_INIT
    assert "ForbiddenStrategy" in exc_info.value.message


def test_validate_tenant_policy_max_bars_pass():
    req = BacktestRequest(limits=ResourceLimitSpec(max_bars=50_000))
    validate_tenant_policy(req, max_tenant_bars=100_000)


def test_validate_tenant_policy_max_bars_fail():
    req = BacktestRequest(limits=ResourceLimitSpec(max_bars=200_000))
    with pytest.raises(ServiceError) as exc_info:
        validate_tenant_policy(req, max_tenant_bars=100_000)
    assert exc_info.value.code == E_RESOURCE_LIMIT
    assert "exceeds tenant policy limit" in exc_info.value.message


def test_validate_tenant_policy_no_restrictions():
    req = BacktestRequest(
        strategy=StrategySpec(name="AnyStrategy"),
        limits=ResourceLimitSpec(max_bars=1_000_000),
    )
    validate_tenant_policy(req)
