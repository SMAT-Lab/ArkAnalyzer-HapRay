"""Capture-local resource and execution facts for Barney's Bridger/Grapher.

Facts are observations, not diagnoses. Inclusive cost is counted once per
sample/method even with recursion. Event types, processes, threads and captures
stay separate: their counters and clocks are not interchangeable. No benchmark
labels, previous root-cause reports or inferred symbol names are read here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

from .base_evidence import parse_arkts_source_loc


def fact_id(kind: str, *parts: Any) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return kind + ':' + hashlib.sha256(encoded).hexdigest()[:24]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info({table})')}


def read_capture(db_path: Path, capture_id: str, *, top_per_thread: int = 40) -> dict[str, Any]:
    """Extract native and ArkTS stacks on *all* observed threads, read-only.

    depth=0 is the stack root in HapRay/TraceStreamer perf_callchain; the
    maximum recorded depth is the sampled leaf. Stack
    edges mean synchronous sampled ancestry, never asynchronous dispatch.
    Unknown leaf symbols remain distinct by library and instruction address.
    """
    if top_per_thread < 1:
        raise ValueError('top_per_thread must be positive')
    with sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True) as conn:
        sample_columns = _columns(conn, 'perf_sample')
        clock = next((c for c in ('timestamp_trace', 'timeStamp') if c in sample_columns), None)
        event = 'event_type_id' if 'event_type_id' in sample_columns else 'NULL'
        timestamp = clock or 'NULL'
        threads = {
            row[0]: {'tid': row[0], 'pid': row[1], 'name': row[2]}
            for row in conn.execute('SELECT thread_id, process_id, thread_name FROM perf_thread')
        }
        symbols = {}
        for file_id, serial_id, symbol, path in conn.execute(
            'SELECT file_id, serial_id, symbol, path FROM perf_files ORDER BY id'
        ):
            key = (file_id, serial_id)
            value = (symbol or '', path or '')
            if key in symbols and symbols[key] != value:
                raise ValueError(f'Ambiguous perf_files key: {key}')
            symbols[key] = value
        nodes: dict[str, dict[str, Any]] = {}
        chains: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for chain, depth, file_id, serial_id, address in conn.execute(
            'SELECT callchain_id, depth, file_id, symbol_id, vaddr_in_file '
            'FROM perf_callchain ORDER BY callchain_id, depth'
        ):
            symbol, library = symbols.get((file_id, serial_id), ('', ''))
            unresolved = not symbol or symbol in {'[unknown]', 'unknown', '??'}
            node_id = fact_id('node', library, symbol, address if unresolved else None)
            nodes[node_id] = {'id': node_id, 'symbol': symbol, 'library': library,
                              'address': address if unresolved else None,
                              'source': parse_arkts_source_loc(symbol)}
            chains[chain].append((depth, node_id))
        metadata = []
        if _columns(conn, 'perf_report'):
            conn.row_factory = sqlite3.Row
            metadata = [dict(row) for row in conn.execute('SELECT * FROM perf_report')]
            conn.row_factory = None
        aggregates = conn.execute(
            f'SELECT callchain_id, thread_id, {event}, SUM(event_count), COUNT(*), '
            f'MIN({timestamp}), MAX({timestamp}) FROM perf_sample '
            f'GROUP BY callchain_id, thread_id, {event}'
        ).fetchall()

    totals: dict[tuple, float] = defaultdict(float)
    resources: dict[tuple, dict[str, Any]] = {}
    edges: dict[tuple, dict[str, Any]] = {}
    missing_stack_weight: dict[tuple, float] = defaultdict(float)
    for chain_id, tid, event_id, weight, samples, first, last in aggregates:
        weight = float(weight or 0)
        if weight < 0:
            raise ValueError('Negative perf counter weight')
        group = (tid, event_id)
        totals[group] += weight
        frames = chains.get(chain_id, [])
        if not frames:
            missing_stack_weight[group] += weight
            continue
        # Recursive appearances must not multiply inclusive sample weight.
        seen = set()
        for depth, node_id in frames:
            key = (*group, node_id)
            record = resources.setdefault(key, {
                'id': fact_id('resource', capture_id, *key), 'capture': capture_id,
                'node': node_id, 'thread': threads.get(tid, {'tid': tid, 'pid': None, 'name': ''}),
                'event_type_id': event_id, 'inclusive_weight': 0.0, 'self_weight': 0.0,
                'samples': 0, 'first_ts': None, 'last_ts': None,
            })
            if depth == frames[-1][0]:
                record['self_weight'] += weight
            if node_id in seen:
                continue
            seen.add(node_id)
            record['inclusive_weight'] += weight
            record['samples'] += samples
            if first is not None:
                record['first_ts'] = first if record['first_ts'] is None else min(first, record['first_ts'])
                record['last_ts'] = last if record['last_ts'] is None else max(last, record['last_ts'])
        seen_edges = set()
        for (caller_depth, caller), (callee_depth, callee) in zip(frames, frames[1:]):
            # Do not fabricate an edge across a missing stack frame.
            if callee_depth != caller_depth + 1 or caller == callee or (caller, callee) in seen_edges:
                continue
            seen_edges.add((caller, callee))
            key = (*group, caller, callee)
            edge = edges.setdefault(key, {
                'id': fact_id('edge', capture_id, *key), 'capture': capture_id,
                'src': caller, 'dst': callee, 'kind': 'sampled-call',
                'tid': tid, 'event_type_id': event_id, 'weight': 0.0,
            })
            edge['weight'] += weight

    selected = []
    groups = []
    for group, total in sorted(totals.items(), key=lambda item: str(item[0])):
        records = [r for (tid, eid, _), r in resources.items() if (tid, eid) == group]
        records.sort(key=lambda r: (-r['inclusive_weight'], -r['self_weight'], r['node']))
        for record in records[:top_per_thread]:
            record['inclusive_share'] = record['inclusive_weight'] / total if total else 0.0
            record['self_share'] = record['self_weight'] / total if total else 0.0
            selected.append(record)
        groups.append({'tid': group[0], 'event_type_id': group[1], 'total_weight': total,
                       'missing_stack_weight': missing_stack_weight[group],
                       'omitted_resource_records': max(0, len(records) - top_per_thread)})
    return {'capture': capture_id, 'database': str(db_path), 'clock': clock,
            'counter_unit': 'event_count (consult perf_report; not necessarily instructions)',
            'perf_report': metadata, 'groups': groups, 'nodes': list(nodes.values()),
            'resources': selected, 'edges': list(edges.values())}


def build_runtime_evidence(report_dir: str | Path, *, top_per_thread: int = 40) -> dict[str, Any]:
    """Build evidence for a HapRay case without collecting or modifying inputs."""
    root = Path(report_dir).resolve().parent
    captures = []
    errors = []
    for db in sorted(root.glob('hiperf/step*/perf.db')):
        capture = db.relative_to(root).as_posix()
        try:
            captures.append(read_capture(db, capture, top_per_thread=top_per_thread))
        except (OSError, sqlite3.Error, ValueError) as exc:
            errors.append({'capture': capture, 'error': f'{type(exc).__name__}: {exc}'})
    return {'schema_version': 1, 'captures': captures, 'errors': errors,
            'caveats': ['Sampled ancestry is not proof of a waste mechanism.',
                        'Missing samples do not prove a method did not execute.',
                        'Never compare absolute timestamps between captures.',
                        'Top-per-thread truncation is explicit in each group.']}
