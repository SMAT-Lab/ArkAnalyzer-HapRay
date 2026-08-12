"""HAPRAY_WORKSPACE / ensure-workspace-layout 落盘一致性。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hapray.core.common import path_utils


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(path_utils.ENV_HAPRAY_WORKSPACE, str(tmp_path))
    return tmp_path


def test_get_reports_root_uses_workspace(workspace: Path) -> None:
    root = path_utils.get_reports_root()
    assert root == workspace / 'reports'
    assert root.is_dir()


def test_get_user_data_root_maps_like_ensure_workspace_layout(workspace: Path) -> None:
    assert path_utils.get_user_data_root('logs') == workspace / 'logs'
    assert path_utils.get_user_data_root('runtime') == workspace / '.hapray' / 'runtime'
    assert path_utils.get_user_data_root('gui_agent') == workspace / '.hapray' / 'gui_agent'
    assert path_utils.get_haptest_reports_root() == workspace / '.hapray' / 'haptest_reports'


def test_without_workspace_falls_back_to_cwd_on_non_darwin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(path_utils.ENV_HAPRAY_WORKSPACE, raising=False)
    monkeypatch.chdir(tmp_path)
    if sys.platform == 'darwin':
        pytest.skip('macOS 无 HAPRAY_WORKSPACE 时回退到 ~/ArkAnalyzer-HapRay')
    assert path_utils.get_reports_root() == tmp_path / 'reports'
