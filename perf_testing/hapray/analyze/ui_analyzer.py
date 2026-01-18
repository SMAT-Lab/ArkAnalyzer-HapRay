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
import glob
import json
import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.ui_detector.arkui_tree_parser import compare_arkui_trees, parse_arkui_tree
from hapray.ui_detector.image_comparator import RegionImageComparator
from hapray.ui_detector.image_size_analyzer import analyze_image_sizes


class UIAnalyzer(BaseAnalyzer):
    """
    UI分析器

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

            # 解析pages.json文件开始UI分析
            pages_json_path = os.path.join(ui_dir, 'pages.json')
            if os.path.exists(pages_json_path):
                # 基于pages.json进行分析
                return self._analyze_from_pages_json(ui_dir, pages_json_path)
            # 兼容旧的start/end阶段分析逻辑
            self.logger.info(f'pages.json不存在，使用旧的start/end阶段分析: {ui_dir}')
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

            # 4. 分析超出尺寸的Image节点
            image_size_result = self._analyze_image_sizes(ui_dir, phase)

            regions = []
            # 添加动画区域的bounds
            for animation_info in image_animation_result.get('animation_regions', []):
                bounds_rect = animation_info['component']['bounds_rect']
                if bounds_rect:
                    regions.append({'type': 'animation', 'bounds_rect': bounds_rect})

            for animation_info in tree_animation_result.get('animation_regions', []):
                bounds_rect = animation_info['component']['bounds_rect']
                if bounds_rect:
                    regions.append({'type': 'animation', 'bounds_rect': bounds_rect})

            # 添加超出尺寸Image的bounds
            for image_info in image_size_result.get('images_exceeding_framerect', []):
                bounds_rect = image_info.get('bounds_rect')
                if bounds_rect:
                    excess_memory_mb = image_info.get('memory', {}).get('excess_memory_mb', 0.0)
                    regions.append(
                        {'type': 'exceeding_image', 'bounds_rect': bounds_rect, 'excess_memory_mb': excess_memory_mb}
                    )

            # 5. 生成标记的截图
            marked_images = self._generate_marked_images(ui_dir, phase, regions)

            return {
                'image_animations': image_animation_result,
                'tree_animations': tree_animation_result,
                'image_size_analysis': image_size_result,
                'marked_images': marked_images,
            }

        except Exception as e:
            self.logger.error(f'分析{phase}阶段动画失败: {str(e)}')
            return {'error': str(e)}

    def _analyze_from_pages_json(self, ui_dir: str, pages_json_path: str) -> list[dict[str, Any]]:
        """基于pages.json文件进行UI分析

        Args:
            ui_dir: UI数据目录
            pages_json_path: pages.json文件路径

        Returns:
            页面分析结果列表: [page_results]
        """
        try:
            # 读取pages.json文件
            with open(pages_json_path, encoding='utf-8') as f:
                pages = json.load(f)

            if not pages:
                self.logger.warning(f'pages.json中没有页面数据: {pages_json_path}')
                return []

            self.logger.info(f'从pages.json解析到{len(pages)}个页面，开始UI分析')

            # 分析每个页面的动画
            page_results = []
            for page_idx, page_info in enumerate(pages):
                page_result = self._analyze_page(ui_dir, page_info, page_idx)
                if page_result:
                    page_results.append(page_result)

            # 直接返回page_results列表
            return page_results

        except Exception as e:
            self.logger.error(f'基于pages.json分析失败: {str(e)}')
            return []

    def _analyze_page(self, ui_dir: str, page_info: dict[str, Any], page_idx: int) -> Optional[dict[str, Any]]:
        """分析单个页面

        Args:
            ui_dir: UI数据目录
            page_info: 页面信息字典（包含element_tree, screenshot等路径）
            page_idx: 页面索引

        Returns:
            页面分析结果，格式: {
                'page_idx': int,
                'description': str,
                'canvasNodeCnt': int,
                'image_size_analysis': {...},
                'animations': {...}  # 可选
            }
        """
        try:
            page_description = page_info.get('description', f'page{page_idx}')
            actual_page_idx = page_info.get('page_idx', page_idx)
            self.logger.info(f'开始分析页面: {page_description} (索引: {actual_page_idx})')

            result = {
                'page_idx': actual_page_idx,
                'description': page_description,
            }

            # 如果存在element_tree文件，进行组件树分析
            element_tree_path = page_info.get('element_tree')
            canvas_node_count = 0

            if element_tree_path:
                if not os.path.isabs(element_tree_path):
                    element_tree_path = os.path.join(ui_dir, os.path.basename(element_tree_path))

                if os.path.exists(element_tree_path):
                    # 分析组件树（包括CanvasNode统计等）
                    tree_analysis = self._analyze_tree_from_file(element_tree_path)
                    if tree_analysis:
                        canvas_node_count = tree_analysis.get('canvas_node_count', 0)
                        result['canvasNodeCnt'] = canvas_node_count

                    # 进行图片尺寸分析
                    image_size_analysis = self._analyze_image_size_from_file(element_tree_path, ui_dir)
                    if image_size_analysis:
                        result['image_size_analysis'] = image_size_analysis

            # 如果存在多个截图或组件树（animate=True的情况），进行动画分析
            screenshot = page_info.get('screenshot')
            screenshot_2 = page_info.get('screenshot_2')
            element_tree_2 = page_info.get('element_tree_2')

            animations = {}
            has_animations = False

            # 图像动画分析
            if screenshot and screenshot_2:
                screenshot_full = (
                    os.path.join(ui_dir, os.path.basename(screenshot)) if not os.path.isabs(screenshot) else screenshot
                )
                screenshot_2_full = (
                    os.path.join(ui_dir, os.path.basename(screenshot_2))
                    if not os.path.isabs(screenshot_2)
                    else screenshot_2
                )

                if os.path.exists(screenshot_full) and os.path.exists(screenshot_2_full):
                    image_animation = self._analyze_image_animation_from_files(
                        screenshot_full, screenshot_2_full, ui_dir
                    )
                    if image_animation:
                        animations['image_animations'] = image_animation.get('image_animations', {})
                        if 'marked_images' in image_animation:
                            animations['marked_images'] = image_animation['marked_images']
                        has_animations = True

            # 组件树动画分析
            if element_tree_path and element_tree_2:
                element_tree_2_full = (
                    os.path.join(ui_dir, os.path.basename(element_tree_2))
                    if not os.path.isabs(element_tree_2)
                    else element_tree_2
                )
                if os.path.exists(element_tree_path) and os.path.exists(element_tree_2_full):
                    tree_animation = self._analyze_tree_animation_from_files(element_tree_path, element_tree_2_full)
                    if tree_animation:
                        animations['tree_animations'] = tree_animation
                        has_animations = True

            # 如果有动画分析结果，添加到结果中
            if has_animations:
                result['animations'] = animations

            return result

        except Exception as e:
            self.logger.error(f'分析页面失败 (索引: {page_idx}): {str(e)}')
            return None

    def _analyze_tree_from_file(self, element_tree_path: str) -> Optional[dict[str, Any]]:
        """从element_tree文件分析组件树

        Args:
            element_tree_path: 组件树文件路径

        Returns:
            组件树分析结果（包括CanvasNode统计等）
        """
        try:
            with open(element_tree_path, encoding='utf-8') as f:
                content = f.read()

            # 解析组件树
            tree_dict = parse_arkui_tree(content)

            # 提取分析结果
            return {
                'canvas_node_count': tree_dict.get('canvas_node_count', 0),
            }

        except Exception as e:
            self.logger.error(f'解析组件树文件失败: {element_tree_path}, 错误: {str(e)}')
            return None

    def _analyze_image_differences_from_files(
        self, screenshot_path_1: str, screenshot_path_2: str
    ) -> Optional[dict[str, Any]]:
        """从两个截图文件进行图像差异分析

        Args:
            screenshot_path_1: 第一个截图路径
            screenshot_path_2: 第二个截图路径

        Returns:
            图像差异分析结果
        """
        # TODO: 实现基于文件的图像差异分析
        # 这里可以调用现有的图像差异分析逻辑
        return None

    def _analyze_image_size_from_file(self, element_tree_path: str, ui_dir: str) -> Optional[dict[str, Any]]:
        """从element_tree文件分析图片尺寸

        Args:
            element_tree_path: 组件树文件路径
            ui_dir: UI数据目录

        Returns:
            图片尺寸分析结果，包含 marked_image (base64)
        """
        try:
            with open(element_tree_path, encoding='utf-8') as f:
                content = f.read()

            # 解析组件树
            tree_dict = parse_arkui_tree(content)

            if not tree_dict:
                return None

            # 分析Image尺寸
            image_size_result = analyze_image_sizes(tree_dict)

            # 如果有超出尺寸的Image，生成标记图片
            marked_image_base64 = None
            if image_size_result.get('images_exceeding_framerect'):
                # 尝试找到对应的截图文件
                screenshot_files = glob.glob(os.path.join(ui_dir, 'screenshot*.png'))
                if screenshot_files:
                    screenshot_path = screenshot_files[0]  # 使用第一个找到的截图

                    # 生成标记图片
                    exceeding_regions = []
                    for img_info in image_size_result.get('images_exceeding_framerect', []):
                        bounds_rect = img_info.get('bounds_rect')
                        if bounds_rect:
                            excess_memory_mb = img_info.get('memory', {}).get('excess_memory_mb', 0.0)
                            exceeding_regions.append({'bounds_rect': bounds_rect, 'excess_memory_mb': excess_memory_mb})

                    if exceeding_regions and os.path.exists(screenshot_path):
                        marked_image_path = self._generate_marked_image_for_size_analysis(
                            screenshot_path, exceeding_regions, ui_dir
                        )
                        if marked_image_path and os.path.exists(marked_image_path):
                            marked_image_base64 = self._image_to_base64(marked_image_path)

            result = {
                **image_size_result,
            }
            if marked_image_base64:
                result['marked_image'] = marked_image_base64

            return result

        except Exception as e:
            self.logger.error(f'分析图片尺寸失败: {element_tree_path}, 错误: {str(e)}')
            return None

    def _analyze_image_animation_from_files(
        self, screenshot_path_1: str, screenshot_path_2: str, ui_dir: str
    ) -> Optional[dict[str, Any]]:
        """从两个截图文件进行图像动画分析

        Args:
            screenshot_path_1: 第一个截图路径
            screenshot_path_2: 第二个截图路径
            ui_dir: UI数据目录

        Returns:
            图像动画分析结果，包含 marked_images (base64)
        """
        # TODO: 实现基于文件的图像动画分析
        # 这里可以调用现有的图像差异分析逻辑
        # 返回格式: {'image_animations': {...}, 'marked_images': base64_string}
        return None

    def _analyze_tree_animation_from_files(self, tree_path_1: str, tree_path_2: str) -> Optional[dict[str, Any]]:
        """从两个组件树文件进行树动画分析

        Args:
            tree_path_1: 第一个组件树文件路径
            tree_path_2: 第二个组件树文件路径

        Returns:
            组件树动画分析结果
        """
        try:
            # 读取并解析两个组件树文件
            with open(tree_path_1, encoding='utf-8') as f:
                content_1 = f.read()
            with open(tree_path_2, encoding='utf-8') as f:
                content_2 = f.read()

            tree_1 = parse_arkui_tree(content_1)
            tree_2 = parse_arkui_tree(content_2)

            # 比较两个组件树
            differences = compare_arkui_trees(tree_1, tree_2)

            return {
                'differences': differences,
                'difference_count': len(differences),
            }

        except Exception as e:
            self.logger.error(f'分析组件树动画失败: {str(e)}')
            return None

    def _generate_marked_image_for_size_analysis(
        self, screenshot_path: str, exceeding_regions: list[dict[str, Any]], ui_dir: str
    ) -> Optional[str]:
        """为图片尺寸分析生成标记图片

        Args:
            screenshot_path: 截图路径
            exceeding_regions: 超出尺寸的区域列表
            ui_dir: UI数据目录

        Returns:
            标记图片路径
        """
        try:
            img = Image.open(screenshot_path)
            img = img.convert('RGB')
            draw = ImageDraw.Draw(img)

            # 尝试加载字体
            try:
                font = ImageFont.truetype('arial.ttf', 40)
            except OSError:
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 40)
                except OSError:
                    font = ImageFont.load_default()

            # 标记超出尺寸Image区域（蓝色）
            for i, region_info in enumerate(exceeding_regions, 1):
                bounds_rect = region_info.get('bounds_rect')
                if not bounds_rect:
                    continue
                x1, y1, x2, y2 = bounds_rect
                # 绘制蓝色矩形框
                draw.rectangle([x1, y1, x2, y2], outline='blue', width=3)
                # 在区域左上角绘制编号
                text = f'I{i}'
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = x1 + 5
                text_y = y1 + 5
                draw.rectangle(
                    [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2],
                    fill='blue',
                )
                draw.text((text_x, text_y), text, fill='white', font=font)

            # 保存标记图片
            output_dir = os.path.join(ui_dir, 'marked_images')
            os.makedirs(output_dir, exist_ok=True)
            marked_image_path = os.path.join(output_dir, f'marked_size_{os.path.basename(screenshot_path)}')
            img.save(marked_image_path)

            return marked_image_path

        except Exception as e:
            self.logger.error(f'生成标记图片失败: {str(e)}')
            return None

    def _image_to_base64(self, image_path: str) -> Optional[str]:
        """将图片转换为base64编码

        Args:
            image_path: 图片路径

        Returns:
            base64编码的图片字符串
        """
        try:
            if not os.path.exists(image_path):
                return None

            with open(image_path, 'rb') as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode('ascii')

        except Exception as e:
            self.logger.error(f'转换图片为base64失败: {image_path}, 错误: {str(e)}')
            return None

    def _analyze_tree_differences_from_files(self, tree_path_1: str, tree_path_2: str) -> Optional[dict[str, Any]]:
        """从两个组件树文件进行差异分析（保留用于兼容性）

        Args:
            tree_path_1: 第一个组件树文件路径
            tree_path_2: 第二个组件树文件路径

        Returns:
            组件树差异分析结果
        """
        return self._analyze_tree_animation_from_files(tree_path_1, tree_path_2)

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
        if component_type in ['XCompose', 'Image']:
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
                        'region': bounds_rect,
                        'similarity': comparison_result['similarity_percentage'],
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

    def _analyze_image_sizes(self, ui_dir: str, phase: str) -> dict[str, Any]:
        """分析超出尺寸的Image节点

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称

        Returns:
            Image尺寸分析结果
        """
        tree_path = os.path.join(ui_dir, f'element_tree_{phase}_1.txt')

        if not os.path.exists(tree_path):
            self.logger.warning(f'Element树文件不存在: {tree_path}')
            return {'error': 'Element树文件不存在'}

        try:
            # 读取并解析Element树
            with open(tree_path, encoding='utf-8') as f:
                tree_content = f.read()

            # 解析为组件树
            tree_dict = parse_arkui_tree(tree_content)

            if tree_dict:
                # 分析Image尺寸
                result = analyze_image_sizes(tree_dict)
                self.logger.info(
                    f'在{phase}阶段找到{len(result.get("images_exceeding_framerect", []))}个超出尺寸的Image节点'
                )
                return result
            return {'error': '无法解析Element树'}

        except Exception as e:
            self.logger.error(f'分析Image尺寸失败: {str(e)}')
            return {'error': str(e)}

    def _generate_marked_images(
        self,
        ui_dir: str,
        phase: str,
        regions: list[dict[str, Any]],
    ) -> list[str]:
        """生成标记了动画区域和超出尺寸Image的截图

        Args:
            ui_dir: UI数据目录
            phase: 阶段名称
            regions: 区域列表，每个区域包含 type ('animation' 或 'exceeding_image') 和 bounds_rect

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

            # 根据type分离动画区域和超出尺寸Image区域
            animation_regions = []
            exceeding_image_regions = []

            for region in regions:
                if not region or not isinstance(region, dict):
                    continue
                region_type = region.get('type')
                bounds_rect = region.get('bounds_rect')
                if not bounds_rect:
                    continue

                if region_type == 'animation':
                    animation_regions.append(bounds_rect)
                elif region_type == 'exceeding_image':
                    # 保存超出大小信息
                    excess_memory_mb = region.get('excess_memory_mb', 0.0)
                    exceeding_image_regions.append({'bounds_rect': bounds_rect, 'excess_memory_mb': excess_memory_mb})

            # 生成标记后的图像（截图1标记动画，截图2标记超出尺寸Image）
            return self._generate_marked_images_with_types(
                screenshot1_path,
                screenshot2_path,
                animation_regions,
                exceeding_image_regions,
                output_dir,
                f'marked_{phase}',
            )

        except Exception as e:
            self.logger.error(f'生成标记图像失败: {str(e)}')
            return []

    def _generate_marked_images_with_types(
        self,
        image1_path: str,
        image2_path: str,
        animation_regions: list[tuple[int]],
        exceeding_image_regions: list[dict[str, Any]],
        output_dir: str,
        file_name: str,
    ) -> list[str]:
        """生成标记了动画区域（红色）和超出尺寸Image（蓝色）的截图

        Args:
            image1_path: 第一张截图路径（标记动画）
            image2_path: 第二张截图路径（标记超出尺寸Image）
            animation_regions: 动画区域列表
            exceeding_image_regions: 超出尺寸Image区域列表，每个元素包含 bounds_rect 和 excess_memory_mb
            output_dir: 输出目录
            file_name: 文件名前缀

        Returns:
            标记后的图像路径列表
        """
        try:
            marked_paths = []

            # 处理截图1（标记动画区域）
            if os.path.exists(image1_path):
                img = Image.open(image1_path)
                img = img.convert('RGB')
                draw = ImageDraw.Draw(img)

                # 尝试加载字体
                try:
                    font = ImageFont.truetype('arial.ttf', 40)
                except OSError:
                    try:
                        font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 40)
                    except OSError:
                        font = ImageFont.load_default()

                if animation_regions:
                    # 标记动画区域（红色）
                    for i, region in enumerate(animation_regions, 1):
                        x1, y1, x2, y2 = region
                        # 绘制红色矩形框
                        draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
                        # 在区域左上角绘制编号
                        text = f'A{i}'
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        text_x = x1 + 5
                        text_y = y1 + 5
                        draw.rectangle(
                            [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2], fill='white'
                        )
                        draw.text((text_x, text_y), text, fill='red', font=font)
                else:
                    # 未发现动画，在图片中央绘制提示
                    text = 'No Animation Found'
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    img_width, img_height = img.size
                    text_x = (img_width - text_width) // 2
                    text_y = (img_height - text_height) // 2
                    # 绘制白色背景
                    padding = 10
                    draw.rectangle(
                        [
                            text_x - padding,
                            text_y - padding,
                            text_x + text_width + padding,
                            text_y + text_height + padding,
                        ],
                        fill='white',
                    )
                    draw.text((text_x, text_y), text, fill='gray', font=font)

                # 保存标记后的图像
                output_path = os.path.join(output_dir, f'{file_name}_1.png')
                img.save(output_path)
                marked_paths.append(output_path)
                self.logger.info(f'已保存标记后的图像1: {output_path}')

            # 处理截图2（标记超出尺寸Image区域）
            if os.path.exists(image2_path):
                img = Image.open(image2_path)
                img = img.convert('RGB')
                draw = ImageDraw.Draw(img)

                # 尝试加载字体
                try:
                    font = ImageFont.truetype('arial.ttf', 40)
                except OSError:
                    try:
                        font = ImageFont.truetype('/System/Library/Fonts/Arial.ttf', 40)
                    except OSError:
                        font = ImageFont.load_default()

                if exceeding_image_regions:
                    # 标记超出尺寸Image区域（蓝色）
                    for i, region_info in enumerate(exceeding_image_regions, 1):
                        if isinstance(region_info, dict):
                            bounds_rect = region_info.get('bounds_rect')
                            excess_memory_mb = region_info.get('excess_memory_mb', 0.0)
                        else:
                            # 兼容旧格式
                            bounds_rect = region_info
                            excess_memory_mb = 0.0

                        x1, y1, x2, y2 = bounds_rect
                        # 绘制蓝色矩形框
                        draw.rectangle([x1, y1, x2, y2], outline='blue', width=3)
                        # 在区域左上角绘制编号和超出大小
                        text = f'M{i} {excess_memory_mb:.2f}M'
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        text_x = x1 + 5
                        text_y = y1 + 5
                        draw.rectangle(
                            [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2], fill='white'
                        )
                        draw.text((text_x, text_y), text, fill='blue', font=font)
                else:
                    # 未发现超尺寸图片，在图片中央绘制提示
                    text = 'No Oversized Image Found'
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    img_width, img_height = img.size
                    text_x = (img_width - text_width) // 2
                    text_y = (img_height - text_height) // 2
                    # 绘制白色背景
                    padding = 10
                    draw.rectangle(
                        [
                            text_x - padding,
                            text_y - padding,
                            text_x + text_width + padding,
                            text_y + text_height + padding,
                        ],
                        fill='white',
                    )
                    draw.text((text_x, text_y), text, fill='gray', font=font)

                # 保存标记后的图像
                output_path = os.path.join(output_dir, f'{file_name}_2.png')
                img.save(output_path)
                marked_paths.append(output_path)
                self.logger.info(f'已保存标记后的图像2: {output_path}')

            return marked_paths

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

        # 获取超出尺寸内存统计（单位M）
        start_excess_memory_mb = start_result.get('image_size_analysis', {}).get('total_excess_memory_mb', 0.0)
        end_excess_memory_mb = end_result.get('image_size_analysis', {}).get('total_excess_memory_mb', 0.0)

        return {
            'total_animations': start_image_count + end_image_count,
            'start_phase_animations': start_image_count,
            'end_phase_animations': end_image_count,
            'start_phase_tree_changes': start_tree_count,
            'end_phase_tree_changes': end_tree_count,
            'has_animations': (start_image_count + end_image_count) > 0,
            'start_phase_excess_memory_mb': start_excess_memory_mb,
            'end_phase_excess_memory_mb': end_excess_memory_mb,
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

        # 调用基类的 write_report 方法（保存ui_animate.json）
        super().write_report(result)

        # 额外保存UI原始数据（用于对比）
        self._save_ui_raw_data()

    def _save_ui_raw_data(self):
        """保存UI原始数据用于前端对比"""
        ui_dir = os.path.join(self.scene_dir, 'ui')
        if not os.path.exists(ui_dir):
            return

        raw_data = {}
        for step_dir in sorted(glob.glob(os.path.join(ui_dir, 'step*'))):
            step_name = os.path.basename(step_dir)

            step_data = {
                'screenshots': {'start': [], 'end': []},
                'trees': {'start': [], 'end': []},
            }

            # 保存所有截图
            for phase in ['start', 'end']:
                screenshots = sorted(glob.glob(os.path.join(step_dir, f'screenshot_{phase}_*.png')))
                for screenshot in screenshots:
                    with open(screenshot, 'rb') as f:
                        img_data = f.read()
                        step_data['screenshots'][phase].append(base64.b64encode(img_data).decode('ascii'))

            # 保存所有组件树（只保存文本，前端不需要解析）
            for phase in ['start', 'end']:
                trees = sorted(glob.glob(os.path.join(step_dir, f'element_tree_{phase}_*.txt')))
                for tree in trees:
                    with open(tree, encoding='utf-8') as f:
                        step_data['trees'][phase].append(f.read())

            if (
                step_data['screenshots']['start']
                or step_data['screenshots']['end']
                or step_data['trees']['start']
                or step_data['trees']['end']
            ):
                raw_data[step_name] = step_data

        if raw_data:
            report_dir = os.path.join(self.scene_dir, 'report')
            os.makedirs(report_dir, exist_ok=True)
            output_path = os.path.join(report_dir, 'ui_raw.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, ensure_ascii=False)
            self.logger.info(f'UI原始数据已保存: {output_path}')
