"""
prompts.py

LLM 提示词。支持两种模式：
  - analyze     : 默认模式，LLM 从原始证据独立推断根因（无需应用源码）
  - with_source : 增强模式，LLM 阅读源码片段 + 调用链，给出行级修复建议
"""

from __future__ import annotations

import copy
import json
from typing import Any

from .formatting import nonempty_thread_name, wakeup_chain_labels
from .proc_source_match import source_path_aligned
from .structured_output import OUTPUT_EXAMPLE_STR

# ── analyze 模式（默认，从证据推断根因）─────────────────────────────────────

_ANALYZE_SYSTEM_PROMPT_ZH = """你是 HarmonyOS / ArkUI 性能专家，专精空刷（empty frame）根因分析。

## 背景
空刷（empty frame）指 VSync 信号触发后，渲染系统完成了完整渲染流程，但最终提交帧与上一帧完全相同（无视觉变化），属于无效渲染。高占比空刷会持续浪费 CPU/GPU 资源并增加功耗。

## 你的任务
基于提供的性能采样证据，**独立推断**空刷根因，输出结构化 JSON 分析报告。
要求：**不要只是复述证据，要给出你的推断结论和具体的修复建议。**

## 证据解读指南
- `proc_source_hints`：从 /proc 虚拟文件系统捕获的用户态源码位置，是最直接的嫌疑代码线索
  - `direct_hit_count` 高 → 空刷帧 callchain 中直接命中，置信度最高
  - `perf_hit_count` 高 → 空刷帧时间窗口内的 perf 采样命中，置信度次之
  - `symbols` → 命中的函数名，判断是哪类入口（生命周期、渲染、数据回调等）
- `wakeup_threads`：VSync 帧的线程唤醒链，说明是哪个线程触发了这次渲染请求
- `symbol_hints`：帧内的关键系统符号，用于判断渲染触发路径类型
- `ui_snapshot_hints`：正在显示的 UI 组件名，用于定位问题所在的页面/组件上下文

## 常见根因模式（按优先级推断）

**模式 A：VSync/JS 持续驱动无效刷新**
- 信号：wakeup chain 含 `OS_VSyncThread → JS线程`，symbol_hints 含 `uv_run` / `RequestNextVSync`
- 原因：JS 事件循环（libuv）与 VSync 请求链持续触发，页面无变化仍持续刷新
- 嫌疑代码：/proc 命中的 JS 侧回调（`aboutToAppear`、`setInterval`、`requestAnimationFrame` 相关）

**模式 B：列表/数据源无差异重复渲染**
- 信号：/proc 命中含 `initialRender`、`build`、`ForEach`、`LazyForEach` 相关符号，UI 快照含 List/WaterFlow/Scroll 组件
- 原因：数据源无 diff 检查被整体重赋值，或父组件状态变化触发子组件整段重建
- 嫌疑代码：/proc 命中的列表渲染入口、`aboutToAppear` 中的无条件状态赋值

**模式 C：骨架屏/动画在静止时持续刷新**
- 信号：/proc 命中含 `skeleton`、`animation`、`Gradient`、`Lottie` 等符号
- 原因：骨架屏动画或 Lottie 动画在内容加载完成后仍持续请求 VSync
- 嫌疑代码：/proc 命中的动画回调、skeleton 渲染入口

**模式 D：WebView/Hybrid 驱动的跨侧刷新**
- 信号：symbol_hints 含 `uv_run`，UI 快照含 Web/Hybrid 相关组件名，/proc 命中含 bridge 相关
- 原因：H5 页面轮询、前端动画或 JS Bridge 回调在页面静止时仍持续写 ArkUI 状态

## 置信度标准
- `high`：2+ 条独立证据（直接 callchain 命中 + perf 命中 + UI 快照吻合）指向同一根因
- `medium`：有 1 条主要证据，其他为间接支持
- `low`：仅靠组件/文件名推断，无直接调用链证据

## 输出格式
**必须输出合法 JSON**（不要输出其他内容）：
{OUTPUT_SCHEMA}
"""

