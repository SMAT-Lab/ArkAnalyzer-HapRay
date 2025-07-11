"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import hashlib
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from hapray.actions.perf_action import PerfAction
from hapray.actions.update_action import UpdateAction
from hapray.actions.opt_action import OptAction


def check_report(report_path: str, perf_steps: [int]):
    # report
    report_html = os.path.join(report_path, 'report/hapray_report.html')
    assert os.path.exists(report_html), f'{os.path.basename(report_path)} hapray_report.html must exist'

    # htrace
    component_reusability_report = os.path.join(report_path, 'htrace/component_reusability_report.json')
    assert os.path.exists(component_reusability_report), f'{os.path.basename(report_path)} component_reusability_report.json must exist'
    empty_frames_analysis = os.path.join(report_path, 'htrace/empty_frames_analysis.json')
    assert os.path.exists(empty_frames_analysis), f'{os.path.basename(report_path)} empty_frames_analysis.json must exist'
    frame_analysis_summary = os.path.join(report_path, 'htrace/frame_analysis_summary.json')
    assert os.path.exists(frame_analysis_summary), f'{os.path.basename(report_path)} frame_analysis_summary.json must exist'

    # hiperf
    hiperf_info = os.path.join(report_path, 'hiperf/hiperf_info.json')
    assert os.path.exists(hiperf_info)
    with open(hiperf_info, 'r', encoding='UTF-8') as f:
        data = json.load(f)
        for i in range(len(data[0]['steps'])):
            step = data[0]['steps'][i]
            if len(perf_steps) > i:
                assert perf_steps[i] * 0.9 < step['count'], report_path
                assert perf_steps[i] * 1.1 > step['count'], report_path


def calculate_hash(files_path: [str], algorithm='sha256', block_size=65536):
    hasher = hashlib.new(algorithm)
    try:
        for file_path in files_path:
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(block_size)
                    if not data:
                        break
                    hasher.update(data)
        return hasher.hexdigest()
    except Exception as e:
        return f"Error: {str(e)}"


def check_update(report_path: str):
    files_path = []
    scenes_dir = [
        'PerformanceDynamic_ComponentReusable_new',
        'PerformanceDynamic_ComponentReusable_old',
        'ResourceUsage_PerformanceDynamic_Douyin_1000'
    ]
    for scene_dir in scenes_dir:
        files_path.append(os.path.join(scene_dir, report_path, 'report/hapray_report.html'))
        files_path.append(os.path.join(scene_dir, report_path, 'htrace/component_reusability_report.json'))
        files_path.append(os.path.join(scene_dir, report_path, 'htrace/empty_frames_analysis.json'))
        files_path.append(os.path.join(scene_dir, report_path, 'htrace/frame_analysis_summary.json'))

    before = calculate_hash(files_path)
    UpdateAction.execute(['-r', report_path])
    end = calculate_hash(files_path)
    assert before == end, f'{os.path.basename(report_path)} files hash must equal {before} == {end}'


@pytest.mark.integration
def test_opt_test():
    output = f'{time.time_ns()}opt.xlsx'
    command_args = [
        '-i',
        os.path.join(os.path.dirname(__file__), 'test_suite-default-unsigned.hsp'),
        '-o',
        output
    ]

    result = OptAction.execute(command_args)

    # 更健壮的断言
    assert result is not None, "Result should not be None"
    assert len(result) > 0, "Result should have at least one entry"
    assert len(result[0]) > 1, "First entry should have multiple elements"

    value_row = result[0][1].values[0]
    assert value_row[0].endswith('arm64-v8a/libc++_shared.so'), \
        f"Unexpected library path: {value_row[0]}"
    assert value_row[2] == 'High Optimization (O3 dominant)', \
        f"Unexpected optimization level: {value_row[2]}"
    os.unlink(output)


@pytest.mark.integration
def test_integration_performance_test():
    test_cases = ['--run_testcases', ".*Reusable.*", ".*Douyin_1000", '--round', '1']

    # test perf
    report_path = PerfAction.execute(test_cases)
    assert report_path is not None, 'PerfAction->execute return is not None'
    assert os.path.exists(report_path), 'PerfAction->execute report_path must exist.'

    check_report(os.path.join(report_path, 'PerformanceDynamic_ComponentReusable_new'), [1567135027])
    check_report(os.path.join(report_path, 'PerformanceDynamic_ComponentReusable_old'), [1622226867])
    check_report(os.path.join(report_path, 'ResourceUsage_PerformanceDynamic_Douyin_1000'), [])

    # test update
    check_update(report_path)
