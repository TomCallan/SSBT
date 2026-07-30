from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

E_DATA_SCHEMA = "E_DATA_SCHEMA"
E_STRATEGY_INIT = "E_STRATEGY_INIT"
E_RESOURCE_LIMIT = "E_RESOURCE_LIMIT"
E_LOOKAHEAD = "E_LOOKAHEAD"
E_RUN_NOT_FOUND = "E_RUN_NOT_FOUND"


@dataclass
class ErrorSpec:
    code: str
    message: str
    hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details if details is not None else {}
        super().__init__(f"[{code}] {message}")

    def to_spec(self) -> ErrorSpec:
        return ErrorSpec(
            code=self.code,
            message=self.message,
            hint=self.hint,
            details=self.details,
        )