_ANALYZE_SYSTEM_PROMPT_EN = """You are a HarmonyOS / ArkUI performance expert specializing in empty-frame root cause analysis.

## Background
An empty frame occurs when a VSync signal triggers a complete rendering pass but the submitted frame is identical to the previous one (no visual change) — wasted CPU/GPU work.

## Your Task
Based on the provided performance sampling evidence, **independently reason** about the root cause and output a structured JSON analysis report.
**Do not merely restate the evidence — provide your diagnostic conclusions and concrete fix recommendations.**

## Evidence Guide
- `proc_source_hints`: User-space source locations captured via /proc — the most direct suspect code pointers
  - `direct_hit_count`: Directly found in empty-frame callchain (highest confidence)
  - `perf_hit_count`: Found in perf samples near the empty frame (medium confidence)
  - `symbols`: Hit function names (lifecycle entries, render callbacks, data handlers, etc.)
- `wakeup_threads`: Thread wakeup chain for representative frames — which thread triggered the render
- `symbol_hints`: Key system symbols in the frame — identifies the rendering trigger path
- `ui_snapshot_hints`: Currently visible UI component names — context for the affected page/component

## Common Root Cause Patterns

**Pattern A: VSync/JS continuous spurious refresh**
- Signals: wakeup chain has `OS_VSyncThread → JS thread`, symbol_hints has `uv_run` / `RequestNextVSync`
- Cause: JS event loop (libuv) keeps requesting VSync even when nothing changes

**Pattern B: List/data source re-rendering without diff**
- Signals: /proc hits contain `initialRender`, `build`, `ForEach`, `LazyForEach`; UI has List/WaterFlow
- Cause: Data source re-assigned without equality check, triggering full list rebuild

**Pattern C: Skeleton/animation refresh while page is idle**
- Signals: /proc hits contain `skeleton`, `animation`, `Gradient`
- Cause: Skeleton screen or Lottie animation keeps requesting VSync after content is loaded

**Pattern D: WebView/Hybrid cross-side refresh**
- Signals: `uv_run` in symbol_hints; Web/Hybrid components in UI snapshot
- Cause: H5 polling or JS Bridge callbacks writing ArkUI state while page is visually idle

## Output Format
Output valid JSON only (no other text):
{OUTPUT_SCHEMA}
"""


# ── with_source 模式（增强，需应用源码）────────────────────────────────────

_CODE_REVIEW_SYSTEM_PROMPT_ZH = """你是一名 HarmonyOS / ArkUI 性能专家，专精空刷（empty frame）根因分析。

## 你的任务
结合性能采样证据、源码片段（部分嫌疑有，部分无）和调用链路，输出**覆盖所有嫌疑**的结构化 JSON 根因报告。

## 混合分析规则（重要）

你会收到两类嫌疑，必须都分析，不得遗漏：

### 类型 A：有源码片段的嫌疑（出现在"源码片段"节）
- 基于实际代码给出行级诊断，修复建议引用代码中的具体行/变量名
- 置信度标准：`high`（发现明确问题模式）/ `medium`（有嫌疑待确认）/ `low`（代码可读性低）

### 类型 B：无源码但有证据的嫌疑（出现在"无源码嫌疑"节）
- 无法读取源码，基于 /proc 命中、符号名、唤醒链独立推断
- 修复建议仍须具体到函数名和修复方向（不能只说"需要检查"）
- 置信度标准：`medium`（有直接 callchain 命中）/ `low`（仅 perf 采样或符号名推断）
- **不要** 以"未提供代码无法分析"为由跳过这类嫌疑，必须给出推断结论

## 代码审查要点（类型 A）
重点检查以下空刷根因模式：
- `aboutToAppear` / 生命周期方法里无 diff 的状态重赋值
- `setInterval` / `requestAnimationFrame` / VSync 回调无条件触发 UI 更新
- `ForEach` / `LazyForEach` 数据源整体重赋值（对象引用变化导致全量重建）
- 父组件状态变化导致子组件整段重建（无 `@Reusable` / 无 key 隔离）
- JS Bridge 回调在页面静止时仍持续写状态

## 证据推断要点（类型 B）
- `direct_hit_count` 高 → callchain 直接命中，优先视为真实嫌疑
- 符号名含 `onFrame` / `requestAnimationFrame` → 动画/VSync 循环
- 符号名含 `aboutToAppear` / `initialRender` → 生命周期无 diff 重建
- 结合唤醒链（wakeup_threads）判断触发路径

## 输出格式
**必须输出合法 JSON**（不要输出其他内容）：

```json
{OUTPUT_SCHEMA}
```
"""

