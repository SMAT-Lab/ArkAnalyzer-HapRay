# 空刷根因分析子 Skill

适用场景：HapRay 检测到 **空刷（empty frame）** 问题后，使用 `hapray root-cause` 命令做根因定位与代码级修复建议。该命令已集成到 `perf_testing/hapray/analyze/llm_root_cause/` 包，与其他 hapray 子命令风格统一。

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
    ╔══════════════════════════════════════════════════════════╗
    ║         每次分析（在线流程，hapray root-cause 驱动）      ║
    ╠══════════════════════════════════════════════════════════╣
    ║                                                          ║
    ║  HapRay 报告目录（含 trace_emptyFrame.json 等）          ║
    ║    │                                                     ║
    ║    ▼  [步骤 1]                                           ║
    ║  ContextBuilder            context_builder.py            ║
    ║  读 summary.json / trace_frames.json 等                  ║
    ║  → AnalysisContext（FPS / 空帧率 / 卡顿率等整体指标）    ║
    ║    │                                                     ║
    ║    ▼  [步骤 2]                                           ║
    ║  EmptyFrameEvidenceExtractor   empty_frame_evidence.py   ║
    ║  数据来源：                                              ║
    ║    · trace_emptyFrame.json → 代表帧 / 线程统计           ║
    ║    · perf.db               → 邻近 perf sample（5ms 内）  ║
    ║    · element_tree_*.txt    → UI 快照组件名               ║
    ║  输出：                                                  ║
    ║    · /proc 源码命中（直接 callchain + perf 邻近）        ║
    ║    · VSync 唤醒链                                        ║
    ║    · UI 场景快照（运行态组件名）                         ║
    ║    · 信号推导（has_taro_js / has_vsync_loop 等）         ║
    ║    · 假设列表 hypotheses（4 类：js_vsync_loop /          ║
    ║      list_rebuild / webview / map）                      ║
    ║    │                                                     ║
    ║    ▼  [步骤 3]                                           ║
    ║  CodeIndexLookup           code_index_lookup.py          ║
    ║  · lookup_hypotheses()  → decompiled_candidates          ║
    ║  · lookup_proc_sources() → decompiled_candidates         ║
    ║  输出：每个嫌疑的 file + line_start + line_end（元数据） ║
    ║    │                                                     ║
    ║    ▼  [步骤 4]                                           ║
    ║  EmptyFrameReportRenderer  report_renderer.py            ║
    ║  → 确定性 Markdown 草稿（嫌疑排序 + 证据 + 修复方向）   ║
    ║    │                                                     ║
    ║    ▼  [步骤 5，可选]                                     ║
    ║  LLM polish    prompts.py + llm_client.py                ║
    ║  输入：草稿 + 结构化证据 JSON                            ║
    ║  → 最终润色报告（当前仅看元数据，未读代码内容）          ║
    ║    │                                                     ║
    ║    ▼                                                     ║
    ║  输出文件：<report_dir>/root_cause.md                    ║
    ╚══════════════════════════════════════════════════════════╝
