"""Tests for experiment config loader (YAML/JSON)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssbt.experiments.loader import LoaderError, load_experiment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _minimal_dict() -> dict:
    return {
        "version": 1,
        "experiment": {"name": "test", "type": "event_study"},
        "dataset": {"source": "data.parquet", "symbol": "BTC", "timeframe": "1h"},
        "events": [{"name": "spike"}],
        "outcomes": [{"name": "ret"}],
    }


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    return tmp_path / "experiment.yaml"


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------
class TestJsonLoader:
    def test_load_minimal_json(self, tmp_path: Path):
        path = tmp_path / "test.json"
        with path.open("w") as f:
            json.dump(_minimal_dict(), f)
        spec = load_experiment(path)
        assert spec.experiment_name == "test"

    def test_json_not_a_dict(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        with path.open("w") as f:
            json.dump([1, 2, 3], f)
        with pytest.raises(LoaderError, match="mapping"):
            load_experiment(path)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------
class TestYamlLoader:
    def test_load_minimal_yaml(self, tmp_config: Path):
        import yaml  # noqa: PLC0415

        with tmp_config.open("w") as f:
            yaml.dump(_minimal_dict(), f)
        spec = load_experiment(tmp_config)
        assert spec.experiment_name == "test"
        assert len(spec.events) == 1

    def test_load_yaml_with_all_sections(self, tmp_path: Path):
        import yaml  # noqa: PLC0415

        data = {
            "version": 1,
            "experiment": {"name": "full_test", "type": "event_study",
                           "description": "Full config"},
            "dataset": {"source": "data.parquet", "symbol": "BTC",
                        "timeframe": "1m", "start": "2024-01-01",
                        "end": "2024-12-31", "timezone": "UTC"},
            "features": [{"name": "vol_sma", "kind": "indicator",
                          "params": {"window": 50}}],
            "events": [{"name": "volume_spike", "params": {"multiplier": 3.0},
                        "cooldown_bars": 3}],
            "outcomes": [{"name": "forward_return",
                          "params": {"horizons": [1, 5, 20]}}],
            "filters": {"pre_event": ["vol > 1000"]},
            "group_by": ["hour"],
            "analysis": {
                "confidence": {"method": "bootstrap", "iterations": 2000, "ci": 0.95},
                "statistics": {"include": ["mean", "std", "hit_rate"],
                               "quantiles": [0.05, 0.25, 0.5, 0.75, 0.95]},
            },
            "reporting": {"output_dir": "artifacts/test",
                          "formats": ["csv", "json"],
                          "charts": ["distribution"]},
            "execution": {"seed": 7, "max_workers": 2, "cache_features": True},
        }
        p = tmp_path / "full.yaml"
        with p.open("w") as f:
            yaml.dump(data, f)
        spec = load_experiment(p)
        assert spec.experiment_name == "full_test"
        assert len(spec.features) == 1
        assert spec.execution is not None
        assert spec.execution.seed == 7

    def test_load_yaml_validation_errors(self, tmp_path: Path):
        import yaml  # noqa: PLC0415

        bad = {
            "version": 99,
            "experiment": {"name": "", "type": "unknown"},
            "dataset": {"source": "", "symbol": "", "timeframe": ""},
            "events": [{"name": ""}],
            "outcomes": [{"name": ""}],
        }
        p = tmp_path / "bad.yaml"
        with p.open("w") as f:
            yaml.dump(bad, f)
        with pytest.raises(LoaderError) as exc:
            load_experiment(p)
        assert "validation failed" in str(exc.value).lower()
        assert len(exc.value.errors) > 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------
class TestLoaderErrors:
    def test_file_not_found(self):
        with pytest.raises(LoaderError, match="not found"):
            load_experiment("nonexistent.yaml")

    def test_unsupported_extension(self, tmp_path: Path):
        p = tmp_path / "config.toml"
        p.write_text("key = 'value'")
        with pytest.raises(LoaderError, match="extension"):
            load_experiment(p)

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(LoaderError):
            load_experiment(p)

    def test_not_a_mapping(self, tmp_path: Path):
        p = tmp_path / "scalar.json"
        with p.open("w") as f:
            json.dump("just a string", f)
        with pytest.raises(LoaderError, match="mapping"):
            load_experiment(p)