_CODE_REVIEW_SYSTEM_PROMPT_EN = """You are a HarmonyOS / ArkUI performance expert specializing in empty-frame root cause analysis.

## Your Task
Analyze ALL suspects using both source code snippets (where available) and evidence-based
reasoning (where code is unavailable). Output a comprehensive structured JSON root cause report.

## Hybrid Analysis Rules (Important)

You will receive two types of suspects — analyze BOTH, do not skip either:

### Type A: Suspects WITH source code snippets (in the "Source Code Snippets" section)
- Give line-level diagnosis based on actual code; fix recommendations must reference specific lines
- Confidence: high (clear problem found) / medium (suspicious, needs verification)

### Type B: Suspects WITHOUT source code (in the "Evidence-Only Suspects" section)
- No code available; reason from /proc hits, symbol names, and wakeup chains
- Still provide specific fix direction (function name + what to check)
- Confidence: medium (direct callchain hit) / low (perf sample or name-based inference)
- Do NOT skip these suspects with "code unavailable" — provide your best inference

## Output Format
Output valid JSON only:

```json
{OUTPUT_SCHEMA}
```
"""


def _analyze_system_prompt(language: str, domain_knowledge: str = '') -> str:
    base = _ANALYZE_SYSTEM_PROMPT_ZH if language == 'zh' else _ANALYZE_SYSTEM_PROMPT_EN
    base = base.replace('{OUTPUT_SCHEMA}', OUTPUT_EXAMPLE_STR)
    if domain_knowledge and domain_knowledge.strip():
        section_title = '## 领域先验知识\n\n以下是人工积累的分析经验，请在推断根因时参考：\n\n'
        base = base.rstrip() + '\n\n' + section_title + domain_knowledge.strip() + '\n'
    return base


def _with_source_system_prompt(language: str, domain_knowledge: str = '') -> str:
    base = _CODE_REVIEW_SYSTEM_PROMPT_ZH if language == 'zh' else _CODE_REVIEW_SYSTEM_PROMPT_EN
    base = base.replace('{OUTPUT_SCHEMA}', OUTPUT_EXAMPLE_STR)
    if domain_knowledge and domain_knowledge.strip():
        section_title = '## 领域先验知识\n\n以下是人工积累的分析经验，请在审查代码时参考：\n\n'
        base = base.rstrip() + '\n\n' + section_title + domain_knowledge.strip() + '\n'
    return base


# ── comprehensive 模式（多信号全面根因，不限空刷）──────────────────────────

