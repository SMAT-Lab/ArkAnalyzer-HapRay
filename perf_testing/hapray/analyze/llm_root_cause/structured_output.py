"""
structured_output.py

定义 LLM 根因分析的结构化输出 Schema，并提供：
1. JSON Schema 定义（可注入 LLM prompt，要求 LLM 输出 JSON）
2. 从 LLM 输出文本中解析结构化结果
3. 将结构化结果渲染为最终 Markdown 报告

LLM 输出 Schema（JSON）：
{
  "summary": "一句话摘要",
  "suspects": [
    {
      "rank": 1,
      "file": "文件名",
      "line_start": 1644434,
      "line_end": 1644448,
      "owner": "SilkTNContainer",
      "symbol": "aboutToAppear",
      "confidence": "high|medium|low",
      "root_cause": "根因描述（1-2句）",
      "problematic_lines": ["具体问题行描述"],
      "fix": "具体修复建议（代码级）",
      "trigger_chain": "OS_VSyncThread → TARO_JS_0 → aboutToAppear"
    }
  ],
  "caveats": ["注意事项"],
  "needs_more_data": ["还需要哪些数据才能提高置信度"]
}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

# ── 数据模型 ──────────────────────────────────────────────────────────────


# 信号类别 → 中文章节标题（render 分章用；未知类别回退原值）
CATEGORY_LABELS: dict[str, str] = {
    'empty-frame': '空刷（Empty Frame）',
    'cpu-hotspot': 'CPU 高负载热点',
    'frame-load': '高负载帧',
    'component-reuse': '组件复用',
    'thread': '冗余线程',
    'ipc': 'IPC / Binder',
    'so-load': 'SO 文件负载',
    'memory': '内存',
    'frame-stats': '帧率 / RS / Vsync',
    'ui-animate': 'UI 动画 / 离树节点 / 超大图',
    'fault-hilog': '故障树 / Hilog',
}


@dataclass
class SuspectRecord:
    rank: int = 0
    category: str = 'empty-frame'  # 信号来源类别（见 CATEGORY_LABELS）
    file: str = ''
    line_start: int = 0
    line_end: int = 0
    owner: str = ''
    symbol: str = ''
    confidence: str = 'medium'  # "high" / "medium" / "low"
    root_cause: str = ''
    problematic_lines: list[str] = field(default_factory=list)
    fix: str = ''
    trigger_chain: str = ''
    code_snippet: str = ''  # 由 CodeSnippetExtractor 填充（非 LLM 输出）
    # 方向三：业务模块归因（由 get_module_attributions 填充，非 LLM 输出）
    module_package: str = ''  # 如 @jd-oh.business-poi
    module_version: str = ''  # 如 2.0.0
    business_domain: str = ''  # 如 地图/POI搜索

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SuspectRecord:
        return cls(
            rank=int(d.get('rank') or 0),
            category=str(d.get('category') or 'empty-frame'),
            file=str(d.get('file') or ''),
            line_start=int(d.get('line_start') or 0),
            line_end=int(d.get('line_end') or 0),
            owner=str(d.get('owner') or ''),
            symbol=str(d.get('symbol') or ''),
            confidence=str(d.get('confidence') or 'medium'),
            root_cause=str(d.get('root_cause') or ''),
            problematic_lines=list(d.get('problematic_lines') or []),
            fix=str(d.get('fix') or ''),
            trigger_chain=str(d.get('trigger_chain') or ''),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'rank': self.rank,
            'category': self.category,
            'file': self.file,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'owner': self.owner,
            'symbol': self.symbol,
            'confidence': self.confidence,
            'root_cause': self.root_cause,
            'problematic_lines': self.problematic_lines,
            'fix': self.fix,
            'trigger_chain': self.trigger_chain,
        }


@dataclass
class ObservationRecord:
    """现象类信号（帧率/UI/故障树等），无需源码 file:line。"""

    category: str = ''
    signal: str = ''  # 现象简称
    finding: str = ''  # 现象描述
    evidence: str = ''  # 支撑数据
    related_owner: str = ''  # 关联组件/SO/线程（可空）
    suggested_direction: str = ''  # 排查/优化方向

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ObservationRecord:
        return cls(
            category=str(d.get('category') or ''),
            signal=str(d.get('signal') or ''),
            finding=str(d.get('finding') or ''),
            evidence=str(d.get('evidence') or ''),
            related_owner=str(d.get('related_owner') or ''),
            suggested_direction=str(d.get('suggested_direction') or ''),
        )


@dataclass
class RootCauseResult:
    summary: str = ''
    suspects: list[SuspectRecord] = field(default_factory=list)
    observations: list[ObservationRecord] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    needs_more_data: list[str] = field(default_factory=list)
    raw_llm_text: str = ''  # 保留原始 LLM 输出，便于降级
    parse_success: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any], raw: str = '') -> RootCauseResult:
        if _looks_like_json_schema(d):
            return cls(raw_llm_text=raw, parse_success=False)
        suspects = [SuspectRecord.from_dict(s) for s in (d.get('suspects') or []) if isinstance(s, dict)]
        observations = [
            ObservationRecord.from_dict(o) for o in (d.get('observations') or []) if isinstance(o, dict)
        ]
        result = cls(
            summary=str(d.get('summary') or ''),
            suspects=suspects,
            observations=observations,
            caveats=list(d.get('caveats') or []),
            needs_more_data=list(d.get('needs_more_data') or []),
            raw_llm_text=raw,
            parse_success=True,
        )
        if not result_has_content(result):
            result.parse_success = False
        return result


# ── JSON Schema（注入 prompt 用）────────────────────────────────────────

OUTPUT_JSON_SCHEMA = {
    'type': 'object',
    'required': ['summary', 'suspects'],
    'properties': {
        'summary': {'type': 'string', 'description': '一句话根因摘要，含最值得修复的嫌疑函数和原因'},
        'suspects': {
            'type': 'array',
            'description': '按置信度排序的根因嫌疑列表（含源码定位），覆盖各信号类别',
            'items': {
                'type': 'object',
                'required': ['rank', 'category', 'owner', 'symbol', 'confidence', 'root_cause', 'fix'],
                'properties': {
                    'rank': {'type': 'integer', 'description': '排名，1 为最高优先级'},
                    'category': {
                        'type': 'string',
                        'description': '信号来源类别',
                        'enum': [
                            'empty-frame',
                            'cpu-hotspot',
                            'frame-load',
                            'component-reuse',
                            'thread',
                            'ipc',
                            'so-load',
                            'memory',
                        ],
                    },
                    'file': {'type': 'string', 'description': '源码文件名（无法定位则留空）'},
                    'line_start': {'type': 'integer', 'description': '代码起始行（无则 0）'},
                    'line_end': {'type': 'integer', 'description': '代码结束行（无则 0）'},
                    'owner': {'type': 'string', 'description': '类名/组件名/线程名/SO 名'},
                    'symbol': {'type': 'string', 'description': '方法名或符号'},
                    'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                    'root_cause': {'type': 'string', 'description': '根因描述，1-2 句'},
                    'problematic_lines': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': '代码中具体有问题的行或逻辑描述（引用实际代码）',
                    },
                    'fix': {'type': 'string', 'description': '代码级修复建议，尽量给出具体改法（伪代码或真实代码）'},
                    'trigger_chain': {'type': 'string', 'description': '触发链路，如 VSync → JS → 该函数'},
                },
            },
        },
        'observations': {
            'type': 'array',
            'description': '现象类信号（帧率/RS/Vsync、UI 动画、故障树/hilog 等），无需源码行',
            'items': {
                'type': 'object',
                'required': ['category', 'finding'],
                'properties': {
                    'category': {
                        'type': 'string',
                        'enum': ['frame-stats', 'ui-animate', 'fault-hilog'],
                    },
                    'signal': {'type': 'string', 'description': '现象简称'},
                    'finding': {'type': 'string', 'description': '现象描述（用数据说话）'},
                    'evidence': {'type': 'string', 'description': '支撑数据 / 来源'},
                    'related_owner': {'type': 'string', 'description': '关联组件/SO/线程（可空）'},
                    'suggested_direction': {'type': 'string', 'description': '排查或优化方向'},
                },
            },
        },
        'caveats': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': '注意事项：哪些结论需要人工验证，哪些证据不充分',
        },
        'needs_more_data': {
            'type': 'array',
            'items': {'type': 'string'},
            'description': '如果以下数据可用，可以进一步提高置信度',
        },
    },
}

OUTPUT_SCHEMA_STR = json.dumps(OUTPUT_JSON_SCHEMA, ensure_ascii=False, indent=2)

# 注入 prompt 的必须是「数据示例」，不能是 JSON Schema 元数据（否则模型会照抄 type/properties 结构）。
OUTPUT_EXAMPLE_DICT: dict[str, Any] = {
    'summary': '一句话摘要：最值得修复的嫌疑函数与原因',
    'suspects': [
        {
            'rank': 1,
            'category': 'cpu-hotspot',
            'file': 'src/main/ets/components/LyricsLineComponent.ts',
            'line_start': 1056,
            'line_end': 1056,
            'owner': 'LyricsLineComponent',
            'symbol': 'rerender',
            'confidence': 'high',
            'root_cause': '1-2 句根因描述',
            'problematic_lines': ['引用实际代码行或逻辑'],
            'fix': '具体修复建议（可含伪代码）',
            'trigger_chain': 'VSync → FlushBuild → LyricsLineComponent.rerender',
        },
    ],
    'observations': [
        {
            'category': 'frame-stats',
            'signal': '帧率',
            'finding': 'step5 平均 FPS 55，UI 卡顿率 0.66%',
            'evidence': 'trace_frames.json: avg_fps=55.04',
            'related_owner': '',
            'suggested_direction': '高刷下卡顿低但主线程负载极高，关注功耗',
        },
    ],
    'caveats': ['需人工验证的结论'],
    'needs_more_data': ['可选：补采哪些数据可提高置信度'],
}
OUTPUT_EXAMPLE_STR = json.dumps(OUTPUT_EXAMPLE_DICT, ensure_ascii=False, indent=2)


def _looks_like_json_schema(d: dict[str, Any]) -> bool:
    """模型误把 JSON Schema 当作输出体时，顶层含 type/properties 且无 summary。"""
    if not isinstance(d, dict):
        return False
    if 'summary' in d or 'suspects' in d:
        return False
    return d.get('type') == 'object' and isinstance(d.get('properties'), dict)


def result_has_content(result: RootCauseResult) -> bool:
    """解析成功但 summary/suspects/observations 皆空时视为无效（常见于 prompt 示例错误）。"""
    if not result.parse_success:
        return False
    if (result.summary or '').strip():
        return True
    if any(
        (s.root_cause or '').strip() or (s.owner or '').strip() or (s.symbol or '').strip() for s in result.suspects
    ):
        return True
    return any((o.finding or '').strip() for o in result.observations)


# ── 解析 ──────────────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r'```(?:json)?\s*(\{[\s\S]+?\})\s*```', re.DOTALL)
_BARE_JSON_RE = re.compile(r'\{[\s\S]+\}', re.DOTALL)


def parse_llm_output(text: str) -> RootCauseResult:
    """
    从 LLM 输出文本中提取结构化 JSON。
    策略：
    1. 优先提取 ```json ... ``` 代码块
    2. 再尝试提取裸 JSON 对象
    3. 失败则返回 parse_success=False，保留原始文本
    """
    if not text:
        return RootCauseResult(raw_llm_text=text, parse_success=False)

    # 尝试 ```json 块
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            d = json.loads(m.group(1))
            return RootCauseResult.from_dict(d, raw=text)
        except json.JSONDecodeError:
            pass

    # 尝试裸 JSON
    m = _BARE_JSON_RE.search(text)
    if m:
        try:
            d = json.loads(m.group(0))
            return RootCauseResult.from_dict(d, raw=text)
        except json.JSONDecodeError:
            pass

    return RootCauseResult(raw_llm_text=text, parse_success=False)


# ── 渲染为 Markdown ────────────────────────────────────────────────────────

_CONFIDENCE_ICON = {'high': '[HIGH]', 'medium': '[MED]', 'low': '[LOW]'}


def _render_suspect(lines: list[str], s: SuspectRecord) -> None:
    icon = _CONFIDENCE_ICON.get(s.confidence, '⚪')
    loc = f'{s.file}:{s.line_start}-{s.line_end}' if s.file else '位置未知（运行时符号/资源级）'
    lines.append(f'### {icon} #{s.rank}  {s.owner}.{s.symbol}')
    lines.append(f'- **位置**: `{loc}`')
    if s.business_domain or s.module_package:
        domain_str = s.business_domain or ''
        pkg_str = s.module_package or ''
        ver_str = f' @{s.module_version}' if s.module_version else ''
        lines.append(f'- **业务归属**: {domain_str}  (`{pkg_str}{ver_str}`)')
    lines.append(f'- **置信度**: {s.confidence}')
    if s.trigger_chain:
        lines.append(f'- **触发链路**: `{s.trigger_chain}`')
    lines.append(f'- **根因**: {s.root_cause}')
    if s.problematic_lines:
        lines.append('- **问题代码行**:')
        for pl in s.problematic_lines:
            lines.append(f'  - {pl}')
    if s.fix:
        lines.append('- **修复建议**:')
        lines.append('  ```typescript')
        lines.append(f'  {s.fix}')
        lines.append('  ```')
    if s.code_snippet:
        lines.append('')
        lines.append('**分析源码**：')
        lines.append('')
        lines.append('```typescript')
        lines.append(s.code_snippet.rstrip())
        lines.append('```')
    elif s.file and (s.file.endswith('.ets') or s.file.endswith('.ts')):
        lines.append('- **源码**: *(该嫌疑未附带代码片段)*')
    else:
        lines.append(
            '- **源码**: *(运行时符号/资源未映射到具体源码行，基于运行时证据推理；可借源码目录进一步定位调用点)*'
        )
    lines.append('')


def render_to_markdown(result: RootCauseResult) -> str:
    """
    将结构化分析结果渲染为最终 Markdown 报告。
    suspects 按信号类别（category）分章；observations 单列现象章节。
    若解析失败，直接返回 LLM 原始文本。
    """
    if not result.parse_success:
        return result.raw_llm_text or '（LLM 未返回有效输出）'

    lines: list[str] = []

    lines.append('# Root Cause Analysis Report')
    lines.append('')
    lines.append('## Executive Summary')
    lines.append(result.summary or '（无摘要）')
    lines.append('')

    if result.suspects:
        # 按 category 分组，保持 CATEGORY_LABELS 的顺序，未知类别追加在后
        order = list(CATEGORY_LABELS.keys())
        grouped: dict[str, list[SuspectRecord]] = {}
        for s in result.suspects:
            grouped.setdefault(s.category or 'empty-frame', []).append(s)
        ordered_cats = [c for c in order if c in grouped] + [c for c in grouped if c not in order]

        lines.append('## Top Suspects')
        lines.append('')
        for cat in ordered_cats:
            lines.append(f'## {CATEGORY_LABELS.get(cat, cat)}')
            lines.append('')
            for s in sorted(grouped[cat], key=lambda x: x.rank or 999):
                _render_suspect(lines, s)

    if result.observations:
        lines.append('## 现象观察（Observations）')
        lines.append('')
        order = list(CATEGORY_LABELS.keys())
        grouped_obs: dict[str, list[ObservationRecord]] = {}
        for o in result.observations:
            grouped_obs.setdefault(o.category or 'other', []).append(o)
        ordered_obs = [c for c in order if c in grouped_obs] + [c for c in grouped_obs if c not in order]
        for cat in ordered_obs:
            lines.append(f'### {CATEGORY_LABELS.get(cat, cat)}')
            for o in grouped_obs[cat]:
                head = o.signal or o.finding[:20]
                lines.append(f'- **{head}**：{o.finding}')
                if o.evidence:
                    lines.append(f'  - 证据：{o.evidence}')
                if o.related_owner:
                    lines.append(f'  - 关联：{o.related_owner}')
                if o.suggested_direction:
                    lines.append(f'  - 方向：{o.suggested_direction}')
            lines.append('')

    if result.caveats:
        lines.append('## Caveats')
        for c in result.caveats:
            lines.append(f'- {c}')
        lines.append('')

    if result.needs_more_data:
        lines.append('## 需要补充的数据')
        for d in result.needs_more_data:
            lines.append(f'- {d}')
        lines.append('')

    return '\n'.join(lines).strip() + '\n'


def render_fallback_markdown(result: RootCauseResult) -> str:
    """
    当 parse_success=False 时的降级处理：
    把 raw_llm_text 包装成标准报告格式返回。
    """
    lines = ['# Root Cause Analysis Report', '']
    lines.append('> ⚠️ LLM 输出未能解析为结构化 JSON，以下为原始文本输出。')
    lines.append('')
    lines.append(result.raw_llm_text or '（无输出）')
    return '\n'.join(lines)
