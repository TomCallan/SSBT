from __future__ import annotations
import json
import pytest

from ssbt.service import (
    E_DATA_SCHEMA,
    E_LOOKAHEAD,
    E_RESOURCE_LIMIT,
    E_RUN_NOT_FOUND,
    E_STRATEGY_INIT,
    BacktestResponse,
    ErrorSpec,
    ServiceError,
    explain_failure,
    get_agent_tool_spec,
)


def test_explain_failure_error_codes():
    codes = [
        E_DATA_SCHEMA,
        E_STRATEGY_INIT,
        E_RESOURCE_LIMIT,
        E_LOOKAHEAD,
        E_RUN_NOT_FOUND,
    ]
    required_keys = {
        "code",
        "message",
        "hint",
        "summary",
        "root_cause",
        "suggested_action",
        "code_fix_snippet",
    }

    for code in codes:
        diag = explain_failure(code)
        assert set(diag.keys()) == required_keys
        assert diag["code"] == code
        assert isinstance(diag["summary"], str) and len(diag["summary"]) > 0
        assert isinstance(diag["root_cause"], str) and len(diag["root_cause"]) > 0
        assert isinstance(diag["suggested_action"], str) and len(diag["suggested_action"]) > 0
        assert isinstance(diag["code_fix_snippet"], str) and len(diag["code_fix_snippet"]) > 0


def test_explain_failure_targets():
    # Test ErrorSpec target
    err_spec = ErrorSpec(code=E_DATA_SCHEMA, message="Missing close column", hint="Add close col")
    diag_spec = explain_failure(err_spec)
    assert diag_spec["code"] == E_DATA_SCHEMA
    assert diag_spec["message"] == "Missing close column"
    assert diag_spec["hint"] == "Add close col"

    # Test BacktestResponse target
    resp = BacktestResponse(
        status="FAILED",
        run_id="run_123",
        config_hash="hash_123",
        error=ErrorSpec(code=E_LOOKAHEAD, message="Future timestamp accessed", hint="Use point-in-time join"),
    )
    diag_resp = explain_failure(resp)
    assert diag_resp["code"] == E_LOOKAHEAD
    assert diag_resp["message"] == "Future timestamp accessed"
    assert diag_resp["hint"] == "Use point-in-time join"

    # Test ServiceError target
    svc_err = ServiceError(code=E_STRATEGY_INIT, message="Failed to import strategy", hint="Check module path")
    diag_svc = explain_failure(svc_err)
    assert diag_svc["code"] == E_STRATEGY_INIT
    assert diag_svc["message"] == "Failed to import strategy"
    assert diag_svc["hint"] == "Check module path"

    # Test generic Exception target
    exc = ValueError("Invalid numeric value")
    diag_exc = explain_failure(exc)
    assert diag_exc["code"] == "E_UNKNOWN"
    assert diag_exc["message"] == "Invalid numeric value"

    # Test JSON string target
    json_str = json.dumps({"code": E_RESOURCE_LIMIT, "message": "Bar limit exceeded", "hint": "Increase limit"})
    diag_json = explain_failure(json_str)
    assert diag_json["code"] == E_RESOURCE_LIMIT
    assert diag_json["message"] == "Bar limit exceeded"
    assert diag_json["hint"] == "Increase limit"


def test_get_agent_tool_spec_openai():
    specs = get_agent_tool_spec(provider="openai")
    assert isinstance(specs, list)
    assert len(specs) == 4

    tool_names = [tool["function"]["name"] for tool in specs]
    assert set(tool_names) == {"run_backtest", "explain_failure", "rerun", "compare"}

    for item in specs:
        assert item["type"] == "function"
        fn = item["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_get_agent_tool_spec_anthropic():
    specs = get_agent_tool_spec(provider="anthropic")
    assert isinstance(specs, list)
    assert len(specs) == 4

    tool_names = [tool["name"] for tool in specs]
    assert set(tool_names) == {"run_backtest", "explain_failure", "rerun", "compare"}

    for item in specs:
        assert "name" in item
        assert "description" in item
        assert "input_schema" in item
        assert item["input_schema"]["type"] == "object"


def test_get_agent_tool_spec_invalid_provider():
    with pytest.raises(ValueError, match="Unsupported LLM tool spec provider"):
        get_agent_tool_spec(provider="unsupported_provider")