_COMPREHENSIVE_SYSTEM_PROMPT_ZH = """你是 HarmonyOS / ArkUI 性能根因专家，做**多信号全面根因分析**（不限空刷）。

## 你的任务
你会收到按信号类别（category）分章的性能证据，**每一类都要评估**，输出结构化 JSON 根因报告。
要求：**不要只复述证据，要给出推断结论和具体修复建议。** 每条根因须标明它来自哪个 `category`。

## 信号类别与解读
**suspect 类（可定位源码，进 `suspects`，须带 category 与尽量准确的 file/line/owner/symbol）**
- `cpu-hotspot`：perf.db inclusive 聚合的高指令数函数。**ArkTS 帧符号自带 `源码:行`**，是最准的源码级根因——优先分析。叶子帧多归于 appspawn（字节码/JIT）属正常，以调用链聚合为准。
- `frame-load`：高负载帧（flag=1 高负载 / 2 空刷），关注 max_load 与主线程帧。
- `component-reuse`：复用率低（reusability_ratio 小）且 build 多的组件 → 对应 `.ets` 文件。
- `thread`：冗余线程（若 has_redundancy=false / 各 step 为 0，则线程健康，写明“无冗余线程问题”即可，不要编造）。
- `ipc`：高 QPS/事务数的进程对。**常是每帧 rerender 的下游表现**，优先核对是否由 UI 高负载驱动，而非独立根因。
- `so-load`：原生库高负载（无源码行），可与 cpu-hotspot 交叉；第三方/旧库可提优化方向。
- `memory`：高分配组件（componentName 可映射 ArkTS）。
- `empty-frame`（可选，可能缺失）：空刷帧，proc_source_hints 含 `源码:行`。**缺失时不要假设有空刷问题。**

**observation 类（现象，无源码行，进 `observations`）**
- `frame-stats`：FPS、卡顿率、RS skip、vsync 异常 → 描述现象（如“高刷下卡顿低但主线程负载极高，关注功耗”）。
- `ui-animate`：离树节点占比、超大图片、动画帧。
- `fault-hilog`：故障树分解、hilog 规则命中（如图片未用 DMA）。

## 分析原则
- **以 cpu-hotspot 为主线**：它直接给出占指令数最高的源码函数；其余信号多为其表现或补充。
- **去重合并**：若多个信号指向同一源码点，合并为一条，证据取并集。
- **诚实**：信号为 0 / 健康时如实写明，不要凑数编造根因。observation 类不要硬塞 file:line。
- **置信度**：`high`=多源证据指向同一源码点；`medium`=单一主证据；`low`=仅名称/现象推断。

## 输出格式
**必须输出合法 JSON**（不要输出其他内容；suspects 每条含 `category`，observations 每条含 `category`+`finding`）：

```json
{OUTPUT_SCHEMA}
```
"""

_COMPREHENSIVE_SYSTEM_PROMPT_EN = """You are a HarmonyOS / ArkUI performance root-cause expert doing **multi-signal comprehensive analysis** (not limited to empty frames).

## Your Task
You receive performance evidence grouped by signal `category`. Evaluate EVERY category and output a
structured JSON root-cause report. Do not merely restate evidence — give conclusions and concrete fixes.
Each root cause must state its source `category`.

## Signal categories
suspect (source-locatable → `suspects`, each with category + file/line/owner/symbol when possible):
- `cpu-hotspot`: top instruction-count functions from perf.db inclusive aggregation. ArkTS frame symbols
  carry `source:line` — the most accurate source-level root cause; analyze first.
- `frame-load`, `component-reuse`, `thread`, `ipc`, `so-load`, `memory`, `empty-frame` (optional, may be absent).

observation (phenomena, no source line → `observations`): `frame-stats`, `ui-animate`, `fault-hilog`.

## Principles
- Make cpu-hotspot the main thread of analysis; dedupe signals pointing at the same source location.
- Be honest: if a signal is zero/healthy, say so; don't fabricate. Don't force file:line on observations.

## Output Format
Output valid JSON only:

```json
{OUTPUT_SCHEMA}
```
"""


def _comprehensive_system_prompt(language: str, domain_knowledge: str = '') -> str:
    base = _COMPREHENSIVE_SYSTEM_PROMPT_ZH if language == 'zh' else _COMPREHENSIVE_SYSTEM_PROMPT_EN
    base = base.replace('{OUTPUT_SCHEMA}', OUTPUT_EXAMPLE_STR)
    if domain_knowledge and domain_knowledge.strip():
        section_title = '## 领域先验知识\n\n以下是人工积累的分析经验，请参考：\n\n'
        base = base.rstrip() + '\n\n' + section_title + domain_knowledge.strip() + '\n'
    return base


