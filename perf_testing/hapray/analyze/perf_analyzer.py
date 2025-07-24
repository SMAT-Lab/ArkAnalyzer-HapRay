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

import json
import logging
import os
import re
from typing import Dict, Any, Optional

from hapray.analyze import BaseAnalyzer
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.config.config import Config


class PerfAnalyzer(BaseAnalyzer):
    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'perf')

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        """Run performance analysis"""
        self.generate_hiperf_report(perf_db_path)
        # Execute only in step1
        if step_dir != 'step1':
            return None
        args = ['dbtools', '-i', self.scene_dir]
        so_dir = Config.get('so_dir', None)
        if so_dir:
            args.extend(['-s', os.path.abspath(so_dir)])

        kind = self.convert_kind_to_json()
        if len(kind) > 0:
            args.extend(['-k', kind])

        logging.debug("Running perf analysis with command: %s", ' '.join(args))
        ExeUtils.execute_hapray_cmd(args)
        return {}

    @staticmethod
    def convert_kind_to_json() -> str:
        kind = Config.get('kind', None)
        if kind is None:
            return ''

        kind_entry = {
            "name": 'APP_SO',
            "kind": 1,
            "components": []
        }

        for category in Config.get('kind', None):
            component = {
                "name": category['name'],
                "files": category['files']
            }

            if 'thread' in category:
                component["threads"] = category['thread']

            kind_entry["components"].append(component)

        return json.dumps([kind_entry])

    @staticmethod
    def generate_hiperf_report(perf_path: str):
        report_file = os.path.join(os.path.dirname(perf_path), 'hiperf_report.html')
        if os.path.exists(report_file):
            return
        template_file = os.path.join(CommonUtils.get_project_root(), 'hapray-toolbox', 'res',
                                     'hiperf_report_template.html')
        if not os.path.exists(template_file):
            logging.warning('Not found file %s', template_file)
            return
        perf_json_file = os.path.join(os.path.dirname(perf_path), 'perf.json')
        if not os.path.exists(perf_json_file):
            logging.warning('Not found file %s', perf_json_file)
            return

        all_json = PerfAnalyzer.apply_symbol_split_rules(perf_json_file)
        with open(template_file, 'r', encoding='utf-8') as html_file:
            html_str = html_file.read()
        with open(report_file, 'w', encoding='utf-8') as report_html_file:
            report_html_file.write(html_str + all_json + '</script>'
                                                         ' </body>'
                                                         ' </html>')

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

            filter_strs = ", ".join(f"'{fs}'" for fs in filter_str_list)
            logging.info("处理规则: 从 '%s' 移动包含 %s 的符号到 '%s'",
                         rule['source_file'], filter_strs, new_lib_name)
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

            logging.info("从源库中找到 %s 个匹配 %s 的符号", len(filtered_symbol_ids), filter_strs)
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
        new_lib_obj = {
            "fileId": new_index,
            "eventCount": 0,
            "functions": []
        }

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
        with open(perf_json_file, 'r', errors='ignore', encoding='UTF-8') as json_file:
            data = json.load(json_file)
        rules = []
        config_file = os.path.join(CommonUtils.get_project_root(), 'hapray-toolbox', 'res', 'perf', 'symbol_split.json')
        # 1. 从配置文件加载规则
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r', encoding='UTF-8') as f:
                rules.extend(json.load(f))

        return json.dumps(PerfAnalyzer.filter_and_move_symbols(data, rules))
