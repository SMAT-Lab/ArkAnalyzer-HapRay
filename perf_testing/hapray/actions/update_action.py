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
import json
import logging
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from hapray import VERSION
from hapray.core.common.action_return import ActionExecuteReturn
from hapray.core.common.symbol_recovery_bridge import (
    ENV_SO_DIR,
    ENV_SYMBOL_RECOVERY_EXE,
    ENV_SYMBOL_RECOVERY_PYTHON,
    ENV_SYMBOL_RECOVERY_ROOT,
    check_symbol_recovery_llm_ready,
    llm_env_ready_for_symbol_recovery,
    maybe_run_symbol_recovery_for_step,
    maybe_generate_symbol_recovery_html_for_step,
    parse_output_root_from_env,
    parse_stat_from_env,
    parse_top_n_from_env,
    probe_symbol_recovery_llm_runtime,
    resolve_effective_so_dir,
    resolve_symbol_recovery_exe,
    resolve_symbol_recovery_python,
    resolve_symbol_recovery_root,
    try_load_dotenv_for_llm,
)
from hapray.core.common.report_paths import find_testcase_dirs_under_report_root
from hapray.core.config.config import Config
from hapray.core.report import ReportGenerator, create_perf_summary_excel
from hapray.ext.hapflow.runner import run_hapflow_pipeline
from hapray.mode.mode import Mode
from hapray.mode.simple_mode import (
    create_simple_mode_structure,
    restore_perf_json_from_flame_html,
    update_load_excel_with_recovered_symbols,
)


