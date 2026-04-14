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

import argparse
import io
import logging
import multiprocessing
import os
import sys
from logging.handlers import RotatingFileHandler

from hapray import VERSION
from hapray.actions.compare_action import CompareAction
from hapray.actions.gui_agent_action import GuiAgentAction
from hapray.actions.haptest_action import HapTestAction

# from hapray.actions.gui_agent_action import GuiAgentAction
from hapray.actions.hilog_action import HilogAction
from hapray.actions.perf_action import PerfAction
from hapray.actions.prepare_action import PrepareAction
from hapray.actions.root_cause_action import RootCauseAction
from hapray.actions.static_action import StaticAction
from hapray.actions.ui_action import UIAction
from hapray.actions.ui_compare_action import UICompareAction
from hapray.actions.update_action import UpdateAction
from hapray.core.common.action_return import is_valid_action_execute_return
from hapray.core.common.machine_output import finish_perf_testing_contract
from hapray.core.common.path_utils import get_log_file_path, get_runtime_root


def _ensure_writable_cwd():
    """
    在打包后的 macOS App 中，默认 cwd 可能落在只读的 Resources 目录，
    会导致依赖库使用相对路径（例如 ./tmp_hypium）时创建目录失败。
    这里仅在 macOS 下，把进程 cwd 统一切到当前用户的数据目录下。
    """
    if sys.platform != 'darwin':
        return
    try:
        os.chdir(str(get_runtime_root()))
    except Exception:
        # 如果这里失败，就保持原 cwd，让上层明确暴露错误，而不是静默吞掉
        logging.warning('切换到可写工作目录失败，当前 cwd: %s', os.getcwd())


def configure_logging(log_file='HapRay.log', machine_json=False):
    """配置日志系统，同时输出到控制台和文件。machine_json 为 True 时控制台走 stderr（tool-result 走 stdout 兜底时）。"""
    # 在 Windows 上设置 UTF-8 编码
    if sys.platform == 'win32':
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        # 重新配置 stdout 和 stderr 的编码
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                # 如果 reconfigure 方法失败，使用 TextIOWrapper 包装
                try:
                    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
                except Exception:
                    pass

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台处理器 - 使用 UTF-8 编码和错误处理（machine-json 模式下走 stderr）
    _log_stream = sys.stderr if machine_json else sys.stdout
    console_handler = logging.StreamHandler(_log_stream)
    console_handler.setLevel(logging.INFO)
    # 对于 Windows，使用 UTF-8 编码包装器
    if sys.platform == 'win32' and hasattr(_log_stream, 'buffer'):
        try:
            utf8_log = io.TextIOWrapper(_log_stream.buffer, encoding='utf-8', errors='replace')
            console_handler.stream = utf8_log
        except Exception:
            pass
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）- 使用 UTF-8 编码和错误处理
    log_file_path = get_log_file_path(log_file)
    try:
        file_handler = RotatingFileHandler(
            log_file_path,
            mode='a',
            maxBytes=10 * 1024 * 1024,
            backupCount=10,
            encoding='UTF-8',
            errors='replace',
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # 如果日志文件仍然不可写，则只保留控制台输出，避免程序崩溃
        logger.warning('日志文件不可写，将仅输出到控制台：%s', log_file_path)


def _strip_contract_flags(argv: list[str]) -> tuple[list[str], bool, str | None]:
    """
    移除 --machine-json、--result-file <path>，返回 (新 argv, machine_json, result_file)。
    契约优先写入 result_file 或与 output 同目录的 hapray-tool-result.json；仅当无可用路径或显式需要时用 machine-json 走 stdout。
    """
    machine_json = '--machine-json' in argv
    result_file: str | None = None
    out: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == '--machine-json':
            i += 1
            continue
        if argv[i] == '--result-file' and i + 1 < len(argv):
            result_file = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return out, machine_json, result_file


class HapRayCmd:
    def __init__(self):
        argv_rest, machine_json, result_file = _strip_contract_flags(sys.argv[1:])

        # 先确保 cwd 在一个可写目录（仅 macOS 生效），避免依赖内部使用 ./tmp_xxx 时报只读错误
        _ensure_writable_cwd()
        configure_logging('HapRay.log', machine_json=machine_json)

        actions = {
            'perf': PerfAction,
            'static': StaticAction,
            'update': UpdateAction,
            'compare': CompareAction,
            'prepare': PrepareAction,
            'ui': UIAction,
            'ui-compare': UICompareAction,
            'hilog': HilogAction,
            'gui-agent': GuiAgentAction,
            'haptest': HapTestAction,
            'root-cause': RootCauseAction,
        }

        parser = argparse.ArgumentParser(
            description='Code-oriented Performance Analysis for OpenHarmony Apps',
            usage=f'{sys.argv[0]} [--result-file PATH] [--machine-json] [action] [<args>]\nActions: {" | ".join(actions.keys())}',
            add_help=False,
            epilog='Tool-result 契约: 优先写入文件（--result-file 或与 output/report 同目录的 hapray-tool-result.json）；'
            '仅当无可用路径或写失败时用 --machine-json 输出到 stdout。',
        )

        parser.add_argument(
            'action',
            choices=list(actions.keys()),
            nargs='?',
            default='perf',
            help='Action to perform (perf: performance testing, static: HAP static analysis, update: update reports, compare: compare reports, prepare: simplified test execution, ui: UI analysis, ui-compare: UI tree comparison, hilog: hilog log analysis, haptest: strategy-driven UI automation with perf collection, root-cause: LLM-powered root cause analysis)',
        )
        # Parse action（使用已去掉 --machine-json 的 argv）
        action_args = []
        if len(argv_rest[:1]) > 0 and argv_rest[0] not in actions:
            action_args.append('perf')
            sub_args = argv_rest
        else:
            action_args = argv_rest[:1]
            sub_args = argv_rest[1:]
        args = parser.parse_args(action_args)

        # Dispatch to action handler（返回值须为 (exit_code, reports_path)）
        ret = actions[args.action].execute(sub_args)
        if not is_valid_action_execute_return(ret):
            logging.warning(
                'Action %s 的 execute 返回了非契约类型 %s，契约解析可能不完整', args.action, type(ret).__name__
            )
        if '--multiprocessing-fork' not in sys.argv:
            finish_perf_testing_contract(
                args.action,
                ret,
                sub_args,
                tool_version=VERSION,
                explicit_result_file=result_file,
                machine_json=machine_json,
            )

        if is_valid_action_execute_return(ret):
            sys.exit(ret[0])
        sys.exit(1)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    HapRayCmd()
