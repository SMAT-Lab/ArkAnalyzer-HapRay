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
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

from hapray import VERSION
from hapray.core.common.action_return import ActionExecuteReturn
from hapray.core.common.symbol_recovery_bridge import (
    ENV_SO_DIR,
    ENV_SYMBOL_RECOVERY_EXE,
    ENV_SYMBOL_RECOVERY_PYTHON,
    ENV_SYMBOL_RECOVERY_ROOT,
    check_symbol_recovery_llm_ready,
    parse_output_root_from_env,
    parse_stat_from_env,
    parse_top_n_from_env,
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
from hapray.mode.simple_mode import create_simple_mode_structure


class UpdateAction:
    """Handles report update actions for existing performance reports."""

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
        parsed_args = parser.parse_args(args)

        try_load_dotenv_for_llm()

        report_dir = os.path.abspath(parsed_args.report_dir)
        effective_so, so_source = resolve_effective_so_dir(parsed_args.so_dir)
        if effective_so:
            logging.info('Effective SO directory (%s): %s', so_source, effective_so)
        elif parsed_args.so_dir or os.environ.get(ENV_SO_DIR, '').strip():
            logging.warning(
                'SO directory was requested via CLI or %s but path is missing or not a directory',
                ENV_SO_DIR,
            )

        Config.set('mode', parsed_args.mode)
        if not os.path.exists(report_dir) and Config.get('mode') == Mode.COMMUNITY:
            logging.error('Report directory not found: %s', report_dir)
            return (1, '')
        if Config.get('mode') == Mode.SIMPLE:
            # 简单模式构造目录
            perf_paths = parsed_args.perfs
            trace_paths = parsed_args.traces
            pids = parsed_args.pids
            app_name = parsed_args.app_name
            app_version = parsed_args.app_version
            rom_version = parsed_args.rom_version
            scene = parsed_args.scene

            # if not perf_paths:
            #     logging.error('SIMPLE mode requires --perfs parameter')
            #     return

            # if not parsed_args.package_name:
            #     logging.error('SIMPLE mode requires --package_name parameter')
            #     return

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
        logging.info('Updating reports in: %s', report_dir)
        # 每次 update 都显式刷新 so_dir，避免沿用同进程上一次执行遗留的值
        Config.set('so_dir', effective_so or '')

        llm_ready = check_symbol_recovery_llm_ready()
        top_n = parse_top_n_from_env(parsed_args.symbol_recovery_top_n)
        stat_method = parse_stat_from_env(parsed_args.symbol_recovery_stat)
        output_root = parse_output_root_from_env(
            parsed_args.symbol_recovery_output if parsed_args.symbol_recovery_output else None
        )
        Config.set('symbol_recovery_llm_ready', llm_ready)
        Config.set('symbol_recovery_top_n', top_n)
        Config.set('symbol_recovery_stat_method', stat_method)
        Config.set('symbol_recovery_output_root', output_root or '')
        Config.set('symbol_recovery_context', (parsed_args.symbol_recovery_context or '').strip())
        Config.set('symbol_recovery_no_llm', bool(parsed_args.symbol_recovery_no_llm))
        Config.set(
            'symbol_recovery_timeout',
            parsed_args.symbol_recovery_timeout if parsed_args.symbol_recovery_timeout is not None else 0,
        )
        if not parsed_args.symbol_recovery_no_llm:
            if llm_ready and effective_so:
                sr_root = resolve_symbol_recovery_root()
                entry_exe = resolve_symbol_recovery_exe(sr_root) if sr_root else None
                py_exe = None if entry_exe is not None else resolve_symbol_recovery_python()
                launcher_ok = bool(entry_exe or py_exe)
                if sr_root and launcher_ok:
                    logging.info(
                        'Integrated symbol recovery enabled (LLM ok, top_n=%s, stat=%s, root=%s, launcher=%s)',
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
            elif llm_ready and not effective_so:
                logging.info('LLM configured for symbol recovery but no SO dir (--so_dir or %s); skipping', ENV_SO_DIR)
            elif effective_so and not llm_ready:
                logging.info(
                    'SO dir set but LLM env not ready for symbol recovery (need non-empty API key and base URL); '
                    'skipping. If you use HapRay GUI settings, ensure ~/.hapray-gui/config.json has llm_api_key / '
                    'llm_base_url (or set LLM_SERVICE_TYPE with matching service key), or export LLM_* / place .env '
                    'next to perf-testing.'
                )

        testcase_dirs = UpdateAction.find_testcase_dirs(report_dir)
        if not testcase_dirs:
            UpdateAction._log_no_testcase_dirs_help(report_dir)
            return (1, '')

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

        # Generate summary report
        logging.info('Generating summary Excel report')
        if create_perf_summary_excel(report_dir):
            logging.info('Summary Excel created successfully')
        else:
            logging.error('Failed to create summary Excel')
