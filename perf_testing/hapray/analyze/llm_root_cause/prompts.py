"""
prompts.py

LLM 提示词。支持两种模式：
  - analyze     : 默认模式，LLM 从原始证据独立推断根因（无需反编译代码）
  - with_source : 增强模式，LLM 阅读反编译代码片段 + 调用链，给出行级修复建议
"""

from __future__ import annotations

import json
from typing import Any

from .structured_output import OUTPUT_SCHEMA_STR


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


# ── with_source 模式（增强，需反编译源码）────────────────────────────────────

_CODE_REVIEW_SYSTEM_PROMPT_ZH = """你是一名 HarmonyOS / ArkUI 性能专家，专精空刷（empty frame）根因分析。

## 你的任务
阅读提供的「反编译代码片段」和「调用链路」，结合性能证据，输出结构化 JSON 根因报告。

## 分析要点
1. **代码审查**：重点检查以下模式（常见空刷根因）：
   - `aboutToAppear` / 生命周期方法里无 diff 的状态重赋值（每次都 `this.xxx = newVal`）
   - `setInterval` / `requestAnimationFrame` / VSync 回调里无条件触发 UI 更新
   - `ForEach` / `LazyForEach` 数据源引用变化（对象重建而非原地修改）
   - 父组件状态变化导致子组件整段重建（无 `@Reusable` 或无 key 隔离）
   - JS Bridge 回调在页面静止时仍持续写状态
2. **调用链路**：确认触发路径是否合理（VSync → JS → ArkUI → 嫌疑函数）
3. **置信度判断**：
   - `high`：代码中明确存在问题模式 + 调用链命中
   - `medium`：代码有嫌疑但需人工确认 / 调用链不完整
   - `low`：仅靠名字关联，未见明确问题代码

## 强约束
- 只分析提供的代码片段，不得编造未出现的代码
- 修复建议必须基于代码片段中的实际代码（引用具体行或变量名）
- 如果代码片段为空或不可读，置信度设为 `low` 并在 caveats 中说明

## 输出格式
**必须输出合法 JSON**，格式如下（不要输出其他内容）：

```json
{OUTPUT_SCHEMA}
```
"""

_CODE_REVIEW_SYSTEM_PROMPT_EN = """You are a HarmonyOS / ArkUI performance expert specializing in empty-frame root cause analysis.

## Your Task
Read the provided decompiled code snippets and call chains, combine them with performance evidence,
and output a structured JSON root cause report.

## Analysis Focus
Look for these common empty-frame root causes:
- Unconditional state re-assignment in lifecycle methods (no diff check)
- setInterval / requestAnimationFrame callbacks that trigger UI updates unconditionally
- ForEach / LazyForEach data source reference changes causing full rebuild
- Parent state changes causing child component full reconstruction
- JS Bridge callbacks writing state even when page is visually idle

## Output Format
Output valid JSON only, matching this schema:

```json
{OUTPUT_SCHEMA}
```
"""


def _analyze_system_prompt(language: str, domain_knowledge: str = "") -> str:
    base = _ANALYZE_SYSTEM_PROMPT_ZH if language == "zh" else _ANALYZE_SYSTEM_PROMPT_EN
    base = base.replace("{OUTPUT_SCHEMA}", OUTPUT_SCHEMA_STR)
    if domain_knowledge and domain_knowledge.strip():
        section_title = "## 领域先验知识\n\n以下是人工积累的分析经验，请在推断根因时参考：\n\n"
        base = base.rstrip() + "\n\n" + section_title + domain_knowledge.strip() + "\n"
    return base


def _with_source_system_prompt(language: str, domain_knowledge: str = "") -> str:
    base = _CODE_REVIEW_SYSTEM_PROMPT_ZH if language == "zh" else _CODE_REVIEW_SYSTEM_PROMPT_EN
    base = base.replace("{OUTPUT_SCHEMA}", OUTPUT_SCHEMA_STR)
    if domain_knowledge and domain_knowledge.strip():
        section_title = "## 领域先验知识\n\n以下是人工积累的分析经验，请在审查代码时参考：\n\n"
        base = base.rstrip() + "\n\n" + section_title + domain_knowledge.strip() + "\n"
    return base


# ── 公共接口 ──────────────────────────────────────────────────────────────

def get_system_prompt(
    language: str = "zh",
    checker: str = "empty-frame",
    mode: str = "analyze",
    domain_knowledge: str = "",
) -> str:
    """
    Parameters
    ----------
    mode : "analyze" | "with_source"
        - analyze     : 默认模式，LLM 从原始证据独立推断，输出结构化 JSON
        - with_source : 增强模式，LLM 阅读反编译代码片段，给出行级修复建议
    domain_knowledge : str
        从 knowledge/ 目录加载的先验知识文本，注入 system prompt。
    """
    if mode == "with_source":
        return _with_source_system_prompt(language, domain_knowledge=domain_knowledge)
    return _analyze_system_prompt(language, domain_knowledge=domain_knowledge)