def _build_comprehensive_user_prompt(
    context_text: str,
    structured_evidence: dict[str, Any] | None,
    code_snippets: list[dict[str, Any]] | None = None,
) -> str:
    """comprehensive 模式 user prompt：按 category 分章渲染证据 + 源码片段。"""
    parts: list[str] = []
    parts.append('请对以下**多信号**性能证据做全面根因分析（不限空刷），逐类评估并推断根因。\n')
    parts.append('## 性能摘要\n')
    parts.append(context_text)

    sections = (structured_evidence or {}).get('sections', {})
    if sections:
        parts.append('\n## 分信号证据（按 category 分章）\n')
        for cat, sec in sections.items():
            kind = sec.get('kind', '')
            parts.append(f'\n### [{kind}] {cat}\n')
            parts.append('```json')
            payload = {
                'category': sec.get('category', cat),
                'kind': kind,
                'summary': sec.get('summary', {}),
                'items': (sec.get('items') or [])[:15],
            }
            for extra_key in ('dominant_threads', 'representative_frames', 'caveats'):
                if sec.get(extra_key):
                    payload[extra_key] = sec[extra_key]
            parts.append(json.dumps(payload, ensure_ascii=False, indent=2))
            parts.append('```')

    if code_snippets:
        parts.append('\n## 关联源码片段（请在分析中直接引用相关代码行）\n')
        for i, item in enumerate(code_snippets[:12], 1):
            owner = item.get('owner_name', 'unknown')
            symbol = item.get('symbol_name', 'unknown')
            file_name = item.get('file', 'unknown')
            line_start = item.get('line_start', 0)
            cat = item.get('category', '')
            snippet = item.get('code_snippet') or ''
            parts.append(f'### [{i}] {owner}.{symbol}  ({file_name}:{line_start})  [{cat}]\n')
            if snippet.strip():
                parts.append('```typescript')
                parts.append(snippet.rstrip())
                parts.append('```\n')

    parts.append('\n请输出 JSON 根因报告（suspects 每条含 category；observations 单列现象），不要输出其他内容。')
    return '\n'.join(parts).strip() + '\n'


# ── 公共接口 ──────────────────────────────────────────────────────────────


def get_system_prompt(
    language: str = 'zh',
    checker: str = 'empty-frame',
    mode: str = 'analyze',
    domain_knowledge: str = '',
) -> str:
    """
    Parameters
    ----------
    mode : "analyze" | "with_source"
        - analyze     : 默认模式，LLM 从原始证据独立推断，输出结构化 JSON
        - with_source : 增强模式，LLM 阅读源码片段，给出行级修复建议
    domain_knowledge : str
        从 knowledge/ 目录加载的先验知识文本，注入 system prompt。
    """
    if checker == 'comprehensive':
        return _comprehensive_system_prompt(language, domain_knowledge=domain_knowledge)
    if mode == 'with_source':
        return _with_source_system_prompt(language, domain_knowledge=domain_knowledge)
    return _analyze_system_prompt(language, domain_knowledge=domain_knowledge)


def build_user_prompt(
    context_text: str,
    extra_context: str = '',
    checker: str = 'empty-frame',
    structured_evidence: dict[str, Any] | None = None,
    code_snippets: list[dict[str, Any]] | None = None,
    call_chains_text: str = '',
    mode: str = 'analyze',
) -> str:
    """
    构建 user prompt。

    mode="analyze"     : 传入结构化证据 JSON（+ 可选代码片段），LLM 独立推断根因
    mode="with_source" : 传入代码片段 + 调用链 + 精简证据，LLM 阅读代码给出行级建议
    """
    if checker == 'comprehensive':
        return _build_comprehensive_user_prompt(
            context_text=context_text,
            structured_evidence=structured_evidence,
            code_snippets=code_snippets or [],
        )
    if mode == 'with_source':
        return _build_with_source_user_prompt(
            context_text=context_text,
            code_snippets=code_snippets or [],
            call_chains_text=call_chains_text,
            structured_evidence=structured_evidence,
        )
    return _build_analyze_user_prompt(
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets or [],
        extra_context=extra_context,
    )


