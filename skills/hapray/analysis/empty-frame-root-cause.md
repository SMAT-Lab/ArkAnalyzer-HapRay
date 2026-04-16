# 空刷根因分析子 Skill

适用场景：HapRay 检测到**空刷（empty frame）** 问题后，使用 `hapray root-cause` 命令做根因定位与代码级修复建议。该命令已集成到 `perf_testing/hapray/analyze/llm_root_cause/` 包，与其他 hapray 子命令风格统一。

---

## 一、端到端流程

```
HAP 包（一次性离线预处理）
    │
    ▼
[预处理] hap_decompiler
    ├── 反编译 .abc → .ts 文件（streaming 模式支持 21 万+ 函数）
    └── 生成 .callgraph.json（函数调用图）
    │
    ▼
[索引构建] index_builder.py
    ├── symbol_index.jsonl   每个函数/方法一条记录
    ├── ui_index.jsonl       UI API 调用摘要（ForEach / WaterFlow 等）
    ├── file_index.json      文件级聚合（page / component / view 分类）
    └── stats.json           全局统计
    │
    ╔══════════════════════════════════════════════════════════════╗
    ║          每次分析（在线流程，hapray root-cause 驱动）        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  HapRay 报告目录（含 trace_emptyFrame.json 等）              ║
    ║    │                                                         ║
    ║    ▼  [步骤 1]  ContextBuilder                               ║
    ║  读 summary.json / trace_frames.json 等                      ║
    ║  → 整体性能指标（FPS / 空帧率 / 卡顿率）                     ║
    ║    │                                                         ║
    ║    ▼  [步骤 2]  EmptyFrameEvidenceExtractor（纯事实提取）    ║
    ║  数据来源：                                                   ║
    ║    · trace_emptyFrame.json → 代表帧 / 线程统计 / VSync 链    ║
    ║    · perf.db               → 邻近 perf sample（5ms 内）      ║
    ║    · element_tree_*.txt    → UI 快照组件名                   ║
    ║  输出：                                                       ║
    ║    · /proc 源码命中（直接 callchain + perf 邻近）            ║
    ║    · VSync 唤醒链（哪个线程触发渲染）                        ║
    ║    · UI 场景快照（运行态组件名）                              ║
    ║    · 线程统计（角色 + 空刷负载占比）                         ║
    ║    │                                                         ║
    ║    ▼  [步骤 3]  CodeIndexLookup（可选，需 --index-dir）      ║
    ║  lookup_proc_sources() → decompiled_candidates               ║
    ║  （把 /proc 路径/符号 → 反编译文件 file + line_start/end）   ║
    ║    │                                                         ║
    ║    ▼  [步骤 4]  代码片段 + 调用链（可选，需 --decompiled-dir）║
    ║  CodeSnippetExtractor → 读取 .ts 行内容                      ║
    ║  CallgraphTraverser   → 追溯上游调用链路                     ║
    ║    │                                                         ║
    ║    ▼  [步骤 5]  LLM 分析（核心）                             ║
    ║  ┌─────────────────────────────────────────────────────┐    ║
    ║  │  analyze 模式（默认）                                │    ║
    ║  │  输入：结构化证据 JSON（/proc 命中 + 唤醒链 + UI）   │    ║
    ║  │  LLM 独立推断根因 → 结构化 JSON → Markdown 报告     │    ║
    ║  ├─────────────────────────────────────────────────────┤    ║
    ║  │  with_source 模式（需 --decompiled-dir）             │    ║
    ║  │  输入：结构化证据 + 反编译代码片段 + 调用链          │    ║
    ║  │  LLM 阅读代码 → 行级修复建议 → Markdown 报告        │    ║
    ║  └─────────────────────────────────────────────────────┘    ║
    ║    │                                                         ║
    ║    ▼                                                         ║
    ║  输出文件：                                                   ║
    ║    · root_cause.md        LLM 分析报告（主报告）             ║
    ║    · root_cause_evidence.md  规则引擎原始证据（调试用）      ║
    ╚══════════════════════════════════════════════════════════════╝
```

