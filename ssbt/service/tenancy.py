from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ssbt.service.errors import E_RESOURCE_LIMIT, E_STRATEGY_INIT, ServiceError
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