```

---

## 二、核心模块

| 模块 | 文件 | 职责 | 主要输入 | 主要输出 |
|------|------|------|----------|----------|
| **入口** | `hapray/actions/root_cause_action.py`（`hapray root-cause`） | 串联全流程，解析 CLI 参数 | `--report-dir`、`--index-dir` | 触发各子模块 |
| **上下文构建** | `context_builder.py` | 读 HapRay JSON 报告汇总成结构体 | `summary.json`、`trace_frames.json`、`redundant_thread_analysis.json` 等 | `AnalysisContext` |
| **空刷证据提取** | `empty_frame_evidence.py` | 从 trace / perf.db / UI dump 提炼多路证据并生成假设 | `trace_emptyFrame.json`、`perf.db`、`element_tree_*.txt` | 假设列表 + proc 命中 + UI 快照 |
| **代码索引关联** | `code_index_lookup.py` | 基于符号索引匹配嫌疑代码位置 | `symbol_index.jsonl`、`ui_index.jsonl` | `decompiled_candidates`（行号元数据） |
| **索引构建（离线）** | `index_builder.py` | 扫描反编译 .ts 建结构化索引 | 反编译输出目录（*.ts） | `symbol_index.jsonl`、`ui_index.jsonl`、`file_index.json`、`stats.json` |
| **报告渲染** | `report_renderer.py` | 将证据与 candidates 渲染为可读 Markdown | 假设 + candidates + UI hints | 确定性 Markdown 草稿 |
| **提示词** | `prompts.py` | 构造 LLM system / user prompt | 草稿 + 结构化证据 | prompt 字符串 |
| **LLM 客户端** | `llm_client.py` | 调用 OpenAI-compatible API | prompt | 最终润色文本 |

---

## 三、核心输出文档

| 文档 | 位置 | 说明 |
|------|------|------|
| `empty_frame_root_cause.md` | `<report_dir>/` | 最终根因分析报告，面向开发者修复 |
| `symbol_index.jsonl` | `<index_dir>/` | 符号级索引，每行一个函数/类记录（含 file、line_start、line_end、owner_name、ui_keywords 等字段） |
| `ui_index.jsonl` | `<index_dir>/` | UI API 调用索引（ForEach / WaterFlow / LazyForEach 等） |
| `file_index.json` | `<index_dir>/` | 文件级聚合摘要（含 page / component / view 分类列表） |
| `stats.json` | `<index_dir>/` | 全局统计（总符号数、生命周期符号数、page/component/view 数量等） |
| `*.callgraph.json` | 反编译目录 | 函数调用图（当前主流程尚未使用，是重要的待开发资产） |

---

## 四、关键数据流（三路证据汇聚）

```
路径 A  trace_emptyFrame.json
        ↓ callchain 里的 /proc 符号
        → 原始源码路径 + 行号（如 SearchTnContainerView.ts:192）

路径 B  element_tree_*.txt / inspector_*.json
        ↓ 正则提取 *Page / *View / *Container / *Wrapper 命名
        → 运行态 UI 组件名（如 JdHome、TnFloorView）

路径 C  perf.db
        ↓ 时间戳对齐（5ms 内），查 perf_callchain → perf_files
        → 邻近 perf sample 的 /proc 符号命中

三路在 EmptyFrameEvidenceExtractor 汇聚
    ↓
hypotheses（含 code_query：owner_keywords / ui_keywords / symbol_keywords）
    ↓
CodeIndexLookup 查 symbol_index.jsonl
    → decompiled_candidates（file: 0_entry.hap.ts，line_start/end: 具体行）
    ↓
ReportRenderer 格式化
    ⚠️ 当前只输出行号元数据，不读取对应行的实际代码内容
    ↓
LLM 润色
    ⚠️ 只收到元数据 + Markdown 草稿，看不到代码片段
```

---

## 五、当前关键缺口（优化方向）

| 优先级 | 缺口 | 影响 | 建议方案 |
|--------|------|------|----------|
| 🔴 最高 | **代码片段未读取**：有 file + line_start/end，但从未读出代码内容给 LLM | LLM 只能基于元数据润色，无法给出具体代码级修复建议 | 新增 `CodeSnippetExtractor`，读取行范围内的 .ts 代码注入 prompt |
| 🔴 高 | **Proc → 反编译路径匹配不精确**：用名字模糊匹配，未利用 `normalized_recovered_from` 字段做精确路径匹配 | 同一文件可能命中错误的反编译代码块 | 优先用 `normalized_recovered_from` 做精确匹配，模糊匹配降为兜底 |
| 🟡 中 | **App 特化严重**：`empty_frame_evidence.py` 和 `report_renderer.py` 里硬编码了大量京东 App 特有 UI 名（JdHome、SilkTNContainer 等） | 对其他 App 分析质量急剧下降 | 将 App 特有名单提取到 `config.yaml` |
| 🟡 中 | **LLM 任务定位偏**：当前只做"润色草稿"，system prompt 甚至要求不要展开 | 浪费了 LLM 最强的代码阅读和审查能力 | 改为"代码审查"任务：给代码片段，要求输出具体行级修复建议 |
| 🟢 低 | **callgraph 未利用**：已生成 `.callgraph.json`，但主流程完全未读取 | 无法追溯"是哪个顶层入口触发了嫌疑函数" | 读取 callgraph 做上游调用者分析，形成完整触发链路 |

---

## 六、运行方式

### 前置（一次性）：反编译 + 建索引

```bash
# 1. 反编译 HAP（需要 ark_disasm，DevEco Studio 附带）
cd standalone_tools/llm_root_cause/binary_insight_framework-main-tools-hap_decompiler/tools/hap_decompiler/decompiler
python decompiler.py --input <app.hap> --output <decompiled_dir>/

