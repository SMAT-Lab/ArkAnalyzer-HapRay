"""Validate Grapher code citations against supplied source/disassembly only."""
from __future__ import annotations

import hashlib
from pathlib import Path


def source_inventory(source_dir: str | None) -> list[dict]:
    if not source_dir:
        return []
    root = Path(source_dir).resolve()
    records = []
    for path in sorted(root.rglob('*')):
        if (not path.is_file() or path.suffix not in {'.ets', '.ts', '.js', '.pa', '.jsonl'}
                or not path.resolve().is_relative_to(root)
                or any(p in {'.git', 'node_modules', 'oh_modules'} for p in path.relative_to(root).parts)):
            continue
        records.append({'file': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def add_source_nodes(graph, proposed: list[dict], source_dir: str | None) -> dict:
    """Accept code nodes only with exact, bounded excerpts from allowed files.

    Citations prove the code exists, not that it ran or caused the symptom.
    A source location in disassembly is a disassembly line, never presented as
    an original ArkTS source line. Runtime source locations remain separate.
    """
    accepted, rejected = [], []
    root = Path(source_dir).resolve() if source_dir else None
    for item in proposed:
        try:
            node_id = item['id']
            if not isinstance(node_id, str) or not node_id.startswith('code:') or node_id in graph.nodes:
                raise ValueError('new code node id must be unique and start with code:')
            path = (root / item['file']).resolve() if root else None
            # Agents run in the case workspace, so a workspace-relative spelling
            # such as binary/module.pa can also refer to the supplied source root.
            # Resolve that spelling only when the canonical root-relative path is
            # absent, and still enforce containment and exact quotation below.
            if path and not path.is_file() and not Path(item['file']).is_absolute():
                alternative = (root.parent / item['file']).resolve()
                if alternative.is_relative_to(root) and alternative.is_file():
                    path = alternative
            if not path or not path.is_relative_to(root) or path.suffix not in {'.ets', '.ts', '.js', '.pa'}:
                raise ValueError('code path is outside the supplied source tree or unsupported')
            canonical_file = path.relative_to(root).as_posix()
            start, end = item['line_start'], item['line_end']
            if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= start + 100:
                raise ValueError('invalid or unbounded source range')
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
            quote = '\n'.join(lines[start - 1:end])
            if end > len(lines) or quote.strip() != str(item['quote']).strip() or not quote.strip():
                raise ValueError('source quotation does not match file')
            if not item.get('symbol') or item['symbol'] not in quote:
                raise ValueError('symbol must occur verbatim in the source quotation')
            node = {'id': node_id, 'symbol': item['symbol'], 'library': '', 'address': None,
                    'source': {'source_path': canonical_file, 'line': start, 'symbol_name': item['symbol'],
                               'owner_name': item.get('owner', ''),
                               'kind': 'disassembly' if path.suffix == '.pa' else 'source'},
                    'code_evidence_id': 'source:' + node_id}
            graph.nodes[node_id] = node
            graph.facts['source:' + node_id] = {'id': 'source:' + node_id, 'node': node_id,
                                              'kind': 'source-excerpt', 'file': canonical_file,
                                              'line_start': start, 'line_end': end, 'quote': quote}
            accepted.append(node)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            rejected.append({'node': item, 'reason': str(exc)})
    return {'accepted': accepted, 'rejected': rejected}
