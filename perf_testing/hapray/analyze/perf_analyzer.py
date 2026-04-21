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

import base64
import json
import logging
import os
import re
import zlib
from pathlib import Path
from typing import Any, Optional

from hapray.analyze import BaseAnalyzer
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.common.symbol_recovery_bridge import (
    default_symbol_recovery_output_dir,
    embed_symbol_recovery_report_into_hiperf_html,
    maybe_generate_symbol_recovery_html_for_step,
    maybe_run_symbol_recovery_for_step,
    symbol_recovery_report_name,
    symbol_recovery_replaced_html_name,
    symbol_recovery_should_run,
)
from hapray.core.config.config import Config


class PerfAnalyzer(BaseAnalyzer):
    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/flame_graph')
        self.time_ranges = time_ranges

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Run performance analysis"""
        # step1 先跑 perf -i，再符号恢复写 perf.json，最后读入火焰图，避免读到过期 perf.json
        if step_dir == 'step1':
            args = ['perf', '-i', self.scene_dir]
            so_dir = Config.get('so_dir', None)
            if so_dir:
                args.extend(['-s', os.path.abspath(so_dir)])

            kind = self.convert_kind_to_json()
            if len(kind) > 0:
                args.extend(['-k', kind])

            # Add time ranges if provided
            if self.time_ranges:
                time_range_strings = []
                for tr in self.time_ranges:
                    time_range_str = f'{tr["startTime"]}-{tr["endTime"]}'
                    time_range_strings.append(time_range_str)
                args.extend(['--time-ranges'] + time_range_strings)
                logging.info('Adding time ranges to perf command: %s', time_range_strings)

            logging.debug('Running perf analysis with command: %s', ' '.join(args))
            ExeUtils.execute_hapray_cmd(args)

        sr_applied = self._maybe_apply_symbol_recovery(step_dir, perf_db_path)

        result = self.generate_hiperf_report(perf_db_path)
        if sr_applied:
            generated_html = self._maybe_generate_symbol_recovery_html(step_dir)
            self._maybe_embed_symbol_recovery_report(step_dir, perf_db_path, generated_html)
        return result

    def _maybe_apply_symbol_recovery(self, step_dir: str, perf_db_path: str) -> bool:
        """在生成火焰图数据前，可选运行符号恢复并写回 perf.json。"""
        no_llm = bool(Config.get('symbol_recovery_no_llm', False))
        llm_ready = bool(Config.get('symbol_recovery_llm_ready', False))
        so_dir = (Config.get('so_dir', None) or '').strip()
        if not symbol_recovery_should_run(
            llm_ready=llm_ready,
            effective_so_dir=so_dir or None,
            perf_db_path=perf_db_path,
            no_llm_override=no_llm,
        ):
            return False
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = (Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count').strip()
        if stat_method not in ('event_count', 'call_count'):
            stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        timeout_raw = Config.get('symbol_recovery_timeout', 0)
        try:
            tval = float(timeout_raw) if timeout_raw else 0.0
        except (TypeError, ValueError):
            tval = 0.0
        timeout_sec = tval if tval > 0 else None
        extras: list[str] = []
        ctx = (Config.get('symbol_recovery_context', '') or '').strip()
        if ctx:
            extras.extend(['--context', ctx])
        ok = maybe_run_symbol_recovery_for_step(
            self.scene_dir,
            step_dir,
            perf_db_path,
            effective_so_dir=so_dir,
            top_n=top_n,
            stat_method=stat_method,
            output_root=output_root,
            subprocess_timeout_sec=timeout_sec,
            extra_args=extras or None,
        )
        if not ok:
            logging.warning(
                'Integrated symbol recovery did not complete for scene=%s step=%s',
                self.scene_dir,
                step_dir,
            )
            return False
        return True

    def _maybe_embed_symbol_recovery_report(
        self, step_dir: str, perf_db_path: str, generated_html: Optional[Path] = None
    ) -> None:
        """符号恢复成功后，将详细 HTML 嵌入 hiperf_report.html（iframe）。"""
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = (Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count').strip()
        if stat_method not in ('event_count', 'call_count'):
            stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        out_dir = default_symbol_recovery_output_dir(self.scene_dir, step_dir, output_root)
        hiperf = Path(perf_db_path).parent / 'hiperf_report.html'
        generated = generated_html or (hiperf.parent / symbol_recovery_replaced_html_name(hiperf.name))
        detail = generated if generated.is_file() else out_dir / symbol_recovery_report_name(stat_method, top_n)
        embed_symbol_recovery_report_into_hiperf_html(hiperf, detail)

    def _maybe_generate_symbol_recovery_html(self, step_dir: str) -> Optional[Path]:
        """在 update 生成新的 hiperf_report.html 后，再补跑 symbol_recovery Step4。"""
        top_n = int(Config.get('symbol_recovery_top_n', 50) or 50)
        stat_method = (Config.get('symbol_recovery_stat_method', 'event_count') or 'event_count').strip()
        if stat_method not in ('event_count', 'call_count'):
            stat_method = 'event_count'
        output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
        return maybe_generate_symbol_recovery_html_for_step(
            self.scene_dir,
            step_dir,
            top_n=top_n,
            stat_method=stat_method,
            output_root=output_root,
        )

    @staticmethod
    def convert_kind_to_json() -> str:
        kind = Config.get('kind', None)
        if kind is None:
            return ''

        kind_entry = {'name': 'APP_SO', 'kind': 1, 'components': []}

        for category in Config.get('kind', None):
            component = {'name': category['name'], 'files': category['files']}

            if 'thread' in category:
                component['threads'] = category['thread']

            kind_entry['components'].append(component)

        return json.dumps([kind_entry])

    @staticmethod
    def generate_hiperf_report(perf_path: str) -> Optional[str]:
        """生成火焰图报告，返回原始JSON字符串"""
        report_file = os.path.join(os.path.dirname(perf_path), 'hiperf_report.html')
        template_file = os.path.join(ExeUtils.get_tools_dir('web', 'hiperf_report_template.html'))
        if not os.path.exists(template_file):
            logging.warning('Not found file %s', template_file)
            return None
        perf_json_file = os.path.join(os.path.dirname(perf_path), 'perf.json')
        if not os.path.exists(perf_json_file):
            logging.warning('Not found file %s', perf_json_file)
            return None

        with open(perf_json_file, encoding='utf-8') as perf_json_file:
            all_json = perf_json_file.read()

        script_start = '<script id="record_data" type="application/gzip+json;base64">'
        script_end = '</script></body></html>'

        # 为HTML报告压缩数据
        compressed_bytes = zlib.compress(all_json.encode('utf-8'), level=9)
        base64_bytes = base64.b64encode(compressed_bytes)
        base64_all_json_str = base64_bytes.decode('ascii')

        with open(template_file, encoding='utf-8') as html_file:
            html_str = html_file.read()
        with open(report_file, 'w', encoding='utf-8') as report_html_file:
            report_html_file.write(html_str)
            report_html_file.write(script_start + base64_all_json_str + script_end)

        # 返回原始JSON字符串，供后续处理
        return all_json

    @staticmethod
    def filter_and_move_symbols(data, filter_rules):
        """
        在JSON数据中根据多个过滤规则过滤并移动符号到新的库，仅从指定源库拆分

        参数:
        data: 原始JSON数据
        filter_rules: 过滤规则列表，每个规则是一个字典，包含:
            - filter_symbols: 用于筛选符号的字符串列表（如["v8::", "Builtins_"]）
            - new_file: 新库的名称（如"/system/lib64/libarkweb_v8.so"）
            - source_file: 要拆分的源库名称（如"libarkweb_engine.so"）
        """
        # 预处理：为所有新库添加条目并记录索引映射
        new_lib_indices = {}
        for rule in filter_rules:
            new_lib_name = rule['new_file']
            if new_lib_name not in data['symbolsFileList']:
                data['symbolsFileList'].append(new_lib_name)
                new_lib_indices[new_lib_name] = len(data['symbolsFileList']) - 1

        # 处理每个过滤规则
        for rule in filter_rules:
            filter_str_list = rule['filter_symbols']  # 现在是一个字符串列表
            new_lib_name = rule['new_file']
            source_lib_name_regex = re.compile(rule['source_file'])
            filter_symbols_regex = [re.compile(s) for s in rule['filter_symbols']]

            # 获取新库的索引
            new_index = new_lib_indices[new_lib_name]

            # 查找源库的索引
            source_lib_indices = set()
            for idx, lib_path in enumerate(data['symbolsFileList']):
                if source_lib_name_regex.match(lib_path):
                    source_lib_indices.add(idx)

            if not source_lib_indices:
                logging.warning("警告: 未找到源库 '%s'，跳过符号拆分", rule['source_file'])
                continue

            filter_strs = ', '.join(f"'{fs}'" for fs in filter_str_list)
            logging.info("处理规则: 从 '%s' 移动包含 %s 的符号到 '%s'", rule['source_file'], filter_strs, new_lib_name)
            logging.info("找到源库 '%s' 的索引: %s", rule['source_file'], source_lib_indices)

            # 收集包含任一过滤字符串的符号的symbol ID
            filtered_symbol_ids = set()

            # 遍历SymbolMap，修改file字段并收集相关信息
            for key, sym_info in data['SymbolMap'].items():
                # 只处理源库中的符号
                if sym_info['file'] in source_lib_indices:
                    # 检查符号是否包含任一过滤字符串
                    symbol = sym_info['symbol']
                    for symbol_regex in filter_symbols_regex:
                        if symbol_regex.match(symbol):
                            # 记录symbol ID
                            symbol_id = int(key)
                            filtered_symbol_ids.add(symbol_id)

                            # 修改file字段为新的索引
                            sym_info['file'] = new_index
                            break

            logging.info('从源库中找到 %s 个匹配 %s 的符号', len(filtered_symbol_ids), filter_strs)
            PerfAnalyzer.process_record_sample(data, source_lib_indices, filtered_symbol_ids, new_index)

        return data

    @staticmethod
    def process_record_sample(data, source_lib_indices, filtered_symbol_ids, new_index):
        # 处理recordSampleInfo - 只遍历源库
        if 'recordSampleInfo' not in data:
            return
        for event_info in data['recordSampleInfo']:
            for process_info in event_info.get('processes', []):
                for thread_info in process_info.get('threads', []):
                    PerfAnalyzer.update_thread_libs(source_lib_indices, filtered_symbol_ids, new_index, thread_info)

    @staticmethod
    def update_thread_libs(source_lib_indices, filtered_symbol_ids, new_index, thread_info):
        # 为当前线程创建新的lib对象
        new_lib_obj = {'fileId': new_index, 'eventCount': 0, 'functions': []}

        # 处理线程中的每个lib
        libs = thread_info.get('libs', [])

        # 只处理源库
        for lib in libs:
            file_id = lib.get('fileId')
            if file_id not in source_lib_indices:
                continue  # 跳过非源库

            # 分离匹配和不匹配的函数
            filtered_functions = []
            remaining_functions = []
            filtered_event_count = 0

            for func in lib.get('functions', []):
                if func.get('symbol') in filtered_symbol_ids:
                    filtered_functions.append(func)
                    # 累加counts[1]的值
                    if len(func.get('counts', [])) > 1:
                        filtered_event_count += func['counts'][1]
                else:
                    remaining_functions.append(func)

            # 如果有匹配的函数，更新原lib和新lib
            if filtered_functions:
                # 更新原lib
                lib['functions'] = remaining_functions
                lib['eventCount'] = max(0, lib.get('eventCount', 0) - filtered_event_count)

                # 更新新lib
                new_lib_obj['functions'].extend(filtered_functions)
                new_lib_obj['eventCount'] += filtered_event_count

        # 如果有匹配的函数，将新lib添加到线程的libs中
        if new_lib_obj['functions']:
            libs.append(new_lib_obj)

    @staticmethod
    def apply_symbol_split_rules(perf_json_file: str) -> str:
        """应用符号拆分规则"""
        with open(perf_json_file, errors='ignore', encoding='UTF-8') as json_file:
            data = json.load(json_file)
        rules = []
        config_file = os.path.join(CommonUtils.get_project_root(), 'sa-cmd', 'res', 'perf', 'symbol_split.json')
        # 1. 从配置文件加载规则
        if config_file and os.path.exists(config_file):
            with open(config_file, encoding='UTF-8') as f:
                rules.extend(json.load(f))

        return json.dumps(PerfAnalyzer.filter_and_move_symbols(data, rules))
