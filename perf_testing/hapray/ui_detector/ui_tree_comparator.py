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
from typing import Any

from PIL import Image, ImageDraw

from hapray.ui_detector.arkui_tree_parser import compare_arkui_trees, parse_arkui_tree


class UITreeComparator:
    """UI组件树对比工具"""

    # 默认忽略的属性（系统内部状态，不影响UI）
    DEFAULT_IGNORE_ATTRS = {
        'id',
        'accessibilityId',  # 系统自动生成的ID
        'rsNode',
        'frameProxy',
        'frameRecord',  # 渲染引擎内部状态
        'contentConstraint',
        'parentLayoutConstraint',
        'user defined constraint',  # 布局约束
    }

    def compare_ui_trees(
        self,
        tree1_path: str,
        screenshot1_path: str,
        tree2_path: str,
        screenshot2_path: str,
        output_dir: str,
        ignore_attrs: set = None,
        filter_minor_changes: bool = False,
    ) -> dict[str, Any]:
        """对比两个UI组件树并标记差异

        Args:
            tree1_path: 组件树1文件路径
            screenshot1_path: 截图1文件路径
            tree2_path: 组件树2文件路径
            screenshot2_path: 截图2文件路径
            output_dir: 输出目录
            ignore_attrs: 要忽略的属性集合（默认使用DEFAULT_IGNORE_ATTRS）
            filter_minor_changes: 是否过滤微小变化（如<5px的位置差异）

        Returns:
            包含差异信息和输出文件路径的字典
        """
        # 使用默认忽略属性
        if ignore_attrs is None:
            ignore_attrs = self.DEFAULT_IGNORE_ATTRS

        # 读取并解析组件树
        with open(tree1_path, encoding='utf-8') as f:
            tree1 = parse_arkui_tree(f.read())
        with open(tree2_path, encoding='utf-8') as f:
            tree2 = parse_arkui_tree(f.read())

        # 对比组件树
        all_differences = compare_arkui_trees(tree1, tree2)

        # 过滤差异
        differences = self._filter_differences(all_differences, ignore_attrs, filter_minor_changes)

        # 提取差异区域的bounds
        diff_regions = self._extract_diff_regions(differences)

        # 生成标记后的对比图
        os.makedirs(output_dir, exist_ok=True)
        marked_img1 = os.path.join(output_dir, 'diff_marked_1.png')
        marked_img2 = os.path.join(output_dir, 'diff_marked_2.png')

        self._mark_differences(screenshot1_path, diff_regions, marked_img1)
        self._mark_differences(screenshot2_path, diff_regions, marked_img2)

        return {
            'differences': differences,
            'diff_count': len(differences),
            'diff_regions': diff_regions,
            'marked_images': [marked_img1, marked_img2],
            'total_differences': len(all_differences),
            'filtered_count': len(all_differences) - len(differences),
        }

    def _filter_differences(
        self, differences: list[dict[str, Any]], ignore_attrs: set, filter_minor: bool
    ) -> list[dict[str, Any]]:
        """过滤差异"""
        filtered = []
        for diff in differences:
            # 过滤属性差异
            filtered_attrs = []
            for attr_diff in diff.get('comparison_result', []):
                attr_name = attr_diff.get('attribute', '')

                # 跳过忽略的属性
                if attr_name in ignore_attrs:
                    continue

                # 过滤微小变化
                if filter_minor and self._is_minor_change(attr_name, attr_diff):
                    continue

                filtered_attrs.append(attr_diff)

            # 如果还有差异，保留该组件
            if filtered_attrs:
                diff_copy = diff.copy()
                diff_copy['comparison_result'] = filtered_attrs
                filtered.append(diff_copy)

        return filtered

    def _is_minor_change(self, attr_name: str, attr_diff: dict) -> bool:
        """判断是否为微小变化"""
        # 位置和尺寸的微小变化（<5px）
        if attr_name in ['top', 'left', 'width', 'height']:
            try:
                v1 = float(attr_diff.get('value1', 0))
                v2 = float(attr_diff.get('value2', 0))
                return abs(v1 - v2) < 5
            except (ValueError, TypeError):
                return False
        return False

    def _extract_diff_regions(self, differences: list[dict[str, Any]]) -> list[tuple[int, int, int, int]]:
        """从差异列表中提取bounds区域"""
        regions = []
        for diff in differences:
            component = diff.get('component', {})
            bounds_rect = component.get('bounds_rect')
            if bounds_rect and len(bounds_rect) == 4:
                x1, y1, x2, y2 = bounds_rect
                # 确保坐标有效（x2 >= x1, y2 >= y1）
                if x2 >= x1 and y2 >= y1:
                    regions.append((x1, y1, x2, y2))
        return regions

    def _mark_differences(self, screenshot_path: str, regions: list[tuple], output_path: str):
        """在截图上标记差异区域"""
        if not os.path.exists(screenshot_path):
            return

        img = Image.open(screenshot_path).convert('RGB')
        draw = ImageDraw.Draw(img)

        for i, region in enumerate(regions, 1):
            if len(region) != 4:
                continue
            x1, y1, x2, y2 = region
            # 再次验证坐标有效性
            if x2 >= x1 and y2 >= y1:
                draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
                draw.text((x1 + 5, y1 + 5), f'D{i}', fill='red')

        img.save(output_path)
