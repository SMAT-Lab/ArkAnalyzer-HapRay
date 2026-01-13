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

from hapray.haptest import HapTest


class HapTest_JD(HapTest):
    """
    HapTest京东示例测试用例

    使用方法:
    1. 确保京东应用已安装在设备上
    2. 激活虚拟环境: activate.bat (Windows) 或 source activate.sh (Mac/Linux)
    3. 运行测试: python -m scripts.main perf --run_testcases HapTest_JD
    
    或直接使用haptest命令:
    python -m scripts.main haptest --app-package com.jd.hm.mall --app-name "京东" --max-steps 20
    """

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='com.jd.hm.mall',
            app_name='京东',
            strategy_type='depth_first',
            max_steps=20,
        )