class UpdateAction:
    """Handles report update actions for existing performance reports."""

    @staticmethod
    def _read_bundle_name_from_testinfo(case_dir: str) -> str:
        test_info = Path(case_dir) / 'testInfo.json'
        if not test_info.is_file():
            return ''
        try:
            raw = json.loads(test_info.read_text(encoding='utf-8', errors='replace'))
        except (OSError, json.JSONDecodeError):
            return ''
        if not isinstance(raw, dict):
            return ''
        return str(raw.get('app_id', '')).strip()

    @staticmethod
    def _collect_bundle_names(testcase_dirs: list[str]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for case_dir in testcase_dirs:
            bundle = UpdateAction._read_bundle_name_from_testinfo(case_dir)
            if not bundle:
                continue
            if bundle in seen:
                continue
            seen.add(bundle)
            names.append(bundle)
        return names

    @staticmethod
    def _looks_like_downloaded_libs(path: Path) -> bool:
        try:
            return any(path.rglob('*.so'))
        except OSError:
            return False

    @staticmethod
    def _run_hdc_cmd(args: list[str], timeout_sec: int = 20) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                ['hdc', *args],
                check=False,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout_sec,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return (False, str(e))
        output = f'{completed.stdout or ""}\n{completed.stderr or ""}'.strip()
        return (completed.returncode == 0, output)

    @staticmethod
    def _is_hdc_device_ready() -> bool:
        if not shutil.which('hdc'):
            return False
        ok, out = UpdateAction._run_hdc_cmd(['list', 'targets'], timeout_sec=10)
        if not ok:
            return False
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        return len(lines) > 0

    @staticmethod
    def _try_recv_remote_dir(remote_dir: str, local_dir: Path) -> bool:
        local_dir.parent.mkdir(parents=True, exist_ok=True)
        ok, out = UpdateAction._run_hdc_cmd(['file', 'recv', remote_dir, str(local_dir)], timeout_sec=90)
        if not ok:
            logging.debug('hdc recv failed: %s -> %s (%s)', remote_dir, local_dir, out)
            return False
        return UpdateAction._looks_like_downloaded_libs(local_dir)

    @staticmethod
    def _parse_json_from_shell_output(out: str) -> Optional[dict]:
        """解析 bm dump 等命令输出中的 JSON（跳过前缀说明文字）。"""
        if not out or not out.strip():
            return None
        i = out.find('{')
        if i < 0:
            return None
        tail = out[i:]
        try:
            data = json.loads(tail)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    # bm dump JSON 中常见「安装目录 / 模块根路径」字段（仅按包名查询，不依赖 pid）
    _BM_PATH_KEYS = frozenset(
        {
            'modulePath',
            'hapPath',
            'moduleInstallPath',
            'bundleDataDir',
            'bundleDataPath',
            'appDataDir',
            'hapModulePath',
        }
    )

    @staticmethod
    def _collect_bm_install_paths(data: object, bundle_name: str) -> list[str]:
        """从 bm dump -n <包名> 的 JSON 中收集与安装相关的目录路径。"""
        bases: list[str] = []

        def walk(obj: object) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and k in UpdateAction._BM_PATH_KEYS and v.startswith('/'):
                        bases.append(v.rstrip('/'))
                    else:
                        walk(v)
            elif isinstance(obj, list):
                for x in obj:
                    walk(x)

        walk(data)
        # 补充：JSON 中出现且包含该包名的 /data 路径（模块根、沙箱路径等）
        extra: list[str] = []

        def walk_bundle_strings(obj: object) -> None:
            if len(extra) >= 24:
                return
            if isinstance(obj, dict):
                for v in obj.values():
                    walk_bundle_strings(v)
            elif isinstance(obj, list):
                for x in obj:
                    walk_bundle_strings(x)
            elif (
                isinstance(obj, str)
                and obj.startswith('/data/')
                and bundle_name in obj
                and obj.rstrip('/').count('/') >= 4
            ):
                p = obj.rstrip('/')
                if p.endswith('.hap') or p.endswith('.har'):
                    p = str(Path(p).parent)
                if p not in extra:
                    extra.append(p)

        walk_bundle_strings(data)
        merged: list[str] = []
        seen: set[str] = set()
        for p in bases + extra:
            if p and p not in seen:
                seen.add(p)
                merged.append(p)
        return merged

    @staticmethod
    def _paths_to_lib_recv_targets(base: str) -> list[tuple[str, Path]]:
        """将 bm 给出的模块/安装根路径展开为可能存放 .so 的远端目录。"""
        b = base.rstrip('/')
        if not b.startswith('/'):
            return []
        if b.endswith('.hap') or b.endswith('.har'):
            b = str(Path(b).parent)
        triples: list[tuple[str, Path]] = []
        for suffix, local_leaf in (
            ('/libs', Path('')),
            ('/libs/arm64', Path('arm64')),
        ):
            triples.append((b + suffix, local_leaf))
        return triples

    @staticmethod
    def _static_paths_by_bundle_name(bundle_name: str) -> list[str]:
        """无 bm 或为兜底时，仅用包名拼常见 bundle 目录（与系统集成约定有关）。"""
        return [
            f'/data/storage/el1/bundle/{bundle_name}/libs',
            f'/data/storage/el1/bundle/{bundle_name}/libs/arm64',
            f'/data/app/el1/bundle/{bundle_name}/libs',
            f'/data/app/el1/bundle/{bundle_name}/libs/arm64',
            f'/data/app/el2/bundle/{bundle_name}/libs',
            f'/data/app/el2/bundle/{bundle_name}/libs/arm64',
        ]

    @staticmethod
    def _recv_candidates_for_bundle(bundle_name: str, target_root: Path) -> list[tuple[str, Path]]:
        """顺序：先 bm dump 按包名解析安装路径，再用包名字符串兜底路径。"""
        ordered: list[tuple[str, Path]] = []
        seen: set[tuple[str, str]] = set()

        def add_pair(remote: str, local_leaf: Path) -> None:
            key = (remote, str(local_leaf))
            if key in seen:
                return
            seen.add(key)
            local = target_root if not local_leaf.parts else target_root / local_leaf
            ordered.append((remote, local))

        ok, out = UpdateAction._run_hdc_cmd(['shell', 'bm', 'dump', '-n', bundle_name], timeout_sec=45)
        if ok:
            dump = UpdateAction._parse_json_from_shell_output(out)
            if dump is None:
                logging.warning(
                    'bm dump -n %s produced no parseable JSON (first 200 chars): %s',
                    bundle_name,
                    out[:200].replace('\n', ' ') if out else '',
                )
            else:
                bm_paths = UpdateAction._collect_bm_install_paths(dump, bundle_name)
                logging.info(
                    'bm dump -n %s: extracted %d path(s) by bundle name for .so recv',
                    bundle_name,
                    len(bm_paths),
                )
                for base in bm_paths:
                    for remote, leaf in UpdateAction._paths_to_lib_recv_targets(base):
                        add_pair(remote, leaf)
        else:
            logging.warning(
                'bm dump -n %s failed (non-zero exit). stderr/stdout: %s',
                bundle_name,
                (out[:400] if out else '').replace('\n', ' '),
            )

        for remote in UpdateAction._static_paths_by_bundle_name(bundle_name):
            add_pair(remote, Path(''))

        return ordered

    @staticmethod
    def _download_libs_for_bundle(bundle_name: str, bundle_root: Path) -> Optional[Path]:
        target = bundle_root / bundle_name
        if UpdateAction._looks_like_downloaded_libs(target):
            return target

        for remote_dir, local_base in UpdateAction._recv_candidates_for_bundle(bundle_name, target):
            if UpdateAction._try_recv_remote_dir(remote_dir, local_base):
                return target
        return None

    @staticmethod
    def _auto_prepare_so_dir(report_dir: str, testcase_dirs: list[str]) -> tuple[Optional[str], str]:
        bundle_names = UpdateAction._collect_bundle_names(testcase_dirs)
        if not bundle_names:
            return (None, 'no_bundle_name')
        if not UpdateAction._is_hdc_device_ready():
            return (None, 'hdc_or_device_unavailable')

        libs_root = Path(report_dir) / '.symbol_recovery_libs'
        libs_root.mkdir(parents=True, exist_ok=True)
        resolved: list[Path] = []
        for bundle in bundle_names:
            got = UpdateAction._download_libs_for_bundle(bundle, libs_root)
            if got is not None:
                resolved.append(got)
                logging.info('Auto-downloaded libs for %s -> %s', bundle, got)
            else:
                logging.warning('Failed to auto-download libs for bundle: %s', bundle)
        if not resolved:
            return (None, 'libs_download_failed')
        if len(resolved) == 1:
            return (str(resolved[0].resolve()), 'auto_device_bundle')
        return (str(libs_root.resolve()), 'auto_device_bundle_root')

    @staticmethod
    def _parse_bool_env(name: str, default: bool = False) -> bool:
        raw = os.environ.get(name, '').strip().lower()
        if not raw:
            return default
        return raw in {'1', 'true', 'yes', 'on'}

    @staticmethod
    def execute(args) -> ActionExecuteReturn:
        """Executes report update workflow."""
        parser = argparse.ArgumentParser(
            description='Update existing performance reports',
            prog='ArkAnalyzer-HapRay update',
        )
        parser.add_argument(
            '-r',
            '--report_dir',
            required=True,
            help=(
                '一次跑测输出根目录：其下每个用例为子目录且含 hiperf/（或该根下有一层时间戳等中间目录再为用例）。'
                '不要填 perf-testing 的安装目录（如 dist）。'
            ),
        )
        parser.add_argument('--so_dir', default=None, help='Directory for symbolicated .so files')
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )
        parser.add_argument(
            '--mode',
            type=int,
            default=Mode.COMMUNITY,
            help=f'select mode: {Mode.COMMUNITY} COMMUNITY, {Mode.SIMPLE} SIMPLE',
        )
        parser.add_argument(
            '--perfs',
            nargs='+',
            default=[],
            help='SIMPLE mode need perf paths (supports multiple files)',
        )
        parser.add_argument(
            '--app-name',
            default='',
            help='SIMPLE mode optional app name',
        )
        parser.add_argument(
            '--rom-version',
            default='',
            help='SIMPLE mode optional rom version',
        )
        parser.add_argument(
            '--app-version',
            default='',
            help='SIMPLE mode optional app version',
        )
        parser.add_argument(
            '--scene',
            default='',
            help='SIMPLE mode optional scene name',
        )
        parser.add_argument(
            '--traces',
            nargs='+',
            default=[],
            help='SIMPLE mode optional trace paths (supports multiple files). If not provided, only perf analysis will be performed',
        )
        parser.add_argument(
            '--package-name',
            default='',
            help='SIMPLE mode need package name',
        )
        parser.add_argument(
            '--pids', nargs='+', type=int, default=[], help='SIMPLE mode可选填pids（提供整数ID列表，如: --pids 1 2 3）'
        )
        parser.add_argument(
            '--steps', default='', help='SIMPLE mode可选填steps.json文件路径，如果提供则使用该文件而不是自动生成'
        )
        parser.add_argument(
            '--time-ranges',
            nargs='*',
            default=[],
            help='可选的时间范围过滤，格式为 "startTime-endTime"（纳秒），支持多个时间范围，如: --time-ranges "1000000000-2000000000" "3000000000-4000000000"',
        )
        parser.add_argument(
            '--use-refined-lib-symbol',
            action='store_true',
            default=False,
            help='Enable refined mode for memory analysis: use callchain to find real allocation source instead of database default values',
        )
        parser.add_argument(
            '--export-comparison',
            action='store_true',
            default=False,
            help='Export comparison Excel showing differences between original and refined lib_id/symbol_id values',
        )
        parser.add_argument(
            '--symbol-statistic', type=str, default=None, help='Path to SymbolsStatistic.txt for symbol analysis'
        )
        parser.add_argument(
            '--hapflow',
            type=str,
            metavar='HOMECHECK_DIR',
            help='Enable HapFlow pipeline and specify Homecheck root directory',
        )
        parser.add_argument(
            '--no-thread-analysis',
            action='store_true',
            default=False,
            help='Disable redundant thread analysis (ThreadAnalyzer). By default thread analysis is enabled.',
        )
        parser.add_argument(
            '--symbol-recovery-top-n',
            type=int,
            default=None,
            help=(
                'Symbol recovery: top N hot functions (default 50; env HAPRAY_SYMBOL_RECOVERY_TOP_N). '
                'Uses tools/symbol_recovery checkout: prefers venv entry ``symbol-recovery`` exe, then ``python main.py``; '
                'override with HAPRAY_SYMBOL_RECOVERY_EXE or HAPRAY_SYMBOL_RECOVERY_PYTHON.'
            ),
        )
        parser.add_argument(
            '--symbol-recovery-stat',
            choices=['event_count', 'call_count'],
            default=None,
            help='Symbol recovery stat method (default event_count; env HAPRAY_SYMBOL_RECOVERY_STAT)',
        )
        parser.add_argument(
            '--symbol-recovery-output',
            default=None,
            help='Optional root dir for symbol recovery cache (env HAPRAY_SYMBOL_RECOVERY_OUTPUT)',
        )
        parser.add_argument(
            '--symbol-recovery-context',
            default=None,
            help='Optional --context passed to symbol_recovery for LLM prompts',
        )
        parser.add_argument(
            '--symbol-recovery-no-llm',
            action='store_true',
            default=False,
            help='Disable integrated symbol recovery (even if LLM env is configured)',
        )
        parser.add_argument(
            '--symbol-recovery-timeout',
            type=int,
            default=None,
            help='Subprocess timeout in seconds for symbol recovery (default: no limit)',
        )
        parser.add_argument(
            '--symbol-recovery-agent-mode',
            action='store_true',
            default=False,
            help='Enable offline/agent symbol recovery orchestration mode when direct LLM is unavailable',
        )
        parser.add_argument(
            '--symbol-recovery-import-results',
            default=None,
            help='Optional external LLM result JSON for agent mode (supports {step} placeholder, e.g. /tmp/{step}.json)',
        )
        parser.add_argument(
            '--flame-html',
            default=None,
            help='SIMPLE mode: optional existing hiperf_report.html to extract perf.json from, '
            'bypassing perf -i for flame graph data preparation',
        )
        parsed_args = parser.parse_args(args)

        try_load_dotenv_for_llm()

        Config.set('mode', parsed_args.mode)
        report_dir = os.path.abspath(parsed_args.report_dir)

        # SIMPLE mode: 必须先创建目录结构，然后才能查找 testcase_dirs
        if Config.get('mode') == Mode.SIMPLE:
            perf_paths = parsed_args.perfs
            trace_paths = parsed_args.traces
            pids = parsed_args.pids
            app_name = parsed_args.app_name
            app_version = parsed_args.app_version
            rom_version = parsed_args.rom_version
            scene = parsed_args.scene
            package_name = parsed_args.package_name
            steps_file_path = parsed_args.steps

            timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
            report_dir = os.path.join(report_dir, timestamp)
            create_simple_mode_structure(
                report_dir,
                perf_paths,
                trace_paths,
                package_name,
                pids=pids,
                steps_file_path=steps_file_path,
                app_name=app_name,
                app_version=app_version,
                rom_version=rom_version,
                scene=scene,
            )
            logging.info('SIMPLE mode: created report structure at %s', report_dir)

            # SIMPLE mode: 如果提供了外部火焰图 HTML，提取 perf.json 替代 perf -i
            if parsed_args.flame_html:
                flame_html_abs = os.path.abspath(parsed_args.flame_html)
                if os.path.isfile(flame_html_abs):
                    logging.info('Restoring perf.json from external flame HTML: %s', flame_html_abs)
                    if restore_perf_json_from_flame_html(report_dir, flame_html_abs):
                        logging.info('perf.json restored from flame HTML successfully')
                        Config.set('perf_json_restored', True)
                    else:
                        logging.warning('Failed to restore perf.json from flame HTML')
                else:
                    logging.warning('Flame HTML file not found: %s', flame_html_abs)

            # SIMPLE mode auto-detect: 当未提供 --flame-html 时，自动检测原始 hiperf_report.html
            if not Config.get('perf_json_restored', False):
                UpdateAction._auto_restore_from_original_html(report_dir, perf_paths)

            # SIMPLE mode fallback: 如果 perf.json 仍不存在，尝试从 perf.db 生成
            UpdateAction._try_generate_perf_json_from_db(report_dir)

        # 现在才能在 report_dir 下找到有效的 testcase 目录
        testcase_dirs = UpdateAction.find_testcase_dirs(report_dir)
        if not testcase_dirs:
            UpdateAction._log_no_testcase_dirs_help(report_dir)
            return (1, '')

        effective_so, so_source = resolve_effective_so_dir(parsed_args.so_dir)
        if not effective_so:
            auto_so, auto_source = UpdateAction._auto_prepare_so_dir(report_dir, testcase_dirs)
            if auto_so:
                effective_so = auto_so
                so_source = auto_source
        if effective_so:
            logging.info('Effective SO directory (%s): %s', so_source, effective_so)
        elif parsed_args.so_dir or os.environ.get(ENV_SO_DIR, '').strip():
            logging.warning(
                'SO directory was requested via CLI or %s but path is missing or not a directory',
                ENV_SO_DIR,
            )

        # 每次 update 都显式刷新 so_dir，避免沿用同进程上一次执行遗留的值
        Config.set('so_dir', effective_so or '')

        llm_ready = check_symbol_recovery_llm_ready()
        llm_env_configured = llm_env_ready_for_symbol_recovery()
        llm_probe_ok = True
        env_agent_mode = UpdateAction._parse_bool_env('HAPRAY_SYMBOL_RECOVERY_AGENT_MODE', default=False)
        agent_mode = bool(parsed_args.symbol_recovery_agent_mode or env_agent_mode)
        if llm_ready and not agent_mode:
            sr_root_probe = resolve_symbol_recovery_root()
            runtime_ok, runtime_reason = probe_symbol_recovery_llm_runtime(sr_root_probe, timeout_sec=5)
            llm_probe_ok = runtime_ok
            if not runtime_ok:
                logging.warning(
                    'LLM runtime probe failed before symbol recovery: %s; auto-fallback to agent mode for this update run.',
                    runtime_reason,
                )
                llm_ready = False
                agent_mode = True
        if not parsed_args.symbol_recovery_no_llm and effective_so and not llm_ready and not agent_mode:
            agent_mode = True
            logging.info(
                '未配置可用 LLM（缺少 API/base URL 或探测未通过），自动启用符号恢复 Agent 模式：'
                '将导出任务后由内联 step2、环境命令或手动导入结果完成推断。'
            )
        top_n = parse_top_n_from_env(parsed_args.symbol_recovery_top_n)
        stat_method = parse_stat_from_env(parsed_args.symbol_recovery_stat)
        output_root = parse_output_root_from_env(
            parsed_args.symbol_recovery_output if parsed_args.symbol_recovery_output else None
        )
        Config.set('symbol_recovery_llm_ready', llm_ready)
        Config.set('symbol_recovery_llm_env_configured', llm_env_configured)
        Config.set('symbol_recovery_llm_probe_ok', llm_probe_ok)
        Config.set('symbol_recovery_top_n', top_n)
        Config.set('symbol_recovery_stat_method', stat_method)
        Config.set('symbol_recovery_output_root', output_root or '')
        Config.set('symbol_recovery_context', (parsed_args.symbol_recovery_context or '').strip())
        Config.set('symbol_recovery_no_llm', bool(parsed_args.symbol_recovery_no_llm))
        Config.set('symbol_recovery_agent_mode', agent_mode)
        Config.set('symbol_recovery_import_results', (parsed_args.symbol_recovery_import_results or '').strip())
        Config.set(
            'symbol_recovery_timeout',
            parsed_args.symbol_recovery_timeout if parsed_args.symbol_recovery_timeout is not None else 0,
        )
        if not parsed_args.symbol_recovery_no_llm:
            if (llm_ready or agent_mode) and effective_so:
                sr_root = resolve_symbol_recovery_root()
                entry_exe = resolve_symbol_recovery_exe(sr_root) if sr_root else None
                py_exe = None if entry_exe is not None else resolve_symbol_recovery_python()
                launcher_ok = bool(entry_exe or py_exe)
                if sr_root and launcher_ok:
                    logging.info(
                        'Integrated symbol recovery enabled (llm_ready=%s, agent_mode=%s, top_n=%s, stat=%s, root=%s, launcher=%s)',
                        llm_ready,
                        agent_mode,
                        top_n,
                        stat_method,
                        sr_root,
                        entry_exe or py_exe,
                    )
                else:
                    if not sr_root:
                        logging.warning(
                            'Symbol recovery not runnable: set %s to the directory that contains '
                            'symbol_recovery main.py (separate checkout; not bundled in perf-testing).',
                            ENV_SYMBOL_RECOVERY_ROOT,
                        )
                    if sr_root and not launcher_ok:
                        logging.warning(
                            'Symbol recovery not runnable: no subprocess launcher under %s '
                            '(``uv sync`` in that dir for venv/Scripts/symbol-recovery.exe, or place symbol-recovery.exe, '
                            'or set %s / %s).',
                            sr_root,
                            ENV_SYMBOL_RECOVERY_EXE,
                            ENV_SYMBOL_RECOVERY_PYTHON,
                        )
            elif (llm_ready or agent_mode) and not effective_so:
                logging.info(
                    'Symbol recovery preconditions unmet: no SO dir (CLI/env/auto-device). '
                    'Skipping for this update run.'
                )
            elif effective_so and not llm_ready:
                if llm_env_configured:
                    logging.info(
                        'SO dir set; LLM is not ready or runtime probe failed while API/base URL are configured. '
                        'Symbol recovery uses agent prompt-only export this run; '
                        'place symbol_recovery_external_results.json under .symbol_recovery/<step>/ and rerun update to import.',
                    )
                else:
                    logging.info(
                        'SO dir set but LLM API/base URL not configured; agent_mode=%s. '
                        'Without offline import JSON under .symbol_recovery/<step>/, this run exports prompt tasks only.',
                        agent_mode,
                    )

        # Parse time ranges
        time_ranges = UpdateAction.parse_time_ranges(parsed_args.time_ranges)
        if time_ranges:
            logging.info('Using %d time range filters', len(time_ranges))
            for i, tr in enumerate(time_ranges):
                logging.info('Time range %d: %d - %d nanoseconds', i + 1, tr['startTime'], tr['endTime'])

        logging.info('Found %d test case reports for updating', len(testcase_dirs))
        UpdateAction.process_reports(
            testcase_dirs,
            report_dir,
            time_ranges,
            use_refined_lib_symbol=parsed_args.use_refined_lib_symbol,
            export_comparison=parsed_args.export_comparison,
            symbol_statistic=parsed_args.symbol_statistic,
            time_range_strings=parsed_args.time_ranges,
            enable_thread_analysis=not parsed_args.no_thread_analysis,
        )

        if parsed_args.hapflow:
            try:
                run_hapflow_pipeline(
                    reports_root=report_dir,  # HapRay 当次输出 reports/<timestamp>
                    homecheck_root=parsed_args.hapflow,  # 你的 Homecheck 根目录
                )
            except Exception as e:
                logging.getLogger().exception('HapFlow pipeline failed: %s', e)

        return (0, report_dir)

    @staticmethod
    def find_testcase_dirs(report_dir):
        """Identifies valid test case directories in the report directory.

        A valid test case directory must have at least a 'hiperf' subdirectory.
        The 'htrace' subdirectory is optional (for perf-only mode).
        """
        return find_testcase_dirs_under_report_root(report_dir)

    @staticmethod
    def _log_no_testcase_dirs_help(report_dir: str) -> None:
        logging.error('No valid test case reports found under: %s', report_dir)
        logging.error(
            '--report_dir 必须是「跑测结果」目录：其中每个用例文件夹下应有 hiperf/（内含 perf 数据）。'
            '常见为 HapRay GUI 结果目录下的时间戳文件夹，例如与 hapray-tool-result.json 同级的目录；'
            '不要选择 perf-testing.exe 所在的安装目录（如 .../dist 或 .../tools/perf-testing）。'
        )
        if os.path.isdir(report_dir):
            try:
                names = os.listdir(report_dir)
            except OSError as e:
                logging.error('Cannot list report_dir: %s', e)
                return
            preview = ', '.join(names[:15])
            if len(names) > 15:
                preview += ', ...'
            logging.error('当前目录下条目（前若干项）: %s', preview or '(空)')

    @staticmethod
    def parse_time_ranges(time_range_strings: list[str]) -> list[dict]:
        """Parse time range strings into structured format.

        Args:
            time_range_strings: List of time range strings in format "startTime-endTime"

        Returns:
            List of time range dictionaries with 'startTime' and 'endTime' keys
        """
        time_ranges = []
        for time_range_str in time_range_strings:
            try:
                if '-' not in time_range_str:
                    logging.error('Invalid time range format: %s. Expected format: "startTime-endTime"', time_range_str)
                    continue

                start_str, end_str = time_range_str.split('-', 1)
                start_time = int(start_str.strip())
                end_time = int(end_str.strip())

                if start_time >= end_time:
                    logging.error(
                        'Invalid time range: start time (%d) must be less than end time (%d)', start_time, end_time
                    )
                    continue

                time_ranges.append({'startTime': start_time, 'endTime': end_time})

            except ValueError as e:
                logging.error('Failed to parse time range "%s": %s', time_range_str, str(e))
                continue

        return time_ranges

    @staticmethod
    def _try_generate_perf_json_from_db(report_dir: str) -> None:
        """SIMPLE mode fallback: 对缺少 perf.json 的 step, 尝试从 perf.db 直接生成。

        当 perf -i (hapray-sa-cmd) 不可用时，此方法尝试通过导入编译模块
        flamegraph_generator.generate_perf_json_from_db 来生成 perf.json。
        """
        hiperf_root = Path(report_dir) / 'hiperf'
        if not hiperf_root.is_dir():
            return

        for step_dir in sorted(hiperf_root.glob('step*/')):
            perf_json = step_dir / 'perf.json'
            if perf_json.is_file():
                continue  # 已有 perf.json，跳过
            perf_db = step_dir / 'perf.db'
            if not perf_db.is_file():
                continue  # 无 perf.db，跳过
            try:
                from hapray.mode.flamegraph_generator import generate_perf_json_from_db
            except ImportError:
                logging.debug(
                    'flamegraph_generator.generate_perf_json_from_db not available '
                    '(compiled module may not have this export); skipping perf.json generation'
                )
                return  # 模块不可用，后续 step 也不用尝试了

            logging.info('Generating perf.json from perf.db (fallback) for %s', step_dir)
            try:
                ok = generate_perf_json_from_db(
                    str(perf_db),
                    str(perf_json),
                    '',  # package_name — only used for filtering, empty = no filter
                )
                if ok:
                    logging.info('perf.json generated from perf.db: %s', perf_json)
                else:
                    logging.warning('Failed to generate perf.json from perf.db: %s', perf_db)
            except Exception as e:
                logging.error('Error generating perf.json from perf.db %s: %s', perf_db, e)

    @staticmethod
    def _auto_restore_from_original_html(report_dir: str, perf_paths: list) -> bool:
        restored = False
        for perf_path in perf_paths:
            perf_dir = os.path.dirname(os.path.abspath(perf_path))
            original_html = os.path.join(perf_dir, 'hiperf_report.html')
            if not os.path.isfile(original_html):
                continue
            logging.info('Auto-detected original flame HTML alongside perf.data: %s', original_html)
            if restore_perf_json_from_flame_html(report_dir, original_html):
                logging.info('perf.json restored from original flame HTML, skipping perf -i')
                Config.set('perf_json_restored', True)
                restored = True
                break
        return restored

    @staticmethod
    def _is_valid_symbol_recovery_result(item: dict) -> bool:
        """检查单个 symbol_recovery_results.json 条目是否有效。

        无效结果的标志：
        - inferred_name/function_name 为 null、空字符串或 auto_recovered_ 占位符
        - description/functionality 为 '未知' 或空字符串
        """
        if not isinstance(item, dict):
            return False

        # 获取函数名（兼容两种字段名）
        function_name = item.get('inferred_name') or item.get('function_name', '')
        functionality = item.get('description') or item.get('functionality', '')

        # 函数名必须为有效字符串
        if not function_name:
            return False
        if str(function_name).lower() in ('null', 'none', 'unknown', '未知'):
            return False
        if str(function_name).startswith('auto_recovered_'):
            return False

        # 功能描述不能是默认值
        if not functionality or str(functionality) in ('未知', 'null', 'None', ''):
            return False

        return True

    @staticmethod
    def _cleanup_symbol_recovery_error_outputs(
        scene_dir: str,
        step_dir: str,
        stat_method: str,
        top_n: int,
    ) -> None:
        """清理 LLM 失败时可能产生的错误产物，避免错误结果被写入 perf.json。

        需要删除的文件：
        - event_count_topN_analysis.xlsx / call_count_topN_analysis.xlsx
        - symbol_recovery_results.json（如果含错误结果或为空标记）
        - symbol_recovery_external_results.json（如果含错误结果）
        """
        from hapray.core.common.symbol_recovery_bridge import (
            default_symbol_recovery_output_dir,
            symbol_recovery_excel_name,
        )

        out_dir = default_symbol_recovery_output_dir(scene_dir, step_dir, None)
        excel_path = out_dir / symbol_recovery_excel_name(stat_method, top_n)
        results_json = out_dir / 'symbol_recovery_results.json'
        external_results_json = out_dir / 'symbol_recovery_external_results.json'

        try:
            if excel_path.exists():
                excel_path.unlink()
                logging.info('Cleaned up error Excel: %s', excel_path)
        except OSError as e:
            logging.debug('Failed to cleanup Excel %s: %s', excel_path, e)

        # 清理 symbol_recovery_results.json
        try:
            if results_json.exists():
                should_delete = False
                invalid_reason = ''
                try:
                    data = json.loads(results_json.read_text(encoding='utf-8', errors='replace'))

                    # 检查是否是字典格式（包含 _warning 字段的标记文件）
                    if isinstance(data, dict):
                        if data.get('_warning') or data.get('valid_results') == 0:
                            should_delete = True
                            invalid_reason = 'marked as failed by symbol_recovery'

                    # 检查是否是列表格式
                    elif isinstance(data, list):
                        if len(data) == 0:
                            # 空列表
                            should_delete = True
                            invalid_reason = 'empty results list'
                        else:
                            # 检查是否所有结果都无效
                            valid_count = 0
                            for item in data:
                                if UpdateAction._is_valid_symbol_recovery_result(item):
                                    valid_count += 1

                            if valid_count == 0:
                                should_delete = True
                                invalid_reason = 'all results are invalid (null function names or unknown functionality)'
                            elif valid_count < len(data):
                                # 部分无效，记录日志但仍保留（由后续处理决定）
                                logging.debug(
                                    'Results JSON has %d/%d valid entries, keeping for partial recovery',
                                    valid_count, len(data)
                                )

                    else:
                        # 未知格式
                        should_delete = True
                        invalid_reason = 'unknown format'

                except (json.JSONDecodeError, OSError) as e:
                    # 解析失败也删除
                    should_delete = True
                    invalid_reason = f'parse error: {e}'

                if should_delete:
                    results_json.unlink()
                    logging.info('Cleaned up error results JSON (%s): %s', invalid_reason, results_json)

        except OSError as e:
            logging.debug('Failed to cleanup results JSON %s: %s', results_json, e)

        # 清理 symbol_recovery_external_results.json
        try:
            if external_results_json.exists():
                should_delete = False
                try:
                    data = json.loads(external_results_json.read_text(encoding='utf-8', errors='replace'))
                    has_placeholder = False
                    all_null = True

                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                fn = str(item.get('function_name', ''))
                                if fn.startswith('auto_recovered_'):
                                    has_placeholder = True
                                    break
                                # 检查是否所有 function_name 都是 null/空
                                if fn and fn.lower() not in ('null', 'none', ''):
                                    all_null = False

                    # 如果包含占位符或所有 function_name 都是 null，删除
                    if has_placeholder or (isinstance(data, list) and len(data) > 0 and all_null):
                        should_delete = True
                        logging.info('Cleaned up error external results JSON with placeholders: %s', external_results_json)

                except (json.JSONDecodeError, OSError):
                    should_delete = True
                    logging.info('Cleaned up invalid external results JSON: %s', external_results_json)

                if should_delete:
                    external_results_json.unlink()
        except OSError as e:
            logging.debug('Failed to cleanup external results JSON %s: %s', external_results_json, e)

    @staticmethod
    def _check_symbol_recovery_results_valid(
        scene_dir: str,
        step_dir: str,
    ) -> bool:
        """检查符号恢复结果是否有效（不包含 auto_recovered_* 占位符）。"""
        step_hiperf = Path(scene_dir) / 'hiperf' / step_dir
        manifest_path = step_hiperf / 'symbol_recovery_replacements.json'

        if not manifest_path.exists():
            return False

        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8', errors='replace'))
            if not isinstance(data, list):
                return False

            for item in data:
                if not isinstance(item, dict):
                    continue
                replaced = str(item.get('replaced', ''))
                # 检查是否包含占位符
                if 'auto_recovered_' in replaced:
                    logging.warning('Found auto_recovered placeholder in replacements: %s', replaced)
                    return False
            return True
        except (json.JSONDecodeError, OSError) as e:
            logging.debug('Failed to check replacements validity: %s', e)
            return False

    @staticmethod
    def _run_symbol_recovery_for_case(
        case_dir: str,
        effective_so: Optional[str],
        top_n: int,
        stat_method: str,
        agent_mode: bool = False,
        llm_env_configured: bool = False,
    ):
        """为单个用例目录执行符号恢复。

        遍历 case_dir 下的所有 step 目录，对每个包含 perf.db 的 step 执行符号恢复。

        执行策略：
        1. 如果配置了 LLM 环境且不是强制 agent 模式，先尝试 LLM 模式
        2. 如果 LLM 模式失败或无效，自动回退到 Agent 模式
        3. 如果 Agent 模式也失败，才标记为失败
        """
        if not effective_so:
            logging.debug('Skipping symbol recovery for %s: no effective SO directory', case_dir)
            return

        case_path = Path(case_dir)
        if not case_path.is_dir():
            return

        # 查找所有 step 目录下的 perf.db
        for step_dir in case_path.iterdir():
            if not step_dir.is_dir():
                continue
            # 检查是否是 step 目录 (step1, step2, ...)
            if not step_dir.name.startswith('step'):
                continue

            hiperf_dir = step_dir / 'hiperf'
            if not hiperf_dir.is_dir():
                continue

            perf_db = hiperf_dir / 'perf.db'
            if not perf_db.is_file():
                continue

            logging.info('Running symbol recovery for %s/%s', case_dir, step_dir.name)

            # 判断是否应该先尝试 LLM 模式
            # 条件：LLM 环境已配置 AND (不是强制 agent 模式 OR agent_mode 为 False)
            should_try_llm_first = llm_env_configured and not agent_mode

            llm_success = False
            agent_success = False

            # 第一步：尝试 LLM 模式（如果配置了 LLM）
            if should_try_llm_first:
                logging.info('Attempting LLM mode for symbol recovery (llm_env_configured=%s)', llm_env_configured)
                try:
                    llm_success = maybe_run_symbol_recovery_for_step(
                        scene_dir=str(case_dir),
                        step_dir=step_dir.name,
                        perf_db_path=str(perf_db),
                        effective_so_dir=effective_so,
                        top_n=top_n,
                        stat_method=stat_method,
                        output_root=None,
                        extra_args=None,
                        prompt_only=False,
                    )
                    if llm_success:
                        # 验证结果是否有效（不包含占位符）
                        if UpdateAction._check_symbol_recovery_results_valid(str(case_dir), step_dir.name):
                            logging.info('LLM symbol recovery completed and validated for %s/%s', case_dir, step_dir.name)
                            continue  # 成功且有效，跳到下一个 step
                        else:
                            logging.warning('LLM symbol recovery produced invalid results (placeholders detected), will fallback to agent mode')
                            llm_success = False
                            # 清理错误产物
                            UpdateAction._cleanup_symbol_recovery_error_outputs(
                                str(case_dir), step_dir.name, stat_method, top_n
                            )
                    else:
                        logging.warning('LLM symbol recovery failed for %s/%s, will fallback to agent mode', case_dir, step_dir.name)
                except Exception as e:
                    logging.exception('Error in LLM symbol recovery for %s/%s: %s', case_dir, step_dir.name, str(e))
                    llm_success = False

            # 第二步：如果 LLM 失败或未配置，尝试 Agent 模式
            # 条件：LLM 未配置 或 LLM 失败 或 强制 agent 模式
            should_try_agent = not llm_env_configured or not llm_success or agent_mode

            if should_try_agent:
                logging.info('Attempting Agent mode for symbol recovery (llm_env_configured=%s, llm_success=%s, agent_mode=%s)',
                            llm_env_configured, llm_success, agent_mode)
                try:
                    agent_success = maybe_run_symbol_recovery_for_step(
                        scene_dir=str(case_dir),
                        step_dir=step_dir.name,
                        perf_db_path=str(perf_db),
                        effective_so_dir=effective_so,
                        top_n=top_n,
                        stat_method=stat_method,
                        output_root=None,
                        extra_args=['--prompt-only'],
                        prompt_only=True,
                    )
                    if agent_success:
                        logging.info('Agent mode symbol recovery (prompt-only) completed for %s/%s', case_dir, step_dir.name)
                        # Agent 模式只导出 tasks，需要后续执行 Agent 推断并回填
                        # 这里记录状态，但暂不标记为最终成功
                    else:
                        logging.error('Agent mode symbol recovery failed for %s/%s', case_dir, step_dir.name)
                except Exception as e:
                    logging.exception('Error in Agent symbol recovery for %s/%s: %s', case_dir, step_dir.name, str(e))
                    agent_success = False

            # 最终状态记录
            if llm_success:
                logging.info('Symbol recovery completed (LLM mode) for %s/%s', case_dir, step_dir.name)
            elif agent_success:
                logging.info('Symbol recovery exported tasks (Agent mode) for %s/%s - requires external inference', case_dir, step_dir.name)
            else:
                logging.error('Symbol recovery failed (both LLM and Agent modes) for %s/%s', case_dir, step_dir.name)

    @staticmethod
    def process_reports(
        testcase_dirs,
        report_dir,
        time_ranges: list[dict] = None,
        use_refined_lib_symbol: bool = False,
        export_comparison: bool = False,
        symbol_statistic: str = None,
        time_range_strings: list[str] = None,
        enable_thread_analysis: bool = True,
    ):
        """Processes reports using parallel execution.

        Args:
            testcase_dirs: List of test case directories to process
            report_dir: Root report directory
            time_ranges: Optional time range filters
            use_refined_lib_symbol: Enable refined mode for memory analysis
            export_comparison: Export comparison Excel for memory analysis
            symbol_statistic: Path to SymbolsStatistic.txt for symbol analysis (optional)
            time_range_strings: List of time range strings for symbol statistics (optional)
            enable_thread_analysis: Enable redundant thread analysis (ThreadAnalyzer). Default True.
        """
        # 从 Config 获取符号恢复配置（在 execute 中设置）
        effective_so = Config.get('so_dir', '') or None
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count'
        agent_mode = bool(Config.get('symbol_recovery_agent_mode', False))
        no_llm = bool(Config.get('symbol_recovery_no_llm', False))
        llm_env_configured = bool(Config.get('symbol_recovery_llm_env_configured', False))

        # 检查是否应该执行符号恢复
        should_run_symbol_recovery = (
            not no_llm  # 不是 --no-llm 模式
            and effective_so  # 有有效的 SO 目录
        )

        if should_run_symbol_recovery:
            logging.info(
                'Symbol recovery will be executed for all test cases (so_dir=%s, top_n=%s, stat=%s, agent_mode=%s)',
                effective_so, top_n, stat_method, agent_mode
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator(
                use_refined_lib_symbol=use_refined_lib_symbol,
                export_comparison=export_comparison,
                symbol_statistic=symbol_statistic,
                time_range_strings=time_range_strings,
                enable_thread_analysis=enable_thread_analysis,
            )

            for case_dir in testcase_dirs:
                scene_name = os.path.basename(case_dir)
                logging.info('Updating report: %s', scene_name)
                if time_ranges:
                    logging.info('Using time ranges for %s: %s', scene_name, time_ranges)
                future = executor.submit(report_generator.update_report, case_dir, time_ranges)
                futures.append(future)

            # Monitor completion status
            for future in futures:
                try:
                    if future.result():
                        logging.info('Report updated successfully')
                    else:
                        logging.error('Report update failed')
                except Exception as e:
                    logging.error('Error updating report: %s', str(e))

        # 在所有报告更新完成后，执行符号恢复
        # 符号恢复需要在 report 生成之后执行，因为它需要 report 中的产物
        if should_run_symbol_recovery:
            logging.info('=' * 80)
            logging.info('Starting symbol recovery for all test cases')
            logging.info('=' * 80)

            for case_dir in testcase_dirs:
                UpdateAction._run_symbol_recovery_for_case(
                    case_dir=case_dir,
                    effective_so=effective_so,
                    top_n=top_n,
                    stat_method=stat_method,
                    agent_mode=agent_mode,
                    llm_env_configured=llm_env_configured,
                )

            logging.info('=' * 80)
            logging.info('Symbol recovery completed for all test cases')
            logging.info('=' * 80)

            # 符号恢复完成后,更新负载分析 Excel 中的符号名
            logging.info('Updating load analysis Excel with recovered symbols...')
            for case_dir in testcase_dirs:
                try:
                    if update_load_excel_with_recovered_symbols(case_dir):
                        logging.info('Load analysis Excel updated for %s', case_dir)
                except Exception as e:
                    logging.error('Failed to update load analysis Excel for %s: %s', case_dir, e)

        # Generate summary report
        logging.info('Generating summary Excel report')
        if create_perf_summary_excel(report_dir):
            logging.info('Summary Excel created successfully')
        else:
            logging.error('Failed to create summary Excel')
