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

线程分析工具：pattern 归一化、样本收集、内存估算等。
供 thread_analyzer 与 thread_optimization 使用。
"""

import re
from collections import defaultdict
from typing import Any


def pattern_key(thread_name: str) -> str:
    """同名 pattern：仅去掉尾部 _数字，同一队列/池下的多 worker 合并为一个 pattern。"""
    if not thread_name:
        return thread_name or 'Unknown'
    s = thread_name.strip()
    m = re.match(r'^(.+)_(\d+)$', s)
    return m.group(1) if m else s


def should_ignore_system_pattern(pattern_key_str: str) -> bool:
    """OS_ 前缀为鸿蒙系统/运行时线程，冗余检测中忽略。"""
    if not pattern_key_str:
        return False
    return pattern_key_str.strip().startswith('OS_')


def collect_callchain_sample(
    thread_list: list[dict], max_entries: int = 10, user_space_only: bool = True
) -> list[dict[str, Any]]:
    """从线程列表中收集 callchain 的 symbol/file_path 样本，按出现频率降序。

    Args:
        thread_list: 线程列表（含 wakeup_threads[].callchains）。
        max_entries: 返回条数上限（按出现次数取前 N）。
        user_space_only: 为 True（默认）时仅统计 file_path 含 `/proc/` 的用户态帧，
            面向开发者展示应用层 so/库；为 False 时纳入系统库（如 /system/lib）、
            内核（[kernel.kallsyms]）等全部帧，便于排查系统调用或内核态问题。
    """
    count_map: dict[tuple, int] = defaultdict(int)
    for thread in thread_list:
        for wt in thread.get('wakeup_threads', []):
            for callchain in wt.get('callchains', []):
                if not isinstance(callchain, dict):
                    continue
                for func in callchain.get('functions', []):
                    name = func.get('name') or func.get('symbol') or ''
                    path = func.get('file_path') or ''
                    key = (str(name).strip(), str(path).strip())
                    if not key[0] and not key[1]:
                        continue
                    if user_space_only and '/proc/' not in path:
                        continue
                    count_map[key] += 1
    sorted_items = sorted(count_map.items(), key=lambda x: -x[1])[:max_entries]
    return [{'symbol': name[:200], 'file_path': path[:300], 'count': cnt} for (name, path), cnt in sorted_items]


def count_callchain_frames(thread_list: list[dict]) -> tuple:
    """按 pattern 汇总：callchain 帧总数、sample 数（=调用链条数）。"""
    total_frames = 0
    total_callchains = 0
    for thread in thread_list:
        for wt in thread.get('wakeup_threads', []):
            for callchain in wt.get('callchains', []):
                if not isinstance(callchain, dict):
                    continue
                total_callchains += 1
                for _func in callchain.get('functions', []):
                    total_frames += 1
    return total_frames, total_callchains


def calculate_thread_memory_estimate(thread_count: int, avg_stack_size: int = 1024 * 1024) -> int:
    """估算线程内存占用（保守估计）。"""
    per_thread_memory = avg_stack_size + 8 * 1024 + 16 * 1024
    return thread_count * per_thread_memory


def num(x: Any, default: int = 0) -> int:
    """安全转 int，用于从 dict 取数值。"""
    try:
        return int(x) if x is not None else default
    except (TypeError, ValueError):
        return default
