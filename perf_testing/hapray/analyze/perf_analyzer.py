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
from typing import Dict, Any

from hapray.analyze import BaseAnalyzer
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.config.config import Config


class PerfAnalyzer(BaseAnalyzer):
    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'hiperf_info.json')

    def _analyze_impl(self, step_dir: str, trace_db_path: str, perf_db_path: str) -> Dict[str, Any] | None:
        """Run performance analysis"""
        args = ['dbtools', '-i', self.scene_dir]

        so_dir = Config.get('so_dir', None)
        if so_dir:
            args.extend(['-s', os.path.abspath(so_dir)])

        kind = self.convert_kind_to_json()
        if len(kind) > 0:
            args.extend(['-k', kind])

        logging.debug(f"Running perf analysis with command: {' '.join(args)}")
        ExeUtils.execute_hapray_cmd(args)
        self.generate_hiperf_report(perf_db_path)
        return {}

    def write_report(self):
        # override
        pass

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

        with open(perf_json_file, 'r', errors='ignore') as json_file:
            all_json = json_file.read()
        with open(template_file, 'r', encoding='utf-8') as html_file:
            html_str = html_file.read()
        with open(report_file, 'w', encoding='utf-8') as report_html_file:
            report_html_file.write(html_str + all_json + '</script>'
                                                         ' </body>'
                                                         ' </html>')
