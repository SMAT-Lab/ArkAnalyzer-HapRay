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

import json
import re
import subprocess
import sys
from typing import Any, Optional

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

                # 检查图像尺寸是否大于FrameRect
                if image_width > frame_width or image_height > frame_height:
                    # 计算超出部分
                    excess_width = max(0, image_width - frame_width)
                    excess_height = max(0, image_height - frame_height)

                    # 计算超出面积（简化计算：超出部分的矩形面积）
                    # 实际超出可能是部分重叠，这里用简化方法
                    excess_area = image_area - frame_area

                    # 估算内存占用（假设RGBA格式，每像素4字节）
                    # 实际内存 = 图像尺寸面积 * 4字节
                    image_memory_bytes = image_area * 4
                    frame_memory_bytes = frame_area * 4
                    excess_memory_bytes = excess_area * 4

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

    # 过滤：仅保留超出内存大于0.1MB的Image节点
    threshold_bytes = 0.1 * 1024 * 1024  # 0.1MB = 104857.6 字节
    filtered_images = [
        img for img in results['images_exceeding_framerect'] if img['memory']['excess_memory_bytes'] > threshold_bytes
    ]

    # 重新计算总超出内存（仅统计过滤后的）
    results['images_exceeding_framerect'] = filtered_images
    results['total_excess_memory_bytes'] = sum(img['memory']['excess_memory_bytes'] for img in filtered_images)
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


def print_analysis_report(results: dict[str, Any]):
    """打印分析报告"""
    print('=' * 80)
    print('Image节点RenderedImageInfo与FrameRect尺寸分析报告')
    print('=' * 80)
    print()

    print(f'总Image节点数: {results["total_images"]}')
    print(f'图像尺寸 > FrameRect的Image节点数: {len(results["images_exceeding_framerect"])}')
    print()

    if results['images_exceeding_framerect']:
        print('=' * 80)
        print('超出FrameRect的Image节点详情:')
        print('=' * 80)
        print()

        # 按超出内存排序
        sorted_images = sorted(
            results['images_exceeding_framerect'], key=lambda x: x['memory']['excess_memory_bytes'], reverse=True
        )

        for idx, img in enumerate(sorted_images, 1):
            print(f'[{idx}] 路径: {img["path"]}')
            print(f'    ID: {img["id"]}')
            print(
                f'    FrameRect: {img["frameRect"]["width"]} x {img["frameRect"]["height"]} '
                f'(面积: {img["frameRect"]["area"]})'
            )
            print(
                f'    RenderedImageInfo: {img["renderedImageSize"]["width"]} x {img["renderedImageSize"]["height"]} '
                f'(面积: {img["renderedImageSize"]["area"]})'
            )
            print(
                f'    超出: {img["excess"]["width"]} x {img["excess"]["height"]} '
                f'(面积: {img["excess"]["area"]:.2f}, 比例: {img["excess"]["ratio"]:.1f}%)'
            )
            print('    内存占用:')
            print(f'      - RenderedImageInfo内存: {img["memory"]["raw_memory_mb"]:.2f} MB')
            print(f'      - FrameRect内存: {img["memory"]["frame_memory_mb"]:.2f} MB')
            print(f'      - 超出内存: {img["memory"]["excess_memory_mb"]:.2f} MB')
            print()

        print('=' * 80)
        print('统计汇总:')
        print('=' * 80)
        print(f'总超出内存: {results["total_excess_memory_mb"]:.2f} MB ({results["total_excess_memory_bytes"]:,} 字节)')
    else:
        print('未发现图像尺寸 > FrameRect的Image节点')


def get_focus_window_id() -> Optional[str]:
    """
    从hidumper命令输出中解析Focus window id

    Returns:
        Focus window id字符串，如果解析失败返回None
    """
    try:
        # 执行hidumper命令获取Focus window信息
        # 使用列表形式避免shell转义问题
        cmd = ['hdc', 'shell', 'hidumper -s WindowManagerService -a "-a"']
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding='utf-8', timeout=30)

        if result.returncode != 0:
            print(f'执行hidumper命令失败: {result.stderr}')
            return None

        output = result.stdout
        print(f'hidumper命令输出: {output}')

        # 解析Focus window id
        # 查找 "Focus window: " 后面的数字
        match = re.search(r'Focus window:\s*(\d+)', output)
        if match:
            focus_window_id = match.group(1)
            print(f'解析到Focus window id: {focus_window_id}')
            return focus_window_id
        print('无法从hidumper输出中解析Focus window id')
        return None

    except subprocess.TimeoutExpired:
        print('获取Focus window id超时')
        return None
    except Exception as e:
        print(f'获取Focus window id时发生错误: {e}')
        return None


def execute_hidumper_dump(window_id: str) -> Optional[str]:
    """
    执行hidumper dump命令并返回组件树内容

    Args:
        window_id: Focus window id

    Returns:
        组件树内容字符串，如果执行失败返回None
    """
    try:
        # 执行hidumper dump命令
        # 使用列表形式避免shell转义问题
        dump_cmd = ['hdc', 'shell', f'hidumper -s WindowManagerService -a "-w {window_id} -default"']
        cmd_str = ' '.join(dump_cmd)
        print(f'执行hidumper dump命令: {cmd_str}')

        result = subprocess.run(dump_cmd, check=False, capture_output=True, text=True, encoding='utf-8', timeout=60)

        if result.returncode != 0:
            print(f'执行hidumper dump命令失败: {result.stderr}')
            return None

        output = result.stdout
        print(f'hidumper dump执行成功，输出长度: {len(output)} 字符')
        return output

    except subprocess.TimeoutExpired:
        print('执行hidumper dump超时')
        return None
    except Exception as e:
        print(f'执行hidumper dump时发生错误: {e}')
        return None


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='分析Image节点的RenderedImageInfo与FrameRect尺寸',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从文件分析
  python image_size_analyzer.py element_tree.txt output.json

  # 从设备导出并分析（自动获取window_id）
  python image_size_analyzer.py --dump output.json

  # 从设备导出并分析（指定window_id）
  python image_size_analyzer.py --dump --window-id 12345 output.json
        """,
    )

    parser.add_argument('input_file', nargs='?', help='element_tree文件路径（如果使用--dump则不需要）')
    parser.add_argument('output_file', nargs='?', help='输出JSON报告文件路径（可选）')
    parser.add_argument('--dump', action='store_true', help='从设备执行hidumper命令导出组件树')
    parser.add_argument('--window-id', type=str, help='指定window_id（如果不指定，将自动获取Focus window id）')

    args = parser.parse_args()

    # 确定输入内容来源
    if args.dump:
        # 从设备导出
        window_id = args.window_id
        if not window_id:
            print('正在获取Focus window id...')
            window_id = get_focus_window_id()
            if not window_id:
                print('错误: 无法获取window_id，请使用--window-id手动指定')
                sys.exit(1)

        print(f'使用window_id: {window_id}')
        print('正在执行hidumper dump...')
        content = execute_hidumper_dump(window_id)
        if not content:
            print('错误: 无法导出组件树')
            sys.exit(1)

        with open('element_tree.txt', 'w', encoding='utf-8') as f:
            f.write(content)

        # 解析并分析
        tree_dict = parse_arkui_tree(content)
        results = analyze_image_sizes(tree_dict)
    else:
        # 从文件读取
        if not args.input_file:
            parser.print_help()
            sys.exit(1)

        file_path = args.input_file
        results = analyze_image_sizes_from_file(file_path)

    # 打印报告
    print_analysis_report(results)

    # 保存JSON报告
    if args.output_file:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f'\n详细报告已保存到: {args.output_file}')