# 2. 建索引
cd perf_testing
.venv/Scripts/python index_builder.py --input <decompiled_dir>
# 输出：<decompiled_dir>/index/ 目录下的 4 个文件
```

### 前置（一次性）：配置 LLM Token

推荐使用本地 token 文件，**不需要每次传 `--api-key`，也更安全**（不会出现在 shell 历史）。

**方式一（推荐）：默认位置自动加载**

```bash
cd perf_testing/hapray/core/config
cp llm_tokens.local.yaml.example llm_tokens.local.yaml
# 编辑 llm_tokens.local.yaml，填入 api_key / base_url / model
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

# 仅生成确定性报告（无 LLM，适合验证与调试）
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --skip-llm

# 含 LLM 润色（polish 模式）—— Token 自动从 llm_tokens.local.yaml 加载
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index

# 含 LLM 代码审查（code_review 模式，注入代码片段 + 调用链，给出行级修复建议）
python scripts/main.py root-cause \
  --report-dir <HapRay报告目录> \
  --index-dir <decompiled_dir>/index \
  --decompiled-dir <decompiled_dir> \
  --llm-mode code_review
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--report-dir` | ✅ | HapRay 报告目录（含 `summary.json`、`trace_emptyFrame.json`） |
| `--index-dir` | 推荐 | 反编译索引目录（`symbol_index.jsonl` / `ui_index.jsonl`），无则只输出基础报告 |
| `--decompiled-dir` | 可选 | 反编译源码目录（`*.ts` / `*.callgraph.json`），`code_review` 模式必须提供 |
| `--llm-mode` | 可选 | `polish`（默认）/ `code_review` |
| `--llm-tokens` | 可选 | 指定 token 文件路径（优先于自动发现）|
| `--api-key` | 可选 | 单次覆盖 API Key（优先于所有文件）|
| `--base-url` | 可选 | 单次覆盖接口地址 |
| `--model` | 可选 | 单次覆盖模型名 |
| `--config` | 可选 | 完整配置文件（最高优先级，替换所有默认值）|
| `--output` | 可选 | 自定义输出路径，默认 `<report-dir>/root_cause.md` |
| `--skip-llm` | 可选 | 跳过 LLM，只输出确定性报告 |

### 输出

报告默认保存到 `<report-dir>/root_cause.md`，同时生成 `<report-dir>/root_cause_deterministic.md` 作为确定性草稿。

---

## 七、输出报告结构

```markdown
# Empty-Frame Suspect Report

## Executive Summary
一句话摘要：空刷帧数 / 占比 / 最值得先看的嫌疑入口

## 现象
- 空刷总量 / 占比 / 严重度
- 主线程空刷占比 / 主要线程
- VSync 唤醒链
- 关键符号

## 场景
- 运行态 UI 场景（来自 UI dump）
- 与场景最接近的触发源码入口

## 根因源代码
### 嫌疑源码 N: <文件>:<行号>
- 现象关联 / 证据 / 触发符号
- 根因源码范围（反编译代码文件 + 行号）

## 修复方向
- [ ] 可操作的具体检查项

## Caveats
- 候选范围说明

## Appendix: Top Evidence
- 代表帧详情 + /proc 命中列表
```