def build_user_prompt(
    context_text: str,
    extra_context: str = "",
    checker: str = "empty-frame",
    structured_evidence: dict[str, Any] | None = None,
    # with_source 模式新增字段
    code_snippets: list[dict[str, Any]] | None = None,
    call_chains_text: str = "",
    mode: str = "analyze",
) -> str:
    """
    构建 user prompt。

    mode="analyze"     : 传入结构化证据 JSON，LLM 独立推断根因
    mode="with_source" : 传入代码片段 + 调用链 + 精简证据，LLM 阅读代码给出行级建议
    """
    if mode == "with_source":
        return _build_with_source_user_prompt(
            context_text=context_text,
            code_snippets=code_snippets or [],
            call_chains_text=call_chains_text,
            structured_evidence=structured_evidence,
        )
    return _build_analyze_user_prompt(
        context_text=context_text,
        structured_evidence=structured_evidence,
        extra_context=extra_context,
    )


def _build_analyze_user_prompt(
    context_text: str,
    structured_evidence: dict[str, Any] | None,
    extra_context: str = "",
) -> str:
    """analyze 模式的 user prompt：传入完整结构化证据，LLM 独立推断。"""
    parts: list[str] = []
    parts.append("请分析以下空刷性能证据，推断根因并给出修复建议。\n")

    parts.append("## 性能摘要\n")
    parts.append(context_text)

    if structured_evidence:
        # 传入完整结构化证据（proc_source_hints、wakeup chains、UI snapshot 等）
        parts.append("\n## 结构化证据\n")
        parts.append("```json")
        parts.append(json.dumps(structured_evidence, ensure_ascii=False, indent=2))
        parts.append("```")

    if extra_context:
        parts.append(f"\n## 补充信息\n{extra_context}\n")

    parts.append("\n请输出 JSON 根因报告，不要输出其他内容。")
    return "\n".join(parts).strip() + "\n"


def _build_with_source_user_prompt(
    context_text: str,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
    structured_evidence: dict[str, Any] | None,
) -> str:
    """with_source 模式的 user prompt 构建。"""
    parts: list[str] = []
    parts.append("请分析以下空刷性能问题，输出结构化 JSON 根因报告。\n")

    parts.append("## 性能摘要\n")
    parts.append(context_text)

    # 精简证据摘要（只取最关键字段，减少 token 噪声）
    if structured_evidence:
        overview = structured_evidence.get("overview", {})
        dominant = structured_evidence.get("dominant_threads", [])[:3]
        frames = structured_evidence.get("representative_frames", [])[:1]
        proc_hints = structured_evidence.get("proc_source_hints", [])[:5]
        compact: dict[str, Any] = {
            "empty_frames": overview.get("total_empty_frames"),
            "empty_rate": overview.get("empty_frame_percentage"),
            "severity": overview.get("severity_level"),
            "main_thread_pct": overview.get("main_thread_percentage_in_empty_frame"),
            "top_threads": [t.get("thread_name") for t in dominant],
        }
        if frames:
            compact["top_frame_wakeup"] = [
                w.get("thread_name")
                for w in (frames[0].get("wakeup_threads") or [])[:4]
            ]
            compact["top_frame_symbols"] = frames[0].get("symbol_hints", [])[:4]
        if proc_hints:
            compact["proc_source_hits"] = [
                {
                    "source": h.get("source_path", ""),
                    "lines": h.get("lines", [])[:4],
                    "symbols": h.get("symbols", [])[:4],
                    "direct": h.get("direct_hit_count", 0),
                    "perf": h.get("perf_hit_count", 0),
                }
                for h in proc_hints
            ]
        parts.append("\n## 关键证据\n")
        parts.append("```json")
        parts.append(json.dumps(compact, ensure_ascii=False, indent=2))
        parts.append("```")

    # 调用链路
    if call_chains_text and call_chains_text.strip():
        parts.append("\n## 触发调用链路\n")
        parts.append(call_chains_text)

    # 代码片段（核心输入）
    if code_snippets:
        parts.append("\n## 反编译代码片段\n")
        parts.append("以下是与空刷代表帧最相关的嫌疑代码片段（由反编译工具自动提取）：\n")
        for i, item in enumerate(code_snippets[:5], 1):
            owner = item.get("owner_name", "unknown")
            symbol = item.get("symbol_name", "unknown")
            file_name = item.get("file", "unknown")
            line_start = item.get("line_start", 0)
            line_end = item.get("line_end", 0)
            snippet = item.get("code_snippet") or ""
            evidence_hits = item.get("evidence_hits", 0)
            confidence_hint = item.get("confidence_hint", "")

            parts.append(f"### 片段 {i}: {owner}.{symbol}")
            parts.append(f"- 文件: `{file_name}:{line_start}-{line_end}`")
            if evidence_hits:
                parts.append(f"- 证据命中次数: {evidence_hits}")
            if confidence_hint:
                parts.append(f"- 预置置信度提示: {confidence_hint}")
            if snippet:
                parts.append("```typescript")
                parts.append(snippet)
                parts.append("```")
            else:
                parts.append("（代码片段不可用）")
            parts.append("")

    parts.append("\n请输出 JSON 根因报告，不要输出其他内容。")
    return "\n".join(parts).strip() + "\n"
