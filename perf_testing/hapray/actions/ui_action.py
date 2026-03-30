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
import logging
import os
import sys
import time
from typing import Optional

from hypium import UiDriver

from hapray import VERSION
from hapray.analyze.ui_analyzer import UIAnalyzer
from hapray.core.collection.capture_ui import CaptureUI
from hapray.core.common.action_return import ActionExecuteReturn
from hapray.core.common.path_utils import get_user_data_root


class UIAction:
    """应用UI独立入口，包含dump组件树、截屏、UI动画分析和HTML报告生成"""

    def __init__(self, output_dir: str, device_sn: Optional[str] = None):
        """初始化UI Action

        Args:
            output_dir: 输出目录
            device_sn: 设备序列号（可选）
        """
        self.output_dir = output_dir

        self.logger = logging.getLogger(self.__class__.__name__)
        os.makedirs(output_dir, exist_ok=True)

        self.driver = UiDriver.connect(device_sn=device_sn)
        self.capture_ui = CaptureUI(self.driver)

    def __del__(self):
        """
        析构函数，关闭driver连接以释放资源
        """
        try:
            if hasattr(self, 'driver') and self.driver is not None:
                self.driver.close()
        except Exception:
            # 析构函数中不应该抛出异常，静默处理
            pass

    def collect_ui_data(self) -> bool:
        """收集UI数据（截屏、dump组件树和inspector JSON）

        使用CaptureUI的capture_ui()方法完成完整的UI数据抓取

        Returns:
            是否成功
        """
        try:
            self.logger.info('开始收集UI数据...')

            # 使用CaptureUI的capture_ui()方法完成UI数据抓取
            # step_id设为1，label_name设为'start'以兼容UIAnalyzer
            step_id = 1
            label_name = 'start'

            # 调用capture_ui()完成截屏和dump element树
            self.capture_ui.capture_ui(step_id, self.output_dir, label_name)
            self.logger.info('UI数据收集完成')
            return True

        except Exception as e:
            self.logger.error(f'收集UI数据失败: {e}')
            return False

    def analyze_ui_animation(self) -> Optional[dict]:
        """调用UIAnalyzer进行分析

        Returns:
            分析结果字典
        """
        try:
            self.logger.info('开始UI动画分析')

            # 创建UIAnalyzer实例
            analyzer = UIAnalyzer(self.output_dir)
            # 使用空字符串作为step_dir，数据直接保存在ui目录下
            analyzer.analyze('step1', '', '')
            return analyzer.results

        except Exception as e:
            self.logger.error(f'UI动画分析失败: {e}')
            return None

    def generate_html_report(self, analysis_result: dict, output_path: str) -> bool:
        """生成HTML报告

        Args:
            analysis_result: 分析结果字典
            output_path: HTML报告输出路径

        Returns:
            是否成功
        """
        try:
            self.logger.info(f'开始生成HTML报告: {output_path}')

            # 生成HTML内容
            html_content = self._render_html(analysis_result)

            # 保存HTML文件
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            self.logger.info(f'HTML报告生成成功: {output_path}')
            return True

        except Exception as e:
            self.logger.error(f'生成HTML报告失败: {e}')
            return False

    def _render_html(self, analysis_result: dict) -> str:
        """渲染HTML内容

        Args:
            analysis_result: 分析结果字典

        Returns:
            HTML内容字符串
        """
        # 提取摘要信息
        summary = analysis_result.get('summary', {})
        # 合并所有阶段的数据
        all_phase_data = {}
        marked_images = []

        # 处理所有阶段的标记图片
        for phase_key in ['start_phase', 'end_phase']:
            phase_data = analysis_result.get(phase_key, {})
            if phase_data:
                # 合并动画数据
                for key in ['image_animations', 'tree_animations']:
                    if key in phase_data:
                        if key not in all_phase_data:
                            all_phase_data[key] = phase_data[key]
                        # 合并动画区域
                        elif 'animation_regions' in phase_data[key]:
                            all_phase_data[key].setdefault('animation_regions', []).extend(
                                phase_data[key]['animation_regions']
                            )

                # 处理标记的图片（转换为base64）
                if phase_data.get('marked_images'):
                    for img_path in phase_data['marked_images']:
                        if os.path.exists(img_path):
                            try:
                                with open(img_path, 'rb') as f:
                                    img_data = f.read()
                                    base64_str = base64.b64encode(img_data).decode('ascii')
                                    marked_images.append(base64_str)
                            except Exception as e:
                                self.logger.warning(f'转换图片 {img_path} 为 base64 失败: {e}')

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UI动画分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #ecf0f1;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card h3 {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        .image-container {{
            margin: 20px 0;
        }}
        .image-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin: 10px 0;
        }}
        .animation-list {{
            list-style: none;
            padding: 0;
        }}
        .animation-item {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }}
        .animation-item h4 {{
            color: #2c3e50;
            margin-bottom: 8px;
        }}
        .animation-item p {{
            color: #7f8c8d;
            font-size: 14px;
        }}
        .no-data {{
            text-align: center;
            color: #95a5a6;
            padding: 40px;
            font-style: italic;
        }}
        .timestamp {{
            color: #95a5a6;
            font-size: 12px;
            text-align: right;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 UI动画分析报告</h1>

        <div class="summary">
            <div class="summary-card">
                <h3>总动画数</h3>
                <div class="value">{summary.get('total_animations', 0)}</div>
            </div>
            <div class="summary-card">
                <h3>元素树变化</h3>
                <div class="value">{summary.get('start_phase_tree_changes', 0) + summary.get('end_phase_tree_changes', 0)}</div>
            </div>
        </div>

        <div>
            <h2>📸 UI动画分析结果</h2>
            {self._render_phase_html(all_phase_data, marked_images)}
        </div>

        <div class="timestamp">
            报告生成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}
        </div>
    </div>
</body>
</html>"""

    def _render_phase_html(self, phase_data: dict, marked_images: list) -> str:
        """渲染HTML内容

        Args:
            phase_data: 动画数据
            marked_images: 标记的图片base64列表

        Returns:
            HTML内容字符串
        """
        html_parts = []

        # 图像动画
        image_animations = phase_data.get('image_animations', {})
        animation_regions = image_animations.get('animation_regions', [])
        if animation_regions:
            html_parts.append('<h3>🖼️ 图像动画检测</h3>')
            html_parts.append(f'<p>检测到 <strong>{len(animation_regions)}</strong> 个动画区域</p>')
            html_parts.append('<ul class="animation-list">')
            for i, anim in enumerate(animation_regions, 1):
                component = anim.get('component', {})
                similarity = anim.get('similarity', 0)
                html_parts.append(f"""
                <li class="animation-item">
                    <h4>动画区域 #{i}</h4>
                    <p>组件路径: {component.get('path', 'N/A')}</p>
                    <p>相似度: {similarity:.2f}%</p>
                    <p>动画类型: {anim.get('animation_type', 'N/A')}</p>
                </li>""")
            html_parts.append('</ul>')
        else:
            html_parts.append('<p class="no-data">未检测到图像动画</p>')

        # 元素树动画
        tree_animations = phase_data.get('tree_animations', {})
        tree_animation_regions = tree_animations.get('animation_regions', [])
        if tree_animation_regions:
            html_parts.append('<h3>🌳 元素树变化检测</h3>')
            html_parts.append(f'<p>检测到 <strong>{len(tree_animation_regions)}</strong> 个元素树变化</p>')
            html_parts.append('<ul class="animation-list">')
            for i, anim in enumerate(tree_animation_regions, 1):
                html_parts.append(f"""
                <li class="animation-item">
                    <h4>变化 #{i}</h4>
                    <p>组件ID: {anim.get('component_id', 'N/A')}</p>
                </li>""")
            html_parts.append('</ul>')

        # 标记的图片
        if marked_images:
            html_parts.append('<h3>📷 标记的截图</h3>')
            html_parts.append('<div class="image-container">')
            for i, img_base64 in enumerate(marked_images, 1):
                html_parts.append(f'<img src="data:image/png;base64,{img_base64}" alt="标记截图 {i}" />')
            html_parts.append('</div>')

        return '\n'.join(html_parts)

    def run(self) -> bool:
        """执行完整的UI分析流程

        Returns:
            是否成功
        """
        try:
            self.logger.info('=' * 60)
            self.logger.info('开始UI分析流程')
            self.logger.info(f'输出目录: {self.output_dir}')
            self.logger.info('=' * 60)

            # 1. 收集UI数据
            self.logger.info('收集UI数据...')
            if not self.collect_ui_data():
                self.logger.error('收集UI数据失败')
                return False

            # 2. 调用UIAnalyzer进行分析
            self.logger.info('开始UI动画分析...')
            analysis_result = self.analyze_ui_animation()
            if not analysis_result:
                self.logger.error('UI动画分析失败')
                return False

            # 3. 生成HTML报告
            self.logger.info('生成HTML报告...')
            html_report_path = os.path.join(self.output_dir, 'ui_animation_report.html')
            if not self.generate_html_report(analysis_result, html_report_path):
                self.logger.error('生成HTML报告失败')
                return False

            self.logger.info('=' * 60)
            self.logger.info('✅ UI分析流程完成')
            self.logger.info(f'📄 HTML报告: {html_report_path}')
            self.logger.info('=' * 60)

            return True

        except Exception as e:
            self.logger.error(f'UI分析流程失败: {e}')
            return False

    @staticmethod
    def execute(args) -> ActionExecuteReturn:
        """执行UI分析工作流"""
        if '--multiprocessing-fork' in args:
            return (0, '')

        parser = argparse.ArgumentParser(
            description='应用UI独立入口 - dump组件树、截屏、UI动画分析和HTML报告生成',
            prog='ArkAnalyzer-HapRay ui',
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        parser.add_argument(
            '-o',
            '--output',
            type=str,
            default='./ui_output',
            help='输出目录（默认: ./ui_output）',
        )

        parser.add_argument(
            '--device',
            type=str,
            default=None,
            help='设备序列号（例如: HX1234567890）',
        )

        parsed_args = parser.parse_args(args)

        # 创建输出目录
        output_dir = os.path.abspath(parsed_args.output)
        # macOS 下避免 cwd 只读：无论是否显式传参，输出均落到用户目录下
        if sys.platform == 'darwin':
            output_dir = str(get_user_data_root('ui_output') / os.path.basename(output_dir))
        os.makedirs(output_dir, exist_ok=True)

        # 创建UIAction实例并执行
        action = UIAction(output_dir, device_sn=parsed_args.device)
        success = action.run()

        return (0, output_dir) if success else (1, '')


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    UIAction.execute(sys.argv[1:])
