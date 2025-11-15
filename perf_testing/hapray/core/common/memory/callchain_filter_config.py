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


class CallchainFilterConfig:
    """调用链过滤配置

    用于定义在查询callchain时需要排除的系统符号、系统so文件、计算类符号等
    """

    def __init__(self):
        """初始化过滤配置"""
        # 系统符号排除规则（正则表达式）
        self.system_symbols = [
            r'^malloc',
            r'^free',
            r'^calloc',
            r'^realloc',
            r'^__malloc',
            r'^__free',
            r'^pthread_',
            r'^__pthread_',
            r'^libc\.so',
            r'^libc\+\+\.so',
        ]

        # 系统so文件排除规则（正则表达式）
        self.system_libs = [
            r'libc\.so',
            r'libc\+\+\.so',
            r'libm\.so',
            r'libdl\.so',
            r'libpthread\.so',
            r'libstdc\+\+\.so',
            r'libgcc\.so',
            r'libunwind\.so',
            r'libcamera\.so',
            r'libhilog\.so',
            r'libhitracechain\.so',
        ]

        # 计算类符号排除规则（正则表达式）
        self.compute_symbols = [
            r'^std::',
            r'^__gnu_cxx::',
            r'^boost::',
            r'operator',
        ]

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

