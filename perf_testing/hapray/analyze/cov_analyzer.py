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

import logging
import os
from typing import Dict, Any, Optional

from hapray.analyze import BaseAnalyzer
from hapray.core.common.exe_utils import ExeUtils


class CovAnalyzer(BaseAnalyzer):
    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'perf')

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        cov_file = os.path.join(os.path.dirname(perf_db_path), 'bjc_cov.json')
        if not os.path.exists(cov_file):
            return
        args = ['bjc', '-i', cov_file, '-o', os.path.dirname(perf_db_path)]
        logging.debug("Running cov analysis with command: %s", ' '.join(args))
        ExeUtils.execute_hapray_cmd(args)
        return
