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
import json
import logging
import os

from hapray import VERSION
from hapray.ui_detector.ui_tree_comparator import UITreeComparator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class UICompareAction:
    """UI组件树对比工具入口"""

    @staticmethod
    def execute(args):
        """执行UI对比"""
        parser = argparse.ArgumentParser(
            description='UI组件树对比工具 - 对比两个组件树并标记差异',
            prog='ArkAnalyzer-HapRay ui-compare',
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        parser.add_argument('--tree1', type=str, required=True, help='组件树1文件路径')
        parser.add_argument('--screenshot1', type=str, required=True, help='截图1文件路径')
        parser.add_argument('--tree2', type=str, required=True, help='组件树2文件路径')
        parser.add_argument('--screenshot2', type=str, required=True, help='截图2文件路径')
        parser.add_argument('-o', '--output', type=str, default='./ui_compare_output', help='输出目录')

        parsed_args = parser.parse_args(args)

        # 验证输入文件
        for path in [parsed_args.tree1, parsed_args.screenshot1, parsed_args.tree2, parsed_args.screenshot2]:
            if not os.path.exists(path):
                logging.error(f'文件不存在: {path}')
                return None

        # 执行对比
        comparator = UITreeComparator()
        result = comparator.compare_ui_trees(
            parsed_args.tree1,
            parsed_args.screenshot1,
            parsed_args.tree2,
            parsed_args.screenshot2,
            parsed_args.output,
        )

        # 保存结果
        result_file = os.path.join(parsed_args.output, 'comparison_result.json')
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logging.info(f'对比完成，发现 {result["diff_count"]} 处差异')
        logging.info(f'结果已保存到: {parsed_args.output}')
        logging.info(f'标记图片: {result["marked_images"]}')

        return result

