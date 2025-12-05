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
from typing import Any, Optional


class ArkUIComponent:
    def __init__(self):
        self.depth = None
        self.name = None
        self.children = []
        self.attributes = {}
        self.decorators = []

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'depth': self.depth,
            'children': [child.to_dict() for child in self.children],
            'attributes': self.attributes,
            'decorators': self.decorators,
        }


class ArkUITreeParser:
    def __init__(self):
        self.current_depth = 0
        self.root = None
        self.current_component = None
        self.component_stack = []

    def parse_component_tree(self, content: str) -> ArkUIComponent:
        lines = content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()  # 只去除右侧空白，保留左侧缩进
            if not line:
                i += 1
                continue

            # 检测组件行 - 支持缩进格式
            if '|->' in line:
                component = self._parse_component_line(line)
                if component:
                    # 处理组件层级关系
                    self._handle_component_hierarchy(component)

                    # 解析该组件的后续属性行
                    i = self._parse_component_attributes(lines, i + 1, component)
                else:
                    i += 1
            else:
                i += 1

        return self.root

    def _parse_component_line(self, line: str) -> Optional[ArkUIComponent]:
        # 提取缩进级别和组件信息
        # 匹配模式：任意数量的空格 + |-> + 组件名 + childSize信息
        match = re.match(r'(\s*)\|->\s*(\w+)\s*childSize:(\d+)', line)
        if not match:
            # 尝试匹配没有childSize的组件行
            match = re.match(r'(\s*)\|->\s*(\w+)', line)
            if not match:
                return None

        indent = match.group(1)
        component_name = match.group(2)

        # 计算深度级别 (每2个空格为一级)
        # 根节点深度为1，子节点每缩进2个空格深度增加1
        depth_level = len(indent) // 2 + 1

        # 创建新组件
        component = ArkUIComponent()
        component.name = component_name
        component.depth = depth_level
        component.attributes['type'] = component_name

        return component

    def _parse_component_attributes(self, lines: list[str], start_index: int, component: ArkUIComponent) -> int:
        """解析组件的属性行，直到遇到下一个组件或结束"""
        i = start_index
        while i < len(lines):
            line = lines[i].rstrip()
            if not line:
                i += 1
                continue

            # 如果遇到下一个组件行，停止解析
            if '|->' in line:
                break

            # 检查是否是特殊块开始
            if '------------start print' in line:
                # 特殊处理rsNode块
                if 'rsNode' in line:
                    i = self._parse_rs_node_block(lines, i, component)
                    continue
                # 跳过其他特殊块
                i = self._skip_special_block(lines, i)
                continue

            # 检测装饰器信息块开始
            if '-----start print decoratorInfo' in line:
                i = self._parse_decorator_block(lines, i, component)
                continue

            # 解析属性行 - 现在支持没有竖线的属性行
            if self._is_attribute_line(line):
                self._parse_attribute_line(line, component)

            i += 1

        # 组件属性解析完成后，生成 bounds_rect（若可计算）
        self._finalize_component(component)

        return i

    def _finalize_component(self, component: ArkUIComponent):
        """在组件所有属性解析完毕后生成派生属性，如 bounds_rect"""
        attrs = component.attributes or {}
        try:
            left = attrs.get('left')
            top = attrs.get('top')
            width = attrs.get('width')
            height = attrs.get('height')
            # 仅当四个字段都存在且为数字时生成
            if all(v is not None for v in [left, top, width, height]):
                # 宽高可能是浮点，保证为整数
                left = int(float(left))
                top = int(float(top))
                width = int(float(width))
                height = int(float(height))
                attrs['bounds_rect'] = (left, top, left + width, top + height)
                component.attributes = attrs
        except Exception:
            # 静默失败，不影响整体解析
            pass

    def _is_attribute_line(self, line: str) -> bool:
        """判断是否为属性行"""
        # 包含冒号的行可能是属性行
        if ':' in line:
            # 排除一些特殊行
            return not any(
                marker in line
                for marker in [
                    '|->',
                    '------------start print',
                    '------------end print',
                    '-----start print',
                    '-----end print',
                ]
            )
        return False

    def _skip_special_block(self, lines: list[str], start_index: int) -> int:
        """跳过特殊块（如dragInfo等）"""
        i = start_index
        block_start = lines[i]

        # 提取块类型
        block_type = 'unknown'
        if 'dragInfo' in block_start:
            block_type = 'dragInfo'

        # 寻找块结束
        i += 1
        while i < len(lines):
            line = lines[i].rstrip()

            # 检查是否到达块结束
            if '------------end print' in line and block_type in line:
                return i  # 返回结束行索引

            # 如果遇到下一个组件，提前结束
            if '|->' in line:
                return i - 1

            i += 1

        return i

    def _parse_rs_node_block(self, lines: list[str], start_index: int, component: ArkUIComponent) -> int:
        """解析rsNode信息块"""
        i = start_index + 1  # 跳过开始行

        if i < len(lines):
            line = lines[i].rstrip()
            # 清理行格式 - 去除可能的竖线和多余空格
            clean_line = line.strip().lstrip('|').strip()

            # 将整行内容作为rsNode的值
            component.attributes['rsNode'] = clean_line

        return i + 1

    def _handle_component_hierarchy(self, component: ArkUIComponent):
        # 如果是根组件
        if self.root is None:
            self.root = component
            self.current_component = component
            self.component_stack = [component]
            return

        # 弹出栈直到找到父组件
        while self.component_stack and self.component_stack[-1].depth >= component.depth:
            self.component_stack.pop()

        if self.component_stack:
            # 添加到父组件的子节点
            parent = self.component_stack[-1]
            parent.children.append(component)

        # 将当前组件压入栈
        self.component_stack.append(component)
        self.current_component = component

    def _parse_attribute_line(self, line: str, component: ArkUIComponent):
        # 清理行格式 - 去除可能的竖线和多余空格
        clean_line = line.strip().lstrip('|').strip()

        # 跳过空行
        if not clean_line:
            return

        # 特殊处理 top 和 left 属性
        if 'top:' in clean_line and 'left:' in clean_line:
            self._parse_top_left_attributes(clean_line, component)
            return

        # 提取键值对
        if ':' in clean_line:
            # 分割键值，但注意有些值中可能包含冒号
            parts = clean_line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()

                # 直接使用解析出来的属性值，不进行硬编码处理
                self._set_component_attribute(component, key, value)

    def _set_component_attribute(self, component: ArkUIComponent, key: str, value: str):
        """设置组件属性，直接使用解析出来的属性值"""
        # 尝试将值转换为适当类型
        processed_value = self._process_attribute_value(value)

        # 将key的首字母转换为小写
        key = key[0].lower() + key[1:] if key else key

        # 设置组件属性
        if key == 'iD':
            component.attributes['id'] = processed_value
        elif key == 'time':
            # skip time property
            pass
        elif key == 'frameRect':
            # 特殊处理FrameRect属性，解析为bounds坐标元组
            bounds_tuple = self._parse_framerect_to_size(value)
            if bounds_tuple:
                component.attributes['width'] = bounds_tuple[0]
                component.attributes['height'] = bounds_tuple[1]
                component.attributes['frameRect'] = processed_value  # 保留原始值
            else:
                component.attributes['frameRect'] = processed_value
        elif key == 'renderedImageInfo':
            # 特殊处理RenderedImageInfo属性，解析Width和Height
            size_tuple = self._parse_rendered_image_info_to_size(value)
            if size_tuple:
                component.attributes['renderedImageSize'] = size_tuple
                component.attributes['renderedImageInfoStr'] = processed_value  # 保留原始值
            else:
                component.attributes['renderedImageSize'] = None
                component.attributes['renderedImageInfoStr'] = processed_value
        elif key == 'rawImageSize':
            # 特殊处理rawImageSize属性，解析为(width, height)元组
            size_tuple = self._parse_rawimagesize_to_size(value)
            if size_tuple:
                component.attributes['rawImageSize'] = size_tuple
                component.attributes['rawImageSizeStr'] = processed_value  # 保留原始值
            else:
                component.attributes['rawImageSize'] = None
                component.attributes['rawImageSizeStr'] = processed_value
        else:
            # 存储其他属性
            component.attributes[key] = processed_value

    def _process_attribute_value(self, value: str) -> Any:
        """处理属性值，尝试转换为适当类型"""
        # 去除可能的引号
        value = value.strip('"')

        # 尝试转换为整数
        if re.match(r'^-?\d+$', value):
            try:
                return int(value)
            except ValueError:
                pass

        # 尝试转换为浮点数
        if re.match(r'^-?\d+\.\d+$', value):
            try:
                return float(value)
            except ValueError:
                pass

        # 尝试转换为布尔值
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'

        # 保持原样
        return value

    def _parse_framerect_to_size(self, framerect_value: str) -> Optional[tuple[int, int]]:
        """解析FrameRect属性值为bounds坐标元组

        Args:
            framerect_value: FrameRect属性值，格式如 "RectT (100.00, 200.00) - [200.00 x 200.00]"

        Returns:
            size (width, height) 或 None
        """
        try:
            # 去除可能的引号和空格
            framerect_value = framerect_value.strip().strip('"')

            # 匹配FrameRect格式: RectT (x, y) - [width x height]
            # 支持整数和小数
            pattern = r'RectT\s*\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)\s*-\s*\[\s*([\d.-]+)\s*x\s*([\d.-]+)\s*\]'
            match = re.match(pattern, framerect_value)

            if match:
                width = float(match.group(3))
                height = float(match.group(4))

                # 转换为整数坐标
                return int(width), int(height)

        except Exception:
            # 解析失败时记录警告但不抛出异常
            pass

        return None

    def _parse_rendered_image_info_to_size(self, rendered_image_info_value: str) -> Optional[tuple[int, int]]:
        """解析RenderedImageInfo属性值为尺寸元组

        Args:
            rendered_image_info_value: RenderedImageInfo属性值，格式如 "{RenderStatus: Success, Width: 540, Height: 960, ...}"

        Returns:
            size (width, height) 或 None
        """
        try:
            # 去除可能的引号和空格
            rendered_image_info_value = rendered_image_info_value.strip().strip('"')

            # 匹配RenderedImageInfo格式: {RenderStatus: Success, Width: 540, Height: 960, ...}
            # 提取Width和Height字段
            width_match = re.search(r'Width:\s*(\d+)', rendered_image_info_value)
            height_match = re.search(r'Height:\s*(\d+)', rendered_image_info_value)

            if width_match and height_match:
                width = int(width_match.group(1))
                height = int(height_match.group(1))
                return width, height

        except Exception:
            # 解析失败时记录警告但不抛出异常
            pass

        return None

    def _parse_rawimagesize_to_size(self, rawimagesize_value: str) -> Optional[tuple[int, int]]:
        """解析rawImageSize属性值为尺寸元组

        Args:
            rawimagesize_value: rawImageSize属性值，格式如 "[642.00 x 360.00]"

        Returns:
            size (width, height) 或 None
        """
        try:
            # 去除可能的引号和空格
            rawimagesize_value = rawimagesize_value.strip().strip('"')

            # 匹配rawImageSize格式: [width x height]
            # 支持整数和小数
            pattern = r'\[\s*([\d.-]+)\s*x\s*([\d.-]+)\s*\]'
            match = re.match(pattern, rawimagesize_value)

            if match:
                width = float(match.group(1))
                height = float(match.group(2))

                # 转换为整数尺寸
                return int(width), int(height)

        except Exception:
            # 解析失败时记录警告但不抛出异常
            pass

        return None

    def _parse_top_left_attributes(self, line: str, component: ArkUIComponent):
        """特殊处理 top 和 left 属性"""
        # 使用正则表达式提取 top 和 left 的值
        top_match = re.search(r'top:\s*([\d.-]+)', line)
        left_match = re.search(r'left:\s*([\d.-]+)', line)

        if top_match:
            component.attributes['top'] = int(float(top_match.group(1)))

        if left_match:
            component.attributes['left'] = int(float(left_match.group(1)))

    def _parse_decorator_block(self, lines: list[str], start_index: int, component: ArkUIComponent) -> int:
        """解析装饰器信息块"""
        i = start_index + 1  # 跳过开始行

        current_decorator = None

        while i < len(lines):
            line = lines[i].rstrip()

            # 检查是否到达装饰器块结束
            if '-----end print decoratorInfo' in line:
                return i  # 返回结束行索引

            # 检查是否到达装饰器分隔线
            if '------------------------------' in line:
                # 如果当前有装饰器，保存它
                if current_decorator:
                    component.decorators.append(current_decorator)
                    current_decorator = None
                i += 1
                continue

            # 解析装饰器行
            if 'decorator:' in line:
                # 如果当前有装饰器，先保存它
                if current_decorator:
                    component.decorators.append(current_decorator)

                # 创建新装饰器
                current_decorator = self._parse_decorator_line(line)

            # 解析装饰器的其他属性
            elif current_decorator:
                if 'state Variable id:' in line:
                    match = re.search(r'state Variable id:\s*([^\s]+)', line)
                    if match:
                        current_decorator['state_variable_id'] = match.group(1)
                elif 'inRenderingElementId:' in line:
                    match = re.search(r'inRenderingElementId:\s*([^\s]+)', line)
                    if match:
                        current_decorator['in_rendering_element_id'] = match.group(1)
                elif 'dependentElementIds:' in line:
                    # 提取完整的JSON对象
                    match = re.search(r'dependentElementIds:\s*({.*})', line)
                    if match:
                        current_decorator['dependent_element_ids'] = match.group(1)

            i += 1

        # 保存最后一个装饰器
        if current_decorator:
            component.decorators.append(current_decorator)

        return i

    def _parse_decorator_line(self, line: str) -> dict[str, Any]:
        """解析单个装饰器行"""
        decorator = {}

        # 匹配装饰器格式
        decorator_match = re.search(r'decorator:"([^"]+)"\s+propertyName:"([^"]+)"\s+value:([^$]+)', line)
        if decorator_match:
            decorator_type = decorator_match.group(1)
            property_name = decorator_match.group(2)
            value = decorator_match.group(3).strip()

            decorator['type'] = decorator_type
            decorator['property'] = property_name
            decorator['value'] = value

        return decorator