---

## 二、核心模块

| 模块 | 文件 | 职责 | 主要输入 | 主要输出 |
|------|------|------|----------|----------|
| **入口** | `hapray/actions/root_cause_action.py`（`hapray root-cause`） | 串联全流程，解析 CLI 参数 | `--report-dir`、`--index-dir` | 触发各子模块 |
| **上下文构建** | `context_builder.py` | 读 HapRay JSON 报告汇总成结构体 | `summary.json`、`trace_frames.json` 等 | `AnalysisContext` |
| **空刷证据提取** | `empty_frame_evidence.py` | 从 trace / perf.db / UI dump 提炼原始事实，不含推断 | `trace_emptyFrame.json`、`perf.db`、`element_tree_*.txt` | /proc 命中 + 唤醒链 + UI 快照 |
| **代码索引关联** | `code_index_lookup.py` | 基于符号索引匹配嫌疑代码位置 | `symbol_index.jsonl`、`ui_index.jsonl` | `decompiled_candidates`（行号元数据） |
| **代码片段提取** | `code_snippet_extractor.py` | 从反编译 .ts 文件读取代码行范围 | `decompiled_dir`、`decompiled_candidates` | 代码片段字符串注入 LLM |
| **调用链追溯** | `callgraph_traverser.py` | 读 `.callgraph.json` 追溯上游调用链 | 反编译目录 | 触发链路文本 |
| **证据报告渲染** | `report_renderer.py` | 将原始证据渲染为可读 Markdown（无推断） | evidence dict | `root_cause_evidence.md` 内容 |
| **提示词** | `prompts.py` | 构造 LLM system / user prompt | 证据 + 代码片段 + 先验知识 | prompt 字符串 |
| **结构化输出** | `structured_output.py` | 解析 LLM JSON 输出，渲染为 Markdown | LLM 原始文本 | `RootCauseResult`、最终 Markdown |
| **LLM 客户端** | `llm_client.py` | 调用 OpenAI-compatible API（支持 Anthropic / OpenAI / DeepSeek 等） | prompt | LLM 响应文本 |
| **索引构建（离线）** | `index_builder.py` | 扫描反编译 .ts 建结构化索引 | 反编译输出目录（*.ts） | `symbol_index.jsonl`、`ui_index.jsonl` 等 |

---

## 三、LLM 分析模式

### analyze 模式（默认）

**适用：** 只有 HapRay 报告（必要时加 `--index-dir`），无反编译源码树。

**工作方式：**
1. 规则引擎提取原始事实（/proc 命中、唤醒链、UI 快照、线程统计）
2. 以结构化 JSON 传给 LLM
3. LLM **独立推断**根因：识别根因模式（Lottie 动画循环 / 骨架屏未停止 / 数据无 diff 重建 / JS Bridge 轮询等），给出推断结论 + 修复建议

**适合场景：**
- 只有 HapRay 报告，没有反编译源码
- 需要快速定位根因类别
- 希望 LLM 从证据出发独立给出结论，不依赖预先生成的草稿

### with_source 模式（增强）

**适用：** 提供 `--decompiled-dir`（自动检测，有反编译源码则自动切换此模式）。

**工作方式：**
1. 在 analyze 步骤的基础上，额外读取嫌疑函数的实际代码片段
2. 追溯 callgraph 获取调用链（哪个上层入口触发了嫌疑函数）
3. LLM **阅读实际代码**：定位具体有问题的行，给出基于真实代码的行级修复建议

**相比 analyze 的优势：**
- 修复建议引用具体代码行和变量名（而不是泛化伪代码）
- 能发现仅靠元数据看不出的问题（如 diff 检查缺失、引用而非值比较等）
- 能判断 aboutToAppear 里的代码是否真的有问题

