import json
import pytest
from ssbt.service.errors import (
    E_DATA_SCHEMA,
    E_LOOKAHEAD,
    E_RESOURCE_LIMIT,
    E_RUN_NOT_FOUND,
    E_STRATEGY_INIT,
    ErrorSpec,
    ServiceError,
)
from ssbt.service.schemas import (
    BacktestRequest,
    BacktestResponse,
    DataSpec,
    ExecutionSpec,
    ResourceLimitSpec,
    StrategySpec,
)


def test_service_error_codes_and_to_spec():
    codes = [
        E_DATA_SCHEMA,
        E_STRATEGY_INIT,
        E_RESOURCE_LIMIT,
        E_LOOKAHEAD,
        E_RUN_NOT_FOUND,
    ]
    assert len(codes) == 5

    err = ServiceError(
        code=E_DATA_SCHEMA,
        message="Missing required column 'timestamp'",
        hint="Rename Date to timestamp",
        details={"missing": ["timestamp"]},
    )
    assert err.code == E_DATA_SCHEMA
    assert str(err) == f"[{E_DATA_SCHEMA}] Missing required column 'timestamp'"

    spec = err.to_spec()
    assert isinstance(spec, ErrorSpec)
    assert spec.code == E_DATA_SCHEMA
    assert spec.message == "Missing required column 'timestamp'"
    assert spec.hint == "Rename Date to timestamp"
    assert spec.details == {"missing": ["timestamp"]}


def test_service_error_defaults():
    err = ServiceError(code=E_STRATEGY_INIT, message="Init failed")
    assert err.hint is None
    assert err.details == {}
    spec = err.to_spec()
    assert spec.hint is None
    assert spec.details == {}


def test_backtest_request_defaults_and_serialization():
    req = BacktestRequest()
    assert req.version == "1.0"
    assert req.run_id is None
    assert req.strategy.name == "Strategy"
    assert req.data.symbol == "ASSET"
    assert req.execution.initial_cash == 100_000.0
    assert req.limits.max_bars == 1_000_000

    custom_req = BacktestRequest(
        version="1.1",
        run_id="run_test_001",
        strategy=StrategySpec(name="SmaCross", kwargs={"fast": 10, "slow": 20}),
        data=DataSpec(symbol="BTC-USD"),
        execution=ExecutionSpec(initial_cash=50_000.0),
        limits=ResourceLimitSpec(max_bars=500),
    )

    req_dict = custom_req.to_dict()
    assert req_dict["version"] == "1.1"
    assert req_dict["run_id"] == "run_test_001"
    assert req_dict["strategy"]["name"] == "SmaCross"
    assert req_dict["strategy"]["kwargs"] == {"fast": 10, "slow": 20}
    assert req_dict["data"]["symbol"] == "BTC-USD"
    assert req_dict["execution"]["initial_cash"] == 50_000.0
    assert req_dict["limits"]["max_bars"] == 500

    req_json = custom_req.to_json()
    parsed = json.loads(req_json)
    assert parsed["strategy"]["name"] == "SmaCross"
    assert parsed["data"]["symbol"] == "BTC-USD"


def test_backtest_response_serialization():
    err_spec = ErrorSpec(code=E_RESOURCE_LIMIT, message="Max bars exceeded", hint="Reduce dataset size")
    resp_failed = BacktestResponse(
        status="failed",
        run_id="run_failed_1",
        config_hash="abc12345",
        summary={},
        error=err_spec,
    )
    failed_dict = resp_failed.to_dict()
    assert failed_dict["status"] == "failed"
    assert failed_dict["error"]["code"] == E_RESOURCE_LIMIT
    assert failed_dict["error"]["message"] == "Max bars exceeded"

    failed_json = resp_failed.to_json()
    parsed_failed = json.loads(failed_json)
    assert parsed_failed["error"]["code"] == E_RESOURCE_LIMIT

    resp_success = BacktestResponse(
        status="success",
        run_id="run_success_1",
        config_hash="def67890",
        summary={"total_return": 0.15, "sharpe_ratio": 1.8},
        equity_curve=[[1000.0, 100_000.0], [2000.0, 115_000.0]],
        fills=[{"fill_id": "f1", "price": 100.0, "qty": 10}],
        trades=[{"pnl": 15000.0}],
        audit={"causality_verified": True},
        artifacts={"output_dir": "artifacts/run_success_1"},
    )
    success_dict = resp_success.to_dict()
    assert success_dict["status"] == "success"
    assert success_dict["summary"]["sharpe_ratio"] == 1.8
    assert len(success_dict["equity_curve"]) == 2
    assert success_dict["error"] is None

    success_json = resp_success.to_json()
    parsed_success = json.loads(success_json)
    assert parsed_success["summary"]["total_return"] == 0.15
