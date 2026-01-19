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
            return None

        except Exception as e:
            self.logger.error(f'UI动画分析失败: {str(e)}')
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
            if element_tree_path:
                if not os.path.isabs(element_tree_path):
                    element_tree_path = os.path.join(ui_dir, os.path.basename(element_tree_path))

                if not os.path.exists(element_tree_path):
                    return None

            # 分析组件树（包括CanvasNode统计等）
            tree_analysis = self._analyze_tree_from_file(element_tree_path)
            if tree_analysis:
                canvas_node_count = tree_analysis.get('canvas_node_count', 0)
                result['canvasNodeCnt'] = canvas_node_count

            # 进行图片尺寸分析
            image_size_result = self._analyze_image_sizes(ui_dir, element_tree_path, page_info.get('screenshot'))
            if image_size_result:
                result['image_size_analysis'] = image_size_result

            if page_info.get('element_tree_2') and page_info.get('screenshot_2'):
                # 解析inspector文件，获取可能的动画组件
                animation_components = self._parse_animation_components(page_info.get('inspector'))

                # 图像差异分析
                image_animation_result = self._analyze_image_differences(
                    page_info.get('screenshot'), page_info.get('screenshot_2'), animation_components
                )

                # Element树差异分析
                tree_animation_result = self._analyze_tree_differences(
                    element_tree_path, page_info.get('element_tree_2')
                )

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

                # 5. 生成标记的截图
                marked_image = self._generate_marked_images(ui_dir, page_info.get('screenshot'), 'animation', regions)
                if not regions:
                    result['animations'] = {
                        'image_animations': image_animation_result,
                        'tree_animations': tree_animation_result,
                        'marked_image': marked_image,
                    }

            return result

        except Exception as e:
            self.logger.error(f'分析页面失败 (索引: {page_idx}): {str(e)}')
            return None

    def _parse_animation_components(self, inspector_file: str) -> list[dict[str, Any]]:
        """解析inspector文件中的可能的动画组件

        Args:
            inspector_file: inspector文件路径

        Returns:
            动画组件列表
        """

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

            self.logger.info(f'在{inspector_file}找到{len(animation_components)}个XCompose组件')
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
        self, screenshot1_path: str, screenshot2_path: str, xcompose_components: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """分析图像差异

        Args:
            screenshot1_path: 第一个截图路径
            screenshot2_path: 第二个截图路径
            xcompose_components: XCompose组件列表

        Returns:
            图像差异分析结果
        """

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

    def _analyze_tree_differences(self, tree1_path: str, tree2_path: str) -> dict[str, Any]:
        """分析Element树差异

        Args:
            tree1_path: 第一个组件树文件路径
            tree2_path: 第二个组件树文件路径

        Returns:
            树差异分析结果
        """
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

    def _analyze_image_sizes(self, ui_dir: str, tree_path: str, screenshot_path: str) -> dict[str, Any]:
        """分析超出尺寸的Image节点

        Args:
            ui_dir: UI数据目录
            tree_path: 组件树文件路径
            screenshot_path: 截图文件路径

        Returns:
            Image尺寸分析结果
        """
        if not tree_path:
            return {'error': 'Element树文件路径为空'}

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
                    f'在{tree_path}阶段找到{len(result.get("images_exceeding_framerect", []))}个超出尺寸的Image节点'
                )
                regions = []
                for image_info in result.get('images_exceeding_framerect', []):
                    bounds_rect = image_info.get('bounds_rect')
                    if bounds_rect:
                        excess_memory_mb = image_info.get('memory', {}).get('excess_memory_mb', 0.0)
                        regions.append(
                            {
                                'type': 'exceeding_image',
                                'bounds_rect': bounds_rect,
                                'excess_memory_mb': excess_memory_mb,
                            }
                        )

                marked_image = self._generate_marked_images(ui_dir, screenshot_path, 'exceeding_image', regions)
                if marked_image:
                    result['marked_image'] = marked_image

                return result
            return {'error': '无法解析Element树'}

        except Exception as e:
            self.logger.error(f'分析Image尺寸失败: {str(e)}')
            return {'error': str(e)}

    def _generate_marked_images(
        self, ui_dir: str, image_path: str, region_type: str, regions: list[dict[str, Any]]
    ) -> Optional[str]:
        """生成标记了动画区域（红色）和超出尺寸Image（蓝色）的截图

        Args:
            ui_dir: UI数据目录
            image_path: 截图路径
            region_type: 区域类型 ('animation' 或 'exceeding_image')
            regions: 区域列表，每个元素为 {'type': str, 'bounds_rect': tuple, ...}

        Returns:
            base64编码的标记图像字符串
        """
        try:
            if not regions or not image_path or not os.path.exists(image_path):
                return None

            output_dir = os.path.join(ui_dir, 'marked_images')
            os.makedirs(output_dir, exist_ok=True)

            img = Image.open(image_path)
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

            # 根据区域类型标记不同的区域
            if regions:
                if region_type == 'animation':
                    # 标记动画区域（红色）
                    for i, region_info in enumerate(regions, 1):
                        # 从字典中提取 bounds_rect
                        bounds_rect = region_info.get('bounds_rect') if isinstance(region_info, dict) else region_info

                        if not bounds_rect or not isinstance(bounds_rect, (list, tuple)) or len(bounds_rect) < 4:
                            continue

                        x1, y1, x2, y2 = bounds_rect[:4]
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

                elif region_type == 'exceeding_image':
                    # 标记超出尺寸Image区域（蓝色）
                    for i, region_info in enumerate(regions, 1):
                        bounds_rect = region_info.get('bounds_rect') if isinstance(region_info, dict) else region_info
                        excess_memory_mb = (
                            region_info.get('excess_memory_mb', 0.0) if isinstance(region_info, dict) else 0.0
                        )

                        if not bounds_rect or not isinstance(bounds_rect, (list, tuple)) or len(bounds_rect) < 4:
                            continue

                        x1, y1, x2, y2 = bounds_rect[:4]
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
                # 未发现区域，在图片中央绘制提示
                text = f'No {region_type.replace("_", " ").title()} Found'
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
            marked_image_path = os.path.join(output_dir, f'marked_merged_{region_type}_{os.path.basename(image_path)}')
            img.save(marked_image_path)

            self.logger.info(f'已保存标记后的图像: {marked_image_path}')
            return self._image_to_base64(marked_image_path)

        except Exception as e:
            self.logger.error(f'生成标记图像失败: {str(e)}')
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