**自动选择规则：**
- 提供 `--decompiled-dir` → 自动使用 with_source 模式
- 未提供 `--decompiled-dir` 但指定 `--llm-mode with_source` → 降级为 analyze 并打印警告

---

## 四、关键数据流（三路证据汇聚）

```
路径 A  trace_emptyFrame.json
        ↓ callchain 里的 /proc 符号
        → 原始源码路径 + 行号（如 SearchTnContainerView.ts:192）

路径 B  element_tree_*.txt / inspector_*.json
        ↓ 正则提取 *Page / *View / *Container / *Wrapper 命名
        → 运行态 UI 组件名（如 JdHome、SkeletonScreenView）

路径 C  perf.db
        ↓ 时间戳对齐（5ms 内），查 perf_callchain → perf_files
        → 邻近 perf sample 的 /proc 符号命中

三路在 EmptyFrameEvidenceExtractor 汇聚（纯事实，无推断）
    ↓
[可选] CodeIndexLookup 查 symbol_index.jsonl
        → decompiled_candidates（0_entry.hap.ts 行号元数据）
[可选] CodeSnippetExtractor → 实际 .ts 代码片段
[可选] CallgraphTraverser → 上游调用链路文本
    ↓
LLM 接收结构化证据（JSON）
    ↓ 独立推断（analyze 模式）
    ↓ 或阅读代码 + 推断（with_source 模式）
    ↓
结构化 JSON 输出（suspects / summary / caveats）
    → 渲染为 Markdown → root_cause.md
```

---

## 五、运行方式

### 前置（一次性）：反编译 + 建索引

```bash
# 1. 反编译 HAP（需要 ark_disasm，DevEco Studio 附带）
cd standalone_tools/llm_root_cause/binary_insight_framework-main-tools-hap_decompiler/tools/hap_decompiler/decompiler
python decompiler.py --input <app.hap> --output <decompiled_dir>/

# 2. 建索引
cd perf_testing
python scripts/main.py build-index --input <decompiled_dir>
# 输出：<decompiled_dir>/index/ 目录下的 4 个文件
```

### 前置（一次性）：配置 LLM Token

推荐使用本地 token 文件，**不需要每次传 `--api-key`，也更安全**（不会出现在 shell 历史）。

**方式一（推荐）：默认位置自动加载**

```bash
cd perf_testing/hapray/core/config
cp llm_tokens.local.yaml.example llm_tokens.local.yaml
# ⚠️ 只编辑 llm_tokens.local.yaml，不要修改 .example 文件
# .example 是提交到 git 的模板，.local.yaml 才是 gitignored 的真实凭据文件
vim llm_tokens.local.yaml   # 填入 api_key / base_url / model
```

`hapray root-cause` 启动时自动发现该文件，无需任何额外参数。

**方式二：指定任意位置的 token 文件**

```bash
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --llm-tokens /path/to/my_llm_tokens.yaml
```

**方式三：每次直接传参（一次性使用）**

```bash
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --api-key sk-... \
  --base-url https://api.deepseek.com/v1 \
  --model deepseek-chat
```

`llm_tokens.local.yaml` 已在 `.gitignore` 中，**不会提交到版本库**。  
配置加载优先级（从高到低）：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `--config <file>` | 完整配置替换（最高优先） |
| 2 | `--api-key` / `--base-url` / `--model` | 单次 CLI 覆盖，优先于任何文件 |
| 3 | `--llm-tokens <file>` | 显式指定的 token 文件 |
| 4 | `llm_tokens.local.yaml` | 自动发现（`hapray/core/config/` 目录，gitignored）|
| 5 | `config.yaml` `llm_root_cause:` 节 | 跟踪的默认值（`api_key` 留空）|
| 6 | 环境变量 `LLM_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 最终兜底 |

### 每次分析（`hapray root-cause`）

```bash
cd perf_testing

# 仅生成规则引擎证据报告（无 LLM，适合验证和调试）
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --skip-llm

