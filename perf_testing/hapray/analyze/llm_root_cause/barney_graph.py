"""Evidence-indexed graph and auditable Barney chain scoring.

The model selects candidates and supplies resource interpretation. It cannot
invent fact identifiers, nodes, counter values, or turn an unobserved callback
into an observed stack edge. Inferred dispatch edges remain explicitly typed.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

from .barney_runtime import fact_id

WEIGHTS = {'runtime': .35, 'cpu_explain': .20, 'static_path': .20,
           'ordering': .10, 'ownership': .05, 'llm': .10, 'self_sample': .10}


class EvidenceGraph:
    def __init__(self, evidence: dict[str, Any], sections: dict | None = None):
        self.nodes = {}
        self.facts = {}
        self.resources = []
        self.adjacency = defaultdict(list)
        self.rejected = []
        for capture in evidence['captures']:
            self.nodes.update({n['id']: n for n in capture['nodes']})
            for resource in capture['resources']:
                self.resources.append(resource)
                self.facts[resource['id']] = resource
            for edge in capture['edges']:
                self.facts[edge['id']] = edge
                self.adjacency[edge['src']].append(edge)
        # Keep non-CPU modalities available without pretending their values
        # are sampled instructions or their report scopes are clock captures.
        for category, section in (sections or {}).items():
            for index, item in enumerate(section.get('items') or []):
                if not isinstance(item, dict):
                    continue
                node_id = fact_id('signal-node', category, index, item)
                self.nodes[node_id] = {'id': node_id, 'symbol': item.get('symbol_name', ''),
                                      'source': None, 'signal_category': category}
                resource = {'id': fact_id('signal', category, index, item), 'node': node_id,
                            'kind': 'analyzer-signal', 'category': category, 'measurement': item,
                            'capture': 'signal:' + category, 'first_ts': None, 'last_ts': None,
                            'thread': {'tid': None, 'pid': None, 'name': ''}, 'event_type_id': None}
                self.resources.append(resource)
                self.facts[resource['id']] = resource

    def add_dispatch_edges(self, proposed: list[dict]) -> list[dict]:
        """Validate citations, not the model's semantic interpretation of them."""
        accepted = []
        for edge in proposed:
            reason = ''
            refs = edge.get('evidence_ids', [])
            if not isinstance(edge.get('src'), str) or not isinstance(edge.get('dst'), str):
                reason = 'invalid endpoint'
            elif edge.get('src') not in self.nodes or edge.get('dst') not in self.nodes:
                reason = 'unknown endpoint'
            elif edge['src'] == edge['dst']:
                reason = 'self edge'
            elif not isinstance(edge.get('kind'), str) or edge.get('kind') not in {'source-call', 'dispatch:callback', 'dispatch:task', 'dispatch:event', 'dispatch:ipc'}:
                reason = 'invalid inferred edge kind'
            elif not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in self.facts for r in refs):
                reason = 'missing or unknown evidence citation'
            elif not str(edge.get('rationale', '')).strip():
                reason = 'missing dispatch rationale'
            if reason:
                self.rejected.append({'edge': edge, 'reason': reason})
                continue
            accepted_edge = {**edge, 'id': fact_id('dispatch', edge['src'], edge['dst'], edge['kind'], refs),
                             'status': 'agent-inferred; citations validated, semantics not proven'}
            self.adjacency[edge['src']].append(accepted_edge)
            self.facts[accepted_edge['id']] = accepted_edge
            accepted.append(accepted_edge)
        return accepted

    def path(self, entry: str, sink: str, *, max_depth: int = 16) -> list[dict] | None:
        if entry not in self.nodes or sink not in self.nodes:
            return None
        if entry == sink:
            return []
        queue = deque([(entry, [])])
        visited = {entry}
        while queue:
            node, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            # Stable order: prefer observed calls to equally short inferred paths.
            for edge in sorted(self.adjacency[node], key=lambda e: (e['kind'] != 'sampled-call', e['id'])):
                if edge['dst'] == sink:
                    return path + [edge]
                if edge['dst'] not in visited:
                    visited.add(edge['dst'])
                    queue.append((edge['dst'], path + [edge]))
        return None

    def rank(self, candidates: list[dict]) -> dict[str, Any]:
        """Rank entry-to-sink explanations; return rejected candidates separately.

        A candidate must cite observed resource records, and state the resource
        interpretation numerically (the Bridger's role). Timing and ownership
        are independently computed from capture-local facts. Unreachable sinks
        are never silently promoted to an actionable chain.
        """
        ranked = []
        rejected = []
        for candidate in candidates:
            try:
                ranked.append(self._score(candidate))
            except (ValueError, TypeError, KeyError) as exc:
                rejected.append({'candidate': candidate, 'reason': str(exc)})
        ranked.sort(key=lambda c: (-c['score'], c['sink'], c['entry']))
        # Keep the highest scoring entry per sink, as in Barney's rank_chains.
        unique = {}
        for chain in ranked:
            unique.setdefault(chain['sink'], chain)
        ranked = list(unique.values())
        for rank, chain in enumerate(ranked, 1):
            chain['rank'] = rank
        return {'ranking': ranked, 'rejected_candidates': rejected,
                'rejected_edges': self.rejected, 'weights': WEIGHTS}

    def _score(self, candidate: dict) -> dict:
        entry, sink = candidate['entry'], candidate['sink']
        path = self.path(entry, sink)
        if path is None:
            raise ValueError('no entry-to-sink path')
        refs = candidate.get('resource_ids', [])
        if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
            raise ValueError('resource_ids must be a nonempty unique list')
        records = [self.facts[ref] for ref in refs]
        if any('inclusive_weight' not in r and r.get('kind') != 'analyzer-signal' for r in records):
            raise ValueError('resource_ids must reference resource facts')
        if not str(candidate.get('mechanism', '')).strip():
            raise ValueError('missing waste mechanism')
        signals = candidate['signals']
        if not isinstance(signals, dict):
            raise ValueError('candidate.signals must be one object with runtime, cpu_explain, self_sample; not an array')
        components = {}
        for key in ('runtime', 'cpu_explain', 'self_sample'):
            value = float(signals[key])
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f'invalid Bridger signal: {key}')
            components[key] = value
        prior = float(candidate.get('confidence', .5))
        if not math.isfinite(prior) or not 0 <= prior <= 1:
            raise ValueError('invalid prior')
        # Explicitly record whether evidence is sink-local or cross-layer.
        local = [r for r in records if r['node'] == sink]
        if not local and not str(candidate.get('resource_bridge', '')).strip():
            raise ValueError('cross-layer resources require an explicit bridge explanation')
        captures = {r['capture'] for r in records}
        votes = {'precedes': 0, 'follows': 0}
        for capture in captures:
            target_times = [r['first_ts'] for r in records
                            if r['capture'] == capture and r['first_ts'] is not None]
            entry_times = [r['first_ts'] for r in self.resources
                           if r['node'] == entry and r['capture'] == capture and r['first_ts'] is not None]
            if target_times and entry_times:
                votes['precedes' if min(entry_times) <= min(target_times) else 'follows'] += 1
        comparable = sum(votes.values())
        ordering = .5 if not comparable else float(votes['precedes'] >= votes['follows'])
        # Ownership is supported only by observed sink presence on cited scopes.
        scopes = {(r['capture'], r['thread']['tid'], r['event_type_id']) for r in records}
        owned = any(r['node'] == sink and r['thread']['tid'] is not None
                    and (r['capture'], r['thread']['tid'], r['event_type_id']) in scopes
                    for r in self.resources)
        dispatch = any(e['kind'].startswith('dispatch:') for e in path)
        path_score = max(0, min(1, .5 + .2 * dispatch + .2 * owned - .1 * max(0, len(path) + 1 - 5)))
        components.update(static_path=path_score, ordering=ordering, ownership=float(owned), llm=prior)
        score = sum(WEIGHTS[k] * components[k] for k in WEIGHTS) / sum(WEIGHTS.values())
        return {**candidate, 'confidence': prior, 'score': round(score, 6), 'components': components,
                'path': [entry] + [edge['dst'] for edge in path],
                'edge_ids': [edge['id'] for edge in path], 'edge_types': [edge['kind'] for edge in path],
                'ordering_votes': votes, 'comparable_captures': comparable,
                'resource_scope': 'sink-local' if local else 'cross-layer',
                'resource_facts': records}
