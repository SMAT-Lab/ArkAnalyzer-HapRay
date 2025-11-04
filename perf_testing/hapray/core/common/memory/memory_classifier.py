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

import os
import re
from typing import Optional

from hapray.core.config.config import Config


class ComponentCategory:
    """组件分类常量

    注意：这些值必须与 TypeScript 中的 ComponentCategory 枚举值一致
    """

    APP_ABC = 0
    APP_SO = 1
    APP_LIB = 2
    OS_Runtime = 3
    SYS_SDK = 4
    RN = 5
    Flutter = 6
    WEB = 7
    KMP = 8
    UNKNOWN = -1


class MemoryClassifier:
    """内存数据分类器

    负责对文件、符号、线程进行分类，参考 PerfAnalyzerBase 的分类逻辑
    """

    def __init__(self):
        """初始化分类器，加载配置"""
        self.file_classify_cfg: dict[str, dict] = {}
        self.file_regex_classify_cfg: list[tuple[re.Pattern, dict]] = []
        self._load_perf_kind_cfg()

    def _load_perf_kind_cfg(self):
        """从配置文件加载分类规则"""
        perf_kinds = Config.get('perf.kinds', [])

        for component_config in perf_kinds:
            kind = component_config.get('kind', ComponentCategory.UNKNOWN)
            kind_name = component_config.get('name', 'UNKNOWN')

            for sub in component_config.get('components', []):
                sub_name = sub.get('name', 'unknown')

                for file_pattern in sub.get('files', []):
                    category_info = {
                        'category': kind,
                        'category_name': kind_name,
                        'sub_category_name': sub_name,
                    }

                    if self._has_regex_chart(file_pattern):
                        # 正则表达式模式
                        self.file_regex_classify_cfg.append((re.compile(file_pattern), category_info))
                    else:
                        # 精确匹配
                        self.file_classify_cfg[file_pattern] = category_info

    @staticmethod
    def _has_regex_chart(pattern: str) -> bool:
        """检查字符串是否包含正则表达式字符"""
        return any(char in pattern for char in ['$', '.*', '.+', 'd+'])

    def classify_file(self, file_path: Optional[str]) -> dict:
        """分类文件

        Args:
            file_path: 文件路径

        Returns:
            分类信息字典，包含 category, category_name, sub_category_name
        """
        if not file_path or file_path == 'unknown':
            return {
                'file': 'unknown',
                'category': ComponentCategory.UNKNOWN,
                'category_name': 'UNKNOWN',
                'sub_category_name': 'unknown',
            }

        file_name = os.path.basename(file_path)

        # 1. 精确路径匹配（最高优先级）
        if file_path in self.file_classify_cfg:
            component = self.file_classify_cfg[file_path]
            return {
                'file': file_path,
                'category': component['category'],
                'category_name': component['category_name'],
                'sub_category_name': component['sub_category_name'],
            }

        # 2. 正则表达式匹配
        for regex, component in self.file_regex_classify_cfg:
            if regex.match(file_path):
                return {
                    'file': file_path,
                    'category': component['category'],
                    'category_name': component['category_name'],
                    'sub_category_name': component['sub_category_name'],
                }

        # 3. 应用 Bundle 文件检测
        bundle_regex = re.compile(r'/proc/.*/data/storage/.*/bundle/.*')
        if bundle_regex.match(file_path):
            # Bundle 中的 .so 文件
            if file_name.endswith('.so') or '/bundle/libs/' in file_path:
                return {
                    'file': file_path,
                    'category': ComponentCategory.APP_SO,
                    'category_name': 'APP_SO',
                    'sub_category_name': file_name,
                }
            # Bundle 中的 .abc 文件
            if file_name.endswith('.abc'):
                return {
                    'file': file_path,
                    'category': ComponentCategory.APP_ABC,
                    'category_name': 'APP_ABC',
                    'sub_category_name': file_name,
                }

        # 4. 文件名匹配（作为后备方案）
        if file_name in self.file_classify_cfg:
            component = self.file_classify_cfg[file_name]
            return {
                'file': file_path,
                'category': component['category'],
                'category_name': component['category_name'],
                'sub_category_name': component['sub_category_name'],
            }

        # 5. 默认分类：系统库
        return {
            'file': file_path,
            'category': ComponentCategory.SYS_SDK,
            'category_name': 'SYS_SDK',
            'sub_category_name': file_name,
        }

    def classify_symbol(self, symbol_name: Optional[str], file_classification: dict) -> dict:
        """分类符号

        对于 APP_ABC 类型的符号，提取包名作为小类
        对于 KMP 类型的符号，提取包名作为小类

        Args:
            symbol_name: 符号名称
            file_classification: 文件分类结果

        Returns:
            更新后的分类信息
        """
        if not symbol_name or symbol_name == 'unknown':
            return file_classification

        # 对于 APP_ABC 类型的符号，提取包名
        if file_classification['category'] == ComponentCategory.APP_ABC:
            # ETS 符号格式：functionName: [url:entry|@package/module|version|path:line:column]
            regex = re.compile(r'([^:]+):\[url:([^:\|]+)\|([^|]+)\|([^:\|]+)\|([^\|\]]*):(\d+):(\d+)\]$')
            matches = regex.match(symbol_name)
            if matches:
                package_name = matches.group(3)
                version = matches.group(4)
                file_path = matches.group(5)
                return {
                    'file': f'{package_name}/{version}/{file_path}',
                    'category': file_classification['category'],
                    'category_name': file_classification['category_name'],
                    'sub_category_name': package_name,  # 使用包名作为小类
                }

        # 对于 KMP 类型的符号，提取包名
        if file_classification['category'] == ComponentCategory.KMP and symbol_name.startswith('kfun'):
            # KMP 符号格式：kfun:package.class.function
            parts = symbol_name.split('.')
            if len(parts) > 1:
                package_name = parts[0].replace('kfun:', '')
                return {
                    'file': f'{package_name}.{parts[1]}',
                    'category': file_classification['category'],
                    'category_name': file_classification['category_name'],
                    'sub_category_name': package_name,  # 使用包名作为小类
                }

        return file_classification

    @staticmethod
    def classify_thread(thread_name: Optional[str]) -> dict:
        """分类线程

        Args:
            thread_name: 线程名称

        Returns:
            分类信息字典
        """
        if not thread_name:
            return {
                'file': 'unknown',
                'category': ComponentCategory.UNKNOWN,
                'category_name': 'UNKNOWN',
                'sub_category_name': 'UNKNOWN',
            }

        # 对于 Native Memory，直接使用线程名称作为小类
        return {
            'file': thread_name,
            'category': ComponentCategory.UNKNOWN,
            'category_name': 'Thread',
            'sub_category_name': thread_name,
        }

    def get_final_classification(
        self,
        file_path: Optional[str],
        symbol_name: Optional[str],
        thread_name: Optional[str],
    ) -> dict:
        """获取最终的分类信息

        优先级：符号 > 文件 > 线程
        参考 SA 中的逻辑（native_memory_analyzer.ts 第 351-372 行）

        Args:
            file_path: 文件路径
            symbol_name: 符号名称
            thread_name: 线程名称

        Returns:
            最终的分类信息，包含 file, category, category_name, sub_category_name
        """
        # 1. 先对文件进行分类
        file_classification = self.classify_file(file_path)

        # 2. 再对符号进行分类（如果有符号信息）
        symbol_classification = file_classification
        if symbol_name and symbol_name != 'unknown':
            symbol_classification = self.classify_symbol(symbol_name, file_classification)

        # 3. 对线程进行分类（如果有线程信息）
        thread_classification = self.classify_thread(thread_name)

        # 4. 确定最终的分类信息
        # 优先级：符号 > 文件 > 线程
        final_category_name = symbol_classification['category_name']
        final_sub_category_name = symbol_classification['sub_category_name']

        # 如果符号分类没有返回有效的小类，使用线程分类
        if not final_sub_category_name and thread_name:
            final_sub_category_name = thread_classification['sub_category_name']

        return {
            'file': symbol_classification['file'],
            'category': symbol_classification['category'],
            'category_name': final_category_name,
            'sub_category_name': final_sub_category_name,
        }
