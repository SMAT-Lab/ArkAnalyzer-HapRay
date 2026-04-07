"""
CLI 级契约冒烟：不依赖真机/HDC，验证失败路径仍写出 tool-result 且 JSON 可解析。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hapray.core.common.machine_output import DEFAULT_RESULT_BASENAME, resolve_perf_testing_result_path


def _perf_testing_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_resolve_prepare_result_path_with_reports_path():
    """成功时 prepare 返回非空目录，契约应落在该目录下。"""
    p = resolve_perf_testing_result_path('prepare', (0, '/tmp/prep_session'), [], None)
    assert p == str(Path('/tmp/prep_session') / DEFAULT_RESULT_BASENAME)


def test_static_missing_input_writes_tool_result(tmp_path: Path):
    """static 在输入不存在时 exit 1，且 --result-file 处为合法 tool-result JSON。"""
    missing_hap = tmp_path / 'does_not_exist.hap'
    result_file = tmp_path / 'hapray-tool-result.json'
    r = subprocess.run(
        [
            sys.executable,
            '-m',
            'scripts.main',
            '--result-file',
            str(result_file),
            'static',
            '-i',
            str(missing_hap),
        ],
        cwd=_perf_testing_root(),
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert result_file.is_file()
    payload = json.loads(result_file.read_text(encoding='utf-8'))
    assert payload['tool_id'] == 'perf_testing'
    assert payload['action'] == 'static'
    assert payload['exit_code'] == 1
    assert payload['success'] is False
