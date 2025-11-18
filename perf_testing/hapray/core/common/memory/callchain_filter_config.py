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

        # 从配置中读取 exclude_rules
        exclude_rules = getattr(callchain_filter_config, 'exclude_rules', None)

        # 编译排除规则：文件正则 -> 符号正则列表
        # 支持YAML锚点和引用，跳过共享符号定义（以shared_开头的属性）
        self.exclude_rules_compiled: dict[re.Pattern, list[re.Pattern]] = {}
        if exclude_rules:
            # exclude_rules 是 ConfigObject 类型，需要遍历其属性
            for attr_name in dir(exclude_rules):
                if attr_name.startswith('_'):  # 跳过私有属性
                    continue

                attr_value = getattr(exclude_rules, attr_name)

                # 跳过共享符号定义（以shared_开头的属性）
                if attr_name.startswith('shared_'):
                    continue

                # 处理文件模式 -> 符号列表的映射
                if isinstance(attr_value, list):
                    file_regex = re.compile(attr_name)
                    symbol_regexes = [re.compile(pattern) for pattern in attr_value]
                    self.exclude_rules_compiled[file_regex] = symbol_regexes

    def should_exclude(self, symbol: Optional[str], lib_path: Optional[str]) -> bool:
        """检查符号和库是否应该被排除

        新的过滤逻辑：只有当文件路径匹配排除规则中的文件正则，
        并且符号匹配该文件对应的符号正则列表中的任一模式时，才排除。

        Args:
            symbol: 符号名称
            lib_path: 库文件路径

        Returns:
            如果应该排除返回True，否则返回False
        """
        if not symbol or symbol == 'unknown' or not lib_path or lib_path == 'unknown':
            return False

        # 检查是否匹配任何排除规则
        for file_regex, symbol_regexes in self.exclude_rules_compiled.items():
            if file_regex.search(lib_path):
                # 文件路径匹配，检查符号是否匹配该文件的排除符号
                for symbol_regex in symbol_regexes:
                    if symbol_regex.search(symbol):
                        return True

        return False

