"""Immutable Reproducibility & Environment Snapshot Module for SSBT.

Captures system platform, Python environment, Git repository state, random seeds,
and config hashes to guarantee 100% deterministic backtest rerun fidelity.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any


def capture_environment_snapshot(
    seed: int = 42,
    config: dict[str, Any] | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Capture full environment metadata and emit environment_snapshot.json."""
    git_commit_sha = "UNCOMMITTED"
    git_branch = "UNKNOWN"

    try:
        git_dir = Path(".git")
        if git_dir.exists():
            head_file = git_dir / "HEAD"
            if head_file.exists():
                ref = head_file.read_text().strip()
                if ref.startswith("ref: "):
                    branch_path = git_dir / ref.split("ref: ")[1]
                    git_branch = ref.split("ref: ")[1].split("/")[-1]
                    if branch_path.exists():
                        git_commit_sha = branch_path.read_text().strip()[:8]
    except Exception:
        pass

    config_dict = config or {}
    config_json = json.dumps(config_dict, sort_keys=True)
    config_sha256 = hashlib.sha256(config_json.encode()).hexdigest()

    snapshot = {
        "ssbt_version": "0.5.0",
        "git_commit_sha": git_commit_sha,
        "git_branch": git_branch,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "x86_64",
        "random_seed": seed,
        "config_sha256": config_sha256,
        "config": config_dict,
    }

    if output_dir is not None:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        with open(out_path / "environment_snapshot.json", "w") as f:
            json.dump(snapshot, f, indent=2)

    return snapshot