class ArkUITreeComparator:
    def __init__(self):
        self.differences = []

    def compare_trees(self, tree1: dict[str, Any], tree2: dict[str, Any]) -> list[dict[str, Any]]:
        """
        比较两个ARK UI组件树，找出attributes存在差异的组件节点

        Args:
            tree1: 第一个组件树
            tree2: 第二个组件树

        Returns:
            包含差异信息的列表
        """
        self.differences = []
        self._compare_components(tree1, tree2, '')
        return self.differences

    def _compare_components(self, comp1: dict[str, Any], comp2: dict[str, Any], path: str):
        """
        递归比较两个组件及其子组件

        Args:
            comp1: 第一个组件
            comp2: 第二个组件
            path: 当前组件路径
        """
        if not comp1 or not comp2:
            return

        # 构建当前组件路径
        comp_name = comp1.get('name', comp1.get('type', 'Unknown'))
        current_path = f'{path}/{comp_name}' if path else comp_name

        # 比较当前组件的attributes
        attrs_diff = self._compare_attributes(comp1, comp2)
        if attrs_diff:
            self.differences.append(
                {
                    'component': {
                        'type': comp_name,
                        'bounds_rect': comp1.get('attributes', {}).get('bounds_rect', ''),
                        'path': current_path,
                        'attributes': comp1.get('attributes', {}),
                        'id': comp1.get('attributes', {}).get('id', ''),
                    },
                    'is_animation': True,
                    'comparison_result': attrs_diff,
                    'animate_type': 'attribute_animate',
                }
            )

        # 递归比较子组件
        children1 = comp1.get('children', [])
        children2 = comp2.get('children', [])

        # 按照相同索引位置比较子组件（假设结构相同）
        min_children = min(len(children1), len(children2))
        for i in range(min_children):
            self._compare_components(children1[i], children2[i], current_path)

        # 处理多余的子组件（如果结构不同）
        if len(children1) > len(children2):
            for i in range(len(children2), len(children1)):
                comp = children1[i]
                comp_name = comp.get('name', comp.get('type', 'Unknown'))
                self.differences.append(
                    {
                        'component': {
                            'type': comp_name,
                            'bounds_rect': comp.get('attributes', {}).get('bounds_rect', ''),
                            'path': f'{current_path}/{comp_name}',
                            'attributes': comp.get('attributes', {}),
                            'id': comp.get('attributes', {}).get('id', ''),
                        },
                        'is_animation': True,
                        'comparison_result': attrs_diff,
                        'animate_type': 'attribute_animate',
                    }
                )

        elif len(children2) > len(children1):
            for i in range(len(children1), len(children2)):
                comp = children2[i]
                comp_name = comp.get('name', comp.get('type', 'Unknown'))
                self.differences.append(
                    {
                        'component': {
                            'type': comp_name,
                            'bounds_rect': comp.get('attributes', {}).get('bounds_rect', ''),
                            'path': f'{current_path}/{comp_name}',
                            'attributes': comp.get('attributes', {}),
                            'id': comp.get('attributes', {}).get('id', ''),
                        },
                        'is_animation': True,
                        'comparison_result': attrs_diff,
                        'animate_type': 'attribute_animate',
                    }
                )

    def _compare_attributes(self, comp1: dict[str, Any], comp2: dict[str, Any]) -> list[dict[str, Any]]:
        """
        比较两个组件的attributes差异

        Args:
            comp1: 第一个组件
            comp2: 第二个组件

        Returns:
            attributes差异列表
        """
        differences = []

        attrs1 = comp1.get('attributes', {})
        attrs2 = comp2.get('attributes', {})

        # 获取所有attributes键
        all_keys = set(attrs1.keys()) | set(attrs2.keys())

        for key in all_keys:
            value1 = attrs1.get(key)
            value2 = attrs2.get(key)

            # 检查是否存在差异
            if value1 != value2:
                differences.append({'attribute': key, 'value1': value1, 'value2': value2})

        return differences


def compare_arkui_trees(tree1: dict[str, Any], tree2: dict[str, Any]) -> list[dict[str, Any]]:
    """
    比较两个ARK UI组件树，返回attributes存在差异的组件节点

    Args:
        tree1: 第一个组件树
        tree2: 第二个组件树

    Returns:
        包含差异信息的列表
    """
    comparator = ArkUITreeComparator()
    return comparator.compare_trees(tree1, tree2)


def parse_arkui_tree(file_content: str) -> dict[str, Any]:
    """
    解析鸿蒙ARK UI组件树

    Args:
        file_content: hidumper导出的组件树文本内容

    Returns:
        解析后的组件树字典
    """
    parser = ArkUITreeParser()
    root_component = parser.parse_component_tree(file_content)

    if root_component:
        return root_component.to_dict()
    return {}
