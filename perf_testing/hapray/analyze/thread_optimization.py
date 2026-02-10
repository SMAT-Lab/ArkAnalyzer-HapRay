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

"""
冗余线程与优化机会分析。算法说明见 ALGORITHM.md。
"""

import sys
from collections import defaultdict
from typing import Dict, List, Any

from hapray.core.common.thread_utils import (
    pattern_key,
    should_ignore_system_pattern,
    collect_callchain_sample,
    count_callchain_frames,
    calculate_thread_memory_estimate,
    num,
)


def per_thread_redundancy_score(thread: Dict[str, Any]) -> int:
    """单线程冗余分数 0-100。做工线程自然得低分，只有真正冗余的线程才得高分。"""
    score = 0
    wts = thread.get('wakeup_threads', [])
    if not wts:
        score += 15
        return min(100, score)
    first = wts[0]
    thread_states = first.get('thread_states', [])
    wakeup_depth = first.get('wakeup_depth', -1)
    wakeup_count = 0
    total_dur = sum(num(s.get('dur', 0)) for s in thread_states) if thread_states else 0
    wait_dur = sum(num(s.get('dur', 0)) for s in thread_states if s.get('state', '') in ['S', 'D', 'T']) if thread_states else 0
    waiting_ratio = wait_dur / total_dur if total_dur > 0 else 0.0
    if waiting_ratio > 0.95:
        score += 30
    elif waiting_ratio > 0.85:
        score += 20
    elif waiting_ratio > 0.75:
        score += 10
    inst = num(thread.get('total_instructions', 0))
    if inst == 0:
        score += 15
    elif inst < 1000:
        score += 5
    # 不再按「无 callchain」加分：callchain 可能因采样缺失而为空
    has_yield = False
    for wt in wts:
        for callchain in wt.get('callchains', []):
            if not callchain:
                continue
            if isinstance(callchain, dict):
                for func in callchain.get('functions', []):
                    raw_name = func.get('name') or func.get('symbol', '') or ''
                    raw_path = func.get('file_path', '') or ''
                    s = (str(raw_name) + ' ' + str(raw_path)).lower()
                    if any(k in s for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                        has_yield = True
                        break
            else:
                if any(k in str(callchain).lower() for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                    has_yield = True
            if has_yield:
                break
        if has_yield:
            break
    if has_yield:
        score += 15   # 忙等类（含 yield/ITT）收益大，单线程上给予更高权重
    if not thread_states:
        return min(100, score)
    states = sorted(thread_states, key=lambda x: num(x.get('ts', 0)))
    running_duration = sum(num(s.get('dur', 0)) for s in states if s.get('state') == 'Running')
    for s in states:
        if s.get('state') == 'R':
            wakeup_count += 1
    ti = thread.get('thread_info', {})
    start_ts, end_ts = ti.get('start_ts'), ti.get('end_ts')
    lifetime = (num(end_ts) - num(start_ts)) if (start_ts is not None and end_ts is not None) else total_dur
    if lifetime > 0 and running_duration == 0:
        score += 15
    if wakeup_depth == 0:
        score += 10
    if wakeup_depth == 0 and wakeup_count == 0:
        score += 15
    short_cycles = 0
    for i, s in enumerate(states):
        if s.get('state') != 'Running' or num(s.get('dur', 0)) >= 1_000_000:
            continue
        prev = states[i - 1].get('state', '') if i > 0 else ''
        nxt = states[i + 1].get('state', '') if i < len(states) - 1 else ''
        if prev == 'R' and nxt in ['S', 'D', 'T']:
            short_cycles += 1
        elif prev == 'Running' and nxt == 'Running':
            short_cycles += 1
    if wakeup_count >= 3 and short_cycles / max(wakeup_count, 1) > 0.5:
        score += 10
    if lifetime > 0 and running_duration >= 0:
        run_ratio = running_duration / lifetime
        if inst > 10000 and run_ratio < 0.05 and short_cycles >= 5:
            score += 22   # 强忙等：高指令低运行，收益大，提高分数
        elif inst > 5000 and run_ratio < 0.1 and short_cycles >= 3:
            score += 16
        elif inst > 2000 and run_ratio < 0.15 and short_cycles >= 2:
            score += 12
    return min(100, score)


def thread_redundancy_features(thread: Dict[str, Any]) -> Dict[str, Any]:
    """提取单线程用于冗余打分的特征，供 below_threshold_patterns 的特征汇总使用。"""
    out = {
        'waiting_ratio': 0.0, 'total_instructions': 0, 'has_callchain': False,
        'has_yield': False, 'short_cycles': 0, 'run_ratio': 0.0,
        'wakeup_depth': -1, 'wakeup_count': 0,
    }
    wts = thread.get('wakeup_threads', [])
    if not wts:
        return out
    first = wts[0]
    thread_states = first.get('thread_states', [])
    out['wakeup_depth'] = first.get('wakeup_depth', -1)
    total_dur = sum(num(s.get('dur', 0)) for s in thread_states) if thread_states else 0
    wait_dur = sum(num(s.get('dur', 0)) for s in thread_states if s.get('state', '') in ['S', 'D', 'T']) if thread_states else 0
    out['waiting_ratio'] = wait_dur / total_dur if total_dur > 0 else 0.0
    out['total_instructions'] = num(thread.get('total_instructions', 0))
    out['has_callchain'] = any(wt.get('callchains') for wt in wts)
    for wt in wts:
        for callchain in wt.get('callchains', []):
            if not callchain:
                continue
            if isinstance(callchain, dict):
                for func in callchain.get('functions', []):
                    raw_name = func.get('name') or func.get('symbol', '') or ''
                    raw_path = func.get('file_path', '') or ''
                    s = (str(raw_name) + ' ' + str(raw_path)).lower()
                    if any(k in s for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                        out['has_yield'] = True
                        break
            else:
                if any(k in str(callchain).lower() for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                    out['has_yield'] = True
            if out['has_yield']:
                break
        if out['has_yield']:
            break
    if not thread_states:
        return out
    states = sorted(thread_states, key=lambda x: num(x.get('ts', 0)))
    running_duration = sum(num(s.get('dur', 0)) for s in states if s.get('state') == 'Running')
    for s in states:
        if s.get('state') == 'R':
            out['wakeup_count'] += 1
    ti = thread.get('thread_info', {})
    start_ts, end_ts = ti.get('start_ts'), ti.get('end_ts')
    lifetime = (num(end_ts) - num(start_ts)) if (start_ts is not None and end_ts is not None) else total_dur
    out['run_ratio'] = running_duration / lifetime if lifetime > 0 else 0.0
    short_cycles = 0
    for i, s in enumerate(states):
        if s.get('state') != 'Running' or num(s.get('dur', 0)) >= 1_000_000:
            continue
        prev = states[i - 1].get('state', '') if i > 0 else ''
        nxt = states[i + 1].get('state', '') if i < len(states) - 1 else ''
        if prev == 'R' and nxt in ['S', 'D', 'T']:
            short_cycles += 1
        elif prev == 'Running' and nxt == 'Running':
            short_cycles += 1
    out['short_cycles'] = short_cycles
    return out


def analyze_optimization_opportunities(
    results: List[Dict[str, Any]],
    framework_name: str = '',
    verbose: bool = False,
) -> Dict[str, Any]:
    """分析优化机会（冗余/忙等待等）。算法说明见 ALGORITHM.md。verbose 为 True 时打印分析进度。"""
    analysis = {
        'framework': framework_name,
        'total_threads': len(results),
        'redundant_patterns': [],
        'below_threshold_patterns': [],
        'cpu_optimization_opportunities': [],
        'memory_optimization_opportunities': [],
        'recommendations': []
    }
    min_total_threads = 2
    high_inst_low_work_running_ratio = 0.02
    high_inst_low_work_short_cycles = 10
    busy_wait_min_periods = 20
    busy_wait_short_ratio = 0.9
    high_freq_transitions_per_sec = 2000
    frequent_sleep_wakeup_min = 8
    frequent_sleep_short_cycles_min = 5
    frequent_sleep_ratio = 0.7
    frequent_sleep_alt_periods = 20
    frequent_sleep_alt_cycles = 10

    threads_by_name = defaultdict(list)
    for result in results:
        thread_name = result.get('thread_info', {}).get('thread_name', 'Unknown')
        key = pattern_key(thread_name)
        threads_by_name[key].append(result)

    # 全局总指令：results 中每线程一条，为 perf 按线程汇总的指令数，求和即进程总指令
    total_cpu_instructions = sum(num(r.get('total_instructions', 0)) for r in results)
    redundant_score_threshold = 40
    patterns_to_process = [k for k in threads_by_name if not should_ignore_system_pattern(k)]
    total_patterns = len(patterns_to_process)
    if verbose and total_patterns > 0:
        print(f"  共 {total_patterns} 个 pattern 待分析（已排除 OS_ 系统线程）")
        sys.stdout.flush()
    processed = 0

    for thread_name, thread_list in threads_by_name.items():
        if should_ignore_system_pattern(thread_name):
            continue
        processed += 1
        if verbose and (processed == 1 or processed % 20 == 0 or processed == total_patterns):
            name_display = (thread_name[:36] + '...') if len(thread_name) > 36 else thread_name
            print(f"  进度: pattern {processed}/{total_patterns} — {name_display}")
            sys.stdout.flush()
        total_count = len(thread_list)
        scored = [(per_thread_redundancy_score(t), t) for t in thread_list]
        passed_list = [t for score, t in scored if score >= redundant_score_threshold]
        # 同名 pattern 下指令数最高的那条不计入冗余统计（不进入 redundant_count/ids/instructions），避免误把做工最多的那条算进冗余；该线程本身仍可能冗余，此处仅统计时排除
        if total_count >= 2 and passed_list:
            primary_worker = max(thread_list, key=lambda t: num(t.get('total_instructions', 0)))
            primary_tid = primary_worker.get('thread_id') or primary_worker.get('thread_info', {}).get('tid')
            if primary_tid is not None:
                passed_list = [t for t in passed_list if (t.get('thread_id') or t.get('thread_info', {}).get('tid')) != primary_tid]
            else:
                passed_list = [t for t in passed_list if t is not primary_worker]
        if total_count < min_total_threads:
            if total_count >= 1:
                scores = [s for s, _ in scored]
                feats = [thread_redundancy_features(t) for _, t in scored]
                n = len(feats)
                name_variants = sorted(set(t.get('thread_info', {}).get('thread_name', '') for _, t in scored))
                analysis['below_threshold_patterns'].append({
                    'thread_name': thread_name,
                    'thread_name_variants': name_variants,
                    'total_thread_count': total_count,
                    'redundant_count': len(passed_list),
                    'max_per_thread_score': max(scores),
                    'avg_per_thread_score': round(sum(scores) / len(scores), 1) if scores else 0,
                    'feature_summary': {
                        'avg_waiting_ratio_pct': round(100 * sum(f.get('waiting_ratio', 0) for f in feats) / n, 1) if n else 0,
                        'avg_instructions': round(sum(f.get('total_instructions', 0) for f in feats) / n) if n else 0,
                        'min_instructions': min(f.get('total_instructions', 0) for f in feats) if feats else 0,
                        'max_instructions': max(f.get('total_instructions', 0) for f in feats) if feats else 0,
                        'threads_with_callchain': sum(1 for f in feats if f.get('has_callchain')),
                        'threads_with_yield': sum(1 for f in feats if f.get('has_yield')),
                        'avg_short_cycles': round(sum(f.get('short_cycles', 0) for f in feats) / n, 1) if n else 0,
                        'avg_run_ratio_pct': round(100 * sum(f.get('run_ratio', 0) for f in feats) / n, 1) if n else 0,
                        'threads_wakeup_depth_0': sum(1 for f in feats if f.get('wakeup_depth') == 0),
                    },
                })
            continue
        count = len(passed_list)
        list_for_stats = passed_list if passed_list else thread_list
        n_stats = len(list_for_stats)
        unique_itids = set()
        unique_tids = set()
        for thread in list_for_stats:
            ti = thread.get('thread_info', {})
            if ti.get('itid') is not None:
                unique_itids.add(ti['itid'])
            # wakeup_chain_all_threads 把 TID 放在 result['thread_id']，不在 thread_info 里
            tid_val = thread.get('thread_id') or ti.get('tid')
            if tid_val is not None:
                unique_tids.add(tid_val)
        unique_tid_count = len(unique_tids)
        total_instructions = sum(num(t.get('total_instructions', 0)) for t in list_for_stats)
        avg_instructions = total_instructions // len(list_for_stats) if list_for_stats else 0
        # 按唯一 TID 累加指令，避免同一线程在 passed_list 中多次出现时重复计入（防止 redundant_instructions 偏高）
        seen_tid_for_inst = set()
        redundant_instructions = 0
        for t in passed_list:
            tid_val = t.get('thread_id') or t.get('thread_info', {}).get('tid')
            if tid_val is not None and tid_val not in seen_tid_for_inst:
                seen_tid_for_inst.add(tid_val)
                redundant_instructions += num(t.get('total_instructions', 0))
            elif tid_val is None:
                redundant_instructions += num(t.get('total_instructions', 0))
        estimated_memory = calculate_thread_memory_estimate(unique_tid_count or len(list_for_stats))
        total_waiting_ratio = 0
        threads_with_states = 0
        threads_with_callchains = 0
        threads_with_yield_calls = 0
        total_lifetime = total_running_time = threads_with_lifetime = threads_never_running = 0
        threads_with_zero_wakeup_depth = 0
        threads_frequent_immediate_sleep = threads_never_woken = 0
        total_wakeup_count = total_short_running_cycles = total_short_running_periods = 0
        threads_high_instructions_low_work = threads_busy_waiting_pattern = threads_high_frequency_transitions = 0
        for thread in list_for_stats:
            wts = thread.get('wakeup_threads', [])
            if wts:
                sts = wts[0].get('thread_states', [])
                if sts:
                    total_dur = sum(num(s.get('dur', 0)) for s in sts)
                    wait_dur = sum(num(s.get('dur', 0)) for s in sts if s.get('state', '') in ['S', 'D', 'T'])
                    if total_dur > 0:
                        total_waiting_ratio += wait_dur / total_dur
                        threads_with_states += 1
            has_callchain = has_yield = False
            for wt in thread.get('wakeup_threads', []):
                for callchain in wt.get('callchains', []):
                    if callchain:
                        has_callchain = True
                    if not callchain:
                        continue
                    if isinstance(callchain, dict):
                        for func in callchain.get('functions', []):
                            raw_name = func.get('name') or func.get('symbol', '') or ''
                            raw_path = func.get('file_path', '') or ''
                            s = (str(raw_name) + ' ' + str(raw_path)).lower() if isinstance(func, dict) else str(func).lower()
                            if any(k in s for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                                has_yield = True
                                break
                    else:
                        s = str(callchain).lower()
                        if any(k in s for k in ['yield', 'sched_yield', '__itt_thread_yield', 'itt_thread_yield']):
                            has_yield = True
                    if has_yield:
                        break
                if has_yield:
                    break
            if has_callchain:
                threads_with_callchains += 1
            if has_yield:
                threads_with_yield_calls += 1
            ti = thread.get('thread_info', {})
            start_ts, end_ts = ti.get('start_ts'), ti.get('end_ts')
            if start_ts is not None and end_ts is not None:
                total_lifetime += num(end_ts) - num(start_ts)
                threads_with_lifetime += 1
            if not wts:
                continue
            first = wts[0]
            thread_states = first.get('thread_states', [])
            wakeup_depth = first.get('wakeup_depth', -1)
            if wakeup_depth == 0:
                threads_with_zero_wakeup_depth += 1
            if not thread_states:
                continue
            states = sorted(thread_states, key=lambda x: num(x.get('ts', 0)))
            running_duration = wakeup_count = short_running_cycles = 0
            this_thread_short_periods = 0
            for i, state in enumerate(states):
                name, dur = state.get('state', ''), num(state.get('dur', 0))
                if name == 'Running':
                    running_duration += dur
                    if dur < 1_000_000:
                        total_short_running_periods += 1
                        this_thread_short_periods += 1
                        prev = states[i - 1].get('state', '') if i > 0 else ''
                        nxt = states[i + 1].get('state', '') if i < len(states) - 1 else ''
                        if prev == 'R' and nxt in ['S', 'D', 'T']:
                            short_running_cycles += 1
                        elif prev == 'Running' and nxt == 'S' and i + 3 < len(states):
                            if states[i + 2].get('state') == 'R' and states[i + 3].get('state') == 'Running' and num(states[i + 3].get('dur', 0)) < 1_000_000:
                                short_running_cycles += 1
                        elif prev == 'Running' and nxt == 'Running':
                            short_running_cycles += 1
                elif name == 'R':
                    wakeup_count += 1
            total_running_time += running_duration
            total_wakeup_count += wakeup_count
            total_short_running_cycles += short_running_cycles
            if running_duration == 0:
                threads_never_running += 1
            thread_instructions = num(thread.get('total_instructions', 0))
            thread_lifetime = (num(end_ts) - num(start_ts)) if (start_ts is not None and end_ts is not None) else sum(num(s.get('dur', 0)) for s in thread_states)
            if thread_instructions > 10000 and running_duration > 0 and thread_lifetime > 0:
                if running_duration / thread_lifetime < high_inst_low_work_running_ratio and short_running_cycles >= high_inst_low_work_short_cycles:
                    threads_high_instructions_low_work += 1
            total_running_periods = len([s for s in states if s.get('state') == 'Running'])
            if this_thread_short_periods >= busy_wait_min_periods and total_running_periods > 0:
                if this_thread_short_periods / total_running_periods > busy_wait_short_ratio:
                    threads_busy_waiting_pattern += 1
            if len(states) >= 20 and thread_lifetime > 0:
                rate = len(states) / (thread_lifetime / 1_000_000_000)
                if rate > high_freq_transitions_per_sec:
                    threads_high_frequency_transitions += 1
            if wakeup_count >= frequent_sleep_wakeup_min and short_running_cycles >= frequent_sleep_short_cycles_min:
                if short_running_cycles / max(wakeup_count, 1) > frequent_sleep_ratio:
                    threads_frequent_immediate_sleep += 1
            elif this_thread_short_periods >= frequent_sleep_alt_periods and short_running_cycles >= frequent_sleep_alt_cycles:
                threads_frequent_immediate_sleep += 1
            if wakeup_depth == 0 and wakeup_count == 0:
                threads_never_woken += 1
        avg_waiting_ratio = total_waiting_ratio / threads_with_states if threads_with_states else 0
        callchain_ratio = threads_with_callchains / n_stats if n_stats else 0
        yield_call_ratio = threads_with_yield_calls / n_stats if n_stats else 0
        avg_lifetime = total_lifetime / threads_with_lifetime if threads_with_lifetime else 0
        avg_running_time = total_running_time / n_stats if n_stats else 0
        running_time_ratio = avg_running_time / avg_lifetime if avg_lifetime else 0
        never_running_ratio = threads_never_running / n_stats if n_stats else 0
        zero_wakeup_depth_ratio = threads_with_zero_wakeup_depth / n_stats if n_stats else 0
        frequent_immediate_sleep_ratio = threads_frequent_immediate_sleep / n_stats if n_stats else 0
        never_woken_ratio = threads_never_woken / n_stats if n_stats else 0
        high_instructions_low_work_ratio = threads_high_instructions_low_work / n_stats if n_stats else 0
        busy_waiting_pattern_ratio = threads_busy_waiting_pattern / n_stats if n_stats else 0
        high_frequency_transitions_ratio = threads_high_frequency_transitions / n_stats if n_stats else 0
        redundancy_score = 0
        if unique_tid_count >= 30:
            redundancy_score += 40
        elif unique_tid_count >= 15:
            redundancy_score += 30
        elif unique_tid_count >= 8:
            redundancy_score += 20
        elif unique_tid_count >= 5:
            redundancy_score += 12
        elif unique_tid_count >= 3:
            redundancy_score += 8
        elif unique_tid_count >= 2:
            redundancy_score += 5
        if avg_waiting_ratio > 0.95:
            redundancy_score += 30
        elif avg_waiting_ratio > 0.85:
            redundancy_score += 20
        elif avg_waiting_ratio > 0.75:
            redundancy_score += 10
        # 不再按「无/少 callchain」加分：callchain 可能因采样缺失而为空，不应作为冗余依据
        if avg_instructions == 0:
            redundancy_score += 10
        if zero_wakeup_depth_ratio > 0.5:
            redundancy_score += 10
        if frequent_immediate_sleep_ratio > 0.7:
            redundancy_score += 15
        elif frequent_immediate_sleep_ratio > 0.5:
            redundancy_score += 10
        elif frequent_immediate_sleep_ratio > 0.3:
            redundancy_score += 5
        if busy_waiting_pattern_ratio > 0.8:
            redundancy_score += 10
        elif busy_waiting_pattern_ratio > 0.6:
            redundancy_score += 7
        elif busy_waiting_pattern_ratio > 0.4:
            redundancy_score += 5
        if high_frequency_transitions_ratio > 0.8:
            redundancy_score += 5
        elif high_frequency_transitions_ratio > 0.6:
            redundancy_score += 3
        if yield_call_ratio > 0.5:
            redundancy_score += 15   # 忙等类（yield）收益大，组级加分提高
        elif yield_call_ratio > 0.3:
            redundancy_score += 11
        elif yield_call_ratio > 0.1:
            redundancy_score += 7
        if high_instructions_low_work_ratio > 0.5:
            redundancy_score += 15   # 忙等类（高指令低工作）收益大，组级加分提高
        elif high_instructions_low_work_ratio > 0.3:
            redundancy_score += 11
        elif high_instructions_low_work_ratio > 0.1:
            redundancy_score += 7
        leak_score = 0
        if avg_lifetime > 15_000_000_000 and running_time_ratio < 0.005:
            leak_score += 30
        elif avg_lifetime > 10_000_000_000 and running_time_ratio < 0.01:
            leak_score += 20
        elif avg_lifetime > 5_000_000_000 and running_time_ratio < 0.05:
            leak_score += 10
        if avg_waiting_ratio > 0.95 and avg_lifetime > 5_000_000_000:
            leak_score += 30
        elif avg_waiting_ratio > 0.9 and avg_lifetime > 1_000_000_000:
            leak_score += 20
        elif avg_waiting_ratio > 0.8:
            leak_score += 10
        # 不再按「无 callchain」加分：callchain 可能因采样缺失而为空
        if avg_instructions == 0:
            leak_score += 30
        elif never_running_ratio > 0.5:
            leak_score += 10
        if zero_wakeup_depth_ratio > 0.5:
            leak_score += 10
        if never_woken_ratio > 0.7:
            leak_score += 20
        elif never_woken_ratio > 0.5:
            leak_score += 15
        elif never_woken_ratio > 0.3:
            leak_score += 10
        redundancy_level = 'high' if redundancy_score >= 80 and (unique_tid_count >= 10 or avg_waiting_ratio > 0.9) else 'medium' if redundancy_score >= 60 else 'low' if redundancy_score >= 40 else 'none'
        leak_level = 'high' if leak_score >= 80 and (avg_lifetime > 5_000_000_000 or avg_waiting_ratio > 0.95) else 'medium' if leak_score >= 60 else 'low' if leak_score >= 40 else 'none'
        optimization_potential = 'high' if ((redundancy_level == 'high' and redundancy_score >= 90) or (leak_level == 'high' and leak_score >= 90)) else 'medium' if redundancy_level in ('high', 'medium') or leak_level in ('high', 'medium') else 'low'
        wakeup_pattern = ('frequent_immediate_sleep' if frequent_immediate_sleep_ratio > 0.5 else
                         'never_woken' if never_woken_ratio > 0.5 else
                         'busy_waiting' if busy_waiting_pattern_ratio > 0.5 or high_frequency_transitions_ratio > 0.5 else
                         'busy_wait' if high_instructions_low_work_ratio > 0.5 or yield_call_ratio > 0.5 else 'normal')
        # 忙等类型在算法上给予更高冗余分，便于优先被识别与优化
        if wakeup_pattern == 'busy_wait':
            redundancy_score += 15
        thread_name_variants = sorted(set(t.get('thread_info', {}).get('thread_name', '') for t in thread_list))
        # 默认 user_space_only=True，仅展示 /proc/ 用户态帧；改为 False 可包含系统库与内核帧
        callchain_sample = collect_callchain_sample(list_for_stats, max_entries=10)
        callchain_frame_total, sample_count = count_callchain_frames(list_for_stats)
        redundant_instructions_ratio = (redundant_instructions / total_cpu_instructions) if total_cpu_instructions > 0 else 0.0
        pattern = {
            'thread_name': thread_name, 'thread_name_variants': thread_name_variants,
            'total_thread_count': total_count, 'redundant_count': count,
            'unique_itid_count': len(unique_itids), 'unique_tid_count': unique_tid_count,
            'total_instructions': total_instructions, 'avg_instructions_per_thread': avg_instructions,
            'redundant_instructions': redundant_instructions,
            'redundant_instructions_ratio': redundant_instructions_ratio,
            'estimated_memory_bytes': estimated_memory, 'estimated_memory_mb': estimated_memory / (1024 * 1024),
            'avg_waiting_ratio': avg_waiting_ratio, 'callchain_ratio': callchain_ratio, 'optimization_potential': optimization_potential,
            'redundant_thread_ids': [t.get('thread_id') or t.get('thread_info', {}).get('tid', 0) for t in passed_list], 'is_duplicate': unique_tid_count < max(count, 1) * 0.5,
            'callchain_sample': callchain_sample,
            'callchain_frame_total': callchain_frame_total,
            'sample_count': sample_count,
            'redundancy_score': redundancy_score, 'redundancy_level': redundancy_level, 'leak_score': leak_score, 'leak_level': leak_level,
            'avg_lifetime_ns': avg_lifetime, 'avg_lifetime_sec': avg_lifetime / 1_000_000_000 if avg_lifetime else 0, 'running_time_ratio': running_time_ratio,
            'never_running_ratio': never_running_ratio, 'zero_wakeup_depth_ratio': zero_wakeup_depth_ratio,
            'frequent_immediate_sleep_ratio': frequent_immediate_sleep_ratio, 'never_woken_ratio': never_woken_ratio,
            'avg_wakeup_count': total_wakeup_count / n_stats if n_stats else 0, 'avg_short_running_cycles': total_short_running_cycles / n_stats if n_stats else 0,
            'avg_short_running_periods': total_short_running_periods / n_stats if n_stats else 0, 'yield_call_ratio': yield_call_ratio,
            'high_instructions_low_work_ratio': high_instructions_low_work_ratio,
            'busy_waiting_pattern_ratio': busy_waiting_pattern_ratio, 'high_frequency_transitions_ratio': high_frequency_transitions_ratio,
            'wakeup_pattern': wakeup_pattern,
        }
        analysis['redundant_patterns'].append(pattern)
    analysis['redundant_patterns'].sort(key=lambda x: x['redundant_count'], reverse=True)
    for pattern in analysis['redundant_patterns']:
        if pattern['total_instructions'] > 0 and pattern['redundant_count'] > 10:
            analysis['cpu_optimization_opportunities'].append({
                'thread_name': pattern['thread_name'], 'current_instructions': pattern['total_instructions'],
                'potential_savings': pattern['total_instructions'] * 0.5, 'reduction_percentage': 50, 'method': '减少线程数量'
            })
    for pattern in analysis['redundant_patterns']:
        u = pattern.get('unique_tid_count', pattern['redundant_count'])
        if u >= 5:
            sug = u * 0.6 if u >= 20 else u * 0.4 if u >= 10 else u * 0.2
            analysis['memory_optimization_opportunities'].append({
                'thread_name': pattern['thread_name'], 'current_threads': u, 'suggested_reduction': int(sug),
                'current_memory_mb': pattern['estimated_memory_mb'], 'potential_savings_mb': calculate_thread_memory_estimate(int(sug)) / (1024 * 1024),
                'reduction_percentage': sug / u * 100 if u else 0, 'is_duplicate': pattern.get('is_duplicate', False)
            })
    total_mem = sum(float(o.get('potential_savings_mb', 0) or 0) for o in analysis['memory_optimization_opportunities'])
    total_cpu = sum(float(o.get('potential_savings', 0) or 0) for o in analysis['cpu_optimization_opportunities'])
    total_redundant_instructions = sum(p.get('redundant_instructions', 0) for p in analysis['redundant_patterns'])
    redundant_instructions_ratio = (total_redundant_instructions / total_cpu_instructions) if total_cpu_instructions > 0 else 0.0
    high_priority = [p for p in analysis['redundant_patterns'] if p['optimization_potential'] == 'high']
    analysis['recommendations'] = []
    if high_priority:
        analysis['recommendations'].append({'priority': 'high', 'title': '高优先级优化', 'details': [f"{p['thread_name']}: {p['redundant_count']} 个冗余线程，建议减少到 {max(8, int(p['redundant_count'] * 0.3))} 个" for p in high_priority[:5]]})
    if analysis['cpu_optimization_opportunities']:
        top_cpu = sorted(analysis['cpu_optimization_opportunities'], key=lambda x: x['potential_savings'], reverse=True)[:3]
        analysis['recommendations'].append({'priority': 'medium', 'title': 'CPU优化机会', 'details': [f"{o['thread_name']}: 可节省 {o['potential_savings']:,} 指令 ({o['reduction_percentage']}%)" for o in top_cpu]})
    if analysis['memory_optimization_opportunities']:
        top_mem = sorted(analysis['memory_optimization_opportunities'], key=lambda x: x['potential_savings_mb'], reverse=True)[:5]
        analysis['recommendations'].append({'priority': 'medium', 'title': '内存优化机会', 'details': [f"{o['thread_name']}: {o['current_threads']} → {o['current_threads'] - o['suggested_reduction']} 个，可节省 {o['potential_savings_mb']:.2f} MB" for o in top_mem]})
    analysis['summary'] = {
        'total_memory_savings_mb': total_mem, 'total_cpu_savings_instructions': total_cpu,
        'high_priority_patterns_count': len(high_priority),
        'total_cpu_instructions': total_cpu_instructions,
        'total_redundant_instructions': total_redundant_instructions,
        'redundant_instructions_ratio': redundant_instructions_ratio,
    }
    return analysis


def print_optimization_report(analysis: Dict[str, Any]):
    """打印优化报告。"""
    print("=" * 80)
    print(f"冗余线程优化机会分析 - {analysis['framework'] or '未知框架'}")
    print("=" * 80)
    print()
    s = analysis['summary']
    print("优化摘要:")
    print(f"  总线程数: {analysis['total_threads']}")
    print(f"  perf_sample 总 CPU 指令数: {s.get('total_cpu_instructions', 0):,}")
    print(f"  冗余线程消耗指令数: {s.get('total_redundant_instructions', 0):,} (占比: {s.get('redundant_instructions_ratio', 0)*100:.2f}%)")
    print("  （说明: 冗余包含两类——几乎不做功的线程 与 忙等待线程；忙等待线程指令数高但有效工作占比极低，故占比可较高）")
    print(f"  潜在内存节省: {s['total_memory_savings_mb']:.2f} MB")
    print(f"  潜在CPU指令节省: {s['total_cpu_savings_instructions']:,}")
    print(f"  高优先级优化项: {s['high_priority_patterns_count']}")
    print()
    patterns = analysis['redundant_patterns']
    if not patterns:
        print("未发现明显的冗余线程模式")
        print()
        return
    print(f"{'线程名':<30} {'出现次数':<8} {'唯一TID':<8} {'等待率':<8} {'浪费CPU占比':<10} {'冗余':<8} {'依赖':<8} {'唤醒模式':<18} {'优化潜力':<10}")
    print("-" * 130)
    _hi, _mid, _lo = "[高]", "[中]", "[低]"
    for pattern in patterns[:15]:
        potential_icon = _hi if pattern['optimization_potential'] == 'high' else _mid if pattern['optimization_potential'] == 'medium' else _lo
        u = pattern.get('unique_tid_count', pattern['redundant_count'])
        tc = pattern.get('total_thread_count', pattern['redundant_count'])
        count_display = f"{pattern['redundant_count']}/{tc}" if tc != pattern['redundant_count'] else str(pattern['redundant_count'])
        rl, rs = pattern.get('redundancy_level', 'none'), pattern.get('redundancy_score', 0)
        redundancy_display = f"{_hi}({rs})" if rl == 'high' else f"{_mid}({rs})" if rl == 'medium' else f"{_lo}({rs})" if rl == 'low' else f"-({rs})"
        ll, ls = pattern.get('leak_level', 'none'), pattern.get('leak_score', 0)
        dep_display = f"{_hi}({ls})" if ll == 'high' else f"{_mid}({ls})" if ll == 'medium' else f"{_lo}({ls})" if ll == 'low' else f"-({ls})"
        wp = pattern.get('wakeup_pattern', 'normal')
        pattern_display = (f"频繁唤醒立即等待({pattern.get('frequent_immediate_sleep_ratio', 0)*100:.0f}%)" if wp == 'frequent_immediate_sleep' else
                          f"从未被唤醒({pattern.get('never_woken_ratio', 0)*100:.0f}%)" if wp == 'never_woken' else
                          f"忙等待(含yield {pattern.get('yield_call_ratio', 0)*100:.0f}%)" if wp == 'busy_wait' and pattern.get('yield_call_ratio', 0) > 0.3 else
                          f"忙等待(高指令低工作 {pattern.get('high_instructions_low_work_ratio', 0)*100:.0f}%)" if wp == 'busy_wait' else "正常")
        ratio_pct = pattern.get('redundant_instructions_ratio', 0) * 100
        ratio_str = f"{ratio_pct:.2f}%"
        print(f"{pattern['thread_name']:<30} {count_display:<8} {u:<8} {pattern['avg_waiting_ratio']*100:>6.1f}% {ratio_str:<10} {redundancy_display:<8} {dep_display:<8} {pattern_display:<18} {potential_icon} {pattern['optimization_potential']:<8}")
    below = analysis.get('below_threshold_patterns', [])
    if below:
        print("未达标 pattern（该 pattern 下线程总数<2，仅作参考）:")
        for p in sorted(below, key=lambda x: -x.get('avg_per_thread_score', 0))[:10]:
            line = f"  {p.get('thread_name', '')}: 总个数={p.get('total_thread_count')}, 冗余线程个数={p.get('redundant_count')}, 单线程最高分={p.get('max_per_thread_score')}, 平均分={p.get('avg_per_thread_score')}"
            fs = p.get('feature_summary')
            if fs:
                line += f" | 特征: 平均等待比={fs.get('avg_waiting_ratio_pct', 0)}%, 指令(min/avg/max)={fs.get('min_instructions', 0)}/{fs.get('avg_instructions', 0)}/{fs.get('max_instructions', 0)}, 有callchain={fs.get('threads_with_callchain', 0)}, 有yield={fs.get('threads_with_yield', 0)}, 平均短周期={fs.get('avg_short_cycles', 0)}, 平均运行比={fs.get('avg_run_ratio_pct', 0)}%, wakeup_depth=0数={fs.get('threads_wakeup_depth_0', 0)}"
            print(line)
        print()
    print("说明: 冗余/唤醒模式算法详见 ALGORITHM.md")
    print()
