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

from typing import Optional

from .callchain_filter_config import CallchainFilterConfig


class CallchainRefiner:
    """调用链精化器

    通过callchain_id查询调用链，从depth=0开始向上查找，
    排除系统符号和系统so文件，找到第一个有效的文件和符号
    """

    def __init__(self, filter_config: Optional[CallchainFilterConfig] = None):
        """初始化调用链精化器

        Args:
            filter_config: 过滤配置，如果为None则使用默认配置
        """
        self.filter_config = filter_config or CallchainFilterConfig()

    def refine_callchain(
        self,
        callchain_frames: list[dict],
        data_dict: dict[int, str],
    ) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
        """精化调用链，找到第一个有效的文件和符号

        Args:
            callchain_frames: 调用链帧列表，应按depth排序
            data_dict: 数据字典，用于查询符号和文件名

        Returns:
            元组 (refined_lib_id, refined_symbol_id, refined_lib_path, refined_symbol_name)
            如果找不到有效的帧，返回 (None, None, None, None)
        """
        if not callchain_frames:
            return None, None, None, None

        # 按depth排序（从大到小）
        sorted_frames = sorted(callchain_frames, key=lambda f: f.get('depth', 0), reverse=True)

        # 记录最后一个有效的帧（用于所有帧都被排除的情况）
        last_valid_frame = None

        for frame in sorted_frames:
            symbol_id = frame.get('symbol_id')
            file_id = frame.get('file_id')

            # 获取符号和文件名
            symbol_name = data_dict.get(symbol_id, 'unknown') if symbol_id else None
            lib_path = data_dict.get(file_id, 'unknown') if file_id else None

            # 如果file是空的，跳过当前帧
            if not lib_path or lib_path == 'unknown':
                continue

            # 记录最后一个有效的帧（file不为空）
            last_valid_frame = (file_id, symbol_id, lib_path, symbol_name)

            # 检查是否应该排除（file和symbol作为整体判断）
            if self.filter_config.should_exclude(symbol_name, lib_path):
                continue

            # 找到第一个有效的帧（file不为空且未被排除）
            return file_id, symbol_id, lib_path, symbol_name

        # 如果所有帧都被排除，返回最后一个有效的帧（depth最小的，即最接近depth=0的）
        # 这是为了确保即使过滤后没有匹配，也能生成hapray_report.db文件
        if last_valid_frame:
            return last_valid_frame

        # 如果没有有效的帧，返回None
        return None, None, None, None

    def refine_callchain_with_comparison(
        self,
        callchain_frames: list[dict],
        data_dict: dict[int, str],
        original_lib_id: Optional[int],
        original_symbol_id: Optional[int],
    ) -> dict:
        """精化调用链并返回对比信息

        Args:
            callchain_frames: 调用链帧列表
            data_dict: 数据字典
            original_lib_id: 原始的lib_id
            original_symbol_id: 原始的symbol_id

        Returns:
            包含原始值和精化值的字典
        """
        refined_lib_id, refined_symbol_id, refined_lib_path, refined_symbol_name = self.refine_callchain(
            callchain_frames, data_dict
        )

        original_lib_path = data_dict.get(original_lib_id, 'unknown') if original_lib_id else None
        original_symbol_name = data_dict.get(original_symbol_id, 'unknown') if original_symbol_id else None

        return {
            'original': {
                'lib_id': original_lib_id,
                'symbol_id': original_symbol_id,
                'lib_path': original_lib_path,
                'symbol_name': original_symbol_name,
            },
            'refined': {
                'lib_id': refined_lib_id,
                'symbol_id': refined_symbol_id,
                'lib_path': refined_lib_path,
                'symbol_name': refined_symbol_name,
            },
            'is_different': (original_lib_id != refined_lib_id) or (original_symbol_id != refined_symbol_id),
        }