# analyze 模式（默认）：LLM 从证据独立推断根因，无需反编译源码
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index

# with_source 模式（增强）：LLM 阅读反编译代码，给出行级修复建议
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --decompiled-dir <decompiled_dir>
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--report-dir` | ✅ | HapRay 报告目录（含 `summary.json`、`trace_emptyFrame.json`） |
| `--index-dir` | 推荐 | 反编译索引目录（`symbol_index.jsonl` / `ui_index.jsonl`），提高 /proc 命中的代码定位精度 |
| `--decompiled-dir` | 可选 | 反编译源码目录（`*.ts` / `*.callgraph.json`），提供后自动切换 with_source 模式 |
| `--llm-mode` | 可选 | `analyze`（默认）/ `with_source` |
| `--llm-tokens` | 可选 | 指定 token 文件路径（优先于自动发现）|
| `--api-key` | 可选 | 单次覆盖 API Key（优先于所有文件）|
| `--base-url` | 可选 | 单次覆盖接口地址 |
| `--model` | 可选 | 单次覆盖模型名 |
| `--config` | 可选 | 完整配置文件（最高优先级，替换所有默认值）|
| `--output` | 可选 | 自定义输出路径，默认 `<report-dir>/root_cause.md` |
| `--skip-llm` | 可选 | 跳过 LLM，只输出规则引擎证据报告 |

### 输出

每次运行**固定生成两个文件**：

| 文件 | 内容 | 何时查看 |
|------|------|----------|
| `root_cause.md` | **主报告**：LLM 从证据推断的根因分析，含嫌疑函数、触发链路、修复建议；`--skip-llm` 时内容与 `_evidence.md` 相同 | **日常使用，看这个** |
| `root_cause_evidence.md` | 规则引擎原始证据报告（100% 可复现，无 LLM 依赖）：/proc 命中、UI 快照、代表帧原始数据 | 调试、验证规则引擎提取是否正确、LLM 不可用时的备用 |

> `--output` 参数控制 `root_cause.md` 的路径；`_evidence.md` 始终保存在同一目录，后缀自动追加。

---

## 六、输出报告结构

```markdown
# Root Cause Analysis Report

## Executive Summary
一句话摘要：最关键的根因 + 涉及的嫌疑函数

## Top Suspects
### [HIGH] #1  OwnerName.symbolName
- **位置**: `文件名:起始行-结束行`
- **置信度**: high / medium / low
- **触发链路**: VSync → 线程 → 嫌疑函数
- **根因**: 根因描述（1-2句）
- **问题代码行**:
  - 具体有问题的代码行或逻辑描述
- **修复建议**:
  ```typescript
  // 具体修复代码（引用实际代码）
  ```
- **代码片段**: （with_source 模式下附上反编译代码）

### [MED] #2  ...

## Caveats
- 哪些结论需要人工验证

## 需要补充的数据
- 哪些额外数据可以提高置信度
```

---

## 七、核心输出文档（索引文件）

| 文档 | 位置 | 说明 |
|------|------|------|
| `root_cause.md` | `<report_dir>/` | 最终根因分析报告，面向开发者修复 |
| `root_cause_evidence.md` | `<report_dir>/` | 规则引擎原始证据，调试用 |
| `symbol_index.jsonl` | `<index_dir>/` | 符号级索引，每行一个函数/类记录（含 file、line_start、line_end、owner_name、ui_keywords 等字段） |
| `ui_index.jsonl` | `<index_dir>/` | UI API 调用索引（ForEach / WaterFlow / LazyForEach 等） |
| `file_index.json` | `<index_dir>/` | 文件级聚合摘要（含 page / component / view 分类列表） |
| `stats.json` | `<index_dir>/` | 全局统计（总符号数、生命周期符号数、page/component/view 数量等） |
| `*.callgraph.json` | 反编译目录 | 函数调用图，供 `CallgraphTraverser` 追溯上游调用链 |