def _build_analyze_user_prompt(
    context_text: str,
    structured_evidence: dict[str, Any] | None,
    code_snippets: list[dict[str, Any]] | None = None,
    extra_context: str = '',
) -> str:
    """analyze 模式的 user prompt：传入完整结构化证据（+ 可选代码片段），LLM 独立推断。"""
    parts: list[str] = []
    parts.append('请分析以下空刷性能证据，推断根因并给出修复建议。\n')

    parts.append('## 性能摘要\n')
    parts.append(context_text)

    if structured_evidence:
        # 传入精简版结构化证据（省略 code_snippet 内容，避免重复且节省 token）
        ev_clean = _strip_code_snippets_from_evidence(structured_evidence)
        parts.append('\n## 结构化证据\n')
        parts.append('```json')
        parts.append(json.dumps(ev_clean, ensure_ascii=False, indent=2))
        parts.append('```')

    # 如果有源码，单独展示供 LLM 直接引用
    if code_snippets:
        parts.append('\n## 源码片段（请在分析中直接引用相关代码行）\n')
        for i, item in enumerate(code_snippets[:6], 1):
            owner = item.get('owner_name', 'unknown')
            symbol = item.get('symbol_name', 'unknown')
            file_name = item.get('file', 'unknown')
            line_start = item.get('line_start', 0)
            line_end = item.get('line_end', 0)
            snippet = item.get('code_snippet') or ''
            hits = item.get('evidence_hits', item.get('hit_count', 0))
            parts.append(f'### [{i}] {owner}.{symbol}  ({file_name}:{line_start}-{line_end}, 命中次数={hits})\n')
            if snippet.strip():
                parts.append('```typescript')
                parts.append(snippet.rstrip())
                parts.append('```\n')

    if extra_context:
        parts.append(f'\n## 补充信息\n{extra_context}\n')

    parts.append('\n请输出 JSON 根因报告，不要输出其他内容。')
    return '\n'.join(parts).strip() + '\n'


def _strip_code_snippets_from_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """
    Return a shallow copy of evidence with code_snippet fields removed from
    proc_source_hints.source_candidates to avoid duplicating large code blocks
    when they're already shown in a dedicated section.
    """
    ev = copy.copy(evidence)
    hints = evidence.get('proc_source_hints')
    if hints:
        clean_hints = []
        for h in hints:
            h2 = copy.copy(h)
            cands = h.get('source_candidates')
            if cands:
                h2['source_candidates'] = [{k: v for k, v in c.items() if k != 'code_snippet'} for c in cands]
            clean_hints.append(h2)
        ev['proc_source_hints'] = clean_hints
    return ev


