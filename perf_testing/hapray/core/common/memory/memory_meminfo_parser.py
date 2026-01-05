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

import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryMeminfoParser:
    """一级内存数据解析器

    解析 meminfo 目录下的文件，按照时间戳统计：
    - smaps 内存（按 .hap、dev、.so 分类，其中 .so 按 Category 分类）
    - gpu 内存（应用进程申请的 gpu 内存）
    - dma 内存（应用进程 dma 按照 buf_type 分别统计，特别关注 pixelmap）
    """

    def __init__(self, app_pids: list[int], app_process_name: Optional[str] = None):
        """初始化解析器

        Args:
            app_pids: 应用进程 ID 列表
            app_process_name: 应用进程名称（可选，用于过滤 dma 数据）
        """
        self.app_pids = app_pids
        self.app_process_name = app_process_name

    def parse_meminfo_directory(self, meminfo_dir: str) -> list[dict[str, Any]]:
        """解析 meminfo 目录下的所有文件

        Args:
            meminfo_dir: meminfo 目录路径

        Returns:
            按时间戳排序的统计结果列表，每个元素包含：
            {
                'timestamp': str,  # 时间戳字符串 (YYYYMMDD-HHMMSS)
                'timestamp_epoch': int,  # 时间戳的 epoch 秒数
                'gpu': int,  # GPU 内存大小（字节）
                ...  # 所有 smaps Category 分类（如 '.hap', 'dev', '.so', 'AnonPage other', 'FilePage other', '.ttf' 等）
                ...  # 所有 dma buf_type 分类（如 'dma_pixelmap', 'dma_NULL', 'dma_hw-video-decoder' 等）
            }
        """
        if not os.path.exists(meminfo_dir):
            logger.warning('Meminfo directory does not exist: %s', meminfo_dir)
            return []

        # 收集所有时间戳
        timestamps = set()

        # 解析 smaps 文件
        smaps_data = self._parse_smaps_files(meminfo_dir, timestamps)

        # 解析 gpu 文件
        gpu_data = self._parse_gpu_files(meminfo_dir, timestamps)

        # 解析 dma 文件
        dma_data = self._parse_dma_files(meminfo_dir, timestamps)

        # 合并所有时间戳的数据
        results = []
        for timestamp in sorted(timestamps):
            timestamp_epoch = self._parse_timestamp_to_epoch(timestamp)
            smaps = smaps_data.get(timestamp, {})
            dma = dma_data.get(timestamp, {})

            # 构建结果字典
            result = {
                'timestamp': timestamp,
                'timestamp_epoch': timestamp_epoch,
                'gpu': gpu_data.get(timestamp, 0),
            }
            # 添加所有 smaps 分类
            result.update(smaps)
            # 添加所有 dma 分类
            result.update(dma)

            results.append(result)

        return results

    def _parse_smaps_files(self, meminfo_dir: str, timestamps: set) -> dict[str, dict[str, int]]:
        """解析 smaps 文件

        Args:
            meminfo_dir: meminfo 目录路径
            timestamps: 用于收集时间戳的集合

        Returns:
            按时间戳索引的字典，值为按 Category 分类的字典（key 为 Category 值，value 为内存大小）
        """
        smaps_dir = os.path.join(meminfo_dir, 'dynamic_showmap')
        if not os.path.exists(smaps_dir):
            logger.warning('Smaps directory does not exist: %s', smaps_dir)
            return {}

        results = defaultdict(lambda: defaultdict(int))

        for filename in os.listdir(smaps_dir):
            if not filename.endswith('.txt'):
                continue

            timestamp = self._extract_timestamp_from_filename(filename)
            if not timestamp:
                logger.warning('Failed to extract timestamp from filename: %s', filename)
                continue

            timestamps.add(timestamp)
            filepath = os.path.join(smaps_dir, filename)

            try:
                with open(filepath, encoding='utf-8') as f:
                    content = f.read()

                # 解析 smaps 文件内容
                category_stats = self._parse_smaps_content(content)
                # 当 key 存在时把内存相加
                for key, value in category_stats.items():
                    results[timestamp][key] += value

            except Exception as e:
                logger.warning('Failed to parse smaps file %s: %s', filepath, str(e))

        return dict(results)

    def _parse_smaps_content(self, content: str) -> dict[str, int]:
        """解析 smaps 文件内容

        Args:
            content: 文件内容

        Returns:
            按 Category 分类的字典，key 为 Category 值，value 为内存大小（字节）
        """
        stats = defaultdict(int)

        # 按照 \n 或 \r\n 分隔行
        lines = re.split(r'\r?\n', content)

        # 查找表头行，确定 Size、Pss、SwapPss、Category 和 Name 的列索引
        size_idx = -1
        pss_idx = -1
        swappss_idx = -1
        category_idx = -1
        name_idx = -1
        header_line_idx = -1

        for idx, raw_line in enumerate(lines):
            line = raw_line.strip()
            if not line:
                continue

            # 查找包含 Size 和 Category 的表头行
            if 'Size' in line and 'Category' in line:
                header_line_idx = idx
                # 按照2个以上空格分隔表头
                header_parts = re.split(r'\s{2,}', line)
                try:
                    size_idx = header_parts.index('Size')
                    pss_idx = header_parts.index('Pss')
                    swappss_idx = header_parts.index('SwapPss')
                    category_idx = header_parts.index('Category')
                    name_idx = header_parts.index('Name') if 'Name' in header_parts else -1
                except ValueError:
                    logger.warning('Failed to find required columns (Size, Pss, SwapPss, Category) in header')
                    return {}
                break

        if size_idx < 0 or pss_idx < 0 or swappss_idx < 0 or category_idx < 0:
            logger.warning('Failed to find required columns (Size, Pss, SwapPss, Category) in header')
            return {}

        # 解析数据行（从表头行之后开始）
        for raw_line in lines[header_line_idx + 1 :]:
            line = raw_line.strip()
            if not line or 'Summary' in line:
                continue

            # 按照2个以上空格分隔每行，避免把类型名存在空格的单词切分
            parts = re.split(r'\s{2,}', line)

            # 检查是否有足够的列
            max_idx = max(size_idx, pss_idx, swappss_idx, category_idx)
            if len(parts) <= max_idx:
                continue

            try:
                # 读取 Pss、SwapPss 列（KB），计算三列的和
                pss_kb = int(parts[pss_idx]) if pss_idx < len(parts) else 0
                swappss_kb = int(parts[swappss_idx]) if swappss_idx < len(parts) else 0
                total_kb = pss_kb + swappss_kb
                size_bytes = total_kb * 1024

                # 读取 Category 列
                category = parts[category_idx] if category_idx < len(parts) else ''

                # 读取 Name 列（用于分类的细分）
                name = ''
                if name_idx >= 0 and name_idx < len(parts):
                    name = parts[name_idx]

                # 对 AnonPage other 进行细分
                if category == 'AnonPage other':
                    category = self._categorize_anonpage_other(name)

                # 对 FilePage other 进行细分
                if category == 'FilePage other':
                    category = self._categorize_filepage_other(name)

                # 收集所有分类
                if category:
                    stats[category] += size_bytes

            except (ValueError, IndexError) as e:
                logger.debug('Failed to parse smaps line: %s, error: %s', line, str(e))
                continue

        return dict(stats)

    def _categorize_anonpage_other(self, name: str) -> str:
        """对 AnonPage other 进行分类

        Args:
            name: Name 列的值

        Returns:
            细分后的分类名称：
            - AnonPage other(ArkTS): name 包含 anon:ArkTS
            - AnonPage other(special): name 包含特殊标记
            - AnonPage other(normal): 其他情况
        """
        if not name:
            return 'AnonPage other(normal)'

        # 检查是否是 ArkTS
        if '[anon:ArkTS' in name:
            return 'AnonPage other(ArkTS)'

        # 检查是否是特殊类型
        # 先检查具体的模式（包含冒号的）
        specific_patterns = [
            '[anon:absl]',
            '[anon:async_stack_table]',
            '[anon:cfi_shadow:musl]',
            '[anon:kotlin_native_heap_]',
            '[anon:partition_alloc]',
            '[anon]',
            '[shmm]',
        ]

        for pattern in specific_patterns:
            if pattern in name:
                return 'AnonPage other(special)'

        # 其他情况
        return 'AnonPage other(normal)'

    def _categorize_filepage_other(self, name: str) -> str:
        """对 FilePage other 进行分类

        Args:
            name: Name 列的值

        Returns:
            细分后的分类名称：
            - FilePage other(ashmem): name 包含 ashmem
            - FilePage other(normal): 其他情况
        """
        if not name:
            return 'FilePage other(normal)'

        # 检查是否包含 ashmem
        if 'ashmem' in name:
            return 'FilePage other(ashmem)'

        # 其他情况
        return 'FilePage other(normal)'

    def _parse_gpu_files(self, meminfo_dir: str, timestamps: set) -> dict[str, int]:
        """解析 gpu 内存文件

        Args:
            meminfo_dir: meminfo 目录路径
            timestamps: 用于收集时间戳的集合

        Returns:
            按时间戳索引的字典，值为 GPU 内存大小（字节）
        """
        gpu_dir = os.path.join(meminfo_dir, 'dynamic_gpuMem')
        if not os.path.exists(gpu_dir):
            logger.warning('GPU memory directory does not exist: %s', gpu_dir)
            return {}

        results = {}

        for filename in os.listdir(gpu_dir):
            if not filename.endswith('.txt'):
                continue

            timestamp = self._extract_timestamp_from_filename(filename)
            if not timestamp:
                logger.warning('Failed to extract timestamp from filename: %s', filename)
                continue

            timestamps.add(timestamp)
            filepath = os.path.join(gpu_dir, filename)

            try:
                with open(filepath, encoding='utf-8') as f:
                    content = f.read()

                # 解析 gpu 文件内容，统计应用进程的 GPU 内存
                gpu_size = self._parse_gpu_content(content)
                results[timestamp] = gpu_size

            except Exception as e:
                logger.warning('Failed to parse gpu file %s: %s', filepath, str(e))

        return results

    def _parse_gpu_content(self, content: str) -> int:
        """解析 gpu 文件内容，统计应用进程的 GPU 内存

        Args:
            content: 文件内容

        Returns:
            GPU 内存大小（字节）
        """
        total_bytes = 0
        lines = content.split('\n')

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # 解析 kctx 行
            # 格式：kctx-0x00000007c1cf4000      30789      30432       1550       1616
            # 列说明：第1列=kctx地址，第2列=某个值，第3列=PID，第4列=GPU值(KB)，第5列=其他值
            parts = line.split()
            if len(parts) >= 4:
                try:
                    # 第3列（索引2）是PID
                    pid = int(parts[2])
                    # 只统计应用进程的GPU内存
                    if pid not in self.app_pids:
                        continue
                    # 第4列（索引3）是GPU值（KB）
                    gpu_kb = int(parts[3])
                    total_bytes += gpu_kb * 4 * 1024
                except (ValueError, IndexError):
                    continue

        return total_bytes

    def _parse_dma_files(self, meminfo_dir: str, timestamps: set) -> dict[str, dict[str, int]]:
        """解析 dma 内存文件

        Args:
            meminfo_dir: meminfo 目录路径
            timestamps: 用于收集时间戳的集合

        Returns:
            按时间戳索引的字典，值为按 buf_type 分类的字典（key 为 'dma_' + buf_type，value 为内存大小）
        """
        dma_dir = os.path.join(meminfo_dir, 'dynamic_process_dmabuff_info')
        if not os.path.exists(dma_dir):
            logger.warning('DMA memory directory does not exist: %s', dma_dir)
            return {}

        results = defaultdict(lambda: defaultdict(int))

        for filename in os.listdir(dma_dir):
            if not filename.endswith('.txt'):
                continue

            timestamp = self._extract_timestamp_from_filename(filename)
            if not timestamp:
                logger.warning('Failed to extract timestamp from filename: %s', filename)
                continue

            timestamps.add(timestamp)
            filepath = os.path.join(dma_dir, filename)

            try:
                with open(filepath, encoding='utf-8') as f:
                    content = f.read()

                # 解析 dma 文件内容，按 buf_type 分类统计
                buf_type_stats = self._parse_dma_content(content)
                results[timestamp] = buf_type_stats

            except Exception as e:
                logger.warning('Failed to parse dma file %s: %s', filepath, str(e))

        return dict(results)

    def _parse_dma_content(self, content: str) -> dict[str, int]:
        """解析 dma 文件内容，按 buf_type 分类统计

        Args:
            content: 文件内容

        Returns:
            按 buf_type 分类的字典，key 为 'dma_' + buf_type，value 为内存大小（字节）
        """
        stats = defaultdict(int)
        lines = content.split('\n')

        # 找到表头行（跳过第一行 "Dma-buf objects usage of processes:"）
        header_line_idx = -1
        for idx, line in enumerate(lines):
            if 'buf_type' in line and 'size_bytes' in line:
                header_line_idx = idx
                break

        if header_line_idx < 0:
            logger.warning('Failed to find header line in dma file')
            return stats

        # 解析表头，确定列索引
        header_parts = lines[header_line_idx].split()
        try:
            size_idx = header_parts.index('size_bytes')
            buf_type_idx = header_parts.index('buf_type')
            process_idx = header_parts.index('Process') if 'Process' in header_parts else -1
            pid_idx = header_parts.index('pid') if 'pid' in header_parts else -1
        except ValueError:
            logger.warning('Failed to find required columns in dma file header')
            return stats

        # 解析数据行
        for raw_line in lines[header_line_idx + 1 :]:
            line = raw_line.strip()
            if not line:
                continue

            # 跳过总计行
            if line.startswith('Total dmabuf size'):
                continue

            parts = line.split()
            if len(parts) <= max(size_idx, buf_type_idx):
                continue

            # 检查是否是应用进程
            is_app_process = False
            # 优先通过 pid 判断（更准确）
            if pid_idx >= 0 and pid_idx < len(parts) and self.app_pids:
                try:
                    pid = int(parts[pid_idx])
                    if pid in self.app_pids:
                        is_app_process = True
                except (ValueError, IndexError):
                    pass
            # 如果没有 pid 或 pid 匹配失败，尝试通过进程名判断
            if not is_app_process and process_idx >= 0 and process_idx < len(parts) and self.app_process_name:
                process_name = parts[process_idx]
                if process_name == self.app_process_name:
                    is_app_process = True

            if not is_app_process:
                continue

            try:
                size_bytes = int(parts[size_idx])
                buf_type = parts[buf_type_idx] if buf_type_idx < len(parts) and parts[buf_type_idx] else 'NULL'
                # 如果 buf_type 为空字符串，也使用 'NULL'
                if not buf_type or buf_type.strip() == '':
                    buf_type = 'NULL'

                # 按 buf_type 分类统计，所有类型都统计（包括 NULL）
                # buf_type 可能是 'pixelmap', 'NULL', 'hw-video-decoder' 等
                # 使用 'dma_' 前缀作为 key
                key = f'dma_{buf_type}'
                stats[key] += size_bytes

            except (ValueError, IndexError) as e:
                logger.debug('Failed to parse dma line: %s, error: %s', line, str(e))
                continue

        return dict(stats)

    def _extract_timestamp_from_filename(self, filename: str) -> Optional[str]:
        """从文件名中提取时间戳

        文件名格式示例：
        - gpuMen_20251211-165643_PerfLoad_ImageKnifeDefault.txt
        - process_dmabuff_info_20251211-165643_PerfLoad_ImageKnifeDefault.txt
        - arkanalyzer.hapray.agent_6763_20251211-165643_PerfLoad_ImageKnifeDefault.txt

        Args:
            filename: 文件名

        Returns:
            时间戳字符串 (YYYYMMDD-HHMMSS)，如果提取失败返回 None
        """
        # 匹配 YYYYMMDD-HHMMSS 格式
        pattern = r'(\d{8}-\d{6})'
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
        return None

    def _parse_timestamp_to_epoch(self, timestamp: str) -> int:
        """将时间戳字符串转换为 epoch 秒数

        Args:
            timestamp: 时间戳字符串 (YYYYMMDD-HHMMSS)

        Returns:
            epoch 秒数
        """
        try:
            dt = datetime.strptime(timestamp, '%Y%m%d-%H%M%S')
            return int(dt.timestamp())
        except ValueError:
            logger.warning('Failed to parse timestamp: %s', timestamp)
            return 0
