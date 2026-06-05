"""
signal_extractors.py

多信号根因证据提取器（空刷以外的各信号）。每个类对应 report/ 下一种产物，
统一产出 base_evidence.EvidenceExtractor.build 约定的证据段。

Suspect 类（带源码定位，进 suspects）：
    CpuHotspotEvidenceExtractor   - hiperf/step*/perf.db（ArkTS 帧自带 源码:行）
    FrameLoadEvidenceExtractor    - trace_frameLoads.json
    ComponentReuseEvidenceExtractor - trace_componentReuse.json
    ThreadEvidenceExtractor       - redundant_thread_analysis.json
    IpcEvidenceExtractor          - trace_ipc_binder.json
    SoLoadEvidenceExtractor       - so_file_load.json
    MemoryEvidenceExtractor       - hapray_report.db: memory_records

Observation 类（现象，无源码行，进 observations）：
    FrameStatsEvidenceExtractor   - trace_frames.json + trace_rsSkip.json + trace_vsyncAnomaly.json
    UiAnimateEvidenceExtractor    - ui_animate.json
    FaultHilogEvidenceExtractor   - trace_fault_tree.json + hilog_detail.json
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_evidence import EvidenceExtractor, parse_arkts_source_loc


def _steps_by_total_load(report_dir: Path, summary_json: Any) -> list[tuple[str, int]]:
    """从 summary.json 读各 step 的 total_cpu_instructions，按负载降序返回 [(step_id, load)]。"""
    out: list[tuple[str, int]] = []
    if isinstance(summary_json, list):
        for entry in summary_json:
            if not isinstance(entry, dict):
                continue
            sid = str(entry.get('step_id') or '')
            # step_id 形如 PerfLoad_xxx_step5 → 取末尾 stepN
            short = sid.rsplit('_', 1)[-1] if '_step' in sid else sid
            rt = entry.get('redundant_thread') or {}
            load = rt.get('total_cpu_instructions') if isinstance(rt, dict) else 0
            out.append((short, int(load or 0)))
    out.sort(key=lambda x: -x[1])
    return out


class CpuHotspotEvidenceExtractor(EvidenceExtractor):
    """CPU 高负载热点：对负载最重的若干 step 跑 perf.db 聚合，定位 ArkTS 源码行。"""

    category = 'cpu-hotspot'
    kind = 'suspect'

    def __init__(self, report_dir: str | Path, *, top_n: int = 12, max_steps: int = 2) -> None:
        super().__init__(report_dir, top_n=top_n)
        self.max_steps = max_steps

    def is_available(self) -> bool:
        return bool(self.list_perf_db_steps())

    def _heavy_steps(self) -> list[str]:
        steps = self.list_perf_db_steps()
        available = {s for s, _ in steps}
        ranked = [s for s, _ in _steps_by_total_load(self.report_dir, self.read_json('summary.json')) if s in available]
        if ranked:
            return ranked[: self.max_steps]
        # 无 summary 排序信息时退化为按 perf.db 文件大小
        steps.sort(key=lambda sp: sp[1].stat().st_size if sp[1].exists() else 0, reverse=True)
        return [s for s, _ in steps[: self.max_steps]]

    def _main_thread_id(self, conn) -> int | None:
        # 主线程：进程主线程（process_id == thread_id）中负载最高者 = 应用 UI 线程
        row = conn.execute(
            """
            select pt.thread_id, sum(ps.event_count) load
            from perf_sample ps
            join perf_thread pt on pt.thread_id = ps.thread_id
            where pt.process_id = pt.thread_id
            group by pt.thread_id
            order by load desc
            limit 1
            """
        ).fetchone()
        return int(row[0]) if row else None

    def _analyze_step(self, step_id: str, db_path: Path) -> dict[str, Any] | None:
        conn = self.connect_ro(db_path)
        if conn is None:
            return None
        try:
            total = conn.execute('select sum(event_count) from perf_sample').fetchone()[0] or 0
            if not total:
                return None
            mt = self._main_thread_id(conn)
            mt_load = 0
            if mt is not None:
                mt_load = conn.execute(
                    'select sum(event_count) from perf_sample where thread_id = ?', (mt,)
                ).fetchone()[0] or 0
            # inclusive 聚合：仅取 ArkTS 帧（symbol 含 [url:...src/main/...]），直接拿到 源码:行
            where_tid = 'and ps.thread_id = ?' if mt is not None else ''
            params: tuple = (mt,) if mt is not None else ()
            rows = conn.execute(
                f"""
                select pf.symbol, sum(ps.event_count) ins
                from perf_sample ps
                join perf_callchain pc on ps.callchain_id = pc.callchain_id
                join perf_files pf on pf.file_id = pc.file_id and pf.serial_id = pc.symbol_id
                where pf.symbol like '%:[url:%src/main/%' {where_tid}
                group by pf.symbol
                order by ins desc
                limit ?
                """,
                (*params, self.top_n),
            ).fetchall()
            items: list[dict[str, Any]] = []
            for symbol, ins in rows:
                loc = parse_arkts_source_loc(str(symbol or ''))
                if loc is None:
                    continue
                items.append(
                    {
                        'step': step_id,
                        'source_path': loc['source_path'],
                        'line': loc['line'],
                        'symbol_name': loc['symbol_name'],
                        'owner_name': loc['owner_name'],
                        'instructions': int(ins or 0),
                        'pct_of_step': round(int(ins or 0) * 100.0 / total, 2),
                    }
                )
            return {
                'step': step_id,
                'total_instructions': int(total),
                'main_thread_instructions': int(mt_load),
                'main_thread_pct': round(int(mt_load) * 100.0 / total, 2) if total else 0.0,
                'items': items,
            }
        except Exception:
            return None
        finally:
            conn.close()

    def build(self) -> dict[str, Any] | None:
        steps = self._heavy_steps()
        if not steps:
            return None
        per_step: list[dict[str, Any]] = []
        all_items: list[dict[str, Any]] = []
        for sid in steps:
            db = self.perf_db_path(sid)
            if not db.exists():
                continue
            res = self._analyze_step(sid, db)
            if res is None:
                continue
            per_step.append(
                {k: v for k, v in res.items() if k != 'items'}
            )
            all_items.extend(res['items'])
        if not all_items:
            return None
        all_items.sort(key=lambda x: -x['instructions'])
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {
                'analyzed_steps': [p['step'] for p in per_step],
                'per_step': per_step,
                'note': '叶子帧多归于 appspawn（ArkTS 字节码/JIT）；本表为 inclusive 调用链聚合，'
                'ArkTS 应用帧符号自带 源码:行，无需符号恢复。',
            },
            'items': all_items[: self.top_n],
        }


class FrameLoadEvidenceExtractor(EvidenceExtractor):
    """高负载帧：trace_frameLoads.json 的 statistics + top_frames。"""

    category = 'frame-load'
    kind = 'suspect'

    def is_available(self) -> bool:
        return self.report_file('trace_frameLoads.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('trace_frameLoads.json')
        if not isinstance(data, dict):
            return None
        per_step: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        for step_id, step in data.items():
            if not isinstance(step, dict):
                continue
            stats = step.get('statistics') or {}
            per_step.append(
                {
                    'step': step_id,
                    'total_frames': self.safe_int(stats.get('total_frames')),
                    'high_load_frames': self.safe_int(stats.get('high_load_frames')),
                    'max_load': self.safe_int(stats.get('max_load')),
                    'average_load': self.safe_int(stats.get('average_load')),
                }
            )
            for fr in (step.get('top_frames') or [])[:3]:
                if not isinstance(fr, dict):
                    continue
                items.append(
                    {
                        'step': step_id,
                        'frame_load': self.safe_int(fr.get('frame_load')),
                        'dur_ns': self.safe_int(fr.get('dur')),
                        'flag': self.safe_int(fr.get('flag')),  # 1=high 2=empty
                        'is_main_thread': self.safe_int(fr.get('is_main_thread')),
                        'thread_name': fr.get('thread_name', ''),
                        'vsync': fr.get('vsync'),
                        'callstack_id': fr.get('callstack_id'),
                    }
                )
        if not per_step:
            return None
        items.sort(key=lambda x: -x['frame_load'])
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {'per_step': sorted(per_step, key=lambda x: -x['max_load'])},
            'items': items[: self.top_n],
        }


class ComponentReuseEvidenceExtractor(EvidenceExtractor):
    """组件复用：trace_componentReuse.json，低复用率组件 → .ets 文件（owner）。"""

    category = 'component-reuse'
    kind = 'suspect'

    def is_available(self) -> bool:
        return self.report_file('trace_componentReuse.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('trace_componentReuse.json')
        if not isinstance(data, dict):
            return None
        agg: dict[str, list[int]] = {}  # component -> [total_builds, recycled_builds]
        per_step: list[dict[str, Any]] = []
        for step_id, step in data.items():
            if not isinstance(step, dict):
                continue
            per_step.append(
                {
                    'step': step_id,
                    'max_component': step.get('max_component', ''),
                    'total_builds': self.safe_int(step.get('total_builds')),
                    'recycled_builds': self.safe_int(step.get('recycled_builds')),
                    'reusability_ratio': round(self.safe_float(step.get('reusability_ratio')), 3),
                }
            )
            for comp, pair in (step.get('details') or {}).items():
                if not isinstance(pair, list) or len(pair) < 2:
                    continue
                cur = agg.setdefault(comp, [0, 0])
                cur[0] += self.safe_int(pair[0])
                cur[1] += self.safe_int(pair[1])
        items = []
        for comp, (tb, rb) in agg.items():
            if tb <= 0:
                continue
            items.append(
                {
                    'owner_name': comp,
                    'total_builds': tb,
                    'recycled_builds': rb,
                    'reusability_ratio': round(rb / tb, 3) if tb else 0.0,
                }
            )
        # 复用率低且 build 多的优先
        items.sort(key=lambda x: (x['reusability_ratio'], -x['total_builds']))
        if not items:
            return None
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {'per_step': per_step},
            'items': items[: self.top_n],
        }


class ThreadEvidenceExtractor(EvidenceExtractor):
    """冗余线程：redundant_thread_analysis.json。无直接源码行，owner=线程名。"""

    category = 'thread'
    kind = 'suspect'

    def is_available(self) -> bool:
        return self.report_file('redundant_thread_analysis.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('redundant_thread_analysis.json')
        if not isinstance(data, dict):
            return None
        per_step: list[dict[str, Any]] = []
        items: list[dict[str, Any]] = []
        for step_id, step in data.items():
            if not isinstance(step, dict):
                continue
            rs = step.get('redundant_threads_summary') or {}
            per_step.append(
                {
                    'step': step_id,
                    'total_redundant_threads': self.safe_int(rs.get('total_redundant_threads')),
                    'total_redundant_instructions': self.safe_int(rs.get('total_redundant_instructions')),
                    'redundant_instructions_ratio': round(self.safe_float(rs.get('redundant_instructions_ratio')), 4),
                }
            )
            for t in (rs.get('redundant_threads') or []):
                if not isinstance(t, dict):
                    continue
                items.append(
                    {
                        'step': step_id,
                        'owner_name': t.get('thread_name', ''),
                        'type': t.get('type', ''),
                        'redundancy_count': self.safe_int(t.get('redundancy_count')),
                        'redundant_instructions': self.safe_int(t.get('redundant_instructions')),
                        'waiting_ratio': round(self.safe_float(t.get('waiting_ratio')), 3),
                    }
                )
        if not per_step:
            return None
        items.sort(key=lambda x: -x['redundant_instructions'])
        total_redundant = sum(p['total_redundant_threads'] for p in per_step)
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {
                'per_step': per_step,
                'note': '若各 step total_redundant_threads 均为 0，则线程模型健康，无冗余线程问题。',
                'has_redundancy': total_redundant > 0,
            },
            'items': items[: self.top_n],
        }


class IpcEvidenceExtractor(EvidenceExtractor):
    """IPC/Binder：trace_ipc_binder.json 高频/高 QPS 进程对。owner=调用方。"""

    category = 'ipc'
    kind = 'suspect'

    def is_available(self) -> bool:
        return self.report_file('trace_ipc_binder.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('trace_ipc_binder.json')
        if not isinstance(data, dict):
            return None
        items: list[dict[str, Any]] = []
        for step_id, step in data.items():
            if not isinstance(step, dict):
                continue
            for p in (step.get('process_stats') or []):
                if not isinstance(p, dict):
                    continue
                items.append(
                    {
                        'step': step_id,
                        'caller_proc': p.get('caller_proc', ''),
                        'callee_proc': p.get('callee_proc', ''),
                        'owner_name': p.get('caller_proc', ''),
                        'count': self.safe_int(p.get('count')),
                        'qps': round(self.safe_float(p.get('qps')), 1),
                        'avg_latency_ms': round(self.safe_float(p.get('avg_latency')), 3),
                    }
                )
        if not items:
            return None
        items.sort(key=lambda x: -x['count'])
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {
                'note': '高 QPS/事务数常为每帧 rerender 的下游表现；优先核对是否由 UI 高负载驱动。'
            },
            'items': items[: self.top_n],
        }


class SoLoadEvidenceExtractor(EvidenceExtractor):
    """SO 文件负载：so_file_load.json，按 .so 聚合 load。owner=SO 名（原生库）。"""

    category = 'so-load'
    kind = 'suspect'

    def is_available(self) -> bool:
        return self.report_file('so_file_load.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('so_file_load.json')
        if not isinstance(data, list):
            return None
        agg: dict[str, dict[str, Any]] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            f = str(row.get('file') or '')
            if not f:
                continue
            cur = agg.setdefault(f, {'owner_name': f, 'file_path': row.get('file_path', ''), 'load': 0})
            cur['load'] += self.safe_int(row.get('load'))
        items = sorted(agg.values(), key=lambda x: -x['load'])
        if not items:
            return None
        total = sum(i['load'] for i in items) or 1
        for i in items:
            i['pct'] = round(i['load'] * 100.0 / total, 2)
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {'total_so_load': total, 'note': '原生库无源码行；高负载第三方/系统库可结合 CPU 热点交叉。'},
            'items': items[: self.top_n],
        }


class MemoryEvidenceExtractor(EvidenceExtractor):
    """内存：hapray_report.db 的 memory_records（未开 --memory 时为空 → 不可用）。"""

    category = 'memory'
    kind = 'suspect'

    def _db(self) -> Path:
        return self.report_file('hapray_report.db')

    def is_available(self) -> bool:
        db = self._db()
        if not db.exists():
            return False
        conn = self.connect_ro(db)
        if conn is None:
            return False
        try:
            row = conn.execute('select count(*) from memory_records').fetchone()
            return bool(row and row[0])
        except Exception:
            return False
        finally:
            conn.close()

    def build(self) -> dict[str, Any] | None:
        db = self._db()
        conn = self.connect_ro(db)
        if conn is None:
            return None
        try:
            rows = conn.execute(
                """
                select d.value as component, count(*) cnt, sum(r.heapSize) total
                from memory_records r
                left join memory_data_dicts d on d.dictId = r.componentNameId and d.step_id = r.step_id
                group by r.componentNameId
                order by total desc
                limit ?
                """,
                (self.top_n,),
            ).fetchall()
        except Exception:
            return None
        finally:
            conn.close()
        items = [
            {
                'owner_name': str(comp or 'unknown'),
                'alloc_count': self.safe_int(cnt),
                'heap_bytes': self.safe_int(total),
            }
            for comp, cnt, total in rows
            if self.safe_int(total) > 0
        ]
        if not items:
            return None
        return {
            'category': self.category,
            'kind': self.kind,
            'summary': {'note': 'componentName 可映射 ArkTS 组件；原生分配栈需符号恢复。'},
            'items': items,
        }


# ── Observation 类（现象，无源码行）─────────────────────────────────


class FrameStatsEvidenceExtractor(EvidenceExtractor):
    """帧率/RS/Vsync 现象：trace_frames + trace_rsSkip + trace_vsyncAnomaly。"""

    category = 'frame-stats'
    kind = 'observation'

    def is_available(self) -> bool:
        return self.report_file('trace_frames.json').exists()

    def build(self) -> dict[str, Any] | None:
        frames = self.read_json('trace_frames.json')
        if not isinstance(frames, dict):
            return None
        rs = self.read_json('trace_rsSkip.json')
        vsync = self.read_json('trace_vsyncAnomaly.json')
        items: list[dict[str, Any]] = []
        for step_id, step in frames.items():
            if not isinstance(step, dict):
                continue
            fps = step.get('fps_stats') or {}
            stats = step.get('statistics') or {}
            row = {
                'step': step_id,
                'avg_fps': round(self.safe_float(fps.get('average_fps')), 2),
                'total_frames': self.safe_int(stats.get('total_frames')),
                'stutter_frames': self.safe_int(stats.get('total_stutter_frames')),
                'stutter_rate': round(self.safe_float(stats.get('stutter_rate')), 4),
            }
            if isinstance(rs, dict) and isinstance(rs.get(step_id), dict):
                rsum = rs[step_id].get('summary') or {}
                row['rs_skip_frames'] = self.safe_int(rsum.get('total_skip_frames'))
            if isinstance(vsync, dict) and isinstance(vsync.get(step_id), dict):
                vstat = vsync[step_id].get('statistics') or {}
                row['vsync_anomalies'] = self.safe_int(
                    vstat.get('total_anomalies') or vstat.get('frequency_anomaly_count')
                )
            items.append(row)
        if not items:
            return None
        return {'category': self.category, 'kind': self.kind, 'summary': {}, 'items': items}


class UiAnimateEvidenceExtractor(EvidenceExtractor):
    """UI 动画/离树节点/超大图：ui_animate.json。"""

    category = 'ui-animate'
    kind = 'observation'

    def is_available(self) -> bool:
        return self.report_file('ui_animate.json').exists()

    def build(self) -> dict[str, Any] | None:
        data = self.read_json('ui_animate.json')
        if not isinstance(data, dict):
            return None
        items: list[dict[str, Any]] = []
        for step_id, pages in data.items():
            if not isinstance(pages, list):
                continue
            for pg in pages:
                if not isinstance(pg, dict):
                    continue
                total = self.safe_int(pg.get('canvasNodeCnt'))
                off = self.safe_int(pg.get('canvas_node_off_tree'))
                img = pg.get('image_size_analysis') or {}
                anims = pg.get('animations')
                items.append(
                    {
                        'step': step_id,
                        'desc': pg.get('description', ''),
                        'canvas_nodes': total,
                        'off_tree_nodes': off,
                        'off_tree_ratio': round(off / total, 3) if total else 0.0,
                        'oversize_images': self.safe_int(img.get('exceed_count'))
                        if isinstance(img, dict)
                        else 0,
                        'animation_count': len(anims) if isinstance(anims, list) else 0,
                    }
                )
        if not items:
            return None
        items.sort(key=lambda x: -x['off_tree_ratio'])
        return {'category': self.category, 'kind': self.kind, 'summary': {}, 'items': items[: self.top_n]}


class FaultHilogEvidenceExtractor(EvidenceExtractor):
    """故障树 + hilog 规则命中：trace_fault_tree.json + hilog_detail.json。"""

    category = 'fault-hilog'
    kind = 'observation'

    def is_available(self) -> bool:
        return self.report_file('trace_fault_tree.json').exists() or self.report_file('hilog_detail.json').exists()

    def build(self) -> dict[str, Any] | None:
        items: list[dict[str, Any]] = []
        ft = self.read_json('trace_fault_tree.json')
        if isinstance(ft, dict):
            for step_id, step in ft.items():
                if not isinstance(step, dict):
                    continue
                scal = {k: v for k, v in step.items() if not isinstance(v, (dict, list))}
                cats = [k for k, v in step.items() if isinstance(v, (dict, list))]
                items.append(
                    {'step': step_id, 'source': 'fault_tree', 'categories': cats, 'metrics': scal}
                )
        hilog = self.read_json('hilog_detail.json')
        if isinstance(hilog, dict):
            for rule, payload in hilog.items():
                matched = payload.get('matched') if isinstance(payload, dict) else None
                cnt = len(matched) if isinstance(matched, list) else self.safe_int(matched)
                if cnt:
                    items.append({'source': 'hilog', 'rule': rule, 'matched_count': cnt})
        if not items:
            return None
        return {'category': self.category, 'kind': self.kind, 'summary': {}, 'items': items[: self.top_n * 2]}


# Suspect 类（不含已有的 EmptyFrame，它在 runner 里单独接入）
SUSPECT_EXTRACTORS: list[type[EvidenceExtractor]] = [
    CpuHotspotEvidenceExtractor,
    FrameLoadEvidenceExtractor,
    ComponentReuseEvidenceExtractor,
    ThreadEvidenceExtractor,
    IpcEvidenceExtractor,
    SoLoadEvidenceExtractor,
    MemoryEvidenceExtractor,
]

OBSERVATION_EXTRACTORS: list[type[EvidenceExtractor]] = [
    FrameStatsEvidenceExtractor,
    UiAnimateEvidenceExtractor,
    FaultHilogEvidenceExtractor,
]
