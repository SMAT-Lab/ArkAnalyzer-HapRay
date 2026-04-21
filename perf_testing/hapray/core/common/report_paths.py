"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
"""

from __future__ import annotations

import os
import re

_ROUND_DIR_PATTERN = re.compile(r'.*_round\d$')


def find_testcase_dirs_under_report_root(report_dir: str) -> list[str]:
    """在报告根目录下查找含 ``hiperf`` 的用例目录。

    1. 直接子目录：``<report_dir>/<case>/hiperf``
    2. 若未找到：再扫描一层 ``<report_dir>/<中间目录>/<case>/hiperf``（常见 GUI：
       ``.../perf_testing/<时间戳>/<用例名>/hiperf``）
    3. 若仍无：且 ``<report_dir>/hiperf`` 存在，则把 ``report_dir`` 本身视为单个用例根
    """
    testcase_dirs: list[str] = []

    if not os.path.isdir(report_dir):
        return testcase_dirs

    def _collect_direct_children(root: str, out: list[str]) -> None:
        for entry in os.listdir(root):
            if _ROUND_DIR_PATTERN.match(entry):
                continue
            full_path = os.path.join(root, entry)
            if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, 'hiperf')):
                out.append(full_path)

    _collect_direct_children(report_dir, testcase_dirs)
    if testcase_dirs:
        return testcase_dirs

    for entry in os.listdir(report_dir):
        if _ROUND_DIR_PATTERN.match(entry):
            continue
        mid = os.path.join(report_dir, entry)
        if not os.path.isdir(mid):
            continue
        _collect_direct_children(mid, testcase_dirs)

    if not testcase_dirs and os.path.exists(os.path.join(report_dir, 'hiperf')):
        testcase_dirs.append(report_dir)

    return testcase_dirs
