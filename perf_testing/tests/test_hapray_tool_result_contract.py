"""
验证 HapRay tool-result v1 与 docs/schemas/hapray-tool-result-v1.json 一致，
并校验 perf_testing 的 build_tool_result / interpret_perf_testing_return 产出符合 Schema。
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from hapray.core.common.action_return import ActionExecuteReturn, is_valid_action_execute_return
from hapray.core.common.machine_output import (
    SCHEMA_VERSION,
    build_tool_result,
    enrich_gui_agent_contract_outputs,
    interpret_perf_testing_return,
)


def _schema_path() -> Path:
    # perf_testing/ -> my-dev/docs/schemas/
    return Path(__file__).resolve().parent.parent.parent / "docs" / "schemas" / "hapray-tool-result-v1.json"


@pytest.fixture(scope="module")
def tool_result_validator():
    with open(_schema_path(), encoding="utf-8") as f:
        schema = json.load(f)
    return jsonschema.Draft202012Validator(schema)


def test_schema_file_exists():
    assert _schema_path().is_file(), f"缺少 Schema 文件: {_schema_path()}"


def test_schema_version_constant_matches_schema():
    with open(_schema_path(), encoding="utf-8") as f:
        schema = json.load(f)
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION


@pytest.mark.parametrize(
    "tool_id",
    ["perf_testing", "optimization_detector", "static_analyzer", "symbol_recovery"],
)
def test_build_tool_result_minimal_validates(tool_result_validator, tool_id: str):
    payload = build_tool_result(
        tool_id,
        success=True,
        exit_code=0,
        outputs={},
        error=None,
        tool_version="test",
    )
    tool_result_validator.validate(payload)


@pytest.mark.parametrize(
    ("ret", "expect_ok", "expect_code"),
    [
        ((0, "/tmp/reports"), True, 0),
        ((1, ""), False, 1),
        ((2, "/p"), False, 2),
    ],
)
def test_interpret_perf_testing_return_maps_to_valid_payload(
    tool_result_validator, ret: ActionExecuteReturn, expect_ok: bool, expect_code: int
):
    assert is_valid_action_execute_return(ret)
    ok, code, outputs, err = interpret_perf_testing_return("perf", ret)
    assert ok is expect_ok
    assert code == expect_code
    payload = build_tool_result(
        "perf_testing",
        success=ok,
        exit_code=code,
        action="perf",
        outputs=outputs,
        error=err,
        tool_version="0",
    )
    tool_result_validator.validate(payload)


def test_success_null_still_validates(tool_result_validator):
    """Schema 允许 success 为 null（历史兼容）。"""
    payload = build_tool_result(
        "perf_testing",
        success=None,
        exit_code=0,
        outputs={},
        error=None,
    )
    tool_result_validator.validate(payload)


def test_enrich_gui_agent_outputs_step_events_and_partial(tmp_path, tool_result_validator):
    """gui-agent enrich：llm_step_events、perf_steps_summary、partial、contract_mode。"""
    root = tmp_path / "reports" / "com.example.app" / "scene1"
    root.mkdir(parents=True)
    (root / "testInfo.json").write_text("{}", encoding="utf-8")
    steps = [{"stepIdx": 1, "name": "step1", "description": "场景"}]
    (root / "steps.json").write_text(json.dumps(steps, ensure_ascii=False), encoding="utf-8")
    ui_step = root / "ui" / "step1"
    ui_step.mkdir(parents=True)
    pages = [
        {
            "page_idx": 1,
            "gui_agent": {
                "step_index": 1,
                "finished": False,
                "success": True,
                "error_code": None,
                "action": "tap",
                "message": "ok",
            },
        }
    ]
    (ui_step / "pages.json").write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")

    extra = enrich_gui_agent_contract_outputs(str(tmp_path / "reports"))
    assert extra["partial"] is False
    ga = extra["gui_agent"]
    assert ga["contract_mode"] == "final"
    assert ga["reports_dir"] == str((tmp_path / "reports").resolve())
    sc = ga["scenes"][0]
    assert sc["step_count"] == 1
    assert sc["perf_steps_summary"][0]["step_index"] == 1
    assert len(sc["llm_step_events"]) == 1
    ev = sc["llm_step_events"][0]
    assert ev["step_index"] == 1
    assert ev["finished"] is False
    assert ev["error_code"] is None

    payload = build_tool_result(
        "perf_testing",
        success=True,
        exit_code=0,
        action="gui-agent",
        outputs={"reports_path": str(tmp_path / "reports"), **extra},
        error=None,
        tool_version="0",
    )
    tool_result_validator.validate(payload)
