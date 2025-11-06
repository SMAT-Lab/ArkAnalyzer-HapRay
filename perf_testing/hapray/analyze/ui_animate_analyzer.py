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

import base64
import json
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.ui_detector.arkui_tree_parser import compare_arkui_trees, parse_arkui_tree
from hapray.ui_detector.image_comparator import RegionImageComparator


class UIAnimateAnalyzer(BaseAnalyzer):
    """
    UI动画分析器

    分析步骤：
    1. 解析inspector_start.json中 type 为XCompose组件，获取组件bounds
    2. 比较screenshot_start_1.png，screenshot_start_2.png 和步骤1获取的组件位置图像差异，存在差异识别为动画
    3. 基于2次element树属性差异识别动画，输入element_tree_start_1.txt、element_tree_start_2.txt
    end采用同样的算法识别
    """

    def __init__(self, scene_dir: str):
        """初始化UI动画分析器

        Args:
            scene_dir: 场景根目录
        """
        super().__init__(scene_dir, 'ui/animate')
        self.image_comparator = RegionImageComparator()

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """实现UI动画分析逻辑

        Args:
            step_dir: 步骤目录
            trace_db_path: 跟踪数据库路径
            perf_db_path: 性能数据库路径
            app_pids: 应用进程ID列表

        Returns:
            分析结果字典
        """
        try:
            # 构建UI数据目录路径
            ui_dir = os.path.join(self.scene_dir, 'ui', step_dir)

            if not os.path.exists(ui_dir):
                self.logger.warning(f'UI目录不存在: {ui_dir}')
                return None

            # 分析start阶段的动画
            start_animation_result = self._analyze_animation_phase(ui_dir, 'start')

            # 分析end阶段的动画
            end_animation_result = self._analyze_animation_phase(ui_dir, 'end')

            # 合并结果
            return {
                'start_phase': start_animation_result,
                'end_phase': end_animation_result,
                'summary': self._generate_summary(start_animation_result, end_animation_result),
            }

        except Exception as e:
            self.logger.error(f'UI动画分析失败: {str(e)}')
            return {'error': str(e)}

    def _analyze_animation_phase(self, ui_dir: str, phase: str) -> dict[str, Any]:
        """分析特定阶段的动画

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称 ('start' 或 'end')

        Returns:
            该阶段的动画分析结果
        """
        try:
            # 1. 解析inspector文件，获取可能的动画组件
            animation_components = self._parse_animation_components(ui_dir, phase)

            # 2. 图像差异分析
            image_animation_result = self._analyze_image_differences(ui_dir, phase, animation_components)

            # 3. Element树差异分析
            tree_animation_result = self._analyze_tree_differences(ui_dir, phase)

            regions = []
            for animation_info in image_animation_result.get('animation_regions'):
                bounds_rect = animation_info['component']['bounds_rect']
                regions.append(bounds_rect)

            for animation_info in tree_animation_result.get('animation_regions'):
                bounds_rect = animation_info['component']['bounds_rect']
                regions.append(bounds_rect)

            # 4. 生成标记的截图
            marked_images = self._generate_marked_images(ui_dir, phase, regions)

            return {
                'image_animations': image_animation_result,
                'tree_animations': tree_animation_result,
                'marked_images': marked_images,
            }

        except Exception as e:
            self.logger.error(f'分析{phase}阶段动画失败: {str(e)}')
            return {'error': str(e)}

    def _parse_animation_components(self, ui_dir: str, phase: str) -> list[dict[str, Any]]:
        """解析inspector文件中的可能的动画组件

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称

        Returns:
            动画组件列表
        """
        inspector_file = os.path.join(ui_dir, f'inspector_{phase}.json')

        if not os.path.exists(inspector_file):
            self.logger.warning(f'Inspector文件不存在: {inspector_file}')
            return []

        try:
            with open(inspector_file, encoding='utf-8') as f:
                inspector_data = json.load(f)

            animation_components = []
            for child in inspector_data['children']:
                if child.get('attributes', {}).get('type', '') == 'root':
                    self._extract_animation_components(child, animation_components)

            self.logger.info(f'在{phase}阶段找到{len(animation_components)}个XCompose组件')
            return animation_components

        except Exception as e:
            self.logger.error(f'解析inspector文件失败: {str(e)}')
            return []

    def _extract_animation_components(self, data: dict[str, Any], components: list[dict[str, Any]], path: str = ''):
        """递归提取XCompose组件

        Args:
            data: 组件数据
            components: 组件列表
            path: 当前路径
        """
        if not isinstance(data, dict):
            return

        # 检查当前组件是否为XCompose
        component_type = data.get('attributes', {}).get('type', '')
        if component_type in ['XCompose']:
            bounds = data.get('attributes', {}).get('bounds', '')
            bounds_rect = self._parse_bounds(bounds)

            if bounds_rect:
                component_info = {
                    'type': component_type,
                    'bounds_rect': bounds_rect,
                    'path': path,
                    'attributes': data.get('attributes', {}),
                    'id': data.get('attributes', {}).get('id', ''),
                }
                components.append(component_info)

        # 递归处理子组件
        children = data.get('children', [])
        for _i, child in enumerate(children):
            child_path = (
                f'{path}/{child.get("attributes", {}).get("type", "")}'
                if path
                else f'{child.get("attributes", {}).get("type", "")}'
            )
            self._extract_animation_components(child, components, child_path)

    def _parse_bounds(self, bounds_str: str) -> Optional[tuple[int, int, int, int]]:
        """解析bounds字符串为坐标元组

        Args:
            bounds_str: bounds字符串，格式如 "[0,0][1084,2412]"

        Returns:
            坐标元组 (x1, y1, x2, y2) 或 None
        """
        try:
            # 匹配格式 [x1,y1][x2,y2]
            match = re.match(r'\[(\d+),(\d+)]\[(\d+),(\d+)]', bounds_str)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                return x1, y1, x2, y2
        except Exception as e:
            self.logger.warning(f'解析bounds失败: {bounds_str}, 错误: {str(e)}')

        return None

    def _analyze_image_differences(
        self, ui_dir: str, phase: str, xcompose_components: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """分析图像差异

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称
            xcompose_components: XCompose组件列表

        Returns:
            图像差异分析结果
        """
        screenshot1_path = os.path.join(ui_dir, f'screenshot_{phase}_1.png')
        screenshot2_path = os.path.join(ui_dir, f'screenshot_{phase}_2.png')

        if not os.path.exists(screenshot1_path) or not os.path.exists(screenshot2_path):
            self.logger.warning(f'截图文件不存在: {screenshot1_path} 或 {screenshot2_path}')
            return {'error': '截图文件不存在'}

        animation_regions = []

        # 对每个XCompose组件进行图像比较
        for component in xcompose_components:
            bounds_rect = component['bounds_rect']

            # 比较该区域的图像
            comparison_result = self.image_comparator.compare_regions(screenshot1_path, screenshot2_path, bounds_rect)

            if comparison_result:
                # 如果相似度低于阈值，认为是动画
                similarity_threshold = 85.0  # 可调整的阈值
                if comparison_result['similarity_percentage'] < similarity_threshold:
                    animation_info = {
                        'component': component,
                        'comparison_result': comparison_result,
                        'is_animation': True,
                        'animation_type': self._classify_animation_type(comparison_result),
                    }
                    animation_regions.append(animation_info)
                    self.logger.info(
                        f'检测到动画: {component["path"]}, 相似度: {comparison_result["similarity_percentage"]:.2f}%'
                    )

        return {
            'animation_regions': animation_regions,
            'animation_count': len(animation_regions),
        }

    def _classify_animation_type(self, comparison_result: dict[str, Any]) -> str:
        """根据比较结果分类动画类型

        Args:
            comparison_result: 图像比较结果

        Returns:
            动画类型
        """
        similarity = comparison_result['similarity_percentage']

        if similarity < 50:
            return 'major_change'
        if similarity < 70:
            return 'moderate_change'
        if similarity < 85:
            return 'minor_change'
        return 'no_change'

    def _analyze_tree_differences(self, ui_dir: str, phase: str) -> dict[str, Any]:
        """分析Element树差异

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称

        Returns:
            树差异分析结果
        """
        tree1_path = os.path.join(ui_dir, f'element_tree_{phase}_1.txt')
        tree2_path = os.path.join(ui_dir, f'element_tree_{phase}_2.txt')

        if not os.path.exists(tree1_path) or not os.path.exists(tree2_path):
            self.logger.warning(f'Element树文件不存在: {tree1_path} 或 {tree2_path}')
            return {'error': 'Element树文件不存在'}

        try:
            # 读取并解析两个Element树
            with open(tree1_path, encoding='utf-8') as f:
                tree1_content = f.read()

            with open(tree2_path, encoding='utf-8') as f:
                tree2_content = f.read()

            # 解析为组件树
            tree1 = parse_arkui_tree(tree1_content)
            tree2 = parse_arkui_tree(tree2_content)

            if tree1 and tree2:
                # 比较两个树
                differences = compare_arkui_trees(tree1, tree2)

                # 过滤出可能的动画相关差异
                animation_differences = self._filter_animation_differences(differences)

                return {
                    'animation_regions': animation_differences,
                    'animation_count': len(animation_differences),
                }
            return {'error': '无法解析Element树'}

        except Exception as e:
            self.logger.error(f'分析Element树差异失败: {str(e)}')
            return {'error': str(e)}

    def _filter_animation_differences(self, differences: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """过滤出可能的动画相关差异

        Args:
            differences: 所有差异列表

        Returns:
            动画相关差异列表
        """
        animation_related_attrs = {
            'bounds',
            'frameRect',
            'top',
            'left',
            'width',
            'height',
            'opacity',
            'scale',
            'rotation',
            'transform',
            'zIndex',
            'Alpha',
            'backgroundColor',
            'backgroundImage',
            'visible',
            'value',
            'url',
        }

        animation_differences = []

        for diff in differences:
            animation_attrs = []

            for attr_diff in diff.get('comparison_result', []):
                attr_name = attr_diff.get('attribute', '')

                # 检查是否为动画相关属性
                if any(anim_attr in attr_name.lower() for anim_attr in animation_related_attrs):
                    # 对于 url 属性，需要验证值是否符合URL规范
                    if 'url' in attr_name.lower():
                        value1 = attr_diff.get('value1')
                        value2 = attr_diff.get('value2')

                        # 只有当至少一个值是有效的URL时才包含此差异
                        is_valid_url = False
                        for value in [value1, value2]:
                            if value and isinstance(value, str):
                                try:
                                    result = urlparse(value)
                                    # 检查是否有scheme和netloc（基本URL验证）
                                    if result.scheme and result.netloc:
                                        is_valid_url = True
                                        break
                                except Exception:
                                    pass

                        if not is_valid_url:
                            continue

                    animation_attrs.append(attr_diff)

            if animation_attrs:
                animation_diff = diff.copy()
                animation_diff['comparison_result'] = animation_attrs
                animation_differences.append(animation_diff)

        return animation_differences

    def _generate_marked_images(self, ui_dir: str, phase: str, regions: list[tuple[int]]) -> list[str]:
        """生成标记了动画区域的截图

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称
            regions: 动画位置

        Returns:
            标记后的图像路径列表
        """
        try:
            screenshot1_path = os.path.join(ui_dir, f'screenshot_{phase}_1.png')
            screenshot2_path = os.path.join(ui_dir, f'screenshot_{phase}_2.png')
            if not regions:
                return []

            # 创建输出目录
            output_dir = os.path.join(ui_dir, 'marked_images')
            os.makedirs(output_dir, exist_ok=True)

            # 生成标记后的图像
            return self.image_comparator.generate_marked_images(
                screenshot1_path, screenshot2_path, regions, regions, output_dir, f'marked_{phase}'
            )

        except Exception as e:
            self.logger.error(f'生成标记图像失败: {str(e)}')
            return []

    def _generate_summary(self, start_result: dict[str, Any], end_result: dict[str, Any]) -> dict[str, Any]:
        """生成分析摘要

        Args:
            start_result: start阶段结果
            end_result: end阶段结果

        Returns:
            分析摘要
        """
        start_image_count = start_result.get('image_animations', {}).get('animation_count', 0)
        end_image_count = end_result.get('image_animations', {}).get('animation_count', 0)

        start_tree_count = start_result.get('tree_animations', {}).get('animation_count', 0)
        end_tree_count = end_result.get('tree_animations', {}).get('animation_count', 0)

        return {
            'total_animations': start_image_count + end_image_count,
            'start_phase_animations': start_image_count,
            'end_phase_animations': end_image_count,
            'start_phase_tree_changes': start_tree_count,
            'end_phase_tree_changes': end_tree_count,
            'has_animations': (start_image_count + end_image_count) > 0,
        }

    def _convert_images_to_base64(self):
        """将 self.results 中的图片路径转换为 base64 编码"""
        # 遍历所有步骤的结果
        for _step_key, step_data in self.results.items():
            if not isinstance(step_data, dict) or step_data.get('error'):
                continue

            # 处理 start_phase 和 end_phase
            for phase in ['start_phase', 'end_phase']:
                if phase in step_data and isinstance(step_data[phase], dict):
                    phase_data = step_data[phase]
                    if 'marked_images' in phase_data and isinstance(phase_data['marked_images'], list):
                        base64_images = []
                        for img_path in phase_data['marked_images']:
                            if os.path.exists(img_path):
                                try:
                                    with open(img_path, 'rb') as f:
                                        img_data = f.read()
                                        base64_str = base64.b64encode(img_data).decode('ascii')
                                        base64_images.append(base64_str)
                                except Exception as e:
                                    self.logger.warning(f'转换图片 {img_path} 为 base64 失败: {e}')
                            else:
                                self.logger.warning(f'图片文件不存在: {img_path}')

                        # 替换为 base64 数据
                        phase_data['marked_images_base64'] = base64_images
                        # 保留原始路径用于调试
                        phase_data['marked_images_paths'] = phase_data.pop('marked_images')

    def write_report(self, result: dict):
        """重写 write_report 方法，在写入前转换图片为 base64

        Args:
            result: 分析结果字典
        """
        if not self.results:
            self.logger.warning('No results to write. Skipping report generation for %s', self.report_path)
            return

        try:
            # 转换所有步骤的图片为 base64
            self._convert_images_to_base64()
        except Exception as e:
            self.logger.exception('Failed to convert images to base64: %s', str(e))

        # 调用基类的 write_report 方法
        super().write_report(result)
