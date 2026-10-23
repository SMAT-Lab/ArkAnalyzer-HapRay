"""Barney orchestration for HapRay's API and external skill/agent surfaces.

Grapher -> Bridger -> focused Grapher -> rank -> bounded tie refinement.
Agent decisions are persisted with input fingerprints. Export/resume is the
same workflow as automatic execution, not a separate single-prompt fallback.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Callable

from .barney_graph import EvidenceGraph
from .barney_runtime import build_runtime_evidence
from .barney_source import add_source_nodes, source_inventory
from .llm_client import is_llm_configured, load_client_from_config
from .structured_output import RootCauseResult, render_to_markdown

GRAPH_INSTRUCTIONS = """You are Barney's Grapher. Read the evidence and supplied code/disassembly.
Reconstruct meaningful application entry-to-resource-sink connections, including
callbacks, tasks, events and IPC absent from sampled synchronous stacks.
Do not diagnose just from a costly library name. Do not invent unseen code.
Propose source_nodes only with exact local file quotations (line ranges <=101).
Use existing runtime node IDs where possible. New code node IDs start with code:.
Reuse existing source-node IDs from graph.json rather than inventing new aliases
for the same code in later stages. Only declared, validated new nodes can be used.
New code nodes expose citation IDs source:<node-id>. An inferred edge MUST cite
existing evidence_ids and explain the dispatch or call relationship. A quotation
proves code existence, not execution. Leave unsupported edges absent and record
gaps. Allowed edge kinds: source-call, dispatch:callback, dispatch:task,
dispatch:event, dispatch:ipc. No arbitrary edges merely to make sinks reachable.
Return payload {source_nodes: [...], edges: [...], gaps: [...]}.
source_nodes item: {id,symbol,owner,file,line_start,line_end,quote}; file relative
to source_dir; symbol must occur verbatim in quote. Copy quotations with a local
script preserving whitespace instead of retyping them. edges item:
{src,dst,kind,evidence_ids:[...],rationale}. At most 24 nodes and 40 edges.
"""

BRIDGE_INSTRUCTIONS = """You are Barney's Bridger. Independently explain the reported symptom using
the resource evidence and code. Select symptomatic thread/resource scopes and
application sinks, not just the largest library or benchmark instrumentation.
When the waste is in application code, choose that defective application method
as sink; attach native/worker cost through resource_ids and resource_bridge.
Read source/disassembly around proposed sinks; explain the waste mechanism,
not only a hotspot. Consider rival explanations and evidence against each.
Use the graph IDs exactly; source node additions/edges can be proposed using the
Grapher format if inspection exposes missing code. Each candidate must provide
entry, sink, unique resource_ids (existing resource or analyzer-signal facts),
mechanism, fix, category, confidence in [0,1], resource_bridge (why cross-layer
cost belongs to this sink), counterevidence, and signals as ONE OBJECT (not an
array): {"runtime":0.0,"cpu_explain":0.0,"self_sample":0.0}, each in [0,1].
These are evidence interpretations, not measured counter values; justify them
in a candidate-level signal_rationale string. Missing self samples
are not proof of no execution. Do not mix clocks across captures or counter
types. Never place edge IDs in resource_ids: edges support paths, not resource
amounts. Prefer sink-local evidence; cross-layer attribution needs a concrete
dispatch/ownership/source explanation. Rankable hypotheses must have a real
entry-to-sink path; do not set entry=sink merely to bypass missing reachability.
Return payload {candidates:[...],source_nodes:[...],edges:[...],caveats:[...]}.
At most 12 candidates covering distinct explanations. Do not consult earlier
predictions, benchmark labels, fixed versions, patches or the internet.
"""


class PendingStage(Exception):
    def __init__(self, stage: str, task: Path, result: Path, reason: str):
        super().__init__(reason)
        self.stage, self.task, self.result = stage, task, result


def _dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _parse_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('response must be an object')
    return value


def _payload_schema(stage: str) -> dict:
    """Expose the actual nested data contract, not an unconstrained payload."""
    text = {'type': 'string'}
    unit = {'type': 'number', 'minimum': 0, 'maximum': 1}
    node = {'type': 'object', 'required': ['id', 'symbol', 'file', 'line_start', 'line_end', 'quote'],
            'properties': {**{k: text for k in ('id', 'symbol', 'owner', 'file', 'quote')},
                           'line_start': {'type': 'integer', 'minimum': 1},
                           'line_end': {'type': 'integer', 'minimum': 1}}}
    edge = {'type': 'object', 'required': ['src', 'dst', 'kind', 'evidence_ids', 'rationale'],
            'properties': {**{k: text for k in ('src', 'dst', 'rationale')},
                           'kind': {'enum': ['source-call', 'dispatch:callback', 'dispatch:task',
                                             'dispatch:event', 'dispatch:ipc']},
                           'evidence_ids': {'type': 'array', 'minItems': 1, 'items': text}}}
    candidate = {'type': 'object',
                 'required': ['entry', 'sink', 'resource_ids', 'mechanism', 'fix', 'category',
                              'confidence', 'signals'],
                 'properties': {**{k: text for k in ('entry', 'sink', 'mechanism', 'fix', 'category',
                                                     'resource_bridge', 'signal_rationale')},
                                'confidence': unit,
                                'resource_ids': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                                                 'items': text},
                                'signals': {'type': 'object',
                                            'required': ['runtime', 'cpu_explain', 'self_sample'],
                                            'properties': {k: unit for k in ('runtime', 'cpu_explain', 'self_sample')}}}}
    properties = {'source_nodes': {'type': 'array', 'maxItems': 24, 'items': node},
                  'edges': {'type': 'array', 'maxItems': 40, 'items': edge}}
    if stage in {'bridger', 'refine'}:
        properties.update(candidates={'type': 'array', 'maxItems': 12, 'items': candidate},
                          caveats={'type': 'array', 'items': text})
    else:
        properties['gaps'] = {'type': 'array', 'items': text}
    return {'type': 'object', 'required': ['candidates' if stage in {'bridger', 'refine'} else 'edges'],
            'properties': properties, 'additionalProperties': False}


class BarneySession:
    def __init__(self, output: Path, cfg: dict, execute: Callable | None = None):
        self.output, self.cfg, self.execute = output, cfg, execute
        self.directory = output.parent / (output.stem + '_barney')
        self.directory.mkdir(parents=True, exist_ok=True)

    def stage(self, name: str, instructions: str, context: dict, fingerprint: str, *, export_only=False) -> dict:
        request_id = _hash({'version': 1, 'stage': name, 'instructions': instructions,
                            'context': context, 'inputs': fingerprint, 'schema': _payload_schema(name)})
        task_path = self.directory / f'{name}_task.json'
        result_path = self.directory / f'{name}_result.json'
        schema = {'type': 'object', 'required': ['request_id', 'payload'],
                  'properties': {'request_id': {'const': request_id}, 'payload': _payload_schema(name)}}
        task = {'task_type': 'hapray_barney', 'stage': name, 'request_id': request_id,
                'system_prompt': instructions + '\nReturn only a JSON object with request_id and payload. '
                'Use the exact request_id below; never return a JSON Schema.',
                'user_prompt': json.dumps({'request_id': request_id, **context}, ensure_ascii=False),
                'expected_schema_json': schema, 'result_path': str(result_path)}
        _dump(task_path, task)
        if export_only:
            raise PendingStage(name, task_path, result_path, 'Inference explicitly skipped; evidence only.')

        def read_result(path=result_path):
            value = _parse_object(path.read_text(encoding='utf-8'))
            if value.get('request_id') != request_id or not isinstance(value.get('payload'), dict):
                raise ValueError('stale request_id or invalid payload')
            payload = value['payload']
            required = 'candidates' if name in {'bridger', 'refine'} else 'edges'
            if not isinstance(payload.get(required), list):
                raise ValueError(f'{name} requires a {required} array')
            for field, maximum in [('candidates', 12), ('source_nodes', 24), ('edges', 40)]:
                values = payload.get(field, [])
                if not isinstance(values, list) or len(values) > maximum or any(not isinstance(v, dict) for v in values):
                    raise ValueError(f'invalid/budget-exceeding {field}')
            # Keep roles separate even if an agent emits extra fields: Grapher
            # diagnoses must not become an accidental prior for Bridger.
            allowed = _payload_schema(name)['properties']
            return {field: value for field, value in payload.items() if field in allowed}

        if result_path.is_file():
            try:
                return read_result()
            except (ValueError, OSError) as exc:
                logging.warning('Ignoring invalid Barney %s result: %s', name, exc)
        # The unchanged HapRay skill writes its response beside the report.
        # Accept it only for this exact stage, then preserve the stage cache.
        shared_result = self.output.with_name(self.output.stem + '_agent_result.json')
        if shared_result.is_file():
            try:
                payload = read_result(shared_result)
            except (ValueError, OSError, TypeError):
                pass
            else:
                _dump(result_path, {'request_id': request_id, 'payload': payload})
                return payload
        # External agent is authoritative when explicitly configured; no
        # unannounced provider fallback after its failure.
        execution_mode = str(os.environ.get('HAPRAY_ROOT_CAUSE_EXECUTION') or
                             self.cfg.get('analysis', {}).get('execution_mode') or 'agent').strip().lower()
        if self.execute is not None:
            self.execute(task_path, result_path, self.output)
        elif execution_mode in {'api', 'auto'} and is_llm_configured(self.cfg):
            try:
                raw = load_client_from_config(self.cfg).chat(task['system_prompt'], task['user_prompt'])
                _dump(result_path, _parse_object(raw))
            except Exception as exc:
                raise PendingStage(name, task_path, result_path, str(exc)) from exc
        try:
            return read_result()
        except (OSError, ValueError, TypeError) as exc:
            raise PendingStage(name, task_path, result_path, str(exc)) from exc


def _graph_snapshot(graph: EvidenceGraph) -> dict:
    return {'nodes': list(graph.nodes.values()), 'facts': list(graph.facts.values()),
            'edges': [edge for edges in graph.adjacency.values() for edge in edges],
            'rejected_edges': graph.rejected}


def _preview(graph: EvidenceGraph) -> dict:
    # Bounded initial context, full evidence is accessible through artifacts.
    ranked = sorted(graph.resources, key=lambda r: -r.get('inclusive_weight', 0))
    app = [r for r in ranked if graph.nodes[r['node']].get('source')]
    other = [r for r in ranked if not graph.nodes[r['node']].get('source')]
    resources = app[:36] + other[:24]
    ids = {r['node'] for r in resources}
    return {'resources': resources, 'nodes': [graph.nodes[n] for n in sorted(ids)],
            'full_resource_count': len(graph.resources), 'full_node_count': len(graph.nodes)}


def run_barney_analysis(*, report_dir: str, output_path: str, config: dict,
                        structured_evidence: dict, context_text: str, evidence_report: str,
                        source_dir: str | None = None, execute: Callable | None = None,
                        skip_llm: bool = False) -> str:
    output = Path(output_path)
    session = BarneySession(output, config, execute)
    runtime = build_runtime_evidence(report_dir)
    inventory = source_inventory(source_dir)
    fingerprint = _hash({'runtime': runtime, 'sections': structured_evidence, 'source': inventory,
                         'context': context_text})
    _dump(session.directory / 'runtime.json', runtime)
    _dump(session.directory / 'source_inventory.json', inventory)
    _dump(session.directory / 'signals.json', structured_evidence)
    graph = EvidenceGraph(runtime, structured_evidence.get('sections', {}))
    graph_path = session.directory / 'graph.json'
    _dump(graph_path, _graph_snapshot(graph))
    context = {'summary': context_text, 'source_dir': source_dir,
               'report_dir': str(Path(report_dir).resolve()), 'graph_file': str(graph_path.resolve()),
               'runtime_file': str((session.directory / 'runtime.json').resolve()),
               'signals_file': str((session.directory / 'signals.json').resolve()),
               'source_inventory_file': str((session.directory / 'source_inventory.json').resolve()),
               'preview': _preview(graph)}
    audit = {'engine': 'barney', 'input_fingerprint': fingerprint, 'stages': {}, 'runtime_errors': runtime['errors']}

    def incorporate(payload, stage):
        source = add_source_nodes(graph, payload.get('source_nodes', []), source_dir)
        edges = graph.add_dispatch_edges(payload.get('edges', []))
        audit['stages'][stage] = {'source': source, 'accepted_edges': edges}
        _dump(graph_path, _graph_snapshot(graph))

    try:
        grapher = session.stage('grapher', GRAPH_INSTRUCTIONS, context, fingerprint, export_only=skip_llm)
        incorporate(grapher, 'grapher')
        bridge_context = {**context, 'grapher_decision': grapher,
                          'grapher_validation': audit['stages']['grapher']}
        bridger = session.stage('bridger', BRIDGE_INSTRUCTIONS, bridge_context, fingerprint)
        incorporate(bridger, 'bridger')
        provisional = graph.rank(bridger['candidates'])
        focused = session.stage('grapher_focus', GRAPH_INSTRUCTIONS +
                                '\nFocus on the Bridger candidates and rejected/unreachable paths. '
                                'Repair only evidence-supported connections; do not manufacture reachability.',
                                {**context, 'bridger_decision': bridger, 'provisional': provisional,
                                 'source_validation': {k: v['source'] for k, v in audit['stages'].items()}}, fingerprint)
        incorporate(focused, 'grapher_focus')
        ranking = graph.rank(bridger['candidates'])
        rows = ranking['ranking']
        if not rows or ranking['rejected_candidates'] or (len(rows) > 1 and rows[0]['score'] == rows[1]['score']):
            refined = session.stage('refine', BRIDGE_INSTRUCTIONS +
                                    '\nUse the independently checked path/signal results to resolve ties '
                                    'or unsupported hypotheses. Verify counterevidence; do not inflate scores '
                                    'just to break a tie. This is the final bounded refinement.',
                                    {**context, 'prior': bridger, 'verification': ranking,
                                     'source_validation': {k: v['source'] for k, v in audit['stages'].items()}}, fingerprint)
            incorporate(refined, 'refine')
            bridger = refined
            ranking = graph.rank(refined['candidates'])
        audit['ranking'] = ranking
        suspects = []
        for chain in ranking['ranking'][:5]:
            node = graph.nodes[chain['sink']]
            loc = node.get('source') or {}
            suspects.append({'rank': len(suspects) + 1, 'category': chain.get('category', 'cpu-hotspot'),
                             'file': loc.get('source_path', ''), 'line_start': loc.get('line', 0),
                             'line_end': loc.get('line', 0), 'owner': loc.get('owner_name', ''),
                             'symbol': loc.get('symbol_name') or node.get('symbol', ''),
                             'confidence': 'high' if chain['confidence'] >= .8 else 'medium' if chain['confidence'] >= .5 else 'low',
                             'root_cause': chain['mechanism'], 'fix': chain.get('fix', ''),
                             'trigger_chain': ' → '.join(graph.nodes[n].get('symbol') or n for n in chain['path']),
                             'problematic_lines': [chain.get('resource_bridge', ''), chain.get('counterevidence', '')],
                             'evidence_ids': chain['resource_ids'], 'barney_score': chain['score']})
        caveats = list(bridger.get('caveats') or []) + runtime['caveats']
        if ranking['rejected_candidates']:
            caveats.append(f"Rejected unsupported candidates: {len(ranking['rejected_candidates'])} (see Barney audit).")
        if any((graph.nodes[c['sink']].get('source') or {}).get('kind') == 'disassembly' for c in ranking['ranking'][:5]):
            caveats.append('Locations ending in .pa are disassembly lines, not original source line numbers.')
        result = {'summary': suspects[0]['root_cause'] if suspects else 'No evidence-supported entry-to-sink explanation.',
                  'suspects': suspects, 'caveats': caveats, 'needs_more_data': [] if suspects else ['Additional source/dispatch/resource evidence'],
                  'engine': 'barney', 'input_fingerprint': fingerprint}
        _dump(output.parent / (output.stem + '_agent_result.json'), result)
        report = render_to_markdown(RootCauseResult.from_dict(result))
        audit['status'] = 'complete'
        (output.parent / 'root_cause_pending.json').unlink(missing_ok=True)
        output.with_name(output.stem + '_agent_task.json').unlink(missing_ok=True)
    except PendingStage as pending:
        audit.update(status='pending', pending_stage=pending.stage, reason=str(pending))
        marker = {'pending': True, 'engine': 'barney', 'stage': pending.stage,
                  'task': str(pending.task), 'result': str(pending.result), 'input_fingerprint': fingerprint}
        _dump(output.parent / 'root_cause_pending.json', marker)
        # Preserve the existing skill's complete task/result file contract.
        task_path = output.with_name(output.stem + '_agent_task.json')
        result_path = output.with_name(output.stem + '_agent_result.json')
        task = json.loads(pending.task.read_text(encoding='utf-8'))
        _dump(task_path, {**task, 'result_path': str(result_path), 'pending': True})
        report = ('# Root Cause Analysis (Pending Agent Inference)\n\n'
                  f'Barney stage: `{pending.stage}`.\n\nTask: `{task_path}`\n\n'
                  f'Write the fingerprinted response to `{result_path}` and rerun root-cause. '
                  f'Repeat for each pending stage until the report is complete.\n\n{pending}\n')
    _dump(session.directory / 'audit.json', audit)
    output.write_text(report, encoding='utf-8')
    output.with_name(output.stem + '_evidence.md').write_text(evidence_report, encoding='utf-8')
    return report
