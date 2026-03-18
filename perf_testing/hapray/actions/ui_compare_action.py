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
import base64
import glob
import logging
import os
import sys

from hapray import VERSION
from hapray.core.common.path_utils import get_user_data_root
from hapray.ui_detector.ui_tree_comparator import UITreeComparator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class UICompareAction:
    """UI组件树对比工具入口"""

    @staticmethod
    def _find_ui_files(report_dir: str) -> dict:
        """从报告目录自动查找UI文件

        Args:
            report_dir: 报告根目录，如 PerfLoad_meituan_0010

        Returns:
            包含截图和组件树文件路径的字典，按step组织
        """
        ui_dir = os.path.join(report_dir, 'ui')
        if not os.path.exists(ui_dir):
            logging.error(f'UI目录不存在: {ui_dir}')
            return {}

        result = {}
        # 遍历所有step目录
        for step_dir in sorted(glob.glob(os.path.join(ui_dir, 'step*'))):
            step_name = os.path.basename(step_dir)

            # 查找所有截图和组件树文件（按阶段分组）
            result[step_name] = {
                'screenshots': {
                    'start': sorted(glob.glob(os.path.join(step_dir, 'screenshot_start_*.png'))),
                    'end': sorted(glob.glob(os.path.join(step_dir, 'screenshot_end_*.png'))),
                },
                'trees': {
                    'start': sorted(glob.glob(os.path.join(step_dir, 'element_tree_start_*.txt'))),
                    'end': sorted(glob.glob(os.path.join(step_dir, 'element_tree_end_*.txt'))),
                },
            }

        return result

    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        """将图片转换为base64编码"""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logging.error(f'Failed to encode image {image_path}: {e}')
            return ''

    @staticmethod
    def execute(args):
        """执行UI对比"""
        parser = argparse.ArgumentParser(
            description='UI组件树对比工具 - 对比两个报告的UI组件树',
            prog='ArkAnalyzer-HapRay ui-compare',
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        parser.add_argument('--base_dir', type=str, required=True, help='基准报告根目录')
        parser.add_argument('--compare_dir', type=str, required=True, help='对比报告根目录')
        parser.add_argument('-o', '--output', type=str, default='./ui_compare_output', help='输出目录')

        parsed_args = parser.parse_args(args)

        # 验证目录
        if not os.path.exists(parsed_args.base_dir):
            logging.error(f'基准目录不存在: {parsed_args.base_dir}')
            return None
        if not os.path.exists(parsed_args.compare_dir):
            logging.error(f'对比目录不存在: {parsed_args.compare_dir}')
            return None

        # macOS 下避免 cwd 只读：无论是否显式传参，输出均落到用户目录下
        if sys.platform == 'darwin':
            parsed_args.output = str(get_user_data_root('ui_compare_output') / os.path.basename(parsed_args.output))

        # 自动查找UI文件
        base_files = UICompareAction._find_ui_files(parsed_args.base_dir)
        compare_files = UICompareAction._find_ui_files(parsed_args.compare_dir)

        if not base_files:
            logging.error(f'基准目录未找到UI文件: {parsed_args.base_dir}')
            return None
        if not compare_files:
            logging.error(f'对比目录未找到UI文件: {parsed_args.compare_dir}')
            return None

        # 对比所有共同的step
        all_results = {}
        comparator = UITreeComparator()

        common_steps = set(base_files.keys()) & set(compare_files.keys())
        if not common_steps:
            logging.error('两个报告没有共同的step')
            return None

        for step in sorted(common_steps):
            logging.info(f'正在对比 {step}...')
            step_results = []

            # 对比所有阶段（start和end）
            for phase in ['start', 'end']:
                base_screenshots = base_files[step]['screenshots'][phase]
                base_trees = base_files[step]['trees'][phase]
                compare_screenshots = compare_files[step]['screenshots'][phase]
                compare_trees = compare_files[step]['trees'][phase]

                # 对比每一对截图和组件树
                for i in range(min(len(base_screenshots), len(compare_screenshots))):
                    if i >= len(base_trees) or i >= len(compare_trees):
                        continue

                    logging.info(f'  对比 {phase}_{i + 1}...')
                    step_output = os.path.join(parsed_args.output, step, f'{phase}_{i + 1}')

                    result = comparator.compare_ui_trees(
                        base_trees[i],
                        base_screenshots[i],
                        compare_trees[i],
                        compare_screenshots[i],
                        step_output,
                        filter_minor_changes=True,  # 启用微小变化过滤
                    )

                    # 将图片转换为base64用于HTML
                    result['marked_images_base64'] = [
                        UICompareAction._image_to_base64(result['marked_images'][0]),
                        UICompareAction._image_to_base64(result['marked_images'][1]),
                    ]
                    result['phase'] = phase
                    result['index'] = i + 1

                    step_results.append(result)
                    logging.info(f'  {phase}_{i + 1} 对比完成，发现 {result["diff_count"]} 处差异')

            all_results[step] = step_results

        # 生成HTML报告
        html_path = os.path.join(parsed_args.output, 'ui_compare_report.html')
        UICompareAction._generate_html_report(all_results, html_path, parsed_args.base_dir, parsed_args.compare_dir)

        logging.info('所有对比完成')
        logging.info(f'HTML报告: {html_path}')

        return all_results

    @staticmethod
    def _generate_html_report(results: dict, output_path: str, base_dir: str, compare_dir: str):
        """生成HTML对比报告"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI组件树对比报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; background: #f5f7fa; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: white; padding: 30px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ font-size: 28px; color: #333; margin-bottom: 15px; }}
        .meta {{ color: #666; font-size: 14px; line-height: 1.8; }}
        .step-section {{ background: white; padding: 25px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .step-title {{ font-size: 22px; font-weight: bold; margin-bottom: 20px; color: #333; border-bottom: 2px solid #409eff; padding-bottom: 10px; }}
        .selector {{ margin-bottom: 20px; }}
        .selector select {{ padding: 8px 12px; font-size: 14px; border: 1px solid #dcdfe6; border-radius: 4px; background: white; cursor: pointer; }}
        .phase-section {{ margin-bottom: 30px; padding: 20px; background: #f8f9fa; border-radius: 6px; display: none; }}
        .phase-section.active {{ display: block; }}
        .phase-title {{ font-size: 18px; font-weight: 600; margin-bottom: 15px; color: #555; }}
        .diff-summary {{ background: #ecf5ff; padding: 15px; border-radius: 4px; margin-bottom: 15px; border-left: 4px solid #409eff; }}
        .diff-count {{ font-size: 20px; font-weight: bold; color: #e74c3c; }}
        .images {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
        .image-container {{ text-align: center; }}
        .image-container img {{ max-width: 100%; height: auto; border: 2px solid #ddd; border-radius: 4px; cursor: pointer; transition: transform 0.2s; }}
        .image-container img:hover {{ transform: scale(1.02); border-color: #409eff; }}
        .image-label {{ font-weight: 600; margin-bottom: 10px; color: #555; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; table-layout: fixed; }}
        th, td {{ padding: 8px; text-align: left; border: 1px solid #e4e7ed; word-wrap: break-word; overflow-wrap: break-word; }}
        th {{ background: #f5f7fa; font-weight: 600; color: #333; }}
        tr:hover {{ background: #f5f7fa; }}
        .attr-name {{ color: #409eff; font-weight: 500; }}
        .value-cell {{ max-width: 300px; word-break: break-all; }}
        .no-diff {{ color: #67c23a; text-align: center; padding: 20px; font-size: 16px; }}
        .component-type {{ background: #409eff; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 UI组件树对比报告</h1>
            <div class="meta">
                <div><strong>基准版本:</strong> {os.path.abspath(base_dir)}</div>
                <div><strong>对比版本:</strong> {os.path.abspath(compare_dir)}</div>
                <div><strong>生成时间:</strong> {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
        </div>
"""

        for step, step_results in sorted(results.items()):
            total_diffs = sum(r['diff_count'] for r in step_results)

            # 生成选项列表
            options = []
            for idx, result in enumerate(step_results):
                phase_label = '开始阶段' if result['phase'] == 'start' else '结束阶段'
                options.append(
                    f'<option value="{idx}">{phase_label} #{result["index"]} (差异: {result["diff_count"]})</option>'
                )

            html += f'''
        <div class="step-section" id="{step}">
            <div class="step-title">📱 {step} - 共发现 {total_diffs} 处差异</div>
            <div class="selector">
                <label for="select-{step}">选择对比图片：</label>
                <select id="select-{step}" onchange="showPhase('{step}', this.value)">
                    {chr(10).join(options)}
                </select>
            </div>
'''

            for idx, result in enumerate(step_results):
                phase_label = '开始阶段' if result['phase'] == 'start' else '结束阶段'
                active_class = 'active' if idx == 0 else ''

                html += f'''
            <div class="phase-section {active_class}" id="{step}-phase-{idx}">
                <div class="phase-title">{phase_label} #{result['index']}</div>
                <div class="diff-summary">
                    <div>🔍 发现差异: <span class="diff-count">{result['diff_count']}</span> 处 |
                    总差异数: {result['total_differences']} | 已过滤: {result['filtered_count']}</div>
                </div>
                <div class="images">
                    <div class="image-container">
                        <div class="image-label">📊 基准版本</div>
                        <img src="data:image/png;base64,{result['marked_images_base64'][0]}" alt="Base" onclick="window.open(this.src)">
                    </div>
                    <div class="image-container">
                        <div class="image-label">📊 对比版本</div>
                        <img src="data:image/png;base64,{result['marked_images_base64'][1]}" alt="Compare" onclick="window.open(this.src)">
                    </div>
                </div>
'''

                if result['differences']:
                    html += """
                <details open>
                    <summary style="cursor: pointer; font-weight: 600; padding: 10px; background: #fff; border-radius: 4px; margin-top: 15px;">
                        📋 差异详情列表
                    </summary>
                    <table>
                        <thead>
                            <tr>
                                <th width="5%">#</th>
                                <th width="12%">组件类型</th>
                                <th width="15%">属性名</th>
                                <th width="34%">基准值</th>
                                <th width="34%">对比值</th>
                            </tr>
                        </thead>
                        <tbody>
"""
                    for diff_idx, diff in enumerate(result['differences'], 1):
                        comp_type = diff.get('component', {}).get('type', '未知')
                        for attr_diff in diff.get('comparison_result', []):
                            val1 = str(attr_diff.get('value1', 'N/A'))
                            val2 = str(attr_diff.get('value2', 'N/A'))
                            html += f"""
                            <tr>
                                <td>{diff_idx}</td>
                                <td><span class="component-type">{comp_type}</span></td>
                                <td class="attr-name">{attr_diff.get('attribute', 'N/A')}</td>
                                <td class="value-cell">{val1}</td>
                                <td class="value-cell">{val2}</td>
                            </tr>
"""
                    html += """
                        </tbody>
                    </table>
                </details>
"""
                else:
                    html += '<div class="no-diff">✅ 未发现差异</div>'

                html += """
            </div>
"""

            html += """
        </div>
"""

        html += """
    </div>
    <script>
        function showPhase(step, index) {
            const sections = document.querySelectorAll(`#${step} .phase-section`);
            sections.forEach((section, i) => {
                section.classList.toggle('active', i == index);
            });
        }
    </script>
</body>
</html>"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