def _build_with_source_user_prompt(
    context_text: str,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
    structured_evidence: dict[str, Any] | None,
) -> str:
    """with_source 模式的 user prompt 构建。"""
    parts: list[str] = []
    parts.append('请分析以下空刷性能问题，输出结构化 JSON 根因报告。\n')

    parts.append('## 性能摘要\n')
    parts.append(context_text)

    # 精简证据摘要（只取最关键字段，减少 token 噪声）
    if structured_evidence:
        overview = structured_evidence.get('overview', {})
        dominant = structured_evidence.get('dominant_threads', [])[:3]
        frames = structured_evidence.get('representative_frames', [])[:1]
        proc_hints = structured_evidence.get('proc_source_hints', [])[:8]
        compact: dict[str, Any] = {
            'empty_frames': overview.get('total_empty_frames'),
            'empty_rate': overview.get('empty_frame_percentage'),
            'severity': overview.get('severity_level'),
            'main_thread_pct': overview.get('main_thread_percentage_in_empty_frame'),
            'top_threads': [name for t in dominant if (name := nonempty_thread_name(t.get('thread_name')))],
        }
        if frames:
            compact['top_frame_wakeup'] = wakeup_chain_labels(
                frames[0].get('wakeup_threads'),
                limit=4,
            )
            compact['top_frame_symbols'] = frames[0].get('symbol_hints', [])[:4]
        if proc_hints:
            compact['proc_source_hits'] = [
                {
                    'source': h.get('source_path', ''),
                    'lines': h.get('lines', [])[:4],
                    'symbols': h.get('symbols', [])[:4],
                    'direct': h.get('direct_hit_count', 0),
                    'perf': h.get('perf_hit_count', 0),
                }
                for h in proc_hints
            ]
        parts.append('\n## 关键证据\n')
        parts.append('```json')
        parts.append(json.dumps(compact, ensure_ascii=False, indent=2))
        parts.append('```')

    # 调用链路
    if call_chains_text and call_chains_text.strip():
        parts.append('\n## 触发调用链路\n')
        parts.append(call_chains_text)

    # 类型 A：有源码的嫌疑（行级分析）
    if code_snippets:
        parts.append('\n## 源码片段（类型 A 嫌疑）\n')
        parts.append('以下嫌疑有应用源码，请做行级代码审查：\n')
        for i, item in enumerate(code_snippets[:8], 1):
            owner = item.get('owner_name', 'unknown')
            symbol = item.get('symbol_name', 'unknown')
            file_name = item.get('file', 'unknown')
            line_start = item.get('line_start', 0)
            line_end = item.get('line_end', 0)
            snippet = item.get('code_snippet') or ''
            evidence_hits = item.get('evidence_hits', 0)
            match_kind = item.get('match_kind', '')

            parts.append(f'### 片段 {i}: {owner}.{symbol}')
            parts.append(f'- 文件: `{file_name}:{line_start}-{line_end}`')
            if match_kind:
                parts.append(f'- 关联方式: {match_kind}')
            if evidence_hits:
                parts.append(f'- 证据命中次数: {evidence_hits}')
            ui_count = item.get('ui_snapshot_count')
            if ui_count:
                parts.append(f'- UI 运行态出现次数: {ui_count}')
            if snippet:
                parts.append('```typescript')
                parts.append(snippet)
                parts.append('```')
            else:
                parts.append('（代码片段不可用）')
            parts.append('')

    # 类型 B：无源码但有证据的嫌疑（基于证据推断）
    evidence_only = _collect_evidence_only_suspects(
        proc_hints=structured_evidence.get('proc_source_hints', []) if structured_evidence else [],
        code_snippets=code_snippets,
    )
    if evidence_only:
        parts.append('\n## 无源码嫌疑（类型 B 嫌疑）\n')
        parts.append(
            '以下嫌疑有 /proc 命中证据，但无应用源码可读。'
            '请基于文件名、符号名和命中计数进行证据推断，**必须给出根因结论和修复方向**：\n'
        )
        for hint in evidence_only:
            path_short = hint.get('source_path', '').rsplit('/', 1)[-1] or hint.get('owner_name', 'unknown')
            lines_str = '/'.join(str(ln) for ln in hint.get('lines', [])[:4])
            syms = ', '.join(hint.get('symbols', [])[:4])
            parts.append(
                f'- `{path_short}:{lines_str}` '
                f'hits={hint.get("hit_count", 0)} '
                f'(direct={hint.get("direct_hit_count", 0)}, perf={hint.get("perf_hit_count", 0)})'
            )
            if syms:
                parts.append(f'  symbols: {syms}')

    parts.append('\n请输出 JSON 根因报告，不要输出其他内容。')
    return '\n'.join(parts).strip() + '\n'


def _collect_evidence_only_suspects(
    proc_hints: list[dict[str, Any]],
    code_snippets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    从 proc_source_hints 中找出没有对应源码片段的高信号嫌疑，
    供 with_source 模式以证据推断方式分析。
    """
    result = []
    for hint in proc_hints:
        if any(source_path_aligned(s.get('file', ''), hint.get('source_path', '')) for s in code_snippets):
            continue
        candidates = hint.get('source_candidates') or []
        if any(
            source_path_aligned(c.get('file', ''), hint.get('source_path', ''))
            for c in candidates
            if c.get('code_snippet')
        ):
            continue
        if hint.get('direct_hit_count', 0) >= 1 or hint.get('hit_count', 0) >= 3:
            result.append(hint)

    return result[:4]
