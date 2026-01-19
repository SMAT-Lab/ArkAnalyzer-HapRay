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

from typing import Any

from .arkui_tree_parser import parse_arkui_tree


def analyze_image_sizes(tree_dict: dict[str, Any]) -> dict[str, Any]:
    """
    分析Image节点的图像尺寸（使用RenderedImageInfo的Width和Height）和FrameRect尺寸，统计超出情况

    Args:
        tree_dict: 解析后的组件树字典

    Returns:
        包含统计信息的字典
    """
    results = {
        'total_images': 0,
        'images_exceeding_framerect': [],
        'total_excess_memory_bytes': 0,
        'total_excess_memory_mb': 0.0,
    }

    def traverse_component(component: dict[str, Any], path: str = ''):
        """递归遍历组件树"""
        if not component:
            return

        comp_name = component.get('name', 'Unknown')
        current_path = f'{path}/{comp_name}' if path else comp_name

        # 检查是否是Image组件
        if comp_name == 'Image':
            results['total_images'] += 1
            attrs = component.get('attributes', {})

            # 获取renderedImageSize（从RenderedImageInfo的Width和Height）
            rendered_image_size = attrs.get('renderedImageSize')
            rendered_image_info_str = attrs.get('renderedImageInfoStr', '')

            # 获取FrameRect尺寸
            frame_width = attrs.get('width')
            frame_height = attrs.get('height')
            frame_rect_str = attrs.get('frameRect', '')

            if rendered_image_size and frame_width is not None and frame_height is not None:
                image_width, image_height = rendered_image_size

                # 计算面积
                frame_area = frame_width * frame_height
                image_area = image_width * image_height

                # 估算内存占用（假设RGBA格式，每像素4字节）
                # 实际内存 = 图像尺寸面积 * 4字节
                image_memory_bytes = image_area * 4
                frame_memory_bytes = frame_area * 4
                excess_memory_bytes = image_memory_bytes - frame_memory_bytes

                # 检查图像尺寸是否大于FrameRect，且超出内存大于200KB
                threshold_bytes = 200 * 1024  # 200KB
                if (image_width > frame_width or image_height > frame_height) and excess_memory_bytes > threshold_bytes:
                    # 计算超出部分
                    excess_width = max(0, image_width - frame_width)
                    excess_height = max(0, image_height - frame_height)

                    # 计算超出面积（简化计算：超出部分的矩形面积）
                    # 实际超出可能是部分重叠，这里用简化方法
                    excess_area = image_area - frame_area
                    # 计算超出比例（百分数，保留1位小数）
                    excess_ratio = round(((image_area / frame_area) * 100) if frame_area > 0 else 0, 1)

                    image_info = {
                        'path': current_path,
                        'id': attrs.get('id', ''),
                        'bounds_rect': attrs.get('bounds_rect', ''),
                        'frameRect': {
                            'width': frame_width,
                            'height': frame_height,
                            'area': frame_area,
                            'str': frame_rect_str,
                        },
                        'renderedImageSize': {
                            'width': image_width,
                            'height': image_height,
                            'area': image_area,
                            'str': rendered_image_info_str,
                        },
                        'excess': {
                            'width': excess_width,
                            'height': excess_height,
                            'area': excess_area,
                            'ratio': excess_ratio,
                        },
                        'memory': {
                            'raw_memory_bytes': image_memory_bytes,
                            'raw_memory_mb': round(image_memory_bytes / (1024 * 1024), 2),
                            'frame_memory_bytes': frame_memory_bytes,
                            'frame_memory_mb': round(frame_memory_bytes / (1024 * 1024), 2),
                            'excess_memory_bytes': excess_memory_bytes,
                            'excess_memory_mb': round(excess_memory_bytes / (1024 * 1024), 2),
                        },
                    }

                    results['images_exceeding_framerect'].append(image_info)
                    results['total_excess_memory_bytes'] += excess_memory_bytes

        # 递归处理子组件
        for child in component.get('children', []):
            traverse_component(child, current_path)

    traverse_component(tree_dict)

    # 按超出内存大小降序排序
    results['images_exceeding_framerect'].sort(key=lambda x: x['memory']['excess_memory_bytes'], reverse=True)

    # 重新计算总超出内存
    results['total_excess_memory_mb'] = round(results['total_excess_memory_bytes'] / (1024 * 1024), 2)

    return results


def analyze_image_sizes_from_file(file_path: str) -> dict[str, Any]:
    """
    从文件解析并分析Image节点尺寸

    Args:
        file_path: element_tree文件路径

    Returns:
        包含统计信息的字典
    """
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    tree_dict = parse_arkui_tree(content)
    return analyze_image_sizes(tree_dict)
