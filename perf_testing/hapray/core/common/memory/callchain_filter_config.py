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

import re
from typing import Optional

from ...config.config import Config


class CallchainFilterConfig:
    """调用链过滤配置

    用于定义在查询callchain时需要排除的系统符号、系统so文件、计算类符号等
    """

    def __init__(self, config: Optional[Config] = None):
        """初始化过滤配置

        Args:
            config: 配置对象，如果为None则使用默认配置

        Raises:
            ValueError: 如果配置文件中缺少必要的过滤配置
        """
        # 从配置中读取过滤规则
        config_obj = config or Config()
        callchain_filter_config = getattr(config_obj.data, 'callchain_filter', None)

        if callchain_filter_config is None:
            raise ValueError("callchain_filter configuration section not found in config.yaml")

        # 从配置中读取，必须存在
        try:
            self.system_symbols = getattr(callchain_filter_config, 'system_symbols')
            self.system_libs = getattr(callchain_filter_config, 'system_libs')
            self.compute_symbols = getattr(callchain_filter_config, 'compute_symbols')
        except AttributeError as e:
            missing_attr = str(e).split("'")[1]
            raise ValueError(f"Missing required configuration: callchain_filter.{missing_attr}")

        # 编译正则表达式以提高性能
        self.system_symbols_compiled = [re.compile(pattern) for pattern in self.system_symbols]
        self.system_libs_compiled = [re.compile(pattern) for pattern in self.system_libs]
        self.compute_symbols_compiled = [re.compile(pattern) for pattern in self.compute_symbols]

    def should_exclude_symbol(self, symbol: Optional[str]) -> bool:
        """检查符号是否应该被排除

        Args:
            symbol: 符号名称

        Returns:
            如果应该排除返回True，否则返回False
        """
        if not symbol or symbol == 'unknown':
            return False

        # 检查系统符号
        for pattern in self.system_symbols_compiled:
            if pattern.search(symbol):
                return True

        # 检查计算类符号
        return any(pattern.search(symbol) for pattern in self.compute_symbols_compiled)

    def should_exclude_lib(self, lib_path: Optional[str]) -> bool:
        """检查库文件是否应该被排除

        Args:
            lib_path: 库文件路径

        Returns:
            如果应该排除返回True，否则返回False
        """
        if not lib_path or lib_path == 'unknown':
            return False

        # 检查系统库
        return any(pattern.search(lib_path) for pattern in self.system_libs_compiled)

    def should_exclude(self, symbol: Optional[str], lib_path: Optional[str]) -> bool:
        """检查符号和库是否应该被排除

        Args:
            symbol: 符号名称
            lib_path: 库文件路径

        Returns:
            如果应该排除返回True，否则返回False
        """
        return self.should_exclude_symbol(symbol) or self.should_exclude_lib(lib_path)

