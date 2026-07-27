"""Load experiment configs from YAML or JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssbt.experiments.specs import (
    ExperimentSpec,
    ValidationError,
    ValidationResult,
)


class LoaderError(Exception):
    """Raised when a config cannot be loaded or validated."""

    def __init__(self, message: str, errors: ValidationResult | None = None):
        self.errors = errors or []
        full = message
        if self.errors:
            details = "\n".join(_fmt_error(e) for e in self.errors)
            full = f"{message}\n{details}"
        super().__init__(full)


def _fmt_error(e: ValidationError) -> str:
    line = f"  - {e.path}: {e.message}"
    if e.suggestion:
        line += f"\n    Suggestion: {e.suggestion}"
    return line


def _try_load_yaml(path: Path) -> dict[str, Any] | None:
    """Try loading a YAML file. Returns None if pyyaml is not installed."""
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return None
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise LoaderError(f"Expected a top-level mapping in {path}, got {type(data).__name__}")
    return data


def _try_load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise LoaderError(f"Expected a top-level mapping in {path}, got {type(data).__name__}")
    return data


def _read_config(path: str | Path) -> dict[str, Any]:
    """Read and parse a YAML or JSON config file.

    Tries YAML first (with pyyaml), falls back to JSON.
    """
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        data = _try_load_yaml(path)
        if data is None:
            raise LoaderError(
                f"Cannot parse YAML file {path}: pyyaml is not installed. "
                "Install it with: pip install pyyaml>=6.0"
            )
        return data
    elif suffix == ".json":
        return _try_load_json(path)
    else:
        raise LoaderError(
            f"Unsupported config format '{suffix}' for {path.name}",
            errors=[ValidationError(
                path="",
                message=f"Unsupported file extension '{suffix}'",
                suggestion="Use .yaml, .yml, or .json.",
            )],
        )


def load_experiment(path: str | Path) -> ExperimentSpec:
    """Load and validate an experiment config from a YAML or JSON file.

    Args:
        path: Path to the config file (.yaml, .yml, or .json).

    Returns:
        A fully validated ExperimentSpec.

    Raises:
        LoaderError: If the file cannot be read, parsed, or validated.
    """
    data = _read_config(path)
    spec = ExperimentSpec.from_dict(data)
    errors = spec.validate()
    if errors:
        raise LoaderError(f"Experiment config validation failed ({len(errors)} error(s))", errors)
    return spec
